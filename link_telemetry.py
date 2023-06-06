#!/usr/bin/env python
import serial
import json
import cantools
from pathlib import Path
import random
import time
import argparse
from prettytable import PrettyTable
import requests

__PROGRAM__ = "link_telemetry"
__VERSION__ = "0.4.0"

# <----- Constants ----->

CAR_NAME = "Daybreak"

DBC_FILE = Path("./dbc/daybreak.dbc")

# TODO: use a telemetry.toml file instead
PARSER_URL = "http://localhost:5000/"

EXPECTED_CAN_MSG_LENGTH = 30

# ANSI sequences
ANSI_ESCAPE = "\033[0m"
ANSI_RED = "\033[1;31m"
ANSI_GREEN = "\033[1;32m"

# API endpoints
DEBUG_WRITE_ENDPOINT = f"{PARSER_URL}/api/v1/parse/write/debug"
PROD_WRITE_ENDPOINT = f"{PARSER_URL}/api/v1/parse/write/production"
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


# <----- Utility functions ------>

def check_health_handler():
    """
    Makes requests to the hosted parser to determine whether it is accessible
    and if Influx and Grafana are accessible from the parser. Prints out
    its results.
    """

    # make ping request to parser
    try:
        health_req = requests.get(HEALTH_ENDPOINT)
        health_status = health_req.json()
    except Exception:
        print(f"parser @ {PARSER_URL} -{ANSI_RED} DOWN {ANSI_ESCAPE}")
    else:
        if health_req.status_code == 200:
            print(f"parser @ {PARSER_URL} -{ANSI_GREEN} UP {ANSI_ESCAPE}")
        else:
            print(f"parser @ {PARSER_URL} -{ANSI_RED} DOWN {ANSI_ESCAPE}")

        for service in health_status["services"]:
            name = service["name"]
            url = service["url"]
            status = service["status"]

            if status == "UP":
                print(f"{name} @ {url} -{ANSI_GREEN} UP {ANSI_ESCAPE}")
            else:
                print(f"{name} @ {url} -{ANSI_RED} DOWN {ANSI_ESCAPE}")


def validate_args(parser: 'argparse.ArgumentParser', args: 'argparse.Namespace'):
    """
    Ensures that certain argument patterns have been adhered to.
    """

    if args.randomize:
        if args.port or args.baudrate:
            parser.error("-r cannot be used with -p and -b options")

        if args.prod:
            parser.error("-r cannot be used with --prod since randomly generated data should not be written to the production database")
    else:
        if not (args.port and args.baudrate):
            parser.error("-p and -b options must both be specified")

    if args.no_write:
        if args.debug or args.prod:
            parser.error("Conflicting configuration. Cannot specify --no-write with --debug or --prod.")
    else:
        if args.debug and args.prod:
            parser.error("Conflicting configuration. Cannot specify both --debug and --prod. Must choose one.")

        if args.debug is False and args.prod is False:
            parser.error("Must specify one of --debug, --prod, or --no-write.")


def print_config_table(args: 'argparse.Namespace'):
    """
    Prints a table containing the current configuration.
    """
    print(f"Running {__PROGRAM__} (v{__VERSION__}) with the following configuration...\n")
    config_table = PrettyTable()
    config_table.field_names = ["PARAM", "VALUE"]
    config_table.add_row(["STREAM SOURCE", "RANDOM" if args.randomize else "UART PORT"])
    config_table.add_row(["PARSER URL", PARSER_URL])

    if args.no_write:
        config_table.add_row(["WRITE TARGET", "WRITE DISABLED"])
    else:
        config_table.add_row(["WRITE TARGET", "DEBUG" if args.debug else "PRODUCTION"])

    # case 1: --randomize with --debug: generate random data and write to the `Test` bucket (LIKELY)
    # case 2: --randomize without --debug: generate random data and write to the `Telemetry` bucket (SHOULD BE IMPOSSIBLE)
    # case 3: -p and -b with --debug: parse radio data and write to the `Test` bucket (LIKELY)
    # case 4: -p and -b without --debug: parse radio data and write to the `Telemetry` bucket (ACTUAL OPERATION MODE)

    # TODO: add warnings for specific configs (like -r without --debug)

    if not args.randomize:
        config_table.add_row(["PORT", args.port])
        config_table.add_row(["BAUDRATE", args.baudrate])

    print(config_table)
    print()


