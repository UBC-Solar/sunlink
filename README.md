# UBC Solar's Telemetry System

The goal of UBC Solar's telemetry system is to extract, store, and visualize data produced by our solar cars in real-time.

Collecting and visualizing this data is useful since it allows for:

1) Optimizing drive performance
2) Debugging on-board electronic systems 
3) Verifying race-strategy simulation models
4) Enabling continuous race-strategy simulation recalculations
5) Post-mortem system analysis

This repository contains all of the components for UBC Solar's telemetry system. It contains the implementation of the parser server, a client-side script that communicates with the server, and the Docker Compose file that brings up the entire system.

## Table of contents

- [System overview](#system-overview)
- [Getting started](#getting-started)
- [Telemetry cluster setup](#telemetry-cluster-setup)
- [Telemetry link setup](#telemetry-link-setup)
- [Running the link](#running-the-link)
- [Parser HTTP API](#parser-api)
- [Directory structure](#directory-structure)
- [Screenshots](#screenshots)

## System overview

Here is a high-level image showing all components (and the relationships between them) of the telemetry system:

![Telemetry link high-level architecture](/images/link-telemetry-arch.png)

The core of the telemetry system is the **telemetry cluster**. This cluster consists of three Docker containers:

1. **Parser** - implemented as a Flask server which exposes an HTTP API that accepts parse requests.
2. **InfluxDB** - the database instance that stores the time-series parsed telemetry data.
3. **Grafana** - the observability framework that allows building dashboards for data visualization.

There are two technologies that our cars utilize to transmit data: _radio_ and _cellular_. Due to differences in the way these work, they interact with the telemetry cluster in slightly different ways.

The cellular module on Daybreak runs MicroPython and can make HTTP requests which means it can communicate with the telemetry cluster (specifically the parser) directly.

The radio module, however, is more complicated. It can only send a serial stream to a radio receiver. This radio receiver, when connected to a host computer, makes available the stream of bytes coming from the radio transmitter. Unfortunately, this still leaves a gap between the incoming data stream and the telemetry cluster. 

This is where the `link_telemetry.py` script comes in. Its main function is to bridge the gap between the incoming data stream by splitting the data stream into individual messages, packaging each message in a JSON object, and finally making an HTTP request to the parser.

> NOTE: the only way for a data source (e.g., radio, cellular, etc.) to access the telemetry cluster is to make HTTP requests to the parser. No direct access to the Influx or Grafana containers is available. Only the parser can directly communicate with those services.

A more detailed description of the system components is given [here](/docs/SYSTEM.md).

## Getting started

When attempting to set up the telemetry system, it is important to decide which components need to be brought up. There are two components that need to be brought up: the **telemetry cluster** and the **telemetry link**.

- If the telemetry cluster has **already been set up** and you would like to only set up the telemetry link to communicate with the cluster, skip to [this section]().

- If the telemetry cluster has **not been set up**, continue onwards to set it up.

## Telemetry cluster setup

Since the telemetry cluster consists of three Docker containers that are spun up with Docker Compose, it can easily be deployed on any (although preferably Linux) system.

This means that there are two possibilities for running the telemetry cluster. You may either run it *locally* or *remotely*. Each has its advantages and disadvantages.

(TODO) format below as a table:

**When running the cluster locally**, you have the cluster running on the *same* host as the telemetry link. This means the total pipeline latency from data source to cluster is very small (~5ms). This makes it ideal for debugging applications where data is most time-sensitive. This is also the only option when running the telemetry system on a host without an internet/cellular connection. Furthermore, running the cluster locally only supports radio as a data source since cellular, by its very nature, can only transmit to devices with a cellular/internet connection. 

**When running the cluster remotely**, you have the cluster running on a *different* host from the telemetry link. Latency from data source to cluster is higher (~200ms) since HTTP requests must be transmitted over the internet to the server that the cluster is hosted on. However, since the cluster is hosted, it is accessible by cellular as well as radio. In this case, parsed telemetry data is stored in a centralized location and not just on a single system thus giving broader access to the data.

In any case, the setup instructions for the cluster are exactly the same.

First, you must install the following prerequisites:

### Pre-requisites

- Docker & Docker Compose (https://docs.docker.com/get-docker/)

Check your Docker Compose installation by running:

```bash
sudo docker compose version
```

### Setting up environment variables

Before spinning up the cluster, you must create a `.env` file in the project root directory (i.e., the same directory as the `docker-compose.yaml` file). I find that it is easiest to create the file from the terminal:

For Linux/macOS:

```bash
cd link_telemetry
touch .env
```

For Windows:

```powershell
New-Item -Path . -Name ".env"
```

Then, you may use any code editor to edit the file.

> **NOTE:** make sure you correctly rename your environment variable file to `.env` otherwise Docker compose will not be able to read it. It should **not** have a `.txt` extension.

An example `.env` file is given in `./examples/environment/`. The contents of this file will look something like this:

```env
# Grafana environment variables

GRAFANA_ADMIN_USERNAME=""
GRAFANA_ADMIN_PASSWORD=""

# InfluxDB environment variables

INFLUX_ADMIN_USERNAME=""
INFLUX_ADMIN_PASSWORD=""

INFLUX_ORG="UBC Solar"

# used to store random data for debugging purposes
INFLUX_DEBUG_BUCKET=Test

# used to store real data from the car
INFLUX_PROD_BUCKET=Telemetry

# Parser secret key

SECRET_KEY=""

# Access tokens

INFLUX_TOKEN=""
GRAFANA_TOKEN=""
```

The fields with empty values all need to be filled except for the access tokens. These fields should be manually filled once the docker containers are spun up. An example of what a valid `.env` file will look like **before** starting the docker containers is given below:

```env
# Grafana environment variables

GRAFANA_ADMIN_USERNAME="admin"
GRAFANA_ADMIN_PASSWORD="ubcsolar"

# InfluxDB environment variables

INFLUX_ADMIN_USERNAME="admin"
INFLUX_ADMIN_PASSWORD="ubcsolar"

INFLUX_ORG="UBC Solar"

# used to store random data for debugging purposes
INFLUX_DEBUG_BUCKET="Test"

# used to store real data from the car
INFLUX_PROD_BUCKET="Telemetry"

# Secret key

SECRET_KEY="dsdsxt12pr364s4isWFyu3IBcC392hLJhjEqVvxUwm4"

# Access tokens

INFLUX_TOKEN=""
GRAFANA_TOKEN=""
```

Note that the `INFLUX_TOKEN` and `GRAFANA_TOKEN` keys are left without values (for now).

For the `GRAFANA_ADMIN_USERNAME` and `GRAFANA_ADMIN_PASSWORD`, you may choose any values. The same goes for all of the `INFLUX_*` environment variables.

The `SECRET_KEY` field, however, must be generated.

#### Generating the secret key

The `SECRET_KEY` variable defines the key that the parser will look for in the authentication headers for any HTTP request sent to it. Because the parser API is exposed over the internet, the secret key authentication is a simple form of access control.

The easiest way to generate the value for the `SECRET_KEY` variable is to use the Python `secrets` package.

First, fire up your Python interpreter:

```
$ python
Python 3.10.6 (main, May 29 2023, 11:10:38) [GCC 11.3.0] on linux
Type "help", "copyright", "credits" or "license" for more information.
>>>
```

Then, execute the following:

```
>>> import secrets
>>> secrets.token_urlsafe()
'dsdsxt12pr364s4isWFyu3IBcC392hLJhjEqVvxUwm4'
```

Use the generated key as your secret key.

### Starting the telemetry cluster

Before running the `link_telemetry.py` script, you must first
start the Grafana and InfluxDB instances using docker. 

Ensure your current working directory is the repository
root folder before running the following command:

```bash 
sudo docker compose up
```

This will start a Grafana instance at `http://localhost:3000` and an InfluxDB instance at `http://localhost:8086`.

### Aside: handy docker commands

1) `sudo docker ps` => lists all running containers

2) `sudo docker compose stop` => stops all running containers defined in Compose file

3) `sudo docker compose restart` => restarts all running containers defined in Compose file

4) `sudo docker exec -it <CONTAINER_NAME> /bin/bash` => start a shell instance inside <CONTAINER_NAME>

### Finishing environment set-up

Once the docker containers are up and running, you should be able to access InfluxDB and Grafana at `http://localhost:8086` and `http://localhost:3000`

* Login to the InfluxDB web application with the admin username and password. Generate a new API token. This token should be used as the value for the `INFLUX_TOKEN` key in your `.env` file.
* Access Grafana and generate a new API token. This token should be used as the value for the `GRAFANA_TOKEN` key in your `.env` file.

NOTE: both the InfluxDB and Grafana token need to be given write access since the telemetry link uses them to write data to the InfluxDB bucket
and the Grafana Live endpoint.

## Telemetry link setup

### Pre-requisites

- Python 3.8 or above (https://www.python.org/downloads/)

Check your Python installation by running:

```bash
python --version
```

> NOTE: Ensure your Python version is 3.8 or higher.

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

Refer to [API.md](/docs/API.md) for the full documentation of the endpoints that the parser exposes.

## Directory structure

- `config`: stores config files for Grafana and Influx.
- `core`: contains the CAN parsing Python implementation and some utility functions.
- `dashboards`: contains the provisioned Grafana dashboard JSONs.
- `dbc`: stores DBC files for CAN parsing.
- `docs`: contains Markdown system documentation.
- `examples/environment`: contains example `.env` config files.
- `images`: contains images relevant to the telemetry system.
- `provisioning`: contains YAML files that provision the initial dashboards and data sources for Grafana.
- `test`: contains test framework for the CAN parser.

## Screenshots

Here are some screenshots of real data gathered from Daybreak using the telemetry system:

![Battery state](/images/battery_state.png)

![Battery voltages](/images/battery_voltages.png)

![Current setpoint and bus current](/images/current_setpoint_and_bus_current.png)

![Current setpoint and vehicle velocity](/images/current_setpoint_and_vehicle_velocity.png)

![Vehicle velocity and motor velocity](/images/vehicle_velocity_and_motor_velocity.png)

