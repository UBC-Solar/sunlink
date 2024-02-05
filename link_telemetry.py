#!/usr/bin/env python
import serial
import sys
import signal
import cantools
import can
import random
import time
import argparse
import requests
import toml
import numpy as np
import json
import os

from datetime import datetime

from toml.decoder import TomlDecodeError
from pathlib import Path
from prettytable import PrettyTable
from typing import Dict
from parser.randomizer import RandomMessage

import concurrent.futures

__PROGRAM__ = "link_telemetry"
__VERSION__ = "0.4"

# <----- Constants ----->

DBC_FILE = Path("./dbc/brightside.dbc")

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
    OFFLINE_CAN_CHANNEL = config["offline"]["channel"]
    OFFLINE_CAN_BITRATE = config["offline"]["bitrate"]
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

# default maximum number of worker threads for thread pool executor
DEFAULT_MAX_WORKERS = 32

# default frequency used to generate random messages
DEFAULT_RANDOM_FREQUENCY_HZ = 10

# global flag that indicates whether a SIGINT signal was received
SIGINT_RECVD = False

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
    config_table.add_row(["DATA SOURCE", f"RANDOMLY GENERATED @ {args.frequency_hz} Hz" if args.randomize else f"UART PORT ({args.port})"])

    config_table.add_row(["PARSER URL", PARSER_URL])
    config_table.add_row(["DBC FILE", DBC_FILE])
    if LOG_FILE: config_table.add_row(["LOG FILE", "{}{}".format(LOG_DIRECTORY, LOG_FILE)]) # Only show row if log file option selected
    config_table.add_row(["MAX THREADS", args.jobs])

    if args.prod:
        config_table.add_row(["WRITE TARGET", "PRODUCTION BUCKET"])
    elif args.debug:
        config_table.add_row(["WRITE TARGET", "DEBUG BUCKET"])
    else:
        config_table.add_row(["WRITE TARGET", "WRITE DISABLED"])

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
    """
    Handles ctrl+C (SIGINT). Contains all telemetry link deinitialization steps.
    """
    print("Ctrl+C recv'd, exiting gracefully...")

    # set SIGINT_RECVD flag to prevent future done callbacks from running
    global SIGINT_RECVD
    SIGINT_RECVD = True

    global start_time
    end_time = datetime.now()

    print(f"{ANSI_BOLD}Link start time:{ANSI_ESCAPE} {start_time}")
    print(f"{ANSI_BOLD}Link end time:{ANSI_ESCAPE} {end_time}")
    print(f"{ANSI_BOLD}Link elapsed time:{ANSI_ESCAPE} {end_time - start_time}")

    # shutdown the executor
    global executor
    if executor is not None:
        executor.shutdown(wait=False, cancel_futures=True)

    sys.exit(0)

# <----- Co-routine definitions ----->


def parser_request(payload: Dict, url: str):
    """
    Makes a parse request to the given `url`.
    """
    # Write to log file
    # Characters might not show up as expetced in the log file
    with open(LOG_FILE_NAME, "a") as output_log_file:
        json.dump(payload, output_log_file, indent=2)
        output_log_file.write('\n')
    try:
        r = requests.post(url=url, json=payload, timeout=5.0, headers=AUTH_HEADER)
    except requests.ConnectionError:
        print(f"Unable to make POST request to {url=}!\n")
    except requests.Timeout:
        print(f"Connection timeout when making request to {url=}!\n")
    else:
        return r


def process_response(future: concurrent.futures.Future):
    """
    Implements the post-processing after receiving a response from the parser.
    Formats the parsed measurements into a table for convenience.

    This function should be registered as a "done callback". This means that once a
    future is done executing, this function should be automatically called.
    """

    # get the response from the future
    response = future.result()

    if response is None:
        return

    # if a SIGINT was received by the main thread, abandon printing of parse results
    if SIGINT_RECVD:
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

        print(parse_response["message"])

        # table.field_names = list(parse_response["message"].keys())     # Keys are column headings
        # extracted_measurements = parse_response["message"]
        # for i in range(len(extracted_measurements[table.field_names[0]])):
        #     row_data = [extracted_measurements[key][i] for key in table.field_names]
        #     table.add_row(row_data)

        print(table)
    elif parse_response["result"] == "PARSE_FAIL":
        print(f"Failed to parse message with id={parse_response['id']}!")
    elif parse_response["result"] == "INFLUX_WRITE_FAIL":
        print(f"Failed to write measurements for CAN message with id={parse_response['id']} to InfluxDB!")
    else:
        print(f"Unexpected response: {parse_response['result']}")

    print()


