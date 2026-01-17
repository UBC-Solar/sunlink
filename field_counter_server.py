#!/usr/bin/env python3
"""
frame_counter_server.py

Run a gRPC server that accepts FrameBatch streams from the Pi
and counts ONLY the number of CAN frames received.

Usage (from ~/sunlink):
    source environment/bin/activate
    export GRPC_BIND="0.0.0.0:50051"   # or whatever you use
    export PRINT_INTERVAL_SEC=5        # optional (default 5s)
    export LOG_PER_BATCH=false         # optional: set "true" to log each batch size
    python frame_counter_server.py
"""

import os
import time
from concurrent import futures
import sys
import grpc

# --- Ensure tools/proto is importable ---
BASE_DIR = os.path.dirname(__file__)
PROTO_DIR = os.path.join(BASE_DIR, "tools", "proto")
if PROTO_DIR not in sys.path:
    sys.path.insert(0, PROTO_DIR)

import canlink_pb2
import canlink_pb2_grpc

# -----------------------------
# Config
# -----------------------------
GRPC_BIND          = os.getenv("GRPC_BIND", "0.0.0.0:50051")
PRINT_INTERVAL_SEC = float(os.getenv("PRINT_INTERVAL_SEC", "5.0"))
LOG_PER_BATCH      = os.getenv("LOG_PER_BATCH", "false").lower() == "true"


class FrameCountingServicer(canlink_pb2_grpc.CanIngestServicer):
    """
    Minimal CanIngest service that only counts frames.
    """

    def __init__(self):
        self.total_frames = 0
        self.start_time = time.time()
        self.last_print = self.start_time

    def _maybe_print_stats(self):
        now = time.time()
        if now - self.last_print < PRINT_INTERVAL_SEC:
            return

        elapsed = max(now - self.start_time, 1e-6)
        frames_per_sec = self.total_frames / elapsed
        frames_per_min = frames_per_sec * 60.0

        print(
            f"[Counter] elapsed={elapsed:6.1f}s  "
            f"frames={self.total_frames:9d}  "
            f"frames/min={frames_per_min:10.1f}"
        )
        self.last_print = now

    def UploadFrames(self, request_iterator, context):
        print("[Counter] UploadFrames stream opened")
        for batch in request_iterator:
            n = len(batch.frames)
            self.total_frames += n
            if LOG_PER_BATCH:
                print(f"[Counter] received FrameBatch with {n} frames")
            self._maybe_print_stats()

        # Stream ended: final summary
        end = time.time()
        elapsed = max(end - self.start_time, 1e-6)
        frames_per_sec = self.total_frames / elapsed
        frames_per_min = frames_per_sec * 60.0

        print("\n========== FINAL SUMMARY ==========")
        print(f"Elapsed:            {elapsed:.1f} s")
        print(f"Frames received:    {self.total_frames}")
        print(f"Frames per second:  {frames_per_sec:.1f}")
        print(f"Frames per minute:  {frames_per_min:.1f}")
        print("===================================")

        return canlink_pb2.UploadAck(frames_ingested=self.total_frames)


def serve():
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=8),
        options=[
            ("grpc.max_send_message_length", 50 * 1024 * 1024),
            ("grpc.max_receive_message_length", 50 * 1024 * 1024),
        ],
    )
    canlink_pb2_grpc.add_CanIngestServicer_to_server(FrameCountingServicer(), server)
    server.add_insecure_port(GRPC_BIND)
    print(f"[Counter] gRPC server listening on {GRPC_BIND}")
    server.start()
    try:
        while True:
            time.sleep(24 * 3600)
    except KeyboardInterrupt:
        print("[Counter] Shutting down gRPC server")
        server.stop(0)


if __name__ == "__main__":
    serve()
