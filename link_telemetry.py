#!/usr/bin/env python
import serial
import json
import cantools
from pathlib import Path
import random
import time
import argparse
from prettytable import PrettyTable

from core.standard_frame import StandardFrame

from dotenv import dotenv_values

import requests

__PROGRAM__ = "link_telemetry"
__VERSION__ = "0.4.0"

# <----- Constants ----->

CAR_NAME = "Daybreak"

DBC_FILE = Path("./dbc/daybreak.dbc")
ENV_FILE = Path(".env")

ENV_CONFIG = dotenv_values(ENV_FILE)

PARSER_URL = ENV_CONFIG["PARSER_URL"]
INFLUX_URL = ENV_CONFIG["INFLUX_URL"]
GRAFANA_URL = ENV_CONFIG["GRAFANA_URL"]

# ANSI sequences
ANSI_ESCAPE = "\033[0m"

# API endpoints
WRITE_ENDPOINT = f"{PARSER_URL}/api/v1/parse/write"
NO_WRITE_ENDPOINT = f"{PARSER_URL}/api/v1/parse"
PING_ENDPOINT = f"{PARSER_URL}/api/v1/ping"
HEALTH_ENDPOINT = f"{PARSER_URL}/api/v1/health"


# <----- Randomizer CAN functions ------>

def random_can_str(dbc) -> str:
    # collect CAN IDs
    can_ids = list()
    for message in dbc.messages:
        can_ids.append(message.frame_id)

    # 0 to 2^32
    random_timestamp = random.randint(0, pow(2, 32))
    random_timestamp_str = "{0:0{1}x}".format(random_timestamp, 8)

    # random identifier
    random_identifier = random.choice(can_ids)
    random_id_str = "{0:0{1}x}".format(random_identifier, 4)

    # random data
    random_data = random.randint(0, pow(2, 64))
    random_data_str = "{0:0{1}x}".format(random_data, 16)

    # fixed data length
    data_length = "8"

    # collect into single string
    can_str = random_timestamp_str + random_id_str + random_data_str \
        + data_length + "\n"

    return can_str


def main():
    # <----- Argument parsing ----->

    parser = argparse.ArgumentParser(
        description="Link raw radio stream to frontend telemetry interface.",
        prog=__PROGRAM__)

    normal_group = parser.add_argument_group("Normal operation")
    debug_group = parser.add_argument_group("Debug operation")

    parser.add_argument("--version", action="version",
                        version=f"{__PROGRAM__} {__VERSION__}")

    debug_group.add_argument("-d", "--debug", action="store_true", help=("Enables debug mode. This allows using the "
                                                                         "telemetry link with randomly generated CAN "
                                                                         "data rather using an actual radio telemetry stream"))
    debug_group.add_argument("--no-write", action="store_true", help=(
        "Disables writing to InfluxDB bucket and Grafana live stream endpoints"))

    normal_group.add_argument("-p", "--port", action="store",
                              help=("Specifies the serial port to read radio data from. "
                                    "Typical values include: COM5, /dev/ttyUSB0, etc."))
    normal_group.add_argument("-b", "--baudrate", action="store",
                              help=("Specifies the baudrate for the serial port specified. "
                                    "Typical values include: 9600, 115200, 230400, etc."))
    debug_group.add_argument("--check-health", action="store_true",
                             help=("Allows checking whether the parser is reachable as well as if "
                                   "the parser is able to reach the InfluxDB and Grafana processes."))

    args = parser.parse_args()

    # <----- Argument validation ----->

    if args.check_health:
        # make ping request to parser
        try:
            ping_req = requests.get(PING_ENDPOINT)
            health_req = requests.get(HEALTH_ENDPOINT)
            health_status = health_req.json()
        except Exception:
            print(f"Parser @ {PARSER_URL} -\033[1;31m DOWN {ANSI_ESCAPE}")
        else:
            if ping_req.status_code == 200:
                print(f"Parser @ {PARSER_URL} -\033[1;32m UP {ANSI_ESCAPE}")
            else:
                print(f"Parser @ {PARSER_URL} -\033[1;32m DOWN {ANSI_ESCAPE}")

            if health_status["influxdb"] == "UP":
                print(f"InfluxDB @ {INFLUX_URL} -\033[1;32m UP {ANSI_ESCAPE}")
            else:
                print(f"InfluxDB @ {INFLUX_URL} -\033[1;31m DOWN {ANSI_ESCAPE}")

            if health_status["grafana"] == "UP":
                print(f"Grafana @ {GRAFANA_URL} -\033[1;32m UP {ANSI_ESCAPE}")
            else:
                print(f"Grafana @ {GRAFANA_URL} -\033[1;31m DOWN {ANSI_ESCAPE}")

        return 0

    if args.debug:
        if args.port or args.baudrate:
            parser.error("-d cannot be used with -p and -b options")
    else:
        if not (args.port and args.baudrate):
            parser.error("-p and -b options must both be specified")

    pp = pprint.PrettyPrinter(indent=1)

    # <----- Read in DBC file ----->

    daybreak_dbc = cantools.database.load_file(DBC_FILE)

    while True:
        if args.debug:
            message_str = random_can_str(daybreak_dbc)
            message: bytes = message_str.encode(encoding="UTF-8")
            time.sleep(0.5)
        else:
            with serial.Serial() as ser:
                # <----- Configure COM port ----->
                ser.baudrate = args.baudrate
                ser.port = args.port
                ser.open()

                # read in bytes from COM port
                message: bytes = ser.readline()

                if len(message) != StandardFrame.EXPECTED_CAN_MSG_LENGTH:
                    print(
                        f"WARNING: got message length {len(message)}, expected {StandardFrame.EXPECTED_CAN_MSG_LENGTH}. Dropping message...")
                    print(message)
                    continue

                # TODO: check that all characters in message are valid ascii and are within [a-Z0-9] + "\n" + "\r"

        # partition string into pieces
        timestamp: str = message[0:8].decode()    # 8 bytes
        id: str = message[8:12].decode()
        data: str = message[12:28].decode()
        data_len: str = message[28:29].decode()

        payload = {
                "timestamp": timestamp,
                "id": id,
                "data": data,
                "data_length": data_len,
                "stream": False,
        }

        r = requests.post(PARSER_URL + "parse", json=json.dumps(payload))

        print(r.text)
        print(r.status_code)


if __name__ == "__main__":
    main()
