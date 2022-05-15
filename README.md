# Link Telemetry

This is the link between the raw radio module serial stream that
comes from Daybreak's onboard telemetry system and the telemetry
frontend that consists of Grafana and InfluxDB.

## Getting started

### Pre-requisites

- Python 3.8 or above (https://www.python.org/downloads/)
- Docker & docker compose (https://docs.docker.com/get-docker/)

Check your Python installation by running:

```bash
python --version
```

NOTE: Ensure your Python version is 3.8 or higher.

Check your Docker installation by running:

```bash
docker --version
```

### Starting the docker container

Before running the `link_telemetry.py` script, you must first
start the Grafana and InfluxDB instances using docker. 

Ensure your current working directory is the repository
root folder before running the following command:

```bash 
docker compose up
```

This will start a Grafana instance at `localhost:3000` and 
an InfluxDB instance at `localhost:8086`.

### Running the link

There's two different ways to use the telemetry link: 

- NORMAL mode: this requires that you have the XBee radio module 
connected to the host machine. This mode should be used
when collecting real telemetry information from the car.

- DEBUG mode: this mode does not require that you have the XBee
radio module connected. Instead, the python script randomly
generates CAN messages.

To run the system in NORMAL mode:

```bash
python link_telemetry.py <com_port> <baudrate>
```

Where `com_port` is something like `COM9` or `/dev/ttyS0` and
`baudrate` is something like `230400` or `9600`.

To run the system in DEBUG mode:

```bash
python link_telemetry.py
```

