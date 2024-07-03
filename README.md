# UBC Solar's Sunlink

Sunlink is UBC Solar's radio and cellular-based telemetry system. It allows us to process, store, and visualize data produced by our solar cars in real-time.

Collecting and visualizing this data is useful since it allows for:

1. Optimizing drive performance
2. Debugging on-board electronic systems
3. Verifying race-strategy simulation models
4. Enabling continuous race-strategy simulation recalculations
5. Post-mortem system analysis

This repository contains all of the components that make up Sunlink.

## Table of contents

-   [Directory structure](#directory-structure)
-   [System overview](#system-overview)
-   [Getting started](#getting-started)
-   [Telemetry cluster setup](#telemetry-cluster-setup)
-   [Telemetry link setup](#telemetry-link-setup)
-   [Running the link](#running-the-link)
-   [Running the tests](#running-the-tests)
-   [Parser HTTP API](#parser-http-api)
-   [Screenshots](#screenshots)

## Directory structure

-   `config`: stores config files for Grafana and Influx.
-   `dashboards`: contains the provisioned Grafana dashboard JSONs.
-   `dbc`: stores DBC files for CAN parsing.
-   `docs`: contains additional system documentation.
-   `images`: contains images relevant to Sunlink.
-   `parser`: contains the Python implementation of the parser server.
-   `provisioning`: contains YAML files that provision the initial dashboards and data sources for Grafana.
-   `scripts`: contains post-initialization scripts for InfluxDB.
-   `templates`: contains a template `.env` config file.
-   `test`: contains test framework for the CAN parser.

## System overview

Below is a complete block diagram of all system components:

![Sunlink high-level architecture](/images/sunlink-arch.png)

### Telemetry cluster

The **telemetry cluster** forms the core of Sunlink. The cluster consists of three Docker containers:

1. **Parser** - implemented as a Flask server which exposes an HTTP API that accepts parse requests.
2. **InfluxDB** - the database instance that stores the time-series parsed telemetry data.
3. **Grafana** - the observability framework that allows building dashboards for data visualization.

### Radio and cellular

There are two technologies that our cars utilize to transmit data: _radio_ and _cellular_. Due to differences in the way these work, they interact with the telemetry cluster in slightly different ways.

The cellular module on Daybreak runs MicroPython and can make HTTP requests which means it can communicate with the telemetry cluster directly.

The radio module, however, is more complicated. It can only send a serial stream to a radio receiver. This radio receiver, when connected to a host computer, makes the stream of bytes coming from the radio transmitter available over a serial port. Unfortunately, this still leaves a gap between the incoming data stream and the telemetry cluster.

This is where the `link_telemetry.py` script (AKA the telemetry link) comes in. Its main function is to bridge the gap between the incoming data stream and the telemetry cluster by splitting the data stream into individual messages, packaging each message in a JSON object, and finally making an HTTP request to the cluster.

> **NOTE:** the only way for a data source (e.g., radio, cellular, etc.) to access the telemetry cluster is to make HTTP requests to the parser. No direct access to the Influx or Grafana containers is available. Only the parser can directly communicate with those services.

A detailed description of all system components is given [here](/docs/SYSTEM.md).

## Getting started

When attempting to set up Sunlink, it is important to decide whether you want to set up both the telemetry cluster and telemetry link or just the telemetry link.

-   If the telemetry cluster has **already been set up** and you would like to only set up the telemetry link to communicate with the cluster, skip to [this section](#telemetry-link-setup).

-   If the telemetry cluster has **not been set up**, continue onwards to set it up.

### Automated Sunlink Telemetry Cluster Setup

This includes a bash script to automate the setup of Sunlink with Nginx as a reverse proxy to spin up Docker containers for the telemetry cluster.

#### Overview

The `run_setup.sh` script simplifies the process of installing dependencies and setting up Sunlink. This additionally configures Nginx and Docker to manage your telemetry cluster. It sets up Nginx as a reverse proxy, enabling seamless communication between your Docker containers.

#### Script Summary

The `setup.sh` script:

- Updates the system packages.
- Installs Docker and Docker Compose.
- Clones the Sunlink repository.
- Prompts the user for Grafana and InfluxDB credentials including API tokens.
- Creates necessary configuration files for nginx and docker compose.
- Starts the Docker containers for the telemetry cluster.
- Installs linuxcan and kvlibsdk
- Creates `CAN_log`, `CAN_prod`, and `CAN_test` Influxdb buckets.


#### Usage
If you would like a fresh copy of the Kvaser drivers and SDK for Linux then run `sudo make uninstall` in the `linuxcan/` and `kvlibsdk/` folders and then delete them afterwords. Of course, make sure to type `y` when prompted to install Kvaser drivers and SDK in the setup script.

1. **Download the Script**

   Download the `setup.sh` script into the directory where you want to set up the telemetry cluster:

   ```sh
   curl -O https://github.com/UBC-Solar/sunlink/setup.sh

2. **Run Script**

   To run the script, simply enter the following command:

   ```sh
   ./setup.sh

## Telemetry cluster setup

Since the telemetry cluster consists of three Docker containers that are spun up with Docker Compose, it can easily be deployed on any (although preferably Linux) system.

This means that there are two possibilities for running the telemetry cluster. You may either run it _locally_ or _remotely_. Each has its advantages and disadvantages.

| **Local cluster**                                                       | **Remote cluster**                                                             |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| Cluster runs on the _same_ host as the telemetry link                   | Cluster runs on a _different_ host as the telemetry link                       |
| Total pipeline latency from data source to cluster is very small (~5ms) | Total pipeline latency from data source to cluster is higher (~200ms)          |
| Ideal for time-sensitive control board debugging                        | Allows for a centralized, Internet-accessible storage location for parsed data |
| Useful for when an Internet connection is unavailable/unreliable        | Access to the cluster requires an Internet connection                          |
| Only supports radio as a data source                                    | Supports both radio and cellular as a data source                              |

Whether you're setting up the cluster locally or remotely, the setup instructions are exactly the same.

> **NOTE:** at some point in the future, I envision being able to run a local and remote cluster _concurrently_. The telemetry link would then be able to decide which cluster to access depending on Internet connectivity. Currently, there's nothing stopping you from spinning up both a local and remote cluster, but the telemetry link cannot dynamically switch between them at runtime.

### Pre-requisites

-   Python 3.8 or above (https://www.python.org/downloads/)
-   Docker & Docker Compose (https://docs.docker.com/get-docker/)
-   Linux PCAN Driver (https://www.peak-system.com/fileadmin/media/linux/index.htm)
-   A cloned copy of this repository

### Aside: Using Sunlink with WSL2
> https://learn.microsoft.com/en-us/windows/wsl/connect-usb

Follow these instructions to attach a USB device to a Linux distribution running on WSL 2:
1. Follow the instructions in the link above to install the USBIPD-WIN project as support for connecting USB devices is not natively available in WSL.
2. Follow the instructions in the same link to attach the USB device.

> [!NOTE]
> This has to be done every time WSL2 is restarted.

<br>

Clone the repository with:

```bash
git clone https://github.com/UBC-Solar/sunlink.git
```

Check your Python installation by running:

```bash
python --version
```

> NOTE: In some cases, your python interpreter might be called `python3`.

Check your Docker Compose installation by running:

```bash
sudo docker compose version
```
> [!NOTE]
> If you plan to use the offline mode with the linktelemetry.py script, please see the below settings for VirtualBox and bringing up the CAN interface

Add PCAN USB port to Ubuntu from Virtual Box settings:

- Go to settings from Virtual Box.
- Click on the green + as shown in the picture below.
- Add the USB port the PCAN is connected to and click OK.

![Battery state](/images/virtualbox_usb.png)

Bringing CAN interface up:
```bash
$ sudo ip link set can0 type can bitrate 500000
$ sudo ip link set up can0
```
> NOTE: Make sure you added the usb port for PCAN on the Ubuntu from the settings.

Check if PCAN is connected properly:
```bash
candump -H -td -x -c can0
```
This should output what is on the PCAN at the moment.

### Setting up environment variables

Before spinning up the cluster, you must create a `.env` file in the project root directory (i.e., the same directory as the `docker-compose.yaml` file). I find that it is easiest to create the file from the terminal:

For Linux/macOS:

```bash
cd sunlink/
touch .env
```

For Windows:

```powershell
cd sunlink\
New-Item -Path . -Name ".env"
```

Then, you may use any code editor to edit the file.

A template `.env` file is given in the `templates/` folder. Copy the contents of this file into your new `.env` file. Your `.env` file should look like the following:

```env
# Grafana environment variables

GRAFANA_ADMIN_USERNAME=""
GRAFANA_ADMIN_PASSWORD=""

# InfluxDB environment variables

INFLUX_ADMIN_USERNAME=""
INFLUX_ADMIN_PASSWORD=""

INFLUX_ORG="UBC Solar"

# Needed to Initialize InfluxDB
INFLUX_INIT_BUCKET="Init_test"
INFLUX_DEBUG_BUCKET="CAN_test"

# Parser secret key
SECRET_KEY=""

# Access tokens

INFLUX_TOKEN=""
GRAFANA_TOKEN=""
```

The fields with empty values all need to be filled _except for the access tokens_. These fields should be manually filled once the cluster is spun up. An example of what a valid `.env` file will look like **before** spinning up the cluster is given below:

```env
# Grafana environment variables

GRAFANA_ADMIN_USERNAME="admin"
GRAFANA_ADMIN_PASSWORD="new_password"

# InfluxDB environment variables

INFLUX_ADMIN_USERNAME="admin"
INFLUX_ADMIN_PASSWORD="new_password"

INFLUX_ORG="UBC Solar"

# Needed to Initialize InfluxDB
INFLUX_INIT_BUCKET="Init_test"
INFLUX_DEBUG_BUCKET="CAN_test"

# Secret key

SECRET_KEY="dsdsxt12pr364s4isWFyu3IBcC392hLJhjEqVvxUwm4"

# Access tokens

INFLUX_TOKEN=""
GRAFANA_TOKEN=""
```

Note that the `INFLUX_TOKEN` and `GRAFANA_TOKEN` keys are left without values (for now).

For the `GRAFANA_ADMIN_USERNAME` and `GRAFANA_ADMIN_PASSWORD` fields, you may choose any values. The same goes for the `INFLUX_ADMIN_USERNAME` and `INFLUX_ADMIN_PASSWORD` fields. **For the passwords, however, ensure they are long enough otherwise Grafana and InfluxDB will reject them.**

The `SECRET_KEY` field must be generated.

> :warning: **WARNING: Make sure not to change the `INFLUX_ORG`, `INFLUX_INIT_BUCKET`, and `INFLU_DEBUG_BUCKET` variables from their defaults since that might break the provisioned Grafana dashboards.**

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

You should see a flurry of text as the three services come online.

### Aside: handy docker commands

| **Command**                                       | **Description**                                                                                                                          |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `sudo docker ps`                                  | Lists all running containers.                                                                                                            |
| `sudo docker compose stop`                        | Stops all running containers defined in Compose file.                                                                                    |
| `sudo docker compose restart`                     | Restarts all running containers defined in Compose file.                                                                                 |
| `sudo docker compose up -d`                       | Spins up all containers in detached mode (i.e., in the background).                                                                      |
| `sudo docker exec -it <CONTAINER_NAME> /bin/bash` | Starts a shell instance inside `<CONTAINER_NAME>`.                                                                                       |
| `sudo docker system df`                           | Shows docker disk usage (includes containers, images, volumes, etc.). Useful when checking how much space the InfluxDB volume is taking. |

### Finishing environment set-up

On startup, the InfluxDB container binds to port 8086, the Grafana container binds to port 3000, and the parser container binds to port 5000.

This means that once the cluster is up and running, you should be able to access InfluxDB, Grafana, and the parser at `http://localhost:8086`, `http://localhost:3000`, and `http://localhost:5000` respectively.

Now we can generate the missing API tokens we left out of our `.env` file from before:

-   Go to the InfluxDB URL and login to the InfluxDB web application with the admin username and password you specified in your `.env` file. Generate a new API token. This token should be used as the value for the `INFLUX_TOKEN` key in your `.env` file.

-   Go to the Grafana URL and login to the Grafana web application with the admin username and password you specified in your `.env` file. Create a new service account and create an API token under this service account. This token should be used as the value for the `GRAFANA_TOKEN` key in your `.env` file.

Both the [InfluxDB API docs](https://docs.influxdata.com/influxdb/v2.7/security/tokens/#Copyright) and [Grafana API docs](https://grafana.com/docs/grafana/latest/administration/service-accounts/) provide detailed guides on how to create API tokens for each platform.

> **NOTE:** both the InfluxDB and Grafana token need to be given write access since the telemetry link uses them to write data to the InfluxDB bucket and the Grafana Live endpoint. **Ensure that the Grafana token has admin access since live-streaming data will not work otherwise**.

Once you've filled in all the fields in your `.env` file, you can restart the cluster with:

```bash
sudo docker compose stop
sudo docker compose up
```

> **NOTE:** You may also try using `sudo docker compose restart` but sometimes it causes Grafana to be unable to authorize its connection to InfluxDB.

### Checking your setup

Now that you've finished setting up the cluster, you need to check that everything is up and running. The quickest way to do this would be to use cURL to query the health endpoint that the parser exposes. This does require HTTP authentication so make sure you have access to the `SECRET_KEY` variable in your `.env` file.

Assuming the value of my `SECRET_KEY` was `dsdsxt12pr364s4isWFyu3IBcC392hLJhjEqVvxUwm4` and the parser was available on `localhost:5000/`, my cURL command would look like:

```bash
curl --get localhost:5000/api/v1/health -H "Authorization: Bearer dsdsxt12pr364s4isWFyu3IBcC392hLJhjEqVvxUwm4"
```

If all your tokens are correctly set up, the parser should return the following:

```json
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

- If your output doesn't look like the above, double-check the tokens you entered into the `.env` file and ensure that you **restarted the docker containers** after changing the tokens. Of course, make sure your docker containers are running in the first place. For more information about the parser API health endpoint, go [here](#parser-http-api).

- If your output looks like the above, then congratulations! You've finished setting up the telemetry cluster! :heavy_check_mark:

## Telemetry link setup

The telemetry link must be set up on the host machine on which the radio receiver is connected. This links the radio module to the telemetry cluster and enables using radio as a data source.

### Pre-requisites

-   Python 3.8 or above (https://www.python.org/downloads/)
-   A functional and running telemetry cluster (either local or remote)
-   A cloned copy of this repository

Clone the repository with:

```bash
git clone https://github.com/UBC-Solar/sunlink.git
```

Check your Python installation by running:

```bash
python --version
```

> NOTE: In some cases, your python interpreter might be called `python3`.

### Creating a Python virtual environment

It is highly recommended that you create a Python virtual environment to avoid breaking your system-installed version of Python.

You may choose to create your virtual environment folder anywhere but I like to create it in its own `environment` subdirectory in the project root directory:

```bash
cd sunlink/
python -m venv environment
```

Execute the following to enter your virtual environment on Linux:

```bash
source environment/bin/activate
```

Or on Windows:

```bash
.\environment\Scripts\Activate.ps1
```

To exit your virtual environment:

```bash
deactivate
```

### Installing Python package requirements

Before continuing, enter the Python virtual environment you just created.

To install the package requirements for `link_telemetry.py`, go to the root directory, and execute:

```bash
python -m pip install -r requirements.txt
```

All the required packages for `link_telemetry.py` should now be installed.

### Telemetry link configuration

The `telemetry_link.py` script expects a `telemetry.toml` file in the same directory as it. A template for this TOML file can be found in the `/templates` folder. Copy this template file into the project root directory and rename it to `telemetry.toml`.

An example `telemetry.toml` would look like:

```toml
[parser]
url = "http://143.120.12.53:5000/"

[security]
secret_key = "dsdsxt12pr364s4isWFyu3IBcC392hLJhjEqVvxUwm4"

[offline]
channel = "can0"
bitrate = "500000"
```

The `parser.url` field specifies the URL where the script can find the telemetry cluster parser. If you are running the cluster locally, the url would likely be `http://localhost:5000/`.

The `security.secret_key` field specifies the secret key to use in the HTTP authentication headers when making a request to the parser.

This secret key must match with the secret key configured for the telemetry cluster parser that you are trying to communicate with.

If you set up the telemetry cluster locally then you already have access to this secret key. If the telemetry cluster was set up for you, ask your software lead for the secret key.

The `offline.channel` and `offline.bitrate` fields specify the channel and bitrate of the PCAN.

> [!IMPORTANT]
> The [offline] fields are only required if you plan to use the offline mode with PCAN.

Once all the fields are filled, the `link_telemetry.py` script is ready for use.

## Running the link

Make sure you've entered your virtual environment before trying to run the script.

`link_telemetry.py` takes many command-line arguments. The best way to learn what each one does is to look at the help menu:

```bash
./link_telemetry.py --help
```

Here are some example invocations:

| **Command**                                                | **Description**                                                                                                                                                                                                                    |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `./link_telemetry.py --health`                             | Checks if the parser is available.                                                                                                                                                                                                 |
| `./link_telemetry.py -p /dev/ttyUSB0 -b 230400 --prod`     | Specifies a source port of `/dev/ttyUSB0` with a baudrate of `230400` and requests the parser to write to the CAN InfluxDB bucket.                                                                                                 |
| `./link_telemetry.py -p /dev/ttyUSB0 -b 230400 --no-write` | Specifies a source port of `/dev/ttyUSB0` with a baudrate of `230400` and requests the parser to only parse and not write data to InfluxDB.                                                                                        |
| `./link_telemetry.py -r all --debug`                       | Makes the link randomly generate message data for CAN, GPS, and IMU (all) and requests the parser to write to the debug InfluxDB bucket.                                                                                           |
| `./link_telemetry.py -r can --debug`                       | Makes the link randomly generate message data for can) and requests the parser to write to the debug InfluxDB bucket.                                                                                                              |
| `./link_telemetry.py -r all --live-on 0x401 1795 IMU --debug`     | Makes the link randomly generate message data for CAN, GPS, and IMU (all), requests the parser to write to the debug InfluxDB bucket, and **l**ivestreams only message ID 0x401 (hex), 1795 (decimal), and IMU messages to Grafana |
| `./link_telemetry.py -r all --live-off --debug`            | Makes the link randomly generate message data for CAN, GPS, and IMU (all), requests the parser to write to the debug InfluxDB bucket, and **l**ivestreams nothing to Grafana.                                                      |
| `./link_telemetry.py -r all --live-on all --debug`                | Makes the link randomly generate message data for CAN, GPS, and IMU (all), requests the parser to write to the debug InfluxDB bucket, and **l**ivestreams all data to Grafana.                                                     |
| `./link_telemetry.py -r can -f 100 --debug`                | Makes the link randomly generate CAN message data at 100Hz and requests the parser to write to the debug InfluxDB bucket.                                                                                                          |
| `./link_telemetry.py -o --debug`                           | Makes the link to recieve data from PCAN and requests the parser to write to the debug InfluxDB bucket.                                                                                                                            |
| `./link_telemetry.py -o --prod`                            | Makes the link to recieve data from PCAN and requests the parser to write to the CAN InfluxDB bucket.       
| `./link_telemetry.py -o --raw`                           | Will print out the **hexified** serial messages that will be sent to the parser in the `message` field of the payload                                                                                                                      |
| `./link_telemetry.py -o --rawest`                            | This prints the exact `CHUNK_SIZE` of data received from serial as a **hex** string. Because of the chunking algorithm, **the chunk may have incomplete messages**                                                                           |
                                                                                                                       |

> Previously, the `--prod` option would write to the production InfluxDB bucket. This has been changed to write to the CAN InfluxDB bucket as CAN is currently the only source of data source that is supported in Sunlink. Soon, other buckets will be added along with support for other data sources including GPS, IMU, and VDS (Vehicle Dynamics Sensors) data. New buckets must be created with shell scripts, similar to in the script `scripts/create-influx_debug-bucket.sh`. The .env file must also contain the name for the bucket created on `telemetry.ubcsolar.com:8086`. The parser script must be modified to support posting data to new buckets.

## Running the Offline Log Uploader

The offline log uploader will use the `MemoratorUploader` script in the `tools/` folder to read the contents of the SD card on the Memorator and then upload those messages to InfluxDB. There are two options for this: `-u fast` and `-u all`. `-u fast` will only upload one Log File Container (1 .KMF file will be read). In `-u all` all 15 .KMF files on the SD card will be read and their data will be uploaded. Note: data is sent to the `_log` suffixed bucket.

```bash
./link_telemetry.py -u fast
./link_telemetry.py -u all
```

## Running the tests

To run the parser tests, make sure you're in your virtual environment, go to the project root directory, and execute:

```bash
python -m pytest
```

Currently, the test framework only tests that the parser parses CAN messages as expected. It does not test any other part of Sunlink.

## Parser HTTP API

Refer to [API.md](/docs/API.md) for the full documentation of the endpoints that the parser exposes.

## Screenshots

Here are some screenshots of real data gathered from Daybreak using Sunlink:

![Battery state](/images/battery_state.png)

![Battery voltages](/images/battery_voltages.png)

![Current setpoint and bus current](/images/current_setpoint_and_bus_current.png)

![Current setpoint and vehicle velocity](/images/current_setpoint_and_vehicle_velocity.png)

![Vehicle velocity and motor velocity](/images/vehicle_velocity_and_motor_velocity.png)
