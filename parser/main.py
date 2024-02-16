import cantools
import influxdb_client
import requests
import pprint
import time
import queue
import threading
import flask
import sys

from influxdb_client.client.write_api import SYNCHRONOUS

from pathlib import Path
from typing import Dict, List

from websockets.sync.client import connect

from flask import Flask
from flask_httpauth import HTTPTokenAuth

from parser.create_message import create_message

from dotenv import dotenv_values

__PROGRAM__ = "parser"
__VERSION__ = "0.4"

# <----- Flask ----->

app = Flask(__name__)

# <----- Constants ----->

CAR_NAME = "Brightside"

# paths are relative to project root
DBC_FILE = Path("./dbc/brightside.dbc")
ENV_FILE = Path(".env")
TXT_FILE = Path("./dbc/output.txt")

if not DBC_FILE.is_file():
    app.logger.critical(f"Unable to find expected existing DBC file: \"{DBC_FILE.absolute()}\"")
    sys.exit(1)

if not ENV_FILE.is_file():
    app.logger.critical(f"Unable to find expected existing environment variable file: \"{ENV_FILE.absolute()}\"")
    sys.exit(1)

ENV_CONFIG = dotenv_values(ENV_FILE)

API_PREFIX = "/api/v1"

STREAM_QUEUE_MAXSIZE = 256

# <----- InfluxDB constants ----->

INFLUX_URL = "http://influxdb:8086/"
INFLUX_TOKEN = ENV_CONFIG["INFLUX_TOKEN"]

INFLUX_ORG = ENV_CONFIG["INFLUX_ORG"]
INFLUX_DEBUG_BUCKET = ENV_CONFIG["INFLUX_DEBUG_BUCKET"]
INFLUX_PROD_BUCKET = ENV_CONFIG["INFLUX_PROD_BUCKET"]

INFLUX_CAN_BUCKET = "CAN_test"
INFLUX_GPS_BUCKET = "GPS_test"
INFLUX_IMU_BUCKET = "IMU_test"

# <----- Grafana constants ----->

GRAFANA_URL = "http://grafana:3000/"
GRAFANA_TOKEN = ENV_CONFIG["GRAFANA_TOKEN"]

# url without the 'http://'
GRAFANA_URL_NAME = Path(GRAFANA_URL).name

stream_queue: 'queue.Queue' = queue.Queue(maxsize=STREAM_QUEUE_MAXSIZE)

# <----- InfluxDB object set-up ----->

client = influxdb_client.InfluxDBClient(
    url=INFLUX_URL, org=INFLUX_ORG, token=INFLUX_TOKEN)
write_api = client.write_api(write_options=SYNCHRONOUS)

# <----- Read in DBC file ----->

CAR_DBC = cantools.database.load_file(DBC_FILE)

# <----- Pretty printing ----->

pp = pprint.PrettyPrinter(indent=1)

# <----- Flask authentication ----->

auth = HTTPTokenAuth(scheme='bearer')

try:
    SECRET_KEY = ENV_CONFIG["SECRET_KEY"]
except KeyError:
    app.logger.critical(f"Required SECRET_KEY field in {ENV_FILE.absolute()} not found!")
    sys.exit(1)

# maps between tokens and users
tokens: Dict[str, str] = {
    SECRET_KEY: "admin"
}

# <----- Format Specificer List for all Data Types ----->
format_specifier_list = [CAR_DBC]


@auth.verify_token
def verify_token(token):
    if token in tokens:
        return tokens[token]
    return None


@app.route("/")
def welcome():
    return "Welcome to UBC Solar's Telemetry Parser!\n"


@app.get(f"{API_PREFIX}/health")
@auth.login_required
def check_health():
    """
    Returns the health of the parser and if it is
    able to connect to the relevant services.

    Sample response:
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
                },
            ]
        }
    """

    # build response dictionary
    response_dict: Dict[str, List[Dict[str, str]]] = dict()
    response_dict["services"] = list()

    # try making a request to InfluxDB container
    try:
        influx_response = requests.get(INFLUX_URL + "api/v2/buckets", headers={"Authorization": f"Bearer {INFLUX_TOKEN}"})
    except requests.exceptions.ConnectionError:
        influx_status = "DOWN"
    else:
        if (influx_response.status_code == 200):
            influx_status = "UP"
        elif (influx_response.status_code == 401):
            influx_status = "UNAUTHORIZED"
        else:
            influx_status = "UNEXPECTED_STATUS_CODE"

    # try making a request to Grafana container
    try:
        grafana_response = requests.get(GRAFANA_URL + "api/frontend/settings", headers={"Authorization": f"Bearer {GRAFANA_TOKEN}"})
    except requests.exceptions.ConnectionError:
        grafana_status = "DOWN"
    else:
        if (grafana_response.status_code == 200):
            grafana_status = "UP"
        elif (grafana_response.status_code == 401):
            grafana_status = "UNAUTHORIZED"
        else:
            grafana_status = "UNEXPECTED_STATUS_CODE"

    response_dict["services"].append({
        "name": "influxdb",
        "url": INFLUX_URL,
        "status": influx_status
    })
    response_dict["services"].append({
        "name": "grafana",
        "url": GRAFANA_URL,
        "status": grafana_status
    })

    return response_dict