def main():
    # <----- Argument parsing ----->

    parser = argparse.ArgumentParser(
        description="Link raw radio stream to telemetry backend parser.",
        prog=__PROGRAM__)

    # declare argument groups
    source_group = parser.add_argument_group("Data stream selection")
    write_group = parser.add_argument_group("Data write options")

    parser.add_argument("--version", action="version",
                        version=f"{__PROGRAM__} {__VERSION__}", help=("Show program's version number and exit"))

    parser.add_argument("--health", action="store_true",
                        help=("Checks whether the parser is reachable as well as if "
                              "the parser is able to reach the InfluxDB and Grafana processes."))

    write_group.add_argument("--debug", action="store_true",
                             help=("Writes incoming data to a test InfluxDB bucket."))
    write_group.add_argument("--prod", action="store_true",
                             help=("Writes incoming data to the production InfluxDB bucket."))
    write_group.add_argument("--no-write", action="store_true",
                             help=("Disables writing to InfluxDB bucket and Grafana live "
                                   "stream endpoints. Cannot be used with --debug and --prod options."))

    source_group.add_argument("-p", "--port", action="store",
                              help=("Specifies the serial port to read radio data from. "
                                    "Typical values include: COM5, /dev/ttyUSB0, etc."))
    source_group.add_argument("-b", "--baudrate", action="store",
                              help=("Specifies the baudrate for the serial port specified. "
                                    "Typical values include: 9600, 115200, 230400, etc."))

    source_group.add_argument("-r", "--randomize", action="store_true",
                              help=("Allows using the telemetry link with "
                                    "randomly generated CAN data rather than "
                                    "a real radio telemetry stream."))

    args = parser.parse_args()

    # <----- Argument validation and handling ----->

    if args.health:
        check_health_handler()
        return 0

    validate_args(parser, args)

    # build the correct URL to make POST request to
    if args.no_write:
        PARSER_ENDPOINT = NO_WRITE_ENDPOINT
    elif args.debug:
        PARSER_ENDPOINT = DEBUG_WRITE_ENDPOINT
    else:
        PARSER_ENDPOINT = PROD_WRITE_ENDPOINT

    # <----- Read in DBC file ----->

    daybreak_dbc = cantools.database.load_file(DBC_FILE)

    # <----- Configuration confirmation ----->

    print_config_table(args)
    choice = input("Are you sure you want to continue with this configuration? (y/N) > ")
    if choice.lower() != "y":
        return

    while True:
        if args.randomize:
            message_str = random_can_str(daybreak_dbc)
            message: bytes = message_str.encode(encoding="UTF-8")
            # TODO: make this value configurable via the command line
            time.sleep(0.1)
        else:
            with serial.Serial() as ser:
                # <----- Configure COM port ----->
                ser.baudrate = args.baudrate
                ser.port = args.port
                ser.open()

                # read in bytes from COM port
                message: bytes = ser.readline()

                if len(message) != EXPECTED_CAN_MSG_LENGTH:
                    print(
                        f"WARNING: got message length {len(message)}, expected {EXPECTED_CAN_MSG_LENGTH}. Dropping message...")
                    print(message)
                    continue

                # TODO: check that all characters in message are valid ascii and are within [a-Z0-9] + "\n" + "\r"

        # partition string into pieces
        timestamp: str = message[0:8].decode()      # 8 bytes
        id: str = message[8:12].decode()            # 4 bytes
        data: str = message[12:28].decode()         # 16 bytes
        data_len: str = message[28:29].decode()     # 1 byte

        payload = {
            "timestamp": timestamp,
            "id": id,
            "data": data,
            "data_length": data_len,
        }

        print(f"request: {payload}")

        # try making parse request to cloud parser
        try:
            r = requests.post(PARSER_ENDPOINT, json=json.dumps(payload))
        except Exception:
            # if cloud parser is down, try accessing local parser and write requests to text file
            print(f"Unable to reach the parser @ {PARSER_URL}!\n")
            # TODO: write request to a text file with a timestamp
            continue

        parse_response: dict = r.json()

        if parse_response["result"] == "OK":
            table = PrettyTable()
            table.field_names = ["ID", "Source", "Class", "Measurement", "Value"]
            measurements: list = parse_response["measurements"]

            # format response as a table
            for measurement in measurements:
                id = parse_response['id']
                table.add_row([hex(id), measurement["source"], measurement["m_class"], measurement["name"], measurement["value"]])

            print(table)
        elif parse_response["result"] == "PARSE_FAIL":
            print(f"Failed to parse message with id={id}!")
        elif parse_response["result"] == "INFLUX_WRITE_FAIL":
            print(f"Failed to write measurements for CAN message with id={id} to InfluxDB!")
        else:
            print(f"Unexpected response: {parse_response['result']}")

        print()


if __name__ == "__main__":
    main()
