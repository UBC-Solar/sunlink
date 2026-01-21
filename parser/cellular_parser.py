#!/usr/bin/env python3
"""
cellular_parser.py
- gRPC server that ingests FrameBatch streams
- Decodes CAN frames via DBC (supports standard & extended IDs)
- Writes signal fields to InfluxDB using async batching
- Prints lightweight live metrics
- Logs undecodable/unknown frames to a rotating file

ENV (typical):
  DBC_FILE=/app/dbc/brightside.dbc
  INFLUX_URL=http://influxdb:8086
  INFLUX_ORG=UBC Solar
  INFLUX_BUCKET=CAN_test
  INFLUX_TOKEN=...
  USE_NOW_TIME=true|false
  POINT_BATCH_SIZE=1000
  FLUSH_INTERVAL_MS=1000
  GRPC_BIND=0.0.0.0:50051
  GRPC_MAX_WORKERS=8
  GRPC_COMPRESSION=gzip|zstd|none
  PRINT_EVERY_SEC=5
  FAIL_LOG_PATH=/app/logs/parser_failures.log
"""

import os, time, sys, threading, queue
from datetime import datetime, timezone
from concurrent import futures

import grpc
import cantools
from influxdb_client import InfluxDBClient, Point, WriteOptions

# --- Ensure stubs are importable (tools/proto on PYTHONPATH) ---
BASE_DIR = os.path.dirname(os.path.dirname(__file__)) if __file__ else "."
PROTO_DIR = os.path.join(BASE_DIR, "tools", "proto")
if PROTO_DIR not in sys.path:
    sys.path.insert(0, PROTO_DIR)
import canlink_pb2, canlink_pb2_grpc  # noqa: E402

# -----------------------------
# Config from environment
# -----------------------------
DBC_FILE       = os.getenv("DBC_FILE", "/app/dbc/brightside.dbc")
INFLUX_URL     = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_ORG     = os.getenv("INFLUX_ORG", "UBC Solar")
INFLUX_BUCKET  = os.getenv("INFLUX_BUCKET", "CAN_test")
INFLUX_TOKEN   = os.getenv("INFLUX_TOKEN", "")
USE_NOW_TIME   = os.getenv("USE_NOW_TIME", "true").lower() == "true"

POINT_BATCH_SIZE  = int(os.getenv("POINT_BATCH_SIZE", "1000"))
FLUSH_INTERVAL_MS = int(os.getenv("FLUSH_INTERVAL_MS", "1000"))
GRPC_BIND         = os.getenv("GRPC_BIND", "0.0.0.0:50051")
GRPC_MAX_WORKERS  = int(os.getenv("GRPC_MAX_WORKERS", "8"))
GRPC_COMPRESSION  = os.getenv("GRPC_COMPRESSION", "gzip").lower()
PRINT_EVERY_SEC   = float(os.getenv("PRINT_EVERY_SEC", "5"))
FAIL_LOG_PATH     = os.getenv("FAIL_LOG_PATH", "/app/logs/parser_failures.log")

print(f"[Parser] Loading DBC: {DBC_FILE}")
DBC = cantools.database.load_file(DBC_FILE)

# Build a fast lookup that respects extended vs standard IDs.
# Primary key: (frame_id, is_extended); Fallback: by frame_id only.
_MSG_BY_KEY = {}
_MSG_BY_ID  = {}
for m in DBC.messages:
    is_ext = bool(getattr(m, "is_extended_frame", False))
    _MSG_BY_KEY[(m.frame_id, is_ext)] = m
    _MSG_BY_ID[m.frame_id] = m

def _lookup_msg(can_id: int, is_extended: bool):
    msg = _MSG_BY_KEY.get((can_id, bool(is_extended)))
    if msg is None:
        msg = _MSG_BY_ID.get(can_id)
    return msg

# -----------------------------
# Influx async writer + metrics
# -----------------------------
print(f"[Parser] Connecting to Influx: {INFLUX_URL} org={INFLUX_ORG} bucket={INFLUX_BUCKET}")
metrics = {
    "frames_in": 0,
    "unknown_ids": 0,
    "decodes_ok": 0,
    "decodes_failed": 0,
    "fields_produced": 0,
    "points_enqueued": 0,
    "points_ok": 0,
    "points_err": 0,
    "points_retry": 0,
}
_last_print = time.time()
_t0 = _last_print

def _on_success(_, __):
    metrics["points_ok"] += 1

def _on_error(_, err: Exception):
    metrics["points_err"] += 1
    # sample log to avoid spam
    if (metrics["points_err"] % 1000) == 1:
        print(f"[Parser] write error sample: {err}")

def _on_retry(_, __, ___):
    metrics["points_retry"] += 1

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
    ),
    success_callback=_on_success,
    error_callback=_on_error,
    retry_callback=_on_retry,
)

# -----------------------------
# Failure logger (background)
# -----------------------------
_fail_q: "queue.Queue[str]" = queue.Queue(maxsize=10000)

