# UBC Solar's Telemetry System

The goal of UBC Solar's telemetry system is to extract, store, and visualize data produced by our solar cars in real-time.

Collecting and visualizing this data is useful since it allows for:

1) Optimizing drive performance
2) Debugging on-board electronic systems 
3) Verifying race-strategy simulation models
4) Enabling continuous race-strategy simulation recalculations
5) Post-mortem system analysis

This repository contains all of the components for UBC Solar's telemetry system.

## Table of contents

- [Directory structure](#directory-structure)
- [System overview](#system-overview)
- [Getting started](#getting-started)
- [Telemetry cluster setup](#telemetry-cluster-setup)
- [Telemetry link setup](#telemetry-link-setup)
- [Running the link](#running-the-link)
- [Parser HTTP API](#parser-http-api)
- [Screenshots](#screenshots)

## Directory structure

- `config`: stores config files for Grafana and Influx.
- `core`: contains the Python implementation of the CAN message class.
- `dashboards`: contains the provisioned Grafana dashboard JSONs.
- `dbc`: stores DBC files for CAN parsing.
- `docs`: contains additional system documentation.
- `templates`: contains a template `.env` config file.
- `images`: contains images relevant to the telemetry system.
- `provisioning`: contains YAML files that provision the initial dashboards and data sources for Grafana.
- `test`: contains test framework for the CAN parser.

## System overview

Here is a high-level image showing all components (and the relationships between them) of the telemetry system:

![Telemetry link high-level architecture](/images/link-telemetry-arch.png)

The core of the telemetry system is the **telemetry cluster**. This cluster consists of three Docker containers:

1. **Parser** - implemented as a Flask server which exposes an HTTP API that accepts parse requests.
2. **InfluxDB** - the database instance that stores the time-series parsed telemetry data.
3. **Grafana** - the observability framework that allows building dashboards for data visualization.

There are two technologies that our cars utilize to transmit data: _radio_ and _cellular_. Due to differences in the way these work, they interact with the telemetry cluster in slightly different ways.

The cellular module on Daybreak runs MicroPython and can make HTTP requests which means it can communicate with the telemetry cluster directly.

The radio module, however, is more complicated. It can only send a serial stream to a radio receiver. This radio receiver, when connected to a host computer, makes available the stream of bytes coming from the radio transmitter over a serial port. Unfortunately, this still leaves a gap between the incoming data stream and the telemetry cluster. 

This is where the `link_telemetry.py` script comes in. Its main function is to bridge the gap between the incoming data stream by splitting the data stream into individual messages, packaging each message in a JSON object, and finally making an HTTP request to the parser.

> **NOTE:** the only way for a data source (e.g., radio, cellular, etc.) to access the telemetry cluster is to make HTTP requests to the parser. No direct access to the Influx or Grafana containers is available. Only the parser can directly communicate with those services.

A more detailed description of the system components is given [here](/docs/SYSTEM.md).

## Getting started

When attempting to set up the telemetry system, it is important to decide which components need to be brought up. There are two components that need to be brought up: the **telemetry cluster** and the **telemetry link**.

- If the telemetry cluster has **already been set up** and you would like to only set up the telemetry link to communicate with the cluster, skip to [this section](#telemetry-link-setup).

- If the telemetry cluster has **not been set up**, continue onwards to set it up.

## Telemetry cluster setup

Since the telemetry cluster consists of three Docker containers that are spun up with Docker Compose, it can easily be deployed on any (although preferably Linux) system.

This means that there are two possibilities for running the telemetry cluster. You may either run it *locally* or *remotely*. Each has its advantages and disadvantages.

| **Local cluster** | **Remote cluster** |
| ------------- | -------------- |
| Cluster is running on _same_ host as the telemetry link | Cluster is running on a _different_ host as the telemetry link |
| Total pipeline latency from data source to cluster is very small (~5ms) | Total pipeline latency from data source to cluster is higher (~200ms) |
| Ideal for time-sensitive control board debugging | Allows for a centralized, Internet-accessible storage location for parsed data |
| Useful for when an Internet connection is unavailable/unreliable | Access to the cluster requires an Internet connection |
| Only supports radio as a data source | Supports both radio and cellular as a data source |

Whether you're setting up the cluster locally or remotely, the setup instructions are exactly the same.

> **NOTE:** at some point in the future, I envision being able to run a local and remote cluster _concurrently_. The telemetry link would then be able to decide which cluster to access depending on Internet connectivity.

### Pre-requisites

- Python 3.8 or above (https://www.python.org/downloads/)
- Docker & Docker Compose (https://docs.docker.com/get-docker/)

Check your Python installation by running:

```bash
python --version
```

> NOTE: In some cases, your python interpreter might be called `python3`.

Check your Docker Compose installation by running:

```bash
sudo docker compose version
```

### Setting up environment variables

Before spinning up the cluster, you must create a `.env` file in the project root directory (i.e., the same directory as the `docker-compose.yaml` file). I find that it is easiest to create the file from the terminal:

For Linux/macOS:

```bash
cd link_telemetry/
touch .env
```

For Windows:

```powershell
New-Item -Path . -Name ".env"
```

Then, you may use any code editor to edit the file.

A template `.env` file is given in `./examples/`. The contents of this file will look something like this:

```env
# Grafana environment variables

GRAFANA_ADMIN_USERNAME=""
GRAFANA_ADMIN_PASSWORD=""

# InfluxDB environment variables

INFLUX_ADMIN_USERNAME=""
INFLUX_ADMIN_PASSWORD=""

INFLUX_ORG="UBC Solar"

# used to store random data for debugging purposes
INFLUX_DEBUG_BUCKET="Test"

# used to store real data from the car
INFLUX_PROD_BUCKET="Telemetry"

# Parser secret key

SECRET_KEY=""

# Access tokens

INFLUX_TOKEN=""
GRAFANA_TOKEN=""
```

The fields with empty values all need to be filled except for the access tokens. These fields should be manually filled once the docker containers are spun up. An example of what a valid `.env` file will look like **before** spinning up the cluster is given below:

```env
# Grafana environment variables

GRAFANA_ADMIN_USERNAME="admin"
GRAFANA_ADMIN_PASSWORD="new_password"

# InfluxDB environment variables

INFLUX_ADMIN_USERNAME="admin"
INFLUX_ADMIN_PASSWORD="new_password"

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

Now that you've filled in the relevant parts of the `.env` file, you can now perform the initial telemetry cluster start up.

Ensure your current working directory is the repository root folder before running the following command:

```bash 
sudo docker compose up
```

There should be flurry of text as the three services come online.

### Aside: handy docker commands

1) `sudo docker ps` => lists all running containers

2) `sudo docker compose stop` => stops all running containers defined in Compose file

3) `sudo docker compose restart` => restarts all running containers defined in Compose file

4) `sudo docker compose up -d` => spins up all containers in detached mode (i.e., in the background)

5) `sudo docker exec -it <CONTAINER_NAME> /bin/bash` => start a shell instance inside `<CONTAINER_NAME>`

### Finishing environment set-up

On startup, the InfluxDB container binds to port 8086, the Grafana container binds to port 3000, and the parser container binds to port 5000.

This means that once the cluster is up and running, you should be able to access InfluxDB, Grafana, and the parser at `http://localhost:8086`, `http://localhost:3000`, and `http://localhost:5000` respectively.

Now we can generate the missing API tokens we left out of our `.env` file from before:

* Go to the InfluxDB URL and login to the InfluxDB web application with the admin username and password you specified in your `.env` file. Generate a new API token. This token should be used as the value for the `INFLUX_TOKEN` key in your `.env` file.

* Go to the Grafana URL and login to the Grafana web application with the admin username and password you specified in your `.env` file. Create a new service account and create an API token under this service account. This token should be used as the value for the `GRAFANA_TOKEN` key in your `.env` file.

Both the [InfluxDB API docs](https://docs.influxdata.com/influxdb/v2.7/security/tokens/#Copyright) and [Grafana API docs](https://grafana.com/docs/grafana/latest/administration/service-accounts/) provide detailed guides on how to create API tokens for each platform.

> **NOTE:** both the InfluxDB and Grafana token need to be given write access since the telemetry link uses them to write data to the InfluxDB bucket and the Grafana Live endpoint. **Ensure that the Grafana token has admin access since live-streaming data will not work otherwise**.

Once you've filled in all the fields in your `.env` file, you can restart the cluster with:

```bash
sudo docker compose restart
```

### Checking your setup

Now that you've finished setting up the cluster, you need to check that everything is up and running. The quickest way to do this would be to use cURL to query the health endpoint that the parser exposes. This does require HTTP authentication so make sure you have access to the `SECRET_KEY` variable in your `.env` file.

Assuming the value of my `SECRET_KEY` was `dsdsxt12pr364s4isWFyu3IBcC392hLJhjEqVvxUwm4` and the parser was available on `localhost:5000/`, my cURL command would look like:

```bash
curl --get localhost:5000/api/v1/health -H "Authorization: Bearer dsdsxt12pr364s4isWFyu3IBcC392hLJhjEqVvxUwm4"
```

If all your tokens are correctly setup, the parser should return the following:

```
{
  "services": [
    {
      "name": "influxdb",
      "status": "UP",
      "url": "http://influxdb:8086/"
    },
    {
      "name": "grafana",
      "status": "UP",
      "url": "http://grafana:3000/"
    }
  ]
}
```

Congratulations, you've finished setting up the telemetry cluster!

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

## Parser HTTP API

Refer to [API.md](/docs/API.md) for the full documentation of the endpoints that the parser exposes.

## Screenshots

Here are some screenshots of real data gathered from Daybreak using the telemetry system:

![Battery state](/images/battery_state.png)

![Battery voltages](/images/battery_voltages.png)

![Current setpoint and bus current](/images/current_setpoint_and_bus_current.png)

![Current setpoint and vehicle velocity](/images/current_setpoint_and_vehicle_velocity.png)

![Vehicle velocity and motor velocity](/images/vehicle_velocity_and_motor_velocity.png)

