#!/usr/bin/env python
import serial
import sys
import signal
import cantools
import random
import time
import argparse
import requests

import toml
from toml.decoder import TomlDecodeError

from pathlib import Path
from prettytable import PrettyTable
from typing import Dict, Optional

import concurrent.futures

__PROGRAM__ = "link_telemetry"
__VERSION__ = "0.4.0"

# <----- Constants ----->

DBC_FILE = Path("./dbc/daybreak.dbc")

TOML_CONFIG_FILE = Path("./telemetry.toml")

# file existence check
if not TOML_CONFIG_FILE.is_file():
    print(f"Unable to find expected TOML config file: \"{TOML_CONFIG_FILE.absolute()}\"")
    sys.exit(1)

# <----- Read in TOML file ----->

try:
    config: Dict = toml.load(TOML_CONFIG_FILE)
except TomlDecodeError:
    print(f"Unable to read configuration from {TOML_CONFIG_FILE.absolute()}!")
    sys.exit(1)

try:
    PARSER_URL = config["parser"]["url"]
    SECRET_KEY = config["security"]["secret_key"]
except KeyError:
    print(f"{TOML_CONFIG_FILE} does not contain expected keys!")
    sys.exit(1)

# header to provide with each HTTP request to the parser for API authorization
AUTH_HEADER = {"Authorization": f"Bearer {SECRET_KEY}"}

# API endpoints
DEBUG_WRITE_ENDPOINT = f"{PARSER_URL}/api/v1/parse/write/debug"
PROD_WRITE_ENDPOINT = f"{PARSER_URL}/api/v1/parse/write/production"
NO_WRITE_ENDPOINT = f"{PARSER_URL}/api/v1/parse"
HEALTH_ENDPOINT = f"{PARSER_URL}/api/v1/health"

EXPECTED_CAN_MSG_LENGTH = 30

# ANSI sequences
ANSI_ESCAPE = "\033[0m"
ANSI_RED = "\033[1;31m"
ANSI_GREEN = "\033[1;32m"
ANSI_YELLOW = "\033[1;33m"
ANSI_BOLD = "\033[1m"

DEFAULT_MAX_WORKERS = 32

executor: Optional[concurrent.futures.ThreadPoolExecutor] = None

# <----- Randomizer CAN functions ------>


def random_can_str(dbc) -> str:
    """
    Generates a random string (which represents a CAN message) that mimics
    the format sent over by the telemetry board over radio. This function
    is useful for debugging the telemetry system.
    """
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
        health_req = requests.get(HEALTH_ENDPOINT, headers=AUTH_HEADER)
    except Exception:
        print(f"* parser @ {PARSER_URL} -{ANSI_RED} DOWN {ANSI_ESCAPE}")
        print("failed to connect to parser!")
        sys.exit(1)

    if health_req.status_code == 200:
        print(f"* parser @ {PARSER_URL} -{ANSI_GREEN} UP {ANSI_ESCAPE}")
    elif health_req.status_code == 401:
        print(f"* parser @ {PARSER_URL} -{ANSI_RED} DOWN {ANSI_ESCAPE}")
        print(f"unauthorized access to parser API, secret key specified in \"{TOML_CONFIG_FILE}\" is invalid")
        sys.exit(1)
    else:
        print(f"* parser @ {PARSER_URL} -{ANSI_RED} DOWN {ANSI_ESCAPE}")
        print(f"request failed with HTTP status code {ANSI_BOLD}{health_req.status_code}{ANSI_ESCAPE}!")
        sys.exit(1)

    health_status = health_req.json()

    for service in health_status["services"]:
        name = service["name"]
        url = service["url"]
        status = service["status"]

        if status == "UP":
            print(f"|---> {name} @ {url} -{ANSI_GREEN} UP {ANSI_ESCAPE}")
        elif status == "UNAUTHORIZED":
            print(f"|---> {name} @ {url} -{ANSI_YELLOW} UNAUTHORIZED {ANSI_ESCAPE}")
        else:
            print(f"|---> {name} @ {url} -{ANSI_RED} DOWN {ANSI_ESCAPE}")