@app.post(f"{API_PREFIX}/parse")
@auth.login_required
def parse_request():
    """
    Parses incoming request and sends back the parsed result.
    """
    parse_request = flask.request.json
    format_specifier_list = [CAR_DBC]
    message = create_message(parse_request["message"], format_specifier_list)
    id = message.data.get("ID", "UNKNOWN")
    type = message.type

    app.logger.info(f"Received a {message.type} message. ID = {id=}")

    return {
        "result": "OK",
        "message": message.data["display_data"],
        "id": id,
        "type": type
    }


@app.post(f"{API_PREFIX}/parse/write/debug")
@auth.login_required
def parse_and_write_request():
    return parse_and_write_request_bucket("_test")

@app.post(f"{API_PREFIX}/parse/write/production")
@auth.login_required
def parse_and_write_request_to_prod():
    return parse_and_write_request_bucket("_prod")

"""
Parses incoming request, writes the parsed measurements to InfluxDB bucket (debug or production),
and sends back parsed measurements back to client.
"""
def parse_and_write_request_bucket(bucket):
    parse_request = flask.request.json
    app.logger.info(f"Received raw message. {parse_request["message"]}")

    # try extracting measurements
    try:
        message = create_message(parse_request["message"], format_specifier_list)
        id = message.data.get("ID", "UNKNOWN")
        type = message.type
        app.logger.info(f"Successfully parsed {type} message with id={id} and placed into queue")
    except Exception:
        app.logger.warn(
            f"Unable to extract measurements for {type} message with id={id}")
        app.logger.warn(str(message.data["display_data"]))
        return {
            "result": "PARSE_FAIL",
            "message": {},
            "id": id,
            "type": type
        }

    # try writing the measurements extracted
    for i in range(len(message.data[list(message.data.keys())[0]])):
        name = message.data["Measurement"][i]
        source = message.data["Source"][i]
        m_class = message.data["Class"][i]
        value = message.data["Value"][i]


        point = influxdb_client.Point(source).tag("car", CAR_NAME).tag(
            "class", m_class).field(name, value)
        
        # write to InfluxDB
        try:
            write_api.write(bucket=message.type + bucket, org=INFLUX_ORG, record=point)
            app.logger.info(
                f"Wrote '{name}' measurement to url={INFLUX_URL}, org={INFLUX_ORG}, bucket={INFLUX_DEBUG_BUCKET}!")
        except Exception as e:
            app.logger.warning("Unable to write measurement to InfluxDB!")
            return {
                "result": "INFLUX_WRITE_FAIL",
                "message": message.data["display_data"],
                "error": str(e),
                "id": id,
                "type": type
            }

    return {
        "result": "OK",
        "message": message.data["display_data"],
        "id": id,
        "type": type
    }

# def write_measurements():
#     """
#     Worker thread responsible for live-streaming measurements to Grafana.

#     NOTE: live-streaming measurements to Grafana is done in a separate thread since it is an optional feature and
#     it doesn't matter if it succeeds or not. Furthermore, having this in a separate thread reduces latency.
#     """

#     while True:
#         data_dict = stream_queue.get()

#         # try writing the measurements extracted
#         for i in range(len(data_dict[list(data_dict.keys())[0]])):
#             name = data_dict["Measurement"][i]
#             source = data_dict["Source"][i]
#             m_class = data_dict["Class"][i]
#             value = data_dict["Value"][i]

#             # compute Grafana websocket URL to livestream measurement
#             endpoint_name = "_".join([CAR_NAME, source, m_class, name])
#             websocket_url = f"ws://{GRAFANA_URL_NAME}/api/live/push/{endpoint_name}"

#             # live-stream measurements to Grafana Live
#             try:
#                 with connect(websocket_url,
#                              additional_headers={
#                                  'Authorization': f'Bearer {GRAFANA_TOKEN}'}
#                              ) as websocket:
#                     current_time = time.time_ns()
#                     message = f"test value={value} {current_time}"
#                     websocket.send(message)
#             except Exception:
#                 app.logger.warning(f"Unable to stream measurement \"{name}\" to Grafana!")
#             else:
#                 app.logger.debug(f"Streamed \"{m_class}\" measurement to Grafana instance!")


# # create thread to write to InfluxDB and stream to Grafana
# threading.Thread(target=write_measurements, daemon=True).start()