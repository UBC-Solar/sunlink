# parser/Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps if you need them (optional)
# RUN apt-get update && apt-get install -y --no-install-recommends ... && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY parser/requirements.txt /app/parser/requirements.txt

# ---- Critical pins to match generated code ----
# Your stubs require protobuf >= 6.31.1 and grpcio >= 1.75.1
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir \
      protobuf==6.31.1 \
      grpcio==1.75.1 \
      grpcio-tools==1.75.1

# Now install the rest; keep pins in effect (avoid downgrades)
RUN pip install --no-cache-dir -r /app/parser/requirements.txt

# Copy the whole repo (stubs are at /app/tools/proto)
COPY . /app

# Make sure Python can import the stubs as written: "import canlink_pb2"
ENV PYTHONPATH="/app:/app/tools:/app/tools/proto:${PYTHONPATH}"

# If you have an entrypoint/cmd already, keep it; otherwise:
# CMD ["python", "-m", "parser.main"]