def validate_args(parser: 'argparse.ArgumentParser', args: 'argparse.Namespace'):
    """
    Ensures that certain argument invariants have been adhered to.
    """

    if args.randomize:
        if args.port or args.baudrate:
            parser.error("-r cannot be used with -p and -b options")

        if args.prod:
            parser.error("-r cannot be used with --prod since randomly generated data should not be written to the production database")
    else:
        if not args.port and not args.baudrate:
            parser.error("Must specify either -r or both -p and -b arguments")
        elif not (args.port and args.baudrate):
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
    Prints a table containing the current script configuration.
    """
    print(f"Running {ANSI_BOLD}{__PROGRAM__} (v{__VERSION__}){ANSI_ESCAPE} with the following configuration...\n")
    config_table = PrettyTable()
    config_table.field_names = ["PARAM", "VALUE"]
    config_table.add_row(["DATA SOURCE", "RANDOMLY GENERATED" if args.randomize else f"UART PORT ({args.port})"])
    config_table.add_row(["PARSER URL", PARSER_URL])
    config_table.add_row(["MAX THREADS", args.jobs])

    if args.no_write:
        config_table.add_row(["WRITE TARGET", "WRITE DISABLED"])
    else:
        config_table.add_row(["WRITE TARGET", "DEBUG BUCKET" if args.debug else "PRODUCTION BUCKET"])

    # POSSIBLE CONFIGURATIONS

    # case 1: --randomize with --debug: generate random data and write to the `Test` bucket (INTENDED USAGE)
    # case 2: --randomize without --debug: generate random data and write to the `Telemetry` bucket (SHOULD BE IMPOSSIBLE)
    # case 3: -p and -b with --debug: parse radio data and write to the `Test` bucket (LIKELY)
    # case 4: -p and -b without --debug: parse radio data and write to the `Telemetry` bucket (ACTUAL OPERATION MODE)

    if not args.randomize:
        config_table.add_row(["PORT", args.port])
        config_table.add_row(["BAUDRATE", args.baudrate])

    print(config_table)
    print()


# <----- Signal handling ----->

def sigint_handler(sig, frame):
    print("Ctrl+C recv'd, exiting gracefully...")
    # shutdown the executor
    if executor is not None:
        executor.shutdown(wait=False, cancel_futures=True)

    sys.exit(0)

# <----- Co-routine definitions ----->


def parser_request(payload: Dict, url: str):
    """
    Makes a parse request to the given `url`.
    """
    try:
        r = requests.post(url=url, json=payload, timeout=5.0, headers=AUTH_HEADER)
    except requests.ConnectionError:
        print(f"Unable to make POST request to {url=}!\n")
    else:
        return r


def process_response(future: concurrent.futures.Future):
    """
    Function that defines the post-processing after receiving a response from the hosted parser.
    Formats the parsed measurements into a table for convenience.

    Is registered as a callback so that once a future is done executing and has
    a result this function is called.
    """

    # get the response from the future
    response = future.result()

    if response is None:
        return

    if response.status_code == 401:
        print(f"{ANSI_BOLD}Response HTTP status code:{ANSI_ESCAPE} {ANSI_YELLOW}{response.status_code} (unauthorized access){ANSI_ESCAPE}")
        print(f"Check that your configured secret key matches the parser's ({PARSER_URL}) secret key!")
        print(f"{ANSI_BOLD}Config file location:{ANSI_ESCAPE} \"{TOML_CONFIG_FILE.absolute()}\"\n")
        return

    if response.status_code != 200:
        print(f"{ANSI_BOLD}Response HTTP status code:{ANSI_ESCAPE} {ANSI_YELLOW}{response.status_code}{ANSI_ESCAPE}")

    print(f"{ANSI_BOLD}Response HTTP status code:{ANSI_ESCAPE} {ANSI_GREEN}{response.status_code}{ANSI_ESCAPE}")

    parse_response: dict = response.json()

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
        print(f"Failed to parse message with id={parse_response['id']}!")
    elif parse_response["result"] == "INFLUX_WRITE_FAIL":
        print(f"Failed to write measurements for CAN message with id={parse_response['id']} to InfluxDB!")
    else:
        print(f"Unexpected response: {parse_response['result']}")

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
    parser.add_argument("-j", "--jobs", action="store", default=DEFAULT_MAX_WORKERS,
                        help=("The max number of threads to use for making HTTP requests to the parser."))

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

    # <----- Create the thread pool ----->

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=DEFAULT_MAX_WORKERS)

    print(f"{ANSI_GREEN}Telemetry link is up!{ANSI_ESCAPE}")
    print("Waiting for incoming messages...")

    while True:
        message: bytes

        if args.randomize:
            message_str = random_can_str(daybreak_dbc)
            message = message_str.encode(encoding="UTF-8")
            # TODO: make this value configurable via the command line
            time.sleep(0.1)
        else:
            with serial.Serial() as ser:
                # <----- Configure COM port ----->
                ser.baudrate = args.baudrate
                ser.port = args.port
                ser.open()

                # read in bytes from COM port
                message = ser.readline()

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

        # submit to thread pool
        future = executor.submit(parser_request, payload, PARSER_ENDPOINT)

        # register done callback with future
        future.add_done_callback(process_response)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, sigint_handler)
    main()
