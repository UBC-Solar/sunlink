import cantools
import influxdb_client
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import ASYNCHRONOUS
import requests
from pathlib import Path
import pprint
import time
import json
import queue
import threading
import urllib
from queue import Queue
from typing import Dict, List
from core.standard_frame import Measurement

from websockets.sync.client import connect

from flask import Flask
import flask

from core.standard_frame import StandardFrame

from dotenv import dotenv_values

# <----- Constants ----->

CAR_NAME = "Daybreak"

DBC_FILE = Path("./dbc/daybreak.dbc")
ENV_FILE = Path(".env")

ENV_CONFIG = dotenv_values(ENV_FILE)

API_PREFIX = "/api/v1"

# <----- InfluxDB constants ----->

INFLUX_URL = ENV_CONFIG["INFLUX_URL"]
INFLUX_TOKEN = ENV_CONFIG["INFLUX_TOKEN"]

INFLUX_BUCKET = ENV_CONFIG["INFLUX_BUCKET"]
INFLUX_ORG = ENV_CONFIG["INFLUX_ORG"]

# <----- Grafana constants ----->

GRAFANA_URL = ENV_CONFIG["GRAFANA_URL"]
GRAFANA_TOKEN = ENV_CONFIG["GRAFANA_TOKEN"]

# url without the 'http://'
GRAFANA_URL_NAME = Path(GRAFANA_URL).name

# <----- InfluxDB object set-up ----->

client = influxdb_client.InfluxDBClient(
    url=INFLUX_URL, org=INFLUX_ORG, token=INFLUX_TOKEN)
write_api = client.write_api(write_options=ASYNCHRONOUS)

# <----- Read in DBC file ----->

DAYBREAK_DBC = cantools.database.load_file(DBC_FILE)

# <----- Pretty printing ----->

pp = pprint.PrettyPrinter(indent=1)

# <----- Flask ----->

app = Flask(__name__)

# create queue to hold points to write
write_queue: 'queue.Queue' = queue.Queue()


@app.route("/")
def welcome():
    return "Welcome to UBC Solar's Telemetry Parser!\n"


@app.get(f"{API_PREFIX}/health")
def check_health():
    """
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
    response_dict: Dict[str, str] = dict()
    response_dict["services"] = list()

    # try making a request to InfluxDB container
    try:
        influx_response = requests.get(INFLUX_URL + "ping")
    except requests.exceptions.ConnectionError:
        influx_status = "DOWN"
    else:
        if (influx_response.status_code == 204):
            influx_status = "UP"
        else:
            influx_status = "UNEXPECTED_STATUS_CODE"

    # try making a request to Grafana container
    try:
        grafana_response = requests.get(GRAFANA_URL + "api/health")
    except requests.exceptions.ConnectionError:
        grafana_status = "DOWN"
    else:
        if (grafana_response.status_code == 200):
            grafana_status = "UP"
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
def parse_request():
    """
    Parses incoming request and sends back the parsed result.
    """
    parse_request = json.loads(flask.request.json)
    id: str = parse_request["id"]
    data: str = parse_request["data"]
    timestamp: str = parse_request["timestamp"]
    data_length: str = parse_request["data_length"]

    app.logger.info(f"Received message: {id=}, {data=}")

    # TODO: add validation for received JSON object
    # TODO: add logging messages

    can_msg = StandardFrame(id, data, timestamp, data_length)

    # extract measurements from CAN message
    try:
        extracted_measurements: List[Measurement] = can_msg.extract_measurements(DAYBREAK_DBC)
        app.logger.info(f"Successfully parsed CAN message with id={can_msg.hex_identifier}({can_msg.identifier})")
        return {
            "result": "PARSE_OK",
            "measurements": extracted_measurements,
            "id": can_msg.identifier
        }
    except Exception:
        app.logger.warn(
            f"Unable to extract measurements for CAN message with id={id}")
        return {
            "result": "PARSE_FAIL",
            "measurements": [],
            "id": can_msg.identifier
        }


@app.post(f"{API_PREFIX}/parse/write")
def parse_and_write_request():
    """
    Parses incoming request, sends back the parsed measurements, and writes the
    extracted measurements to a queue for further processing.
    """
    parse_request = json.loads(flask.request.json)
    id: str = parse_request["id"]
    data: str = parse_request["data"]
    timestamp: str = parse_request["timestamp"]
    data_length: str = parse_request["data_length"]

    app.logger.info(f"Received message: {id=}, {data=}")

    # TODO: add validation for received JSON object
    # TODO: add logging messages

    can_msg = StandardFrame(id, data, timestamp, data_length)

    # TODO: put common code between this function and the no-write function into
    # separate function

    # extract measurements from CAN message
    try:
        extracted_measurements: List[Measurement] = can_msg.extract_measurements(DAYBREAK_DBC)
        # if parsing is successful, place extracted measurements in queue
        write_queue.put(extracted_measurements)
        app.logger.info(f"Successfully parsed CAN message with id={can_msg.identifier}")
        app.logger.info("Placed extracted measurements into queue")
        return {
            "result": "PARSE_OK",
            "measurements": extracted_measurements,
            "id": can_msg.identifier
        }
    except Exception:
        app.logger.warn(
            f"unable to extract measurements for CAN message with id={id}")
        return {
            "result": "PARSE_FAIL",
            "measurements": [],
            "id": can_msg.identifier
        }


def write_measurements():
    """
    Worker thread responsible for writing parsed measurements to InfluxDB and Grafana.

    NOTE: the InfluxDB and Grafana write must be in a thread separate from the function that receives the parse request
    since the write does not work otherwise. I assume it has something to do with the fact that the request thread
    dies as soon a response is returned and the InfluxDB write API is async so the write never actually gets to
    complete before the request thread dies. Therefore, a daemon thread whose lifetime is not bound by each request
    is required to write data to Influx and Grafana.
    """
    while True:
        extracted_measurements: List[Measurement] = write_queue.get()

        for measurement in extracted_measurements:
            name = measurement.name
            source = measurement.source
            m_class = measurement.m_class
            value = measurement.value

            # compute Grafana websocket URL to livestream measurement
            endpoint_name = "_".join([CAR_NAME, source, m_class, name])
            websocket_url = f"ws://{GRAFANA_URL_NAME}/api/live/push/{endpoint_name}"

            # live-stream measurements to Grafana Live
            with connect(websocket_url,
                         additional_headers={
                             'Authorization': f'Bearer {GRAFANA_TOKEN}'}
                         ) as websocket:
                current_time = time.time_ns()
                message = f"test value={value} {current_time}"
                websocket.send(message)

            point = influxdb_client.Point(source).tag("car", CAR_NAME).tag(
                "class", m_class).field(name, value)

            # write to InfluxDB
            write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
            app.logger.info(
                f"Wrote measurement to url={INFLUX_URL}, org={INFLUX_ORG}, bucket={INFLUX_BUCKET}!")

        # mark task as completed
        write_queue.task_done()


# create thread to write to InfluxDB and stream to Grafana
threading.Thread(target=write_measurements, daemon=True).start()


if __name__ == "__main__":
    # start the Flask app
    app.run(host="0.0.0.0", debug=False)
