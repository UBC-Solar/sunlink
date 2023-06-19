# UBC Solar's Telemetry System

The goal of UBC Solar's telemetry system is to extract, store, and visualize data produced by our solar cars in real-time. The system aims to provide unified access (whether manually or programmatically) to runtime car data to all Solar members.

Collecting and visualizing this data is important since it allows for things like:

1) Optimizing drive performance
2) Debugging on-board electronic systems 
3) Verifying race-strategy simulation models
4) Enabling continuous race-strategy simulation recalculations
5) Post-mortem detailed system analysis

This repository contains all of the components for UBC Solar's telemetry system. It contains the implementation of the Flask parser server, the client-side script that communicates with the server, and the Docker Compose file that brings up the entire system.

## Table of contents

- [System overview](#system-overview)
- [(TODO) System configurations](#system-configurations)
- [Getting started](#getting-started)
- [Running the link](#running-the-link)
- [Parser HTTP API](#parser-api)
- [Screenshots](#screenshots)

## System overview

![Telemetry link high-level architecture](/images/link-telemetry-arch.png)

The telemetry pipeline has many moving parts distributed over numerous systems. A mostly high-level description of the movement of data from the car's CAN bus to the final Grafana visualization will be given here.

### The telemetry board (TEL)

The telemetry system could not exist without the telemetry board (TEL). This board houses the radio and cellular modules which are used in-tandem to wirelessly transmit data.

At its simplest, the telemetry board is responsible for reading CAN messages from the car's CAN bus, encoding it in a serial format, and transmitting it over radio and cellular.

The radio and cellular modules, while exactly the same in their overall function, have notable differences that influence the architecture of the telemetry system.

First, we will go through how the radio module communicates with the off-board telemetry system.

### Radio module

The radio module communicates directly to a radio receiver. The radio module transmits a serial stream (i.e., simply a stream of bytes) and the radio receiver receives the serial stream. The radio receiver connects to a laptop via USB and is registered as a USB serial device. It is possible to use any serial console (e.g., PuTTY, minicom) to read the raw encoded serial stream.

### Serial stream structure

When opening the radio receiver serial port, you will see something like the following:

```
TODO: add serial stream
```

### The `link_telemetry.py` script

This script is responsible for reading the serial stream from the radio receiver, formatting each message into a JSON object, and making HTTP requests to the parser server.

### The docker services

Before diving into the parser server, it is important to take some time to understand the Docker ccontainer structure.

The Flask parser is deployed as a Docker container along with two other services: InfluxDB and Grafana. InfluxDB is the time-series database that stores the incoming telemetry data and Grafana is the visualization platform used to graph the data.

These three services are all spun up using a single Docker Compose file. They are configured to be connected to the same bridge network and so are able to easily communicate with each other.

### The parser

The parser is responsible for parsing CAN messages (which are usually sent by `link_telemetry.py` but realistically could be sent by any application able to make HTTP requests), writing the parsed measurements to the Influx container, and optionally streaming the parsed measurements directly to the Grafana container.

The parser is implemented as a Flask application and exposes an HTTP API. The `link_telemetry.py` script makes direct use of this API. Detailed API documentation can be found [here](/API.md). 

Note that most of the endpoints exposed by the parser require bearer token authentication. More details about this are given in the setup section.

### Influx and Grafana

Influx is the database for the telemetry system and stores all parsed telemetry data. It is configured with two buckets: a debug bucket and a production bucket.

The debug bucket is usually used when writing randomly generated data. It is intended to be a test bucket for use while working on the telemetry system itself.

The production bucket is used when receiving actual data from the car. 

Grafana is the visualization platform that allows for user-friendly presentation of the parsed telemetry data. 

The main data presentation structure on Grafana is the dashboard. The Grafana instance is provisioned with two dashboards: "Daybreak Test Telemetry" and "Daybreak Telemetry". The first dashboard reads its data from the Influx debug bucket and the second dashboard reads its data from the Influx production bucket.

Both Influx and Grafana implement intuitive web GUIs available on ports 8086 and 3000 respectively.

### Cellular module

As we have seen, the radio module produces a serial stream. This serial stream needs to be sent to the parser which necessitates the `link_telemetry.py` script.

The cellular module does not require the `link_telemetry.py` script since it runs MicroPython and is able to make HTTP requests by itself. This means it can bypass the `link_telemetry.py` script and talk to the parser directly.

It is this discrepancy between the radio and cellular modules that required the parser to be implemented as an HTTP server since it provides a single interface to both modules.

## (TODO) System configurations

## Getting started

### Pre-requisites

- Python 3.8 or above (https://www.python.org/downloads/)
- Docker & Docker Compose (https://docs.docker.com/get-docker/)

Check your Python installation by running:

```bash
python --version
```

NOTE: Ensure your Python version is 3.8 or higher.

Check your Docker Compose installation by running:

```bash
docker compose version
```

### Setting up environment variables

Before starting up the docker instances, you must create a `.env` file in the project root directory. It is easiest to create a file like this from the terminal:

For Linux/macOS:

```bash
touch .env
```

For Windows:

```powershell
New-Item -Path . -Name ".env"
```

Then, you may use any code editor to edit the file.

An example `.env` file is given in `./examples/environment/`. The contents of this file will look something like this:

```env
# Grafana environment variables

GRAFANA_ADMIN_USERNAME=""
GRAFANA_ADMIN_PASSWORD=""

GRAFANA_URL=http://localhost:3000/

# InfluxDB environment variables

INFLUX_ADMIN_USERNAME=""
INFLUX_ADMIN_PASSWORD=""

INFLUX_URL=http://localhost:8086/

INFLUX_ORG=UBC Solar
INFLUX_BUCKET=""

# Access tokens

INFLUX_TOKEN=""
GRAFANA_TOKEN=""

```

The fields with empty values all need to be filled except for the access tokens. These fields should be
manually filled once the docker containers are spun up. An example of what a valid `.env` file will look like **before** 
starting the docker containers is given below:

```env
# Grafana environment variables

GRAFANA_ADMIN_USERNAME=admin
GRAFANA_ADMIN_PASSWORD=new_password

GRAFANA_URL=http://localhost:3000/

# InfluxDB environment variables

INFLUX_ADMIN_USERNAME=admin
INFLUX_ADMIN_PASSWORD=new_password

INFLUX_URL=http://localhost:8086/

INFLUX_ORG=UBC Solar
INFLUX_BUCKET=Telemetry

# Access tokens

INFLUX_TOKEN=""
GRAFANA_TOKEN=""
```

As you can see, the `INFLUX_TOKEN` and `GRAFANA_TOKEN` keys are left without values.

NOTE: make sure you correctly rename your environment variable file to `.env` otherwise Docker compose will not be able to read it. It should **not** have a `.txt` extension.

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

### Finishing environment set-up

Once the docker containers are up and running, you should be able to access InfluxDB and Grafana at the URLs specified in your `.env` file.

* Access InfluxDB and generate a new API token. This token should be used as the value for the `INFLUX_TOKEN` key in your `.env` file.
* Access Grafana and generate a new API token. This token should be used as the value for the `GRAFANA_TOKEN` key in your `.env` file.

NOTE: both the InfluxDB and Grafana token need to be given write access since the telemetry link uses them to write data to the InfluxDB bucket
and the Grafana Live endpoint.

### Installing Python package requirements

Before running the `link_telemetry.py` script, you must install the required Python packages.
It is recommended that you create a Python virtual environment before running the following command.
A detailed guide on how to create a Python virtual environment can be found here: https://docs.python.org/3/library/venv.html.

To install the requirements run:

```bash
python -m pip install -r requirements.txt
```

## Running the link

There's two different ways to use the telemetry link: 

- NORMAL mode: this requires that you have the XBee radio module 
connected to the host machine. This mode should be used
when collecting real telemetry information from the car.

- DEBUG mode: this mode does not require that you have the XBee
radio module connected. Instead, the python script randomly
generates CAN messages.

To run the system in NORMAL mode:

```bash
python link_telemetry.py -p [SERIAL_PORT] -b [BAUDRATE]
```

Where `[SERIAL_PORT]` is something like `COM9` or `/dev/ttyUSB0` and
`[BAUDRATE]` is something like `230400` or `9600`.

To run the system in DEBUG mode:

```bash
python link_telemetry.py -d
```

To look at the help information:

```bash
python link_telemetry.py --help
```

Or:

```bash
python link_telemetry.py -h
```

Once the link starts running, you should be able to access some of the provisioned (i.e., preconfigured) Grafana dashboards in which
you should see the graphs being updated. 

## Parser API

Refer to [API.md](/API.md) for the full documentation of the endpoints that the parser exposes.

## Screenshots

Here are some screenshots of real data gathered from Daybreak using the telemetry system:

![Battery state](/images/battery_state.png)

![Battery voltages](/images/battery_voltages.png)

![Current setpoint and bus current](/images/current_setpoint_and_bus_current.png)

![Current setpoint and vehicle velocity](/images/current_setpoint_and_vehicle_velocity.png)

![Vehicle velocity and motor velocity](/images/vehicle_velocity_and_motor_velocity.png)

