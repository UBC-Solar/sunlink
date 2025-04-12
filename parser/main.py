import re
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
from parser.parameters import CAR_DBC

from dotenv import dotenv_values

__PROGRAM__ = "parser"
__VERSION__ = "0.4"

# <----- Flask ----->

app = Flask(__name__)

# <----- Constants ----->

CAR_NAME = "Brightside"

# paths are relative to project root
ENV_FILE = Path(".env")
TXT_FILE = Path("./dbc/output.txt")

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

"""
Filters what to live stream based on args in link_telemetry

NOTE: if CAN is a filter and a message ID is also a filter, 
      the entire message class (CAN) is allowed to stream
"""
def filter_stream(message, filter_list):  
    if "ALL" in filter_list:
        return True
    elif "NONE" in filter_list:
        return False
      
    for filter in filter_list:
        if len(filter) > 2 and filter[:2] == "0x":
            class_name = message.data["Class"][0]

            # try if it is CAN message
            can_message = None
            try:
                can_message = CAR_DBC.get_message_by_name(class_name)
            except:
                continue

            id = can_message.frame_id

            if hex(id) == filter:
                return True
            continue
        if filter.isdigit():
            class_name = message.data["Class"][0]

            # try if it is CAN message
            can_message = None
            try:
                can_message = CAR_DBC.get_message_by_name(class_name)
            except:
                continue

            id = can_message.frame_id

            if int(filter) == id:
                return True
            else:
                continue
        if filter.isalpha():
            if filter.upper() == message.type:
                return True
            continue

    return False


@app.post(f"{API_PREFIX}/parse")
@auth.login_required
def parse_request():
    """
    Parses incoming request and sends back the parsed result.
    """
    parse_request = flask.request.json

    msgs = []
    msg = parse_request['message']
    if len(msg) == 45:
        msgs.append(msg[:22])                  # Might need to change splitting logic
        msgs.append(msg[23:])                  # Might need to change splitting logic
    else:
        msgs = [msg]

    all_response = []
    for msg in msgs:
        curr_response = {}

        # try extracting measurements
        try:
            message = create_message(msg)
        except Exception as e:
            app.logger.warn(
                f"Unable to extract measurements for raw message {msg}")
            curr_response = {
                "result": "PARSE_FAIL",
                "message": str(msg),
                "error": str(e),
            }
            all_response.append(curr_response)
            continue
        
        type = message.type

        app.logger.info(f"Successfully parsed {type} message placed into queue")

        # try putting the extracted measurements in the queue for Grafana streaming
        try:
            stream_queue.put(message.data, block=False)
        except queue.Full:
            app.logger.warn(
                "Stream queue full. Unable to add measurements to stream queue!"
            )

        # Check if this message should be logged into a file based on args
        log_filters = parse_request.get("log_filters", False)
        doLogMessage = filter_stream(message, log_filters)    

        curr_response =  {
            "result": "OK",
            "message": message.data["display_data"],
            "logMessage": doLogMessage,
            "type": type
        }
        all_response.append(curr_response)

    return {
        "all_responses": all_response,
    }
    

@app.post(f"{API_PREFIX}/parse/write/debug")
@auth.login_required
def parse_and_write_request():
    return parse_and_write_request_bucket("_test")

@app.post(f"{API_PREFIX}/parse/write/production")
@auth.login_required
def parse_and_write_request_to_prod():
    return parse_and_write_request_bucket("_prod")



def static_vars(**kwargs):
    def decorate(func):
        for k in kwargs:
            setattr(func, k, kwargs[k])
        return func
    return decorate

BATCH_SIZE          = 24

"""
Parses incoming request, writes the parsed measurements to InfluxDB bucket (debug or production)
that is specifc to the message type (CAN, GPS, IMU, for example).
Also sends back parsed measurements back to client.
"""
@static_vars(points=[])
def parse_and_write_request_bucket(bucket):
    parse_request = flask.request.json

    msgs = []
    msg = parse_request['message']
    if len(msg) == 45:
        msgs.append(msg[:22])                  # Might need to change splitting logic
        msgs.append(msg[23:])                  # Might need to change splitting logic
    else:
        msgs = [msg]

    all_response = []
    for msg in msgs:
        curr_response = {}
        # try extracting measurements
        try:
            message = create_message(msg)
        except Exception as e:
            app.logger.warn(
                f"Unable to extract measurements for raw message {msg}")
            curr_response =  {
                "result": "PARSE_FAIL",
                "message": str(msg),
                "error": str(e),
            }
            all_response.append(curr_response)
            continue

        type = message.type
        live_filters = parse_request.get("live_filters", False)
        log_filters = parse_request.get("log_filters", False)

        # try putting the extracted measurements in the queue for Grafana streaming
        if (filter_stream(message, live_filters)):
            try:
                stream_queue.put(message.data, block=False)
            except queue.Full:
                app.logger.warn(
                    "Stream queue full. Unable to add measurements to stream queue!"
                )
        
        # Check if this message should be logged into a file based on args
        doLogMessage = filter_stream(message, log_filters)

        # try writing the measurements extracted
        for i in range(len(message.data[list(message.data.keys())[0]])):
            # REQUIRED FIELDS
            name = message.data["Measurement"][i]
            source = message.data["Source"][i]
            m_class = message.data["Class"][i]
            value = message.data["Value"][i]
            
            timestamp = message.data.get("Timestamp", ["NA"])[i]

            point = influxdb_client.Point(source).tag("car", CAR_NAME).tag(
                "class", m_class).field(name, value)
            
            if timestamp != "NA":
                point.time(int(timestamp * 1e9))
            
            parse_and_write_request_bucket.points.append(point)

            # write to InfluxDB
            if len(parse_and_write_request_bucket.points) >= BATCH_SIZE:    # CREDIT: Mridul Singh for Batch Writing Optimization!
                try:
                    write_api.write(bucket=message.type + bucket, org=INFLUX_ORG, record=parse_and_write_request_bucket.points)
                    write_api.close()
                    parse_and_write_request_bucket.points = []
                except Exception as e:
                    app.logger.warning("Unable to write measurement to InfluxDB!")
                    curr_response =  {
                        "result": "INFLUX_WRITE_FAIL",
                        "message": str(msg),
                        "error": str(e),
                        "type": type 
                    }
                    all_response.append(curr_response)
                    continue
                

        curr_response = {
            "result": "OK",
            "message": message.data["display_data"],
            "logMessage": doLogMessage,
            "type": type
        }
        all_response.append(curr_response)

    return {
        "all_responses": all_response
    }

def write_measurements():
    """
    Worker thread responsible for live-streaming measurements to Grafana.

    NOTE: live-streaming measurements to Grafana is done in a separate thread since it is an optional feature and
    it doesn't matter if it succeeds or not. Furthermore, having this in a separate thread reduces latency.
    """

    while True:
        data_dict = stream_queue.get()

        # try writing the measurements extracted
        for i in range(len(data_dict[list(data_dict.keys())[0]])):
            name = data_dict["Measurement"][i]
            source = data_dict["Source"][i]
            m_class = data_dict["Class"][i]
            value = data_dict["Value"][i]

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