def _fail_logger(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", buffering=1) as f:
        while True:
            line = _fail_q.get()
            if line is None:
                break
            f.write(line + "\n")

_fail_thread = threading.Thread(target=_fail_logger, args=(FAIL_LOG_PATH,), daemon=True)
_fail_thread.start()

def _log_fail(can_id: int, is_ext: bool, data: bytes, why: str):
    try:
        hex_data = data.hex()
        ts = datetime.utcnow().isoformat(timespec="milliseconds") + "Z"
        _fail_q.put_nowait(f"{ts} can_id=0x{can_id:X} ext={int(is_ext)} len={len(data)} data={hex_data} reason={why}")
    except queue.Full:
        # drop if backlogged; we don't want to stall ingest
        pass

# -----------------------------
# Helpers
# -----------------------------
def _points_from(msg, vals, can_ts):
    src = (msg.senders or ["UNKNOWN"])[0]
    t = datetime.now(timezone.utc) if USE_NOW_TIME else datetime.fromtimestamp(can_ts, tz=timezone.utc)
    for k, v in vals.items():
        if isinstance(v, bool):
            v = 1.0 if v else 0.0
        elif not isinstance(v, (int, float)):
            continue
        yield (Point(src)
               .tag("class", msg.name)
               .field(k, float(v))
               .field("can_timestamp", float(can_ts))
               .time(t))

def _maybe_print():
    global _last_print
    now = time.time()
    if now - _last_print < PRINT_EVERY_SEC:
        return
    elapsed = now - _t0
    fpm = (metrics["fields_produced"] / elapsed) * 60 if elapsed > 0 else 0.0
    rpm = (metrics["frames_in"] / elapsed) * 60 if elapsed > 0 else 0.0
    print(
        f"[Parser] {elapsed:7.1f}s  "
        f"frames_in={metrics['frames_in']:9d}  "
        f"unknown={metrics['unknown_ids']:7d}  "
        f"dec_ok={metrics['decodes_ok']:9d}  dec_fail={metrics['decodes_failed']:7d}  "
        f"fields={metrics['fields_produced']:9d} ({fpm:10.1f}/min)  "
        f"enq={metrics['points_enqueued']:9d}  ok={metrics['points_ok']:9d}  "
        f"retry={metrics['points_retry']:9d}  err={metrics['points_err']:9d}  "
        f"frames/min={rpm:10.1f}"
    )
    _last_print = now

# -----------------------------
# gRPC service
# -----------------------------
class CanIngestService(canlink_pb2_grpc.CanIngestServicer):
    def UploadFrames(self, request_iter, context):
        print("[Parser] UploadFrames stream opened")
        local_frames = 0

        for batch in request_iter:
            # helpful batch-size visibility
            print(f"[Parser] received FrameBatch with {len(batch.frames)} frames")

            points_buffer = []  # write per batch to reduce write() calls
            for f in batch.frames:
                local_frames += 1
                metrics["frames_in"] += 1

                msg = _lookup_msg(f.can_id, f.is_extended_id)
                if msg is None:
                    metrics["unknown_ids"] += 1
                    _log_fail(f.can_id, f.is_extended_id, bytes(f.data), "UNKNOWN_ID")
                    continue

                try:
                    vals = msg.decode(bytes(f.data))
                except Exception as e:
                    metrics["decodes_failed"] += 1
                    _log_fail(f.can_id, f.is_extended_id, bytes(f.data), f"DECODE_FAIL:{type(e).__name__}")
                    continue

                metrics["decodes_ok"] += 1

                produced_here = 0
                for p in _points_from(msg, vals, f.timestamp):
                    points_buffer.append(p)
                    produced_here += 1

                metrics["fields_produced"] += produced_here

            # one async write per batch if we have points
            if points_buffer:
                metrics["points_enqueued"] += len(points_buffer)
                try:
                    write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=points_buffer)
                except Exception as e:
                    # async write_api rarely raises; if it does, log and continue
                    print(f"[Parser] write_api immediate error: {e}")

            _maybe_print()

        # best-effort final flush
        try:
            write_api.flush()
        except Exception as e:
            print(f"[Parser] flush error: {e}")

        return canlink_pb2.UploadAck(frames_ingested=local_frames)

# -----------------------------
# Server bootstrap
# -----------------------------
def serve():
    comp = grpc.Compression.NoCompression
    if GRPC_COMPRESSION == "zstd":
        comp = grpc.Compression.Zstd
    elif GRPC_COMPRESSION == "gzip":
        comp = grpc.Compression.Gzip

    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=GRPC_MAX_WORKERS),
        options=[
            ("grpc.max_send_message_length", 50 * 1024 * 1024),
            ("grpc.max_receive_message_length", 50 * 1024 * 1024),
        ],
        compression=comp,
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

    try:
        serve()
    finally:
        # stop logger thread
        try:
            _fail_q.put_nowait(None)
        except Exception:
            pass

