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
from typing import Dict

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

daybreak_dbc = cantools.database.load_file(DBC_FILE)

# <----- Pretty printing ----->

pp = pprint.PrettyPrinter(indent=1)

# <----- Flask ----->

app = Flask(__name__)

# create queue to hold points to write
write_queue: 'queue.Queue' = queue.Queue()


@app.route("/")
def welcome():
    return "Welcome to UBC Solar's Telemetry Parser!\n"


@app.get("/ping")
def ping():
    return flask.Response(status=200)


@app.get("/health")
def check_health():
    response_dict: Dict[str, str] = dict()

    # try making a request to InfluxDB container
    try:
        influx_response = requests.get(INFLUX_URL + "ping")
    except requests.exceptions.ConnectionError:
        response_dict["influxdb"] = "DOWN"
    else:
        if (influx_response.status_code == 204):
            response_dict["influxdb"] = "UP"
        else:
            response_dict["influxdb"] = "UNEXPECTED_STATUS_CODE"

    # try making a request to Grafana container
    try:
        grafana_response = requests.get(GRAFANA_URL + "api/health")
    except requests.exceptions.ConnectionError:
        response_dict["grafana"] = "DOWN"
    else:
        if (grafana_response.status_code == 200):
            response_dict["grafana"] = "UP"
        else:
            response_dict["grafana"] = "UNEXPECTED_STATUS_CODE"

    return response_dict


@app.post("/parse")
def parse_request():
    parse_request = json.loads(flask.request.json)
    id: str = parse_request["id"]
    data: str = parse_request["data"]
    timestamp: str = parse_request["timestamp"]
    data_length: str = parse_request["data_length"]

    app.logger.info(f"received msg: {id=}, {data=}")

    # TODO: add validation for received JSON object
    # TODO: add logging messages

    can_msg = StandardFrame(id, data, timestamp, data_length)

    # extract measurements from CAN message
    try:
        extracted_measurements = can_msg.extract_measurements(daybreak_dbc)
        # if parsing is successful, place extracted measurements in queue
        write_queue.put(extracted_measurements)
        return extracted_measurements
    except ValueError as exc:
        print(exc)
        app.logger.warn(
            f"unable to extract measurements for CAN message with id={id}")
        return flask.make_response(f"unable to extract measurements for CAN message with id={id}", 400)


def write_measurement():
    # NOTE: the InfluxDB and Grafana write must be in a thread separate from the function that receives the parse request
    # since the write does not work otherwise. I assume it has something to do with the fact that the request thread
    # dies as soon a response is returned and the InfluxDB write API is async so the write never actually gets to
    # complete before the request thread dies. Therefore, a daemon thread whose lifetime is not bound by each request
    # is required to write data to Influx and Grafana.
    while True:
        extracted_measurements = write_queue.get()

        for measurement, data in extracted_measurements.items():
            source = data["source"]
            m_class = data["class"]
            value = data["value"]

            # compute Grafana websocket URL to livestream measurement
            endpoint_name = "_".join([CAR_NAME, source, m_class, measurement])
            websocket_url = f"ws://{GRAFANA_URL_NAME}/api/live/push/{endpoint_name}"

            # live-stream measurements to Grafana Live
            with connect(websocket_url,
                         additional_headers={
                             'Authorization': f'Bearer {GRAFANA_TOKEN}'}
                         ) as websocket:
                current_time = time.time_ns()
                message = f"test value={value} {current_time}"
                websocket.send(message)

            # place point into queue
            point = influxdb_client.Point(source).tag("car", CAR_NAME).tag(
                "class", m_class).field(measurement, value)

            # write to InfluxDB
            write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
            app.logger.info(
                f"Wrote measurement to url={INFLUX_URL}, org={INFLUX_ORG}, bucket={INFLUX_BUCKET}!")

        # mark task as completed
        write_queue.task_done()


# create thread to write to InfluxDB
threading.Thread(target=write_measurement, daemon=True).start()


if __name__ == "__main__":
    # start the Flask app
    app.run(host="0.0.0.0", debug=True)
