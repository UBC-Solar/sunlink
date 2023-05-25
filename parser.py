import cantools
import influxdb_client
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import ASYNCHRONOUS
from pathlib import Path
import pprint
import time
import json
import queue
import urllib

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

# client = influxdb_client.InfluxDBClient(
#     url=INFLUX_URL, org=INFLUX_ORG, token=INFLUX_TOKEN)
# write_api = client.write_api(write_options=SYNCHRONOUS)

# <----- Read in DBC file ----->

daybreak_dbc = cantools.database.load_file(DBC_FILE)

# <----- Pretty printing ----->

pp = pprint.PrettyPrinter(indent=1)

# <----- Flask ----->

app = Flask(__name__)


@app.route("/")
def welcome():
    return "Welcome to UBC Solar's Telemetry Parser!\n"


@app.post("/parse")
def parse_request():
    parse_request = json.loads(flask.request.json)
    id: str = parse_request["id"]
    data: str = parse_request["data"]
    timestamp: str = parse_request["timestamp"]
    data_length: str = parse_request["data_length"]
    stream: bool = parse_request["stream"]

    app.logger.info(f"received msg: {id=}, {data=}")

    # TODO: add validation for received JSON object
    # TODO: add logging messages

    can_msg = StandardFrame(id, data, timestamp, data_length)

    # extract measurements from CAN message
    try:
        extracted_measurements = can_msg.extract_measurements(daybreak_dbc)
        app.logger.info(can_msg)
        app.logger.info(extracted_measurements)
    except ValueError as exc:
        print(exc)
        app.logger.warn(
            f"unable to extract measurements for CAN message with id={id}")
        return flask.make_response(f"unable to extract measurements for CAN message with id={id}", 400)

    for measurement, data in extracted_measurements.items():
        source = data["source"]
        m_class = data["class"]
        value = data["value"]

        # compute Grafana websocket URL to livestream measurement
        endpoint_name = "_".join([CAR_NAME, source, m_class, measurement])
        websocket_url = f"ws://{GRAFANA_URL_NAME}/api/live/push/{endpoint_name}"

        # live-stream measurements to Grafana Live
        # with connect(websocket_url,
        #              additional_headers={
        #                  'Authorization': f'Bearer {GRAFANA_TOKEN}'}
        #              ) as websocket:
        #     current_time = time.time_ns()
        #     message = f"test value={value} {current_time}"
        #     websocket.send(message)

        # write measurements to InfluxDB
        with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
            write_api = client.write_api(write_options=ASYNCHRONOUS)

            p = influxdb_client.Point(source).tag("car", CAR_NAME).tag(
                "class", m_class).field(measurement, value)
            result = write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=p)
            app.logger.info(f"Write result: {result.__dict__}")

            write_api.flush()
        # app.logger.info(f"Wrote measurement to org={INFLUX_ORG}, bucket={INFLUX_BUCKET}!")

    return extracted_measurements


def main():
    # start the Flask app
    app.run(host="0.0.0.0", debug=True)


if __name__ == "__main__":
    main()