def main():
    """
    Main telemetry link entrypoint.
    """
    # <----- Argument parsing ----->

    parser = argparse.ArgumentParser(
        description="Link raw radio stream to telemetry cluster.",
        prog=__PROGRAM__)

    # declare argument groups
    threadpool_group = parser.add_argument_group("Thread pool options")
    source_group = parser.add_argument_group("Data stream selection and options")
    write_group = parser.add_argument_group("Data write options")

    parser.add_argument("--version", action="version",
                        version=f"{__PROGRAM__} v{__VERSION__}", help=("Show program's version number and exit"))

    parser.add_argument("--health", action="store_true",
                        help=("Checks the health of the telemetry cluster."))

    threadpool_group.add_argument("-j", "--jobs", action="store", default=DEFAULT_MAX_WORKERS,
                                  help=(f"The max number of threads to use for making HTTP requests to \
                                        the parser. Default is {DEFAULT_MAX_WORKERS}."))

    write_group.add_argument("--debug", action="store_true",
                             help=("Requests parser to write parsed data to the debug InfluxDB bucket."))
    write_group.add_argument("--prod", action="store_true",
                             help=("Requests parser to write parsed data to the production InfluxDB bucket."))
    write_group.add_argument("--no-write", action="store_true",
                             help=(("Requests parser to skip writing to the InfluxDB bucket and streaming"
                                   "to Grafana. Cannot be used with --debug and --prod options.")))
    source_group.add_argument("-p", "--port", action="store",
                              help=("Specifies the serial port to read radio data from. "
                                    "Typical values include: COM5, /dev/ttyUSB0, etc."))
    source_group.add_argument("-b", "--baudrate", action="store", type=int,
                              help=("Specifies the baudrate for the serial port specified. "
                                    "Typical values include: 9600, 115200, 230400, etc."))

    source_group.add_argument("-r", "--randomize", action="store_true",
                              help=("Allows using the telemetry link with "
                                    "randomly generated CAN data rather than "
                                    "a real radio telemetry stream."))
    
    source_group.add_argument("-o", "--offline", action="store_true",
                              help=("Allows using the telemetry link with "
                                    "the data recieved directly from the CAN bus "))
    
    source_group.add_argument("--dbc", action="store",
                              help="Specifies the dbc file to use. For example: ./dbc/brightside.dbc"
                              "Default: ./dbc/brightside.dbc")

    source_group.add_argument("-f", "--frequency-hz", action="store", default=DEFAULT_RANDOM_FREQUENCY_HZ, type=int,
                              help=((f"Specifies the frequency (in Hz) for random message generation. \
                                    Default value is {DEFAULT_RANDOM_FREQUENCY_HZ}Hz. Values above 1kHz \
                                    are discouraged.")))

    args = parser.parse_args()

    # <----- Argument validation and handling ----->

    if args.health:
        check_health_handler()
        return 0

    #validate_args(parser, args)

    # build the correct URL to make POST request to
    if args.prod:
        PARSER_ENDPOINT = PROD_WRITE_ENDPOINT
    elif args.debug:
        PARSER_ENDPOINT = DEBUG_WRITE_ENDPOINT
    else:
        PARSER_ENDPOINT = NO_WRITE_ENDPOINT

    # Check if logging is selected
    global LOG_FILE
    global LOG_DIRECTORY
    LOG_FILE = ''
    LOG_DIRECTORY = './logfiles/'

    current_log_time = datetime.now()
    LOG_FILE = Path('link_telemetry_log_{}.json'.format(current_log_time))

    # compute the period to generate random messages at
    period_s = 1 / args.frequency_hz

    # <----- Read in DBC file ----->
        
    if (args.dbc):
        PROVIDED_DBC_FILE = Path(args.dbc)
        car_dbc = cantools.database.load_file(PROVIDED_DBC_FILE)
    else:
        car_dbc = cantools.database.load_file(DBC_FILE)
        

    # <----- Configuration confirmation ----->

    print_config_table(args)
    choice = input("Are you sure you want to continue with this configuration? (y/N) > ")
    if choice.lower() != "y":
        return

    # <----- Create the thread pool ----->

    global executor
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=DEFAULT_MAX_WORKERS)

    global start_time
    start_time = datetime.now()

    print(f"{ANSI_GREEN}Telemetry link is up!{ANSI_ESCAPE}")
    print("Waiting for incoming messages...")

    # <----- Create Empty Log File ----->
    if LOG_FILE and not os.path.exists(LOG_DIRECTORY):
        os.makedirs(LOG_DIRECTORY)
    global LOG_FILE_NAME 
    LOG_FILE_NAME = os.path.join(LOG_DIRECTORY, LOG_FILE)
    

    while True:
        message: bytes

        if args.randomize:
            message = RandomMessage().random_message_str(car_dbc)
            time.sleep(period_s)

        elif args.offline:     
            # Defining the Can bus
            can_bus = can.interface.Bus(bustype='socketcan', channel=OFFLINE_CAN_CHANNEL, bitrate=OFFLINE_CAN_BITRATE)

            # read in bytes from CAN bus
            message = can_bus.recv()          

            # partition string into pieces
            # timestamp: str = np.format_float_positional(message.timestamp)      # float
            timestamp: str = "000000"                           #TODO: convert float to string
            id: str = str(hex(message.arbitration_id))          # int
            data: str = (message.data).hex()                    # bytearray
            data_len: str = str(message.dlc)                    # int

        else:
            with serial.Serial() as ser:
                # <----- Configure COM port ----->
                ser.baudrate = args.baudrate
                ser.port = args.port
                ser.open()

                # read in bytes from COM port
                message = ser.readline()
                             
        payload = {
            "message" : "hi",
        }

        # submit to thread pool
        future = executor.submit(parser_request, payload, PARSER_ENDPOINT)

        # register done callback with future
        future.add_done_callback(process_response)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, sigint_handler)
    main()
