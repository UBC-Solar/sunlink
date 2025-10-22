#!/usr/bin/env python3
import os, sys, time, struct, serial, grpc, threading
from collections import deque

# import generated stubs (you can copy tools/proto/ into the Pi or pip-install from your repo)
from tools.proto import canlink_pb2, canlink_pb2_grpc

# CONFIG
UART_PORT        = os.getenv("TEL_UART_PORT", "COM5" if sys.platform.startswith("win") else "/dev/ttyUSB0")
UART_BAUD        = int(os.getenv("TEL_UART_BAUD", "230400"))
SERVER_ADDR      = os.getenv("INGEST_SERVER", "100.120.214.69:50051")  # Tailscale IP:port of parser host
BATCH_SIZE       = int(os.getenv("BATCH_SIZE", "200"))
BATCH_MAX_MS     = float(os.getenv("BATCH_MAX_MS", "50"))  # flush every T ms if fewer than BATCH_SIZE
USE_ZSTD         = os.getenv("GRPC_COMP", "zstd").lower() == "zstd"   # or gzip/none
# -----------------------------

# TEL UART frame layout (packed, 24 bytes):
#   uint64  timestamp (double as uint64 bit pattern, big-endian serialized)
#   char    ID_DELIMITER ('#')
#   uint32  can_id (bit-reversed in TEL; we correct below)
#   uint8[8] data
#   uint8   data_len (DLC)
#   char    '\r'
#   char    '\n'
UART_FRAME_SIZE = 24

def _bit_reverse32(x: int) -> int:
    # Mirror bits exactly as BITOPS_32BIT_REVERSE does on TEL.
    x = ((x & 0x55555555) << 1) | ((x >> 1) & 0x55555555)
    x = ((x & 0x33333333) << 2) | ((x >> 2) & 0x33333333)
    x = ((x & 0x0F0F0F0F) << 4) | ((x >> 4) & 0x0F0F0F0F)
    x = ((x & 0x00FF00FF) << 8) | ((x >> 8) & 0x00FF00FF)
    x = (x << 16) | ((x >> 16) & 0xFFFF)
    return x & 0xFFFFFFFF

def _double_from_be_uint64(u64: int) -> float:
    # interpret the 64-bit pattern as big-endian double
    b = u64.to_bytes(8, "big")
    return struct.unpack(">d", b)[0]

def _is_extended(can_id: int) -> bool:
    # if any bit beyond 11 is set, treat as 29-bit extended
    return can_id > 0x7FF

def read_uart_frames(ser):
    # Generator yielding parsed RawFrame messages from 24-byte records.
    buf = bytearray()
    while True:
        chunk = ser.read(ser.in_waiting or UART_FRAME_SIZE)
        if not chunk:
            time.sleep(0.001)
            continue
        buf.extend(chunk)
        # resync if buffer is huge
        if len(buf) > UART_FRAME_SIZE * 128:
            buf = buf[-UART_FRAME_SIZE*2:]

        while len(buf) >= UART_FRAME_SIZE:
            rec = bytes(buf[:UART_FRAME_SIZE])
            # quick sanity: CRLF tail
            if rec[-2:] != b"\r\n":
                # resync by dropping first byte
                buf.pop(0)
                continue

            # parse fields
            ts_bits = int.from_bytes(rec[0:8], "big")
            delim   = rec[8:9]
            can_id_bits = int.from_bytes(rec[9:13], "big")
            data    = rec[13:21]
            dlc     = rec[21]
            # 22: CR, 23: LF checked above

            if delim != b"#" or dlc > 8:
                buf.pop(0)
                continue

            # undo TEL’s bit-reversal on CAN ID to restore canonical value
            can_id = _bit_reverse32(can_id_bits)

            ts = _double_from_be_uint64(ts_bits)
            framestr = canlink_pb2.RawFrame(
                timestamp=ts,
                can_id=can_id,
                is_extended_id=_is_extended(can_id),
                data=data[:dlc],
                dlc=dlc,
            )
            yield framestr
            del buf[:UART_FRAME_SIZE]

def batcher(frame_iter, batch_size: int, max_ms: float):
    # Yield FrameBatch respecting size/time windows.
    q = deque()
    last = time.time()
    for f in frame_iter:
        q.append(f)
        now = time.time()
        if len(q) >= batch_size or (now - last) * 1000.0 >= max_ms:
            yield canlink_pb2.FrameBatch(frames=list(q))
            q.clear()
            last = now

def run():
    ser = serial.Serial(UART_PORT, UART_BAUD, timeout=0)
    print(f"[RPi] UART open on {UART_PORT}@{UART_BAUD}, streaming to {SERVER_ADDR}")

    compression = grpc.Compression.NoCompression
    if USE_ZSTD:
        compression = grpc.Compression.Zstd
    elif os.getenv("GRPC_COMP", "").lower() == "gzip":
        compression = grpc.Compression.Gzip

    with grpc.insecure_channel(SERVER_ADDR, options=[
        ("grpc.max_send_message_length", 50*1024*1024),
        ("grpc.max_receive_message_length", 50*1024*1024),
    ]) as channel:
        stub = canlink_pb2_grpc.CanIngestStub(channel)

        def req_iter():
            for batch in batcher(read_uart_frames(ser), BATCH_SIZE, BATCH_MAX_MS):
                yield batch

        ack = stub.UploadFrames(req_iter(), compression=compression)
        print(f"[RPi] stream closed, server ack: {ack.frames_ingested} frames")

if __name__ == "__main__":
    run()
