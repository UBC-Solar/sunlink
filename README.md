# UBC Solar's Telemetry Link

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

### Setting up environment variables

Before starting up the docker instances, a `.env` file is required in the root directory.
An example `.env` file is given in `./examples/environment/`. The contents of this file will look something like this:

```env
# Grafana environment variables

GRAFANA_ADMIN_USERNAME=admin
GRAFANA_ADMIN_PASSWORD=admin

GRAFANA_URL=http://localhost:3000/
GRAFANA_TOKEN=""

# InfluxDB environment variables

INFLUX_ADMIN_USERNAME=admin
INFLUX_ADMIN_PASSWORD=admin

INFLUX_URL=http://localhost:8086/
INFLUX_TOKEN=""

INFLUX_ORG=UBC Solar
INFLUX_BUCKET=""

INFLUX_DATASOURCE_UID=o2uhkwje8832ha
```

The fields with empty values all need to be filled except for `GRAFANA_TOKEN` and `INFLUX_TOKEN`. These fields should be
manually filled once the docker containers are spun up. An example of what a valid `.env` file will look like **before** 
starting the docker containers is given below:

```env
# Grafana environment variables

GRAFANA_ADMIN_USERNAME=admin
GRAFANA_ADMIN_PASSWORD=new_password

GRAFANA_URL=http://localhost:3000/
GRAFANA_TOKEN=""

# InfluxDB environment variables

INFLUX_ADMIN_USERNAME=admin
INFLUX_ADMIN_PASSWORD=new_password

INFLUX_URL=http://localhost:8086/
INFLUX_TOKEN=""

INFLUX_ORG=UBC Solar
INFLUX_BUCKET=Telemetry

INFLUX_DATASOURCE_UID=o2uhkwje8832ha
```

As you can see, the `GRAFANA_TOKEN` and `INFLUX_TOKEN` keys are left without values.

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

### Importing the pre-configured dashboards

You can use Grafana's dashboard import feature to import the pre-configured dashboard JSON files found in the `./dashboards` folder.

NOTE: this is likely unnecessary but you should double check that the UID of the InfluxDB data source specified in the dashboard JSON file
matches the InfluxDB UID specified in your `.env` file.

### Installing Python package requirements

Before running the `link_telemetry.py` script, you must install the required python packages.
It is recommended that you create a python virtual environment before running the following command.
A detailed guide on how to create a python virtual environment can be found here: https://docs.python.org/3/library/venv.html.

To install the requirements run:

```bash
python -m pip install -r requirements.txt
```

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

