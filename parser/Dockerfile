FROM python:3.11-slim
WORKDIR /app

# build tools for wheels (cantools sometimes compiles deps)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY parser/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# bring in DBC, proto stubs, and parser code
COPY dbc/ /app/dbc/
COPY tools/proto/ /app/tools/proto/
COPY parser/ /app/parser/

ENV PYTHONUNBUFFERED=1
EXPOSE 50051

CMD ["python", "-m", "parser.cellular_parser"]
