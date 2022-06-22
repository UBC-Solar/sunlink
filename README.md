# UBC Solar's Telemetry Link

This is the link between the raw radio module serial stream that comes from Daybreak's
onboard telemetry system and the Grafana frontend. This project is responsible for CAN
message parsing with Python, time-series data storage with InfluxDB,
and finally, data visualization with Grafana.

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

Before starting up the docker instances, you must create a `.env` file in the project root directory.
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
