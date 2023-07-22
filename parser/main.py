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

from parser.standard_frame import StandardFrame
from parser.standard_frame import Measurement

from dotenv import dotenv_values

__PROGRAM__ = "parser"
__VERSION__ = "0.4"

# <----- Flask ----->

app = Flask(__name__)

# <----- Constants ----->

CAR_NAME = "Daybreak"

# paths are relative to project root
DBC_FILE = Path("./dbc/daybreak.dbc")
ENV_FILE = Path(".env")

if not DBC_FILE.is_file():
    app.logger.critical(f"Unable to find expected existing DBC file: \"{DBC_FILE.absolute()}\"")
    sys.exit(1)

if not ENV_FILE.is_file():
    app.logger.critical(f"Unable to find expected existing environment variable file: \"{ENV_FILE.absolute()}\"")
    sys.exit(1)

ENV_CONFIG = dotenv_values(ENV_FILE)

API_PREFIX = "/api/v1"

STREAM_QUEUE_MAXSIZE = 256

# <----- Grafana constants ----->

GRAFANA_URL = "http://grafana:3000/"
GRAFANA_TOKEN = ENV_CONFIG["GRAFANA_TOKEN"]

# url without the 'http://'
GRAFANA_URL_NAME = Path(GRAFANA_URL).name

stream_queue: 'queue.Queue' = queue.Queue(maxsize=STREAM_QUEUE_MAXSIZE)

# <----- Read in DBC file ----->

DAYBREAK_DBC = cantools.database.load_file(DBC_FILE)

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


@auth.verify_token
def verify_token(token):
    if token in tokens:
        return tokens[token]
    return None


@app.route("/")
def welcome():
    return "Welcome to UBC Solar's Telemetry Parser!\n"


@app.post(f"{API_PREFIX}/parse")
@auth.login_required
def parse_request():
    """
    Parses incoming request and sends back the parsed result.
    """
    parse_request: Dict = flask.request.json
    id: str = parse_request["id"]
    data: str = parse_request["data"]
    timestamp: str = parse_request["timestamp"]
    data_length: str = parse_request["data_length"]

    app.logger.info(f"Received message: {id=}, {data=}")

    # TODO: add validation for received JSON object

    can_msg = StandardFrame(id, data, timestamp, data_length)

    # extract measurements from CAN message
    try:
        extracted_measurements: List[Measurement] = can_msg.extract_measurements(DAYBREAK_DBC)
        app.logger.info(f"Successfully parsed CAN message with id={can_msg.hex_identifier}({can_msg.identifier})")
        return {
            "result": "OK",
            "measurements": extracted_measurements,
            "id": can_msg.identifier
        }
    except Exception:
        app.logger.warn(
            f"Unable to extract measurements for CAN message with id={can_msg.hex_identifier}({can_msg.identifier})")
        return {
            "result": "PARSE_FAIL",
            "measurements": [],
            "id": can_msg.identifier
        }

def write_measurements():
    """
    Worker thread responsible for live-streaming measurements to Grafana.

    NOTE: live-streaming measurements to Grafana is done in a separate thread since it is an optional feature and
    it doesn't matter if it succeeds or not. Furthermore, having this in a separate thread reduces latency.
    """

    while True:
        extracted_measurements: List[Measurement] = stream_queue.get()

        for measurement in extracted_measurements:
            name = measurement.name
            source = measurement.source
            m_class = measurement.m_class
            value = measurement.value

            # compute Grafana websocket URL to livestream measurement
            endpoint_name = "_".join([CAR_NAME, source, m_class, name])
            websocket_url = f"ws://{GRAFANA_URL_NAME}/api/live/push/{endpoint_name}"

            # live-stream measurements to Grafana Live
            try:
                with connect(websocket_url,
                             additional_headers={
                                 'Authorization': f'Bearer {GRAFANA_TOKEN}'}
                             ) as websocket:
                    current_time = time.time_ns()
                    message = f"test value={value} {current_time}"
                    websocket.send(message)
            except Exception:
                app.logger.warning(f"Unable to stream measurement \"{name}\" to Grafana!")
            else:
                app.logger.debug(f"Streamed \"{m_class}\" measurement to Grafana instance!")


# create thread to write to InfluxDB and stream to Grafana
threading.Thread(target=write_measurements, daemon=True).start()
