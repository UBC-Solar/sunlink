#!/usr/bin/env python3
import os, time, queue, threading
from datetime import datetime, timezone

import grpc
from concurrent import futures

import cantools
from influxdb_client import InfluxDBClient, Point, WriteOptions

from tools.proto import canlink_pb2, canlink_pb2_grpc

# CONFIG (envs or defaults) 
DBC_FILE      = os.getenv("DBC_FILE", "/app/dbc/brightside.dbc")
INFLUX_URL    = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_ORG    = os.getenv("INFLUX_ORG", "UBC Solar")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "CAN_test")
INFLUX_TOKEN  = os.getenv("INFLUX_TOKEN", "")
USE_NOW_TIME  = os.getenv("USE_NOW_TIME", "true").lower() == "true"

# batching to Influx
POINT_BATCH_SIZE   = int(os.getenv("POINT_BATCH_SIZE", "1000"))
FLUSH_INTERVAL_MS  = int(os.getenv("FLUSH_INTERVAL_MS", "1000"))

GRPC_BIND          = os.getenv("GRPC_BIND", "0.0.0.0:50051")
GRPC_MAX_WORKERS   = int(os.getenv("GRPC_MAX_WORKERS", "8"))
GRPC_COMPRESSION   = os.getenv("GRPC_COMPRESSION", "zstd").lower()   # zstd/gzip/none

# ----------------------------------------------------

print(f"[Parser] Loading DBC: {DBC_FILE}")
DBC = cantools.database.load_file(DBC_FILE)

# Set up Influx async writer w/ batching + gzip
print(f"[Parser] Connecting to Influx: {INFLUX_URL} org={INFLUX_ORG} bucket={INFLUX_BUCKET}")
_influx = InfluxDBClient(url=INFLUX_URL, org=INFLUX_ORG, token=INFLUX_TOKEN, enable_gzip=True)
write_api = _influx.write_api(
    write_options=WriteOptions(
        batch_size=POINT_BATCH_SIZE,
        flush_interval=FLUSH_INTERVAL_MS,
        jitter_interval=100,
        retry_interval=5000,
        max_retries=5,
        max_retry_delay=30000,
        exponential_base=2,
    )
)

def _decode(can_id: int, data: bytes):
    """Return (msg_name, senders[], measurements: dict) or None if unknown ID."""
    try:
        msg = DBC.get_message_by_frame_id(can_id)
    except Exception:
        return None
    try:
        vals = DBC.decode_message(can_id, bytearray(data))
    except Exception:
        return None
    senders = getattr(msg, "senders", []) or []
    return msg.name, senders, vals

def _make_points(parsed_tuple, can_ts):
    """Yield Influx points from (msg_name, senders, values)."""
    msg_name, senders, vals = parsed_tuple
    # measurement name = sender (stable), tag class = msg_name
    src = senders[0] if senders else "UNKNOWN"
    t = datetime.now(timezone.utc) if USE_NOW_TIME else datetime.fromtimestamp(can_ts, tz=timezone.utc)
    for k, v in vals.items():
        if isinstance(v, bool):
            v = 1.0 if v else 0.0
        elif not isinstance(v, (int, float)):
            continue
        yield (Point(src)
               .tag("class", msg_name)
               .field(k, float(v))
               .field("can_timestamp", float(can_ts))
               .time(t))

class CanIngestService(canlink_pb2_grpc.CanIngestServicer):
    def __init__(self):
        self._ingested = 0

    def UploadFrames(self, request_iter, context):
        """Client-streaming RPC: Stream of FrameBatch -> one UploadAck."""
        local_count = 0
        for batch in request_iter:
            for f in batch.frames:
                parsed = _decode(f.can_id, f.data)
                if parsed is None:
                    continue
                for p in _make_points(parsed, f.timestamp):
                    try:
                        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=p)
                    except Exception:
                        # swallow but continue; async writer will retry
                        pass
                local_count += 1

        # final flush (best-effort, async writer also auto-flushes)
        try:
            write_api.flush()
        except Exception:
            pass

        self._ingested += local_count
        return canlink_pb2.UploadAck(frames_ingested=local_count)

def serve():
    compression = grpc.Compression.NoCompression
    if GRPC_COMPRESSION == "zstd":
        compression = grpc.Compression.Zstd
    elif GRPC_COMPRESSION == "gzip":
        compression = grpc.Compression.Gzip

    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=GRPC_MAX_WORKERS),
        options=[
            ("grpc.max_send_message_length", 50*1024*1024),
            ("grpc.max_receive_message_length", 50*1024*1024),
        ],
        compression=compression
    )
    canlink_pb2_grpc.add_CanIngestServicer_to_server(CanIngestService(), server)
    server.add_insecure_port(GRPC_BIND)
    print(f"[Parser] gRPC ingest listening on {GRPC_BIND} (compression={GRPC_COMPRESSION})")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    try:
        ok = _influx.ping()
        print(f"[Parser] Influx ping: {ok}")
    except Exception as e:
        print(f"[Parser] Influx ping failed: {e}")
    serve()
