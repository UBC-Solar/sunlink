#!/usr/bin/env python
from ast import parse
import serial
import sys
import signal
import cantools
import can
import time
import argparse
import requests
import toml
import json
import os
import glob
import struct
import re
import threading

from datetime import datetime 
from toml.decoder import TomlDecodeError
from pathlib import Path
from prettytable import PrettyTable
from typing import Dict
from parser.randomizer import RandomMessage
import parser.parameters as parameters
from beautifultable import BeautifulTable
import warnings

import concurrent.futures
from tools.MemoratorUploader import memorator_upload_script


__PROGRAM__ = "link_telemetry"
__VERSION__ = "0.4"

# <----- Supress Beatiful Table Warnings ----->
warnings.simplefilter(action='ignore', category=FutureWarning)


# <----- Constants ----->

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
LOG_WRITE_ENDPOINT = f"{PARSER_URL}/api/v1/parse/write/log"
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

# Chunks read per iteration
CHUNK_SIZE = 512


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
    if args.live_on and args.live_off:
        parser.error("--live-on and --live-off cannot be used together")
    if (args.log_upload and args.debug) or (args.log_upload and args.prod) or (args.log_upload and args.no_write) or (args.offline and args.log_upload):
        parser.error("-u (--log-upload) can only be used alone (cannot be used with ANY other options)")
    elif args.log_upload:
        return
    if args.randomList:
        # Check if it contains 'all' somewhere in the list
        if 'all' in args.randomList:
            args.randomList = []
            type_names = glob.glob('./parser/data_classes' + '/*_Msg.py')
            for name in type_names:
                args.randomList.append(name.split('/')[-1][:-7])    
        if args.port or args.baudrate:
            parser.error("-r cannot be used with -p and -b options")

        if args.prod and not args.force_random:
            parser.error("-r cannot be used with --prod since randomly generated data should not be written to the production database")
    else:
        pass
        # if not args.port and not args.baudrate:
        #     parser.error("Must specify either -r or both -p and -b arguments")
        # elif not (args.port and args.baudrate):
        #     parser.error("-p and -b options must both be specified")

    if args.no_write:
        if args.debug or args.prod:
            parser.error("Conflicting configuration. Cannot specify --no-write with --debug or --prod.")
    else:
        if args.debug and args.prod:
            parser.error("Conflicting configuration. Cannot specify both --debug and --prod. Must choose one.")

        if args.debug is False and args.prod is False:
            parser.error("Must specify one of --debug, --prod, or --no-write.")


def print_config_table(args: 'argparse.Namespace', live_filters: list):
    """
    Prints a table containing the current script configuration.
    """
    print(f"Running {ANSI_BOLD}{__PROGRAM__} (v{__VERSION__}){ANSI_ESCAPE} with the following configuration...\n")
    config_table = PrettyTable()
    config_table.field_names = ["PARAM", "VALUE"]

    msg_types = f"RANDOMLY GENERATED " if args.randomList else "FROM "
    msg_types += ' '.join([item.upper() for item in args.randomList]) if (not args.offline and not args.port) else ("OFFLINE" if not args.port else "RADIO")
    msg_types += f" @ {args.frequency_hz} Hz" if args.randomList else ""
    msg_types += f" {'UART PORT ' + str(args.port) if not args.randomList else ''}" 
    config_table.add_row(["DATA SOURCE", msg_types])

    filters_string = "LIVE STREAM FILTERS: "
    for live_filter in live_filters:
        filters_string += live_filter + ", "
    filters_string = filters_string.rstrip(', ')
    config_table.add_row(["LIVE STREAM FILTERS", filters_string])

    config_table.add_row(["PARSER URL", PARSER_URL])
    config_table.add_row(["DBC FILE", parameters.DBC_FILE])
    if LOG_FILE: config_table.add_row(["LOG FILE", "{}{}".format(LOG_DIRECTORY, LOG_FILE)]) # Only show row if log file option selected
    config_table.add_row(["MAX THREADS", args.jobs])

    if args.prod:
        config_table.add_row(["WRITE TARGET", "PRODUCTION BUCKET"])
    elif args.debug:
        config_table.add_row(["WRITE TARGET", "DEBUG BUCKET"])
    else:
        config_table.add_row(["WRITE TARGET", "WRITE DISABLED"])

    # POSSIBLE CONFIGURATIONS

    # case : --randomize with --debug: generate random data and write to the `Test` bucket (INTENDED USAGE)
    # case 2: --randomize without --debug: generate random data and write to the `Telemetry` bucket (SHOULD BE IMPOSSIBLE)
    # case 3: -p and -b with --debug: parse radio data and write to the `Test` bucket (LIKELY)
    # case 4: -p and -b without --debug: parse radio data and write to the `Telemetry` bucket (ACTUAL OPERATION MODE)

    if not args.randomList:
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
    try:
        r = requests.post(url=url, json=payload, timeout=5.0, headers=AUTH_HEADER)
    except requests.ConnectionError as e:
        print(e)
        print(f"Unable to make POST request to {url=}!\n")
    except requests.Timeout:
        print(f"Connection timeout when making request to {url=}!\n")
    else:
        return r

def write_to_log_file(message: str, log_file_name, convert_to_hex=True):
    # Message encoded to hex to ensure all characters stay
        if convert_to_hex:
            with open(log_file_name, "a", encoding='latin-1') as output_log_file:
                output_log_file.write(message.encode('latin-1').hex() + '\n')
        else:
            with open(log_file_name, "a") as output_log_file:
                print(message, file=output_log_file)


def process_response(future: concurrent.futures.Future, args):
    """
    Implements the post-processing after receiving a response from the parser.
    Formats the parsed measurements into a table for convenience.

    This function should be registered as a "done callback". This means that once a
    future is done executing, this function should be automatically called.
    """
    formatted_time = current_log_time.strftime('%Y-%m-%d_%H:%M:%S')
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
    
    # if response.status_code != 200:
    #     print(f"{ANSI_BOLD}Response HTTP status code:{ANSI_ESCAPE} {ANSI_YELLOW}{response.status_code}{ANSI_ESCAPE}")
    # print(f"{ANSI_BOLD}Response HTTP status code:{ANSI_ESCAPE} {ANSI_GREEN}{response.status_code}{ANSI_ESCAPE}")
    
    try:
        parse_response: dict = response.json()
    except json.JSONDecodeError:
        print(f"Failed to parse response from parser as JSON!")
        print(f"Response content: {response.content}")
        return
    
    if parse_response["result"] == "OK":
        table = None
        if args.log is not None or args.table_on:
            # Create a table
            table = BeautifulTable()

            # Set the table title
            table.set_style(BeautifulTable.STYLE_RST)
            table.column_widths = [110]
            table.width_exceed_policy = BeautifulTable.WEP_WRAP

            # Title
            table.rows.append([f"{ANSI_GREEN}{parse_response['type']}{ANSI_ESCAPE}"])
            display_data = parse_response['message']

            # Add columns as subtable
            subtable = BeautifulTable()
            subtable.set_style(BeautifulTable.STYLE_GRID)

            cols = display_data["COL"]
            subtable.rows.append(cols.keys())
            for i in range(len(list(cols.values())[0])):
                subtable.rows.append([val[i] for val in cols.values()]) 

            table.rows.append([subtable])

            # Add rows
            rows = display_data["ROW"]
            for row_head, row_data in rows.items():
                table.rows.append([f"{ANSI_BOLD}{row_head}{ANSI_ESCAPE}"])
                table.rows.append(row_data)
            
        if args.table_on:
            print(table)

        if parse_response["logMessage"]:
            write_to_log_file(table, LOG_FILE_NAME, convert_to_hex=False)
        
    elif parse_response["result"] == "PARSE_FAIL":
        fail_msg = f"{ANSI_RED}PARSE_FAIL{ANSI_ESCAPE}: \n" + f"{parse_response['error']}"
        print(fail_msg)

        # If log upload AND parse fails then log again to the FAILED_UPLOADS.txt file. If no log upload do normal
        write_to_log_file(parse_response['message'], os.path.join(FAIL_DIRECTORY, "FAILED_UPLOADS_{}.txt".format(formatted_time)) if args.log_upload else FAIL_FILE_NAME)
        write_to_log_file(fail_msg + '\n', os.path.join(DEBUG_DIRECTORY, "FAILED_UPLOADS_{}.txt".format(formatted_time)) if args.log_upload else DEBUG_FILE_NAME, convert_to_hex=False)
    elif parse_response["result"] == "INFLUX_WRITE_FAIL":
        print(f"Failed to write measurements for {parse_response['type']} message to InfluxDB!")
        print(parse_response)

        # If log upload AND INFLUX_WRITE_FAIL fails then log again to the FAILED_UPLOADS.txt file. If no log upload do normal
        write_to_log_file(parse_response['message'], os.path.join(FAIL_DIRECTORY, "FAILED_UPLOADS_{}.txt".format(formatted_time)) if args.log_upload else FAIL_FILE_NAME)
        write_to_log_file(fail_msg + '\n', os.path.join(DEBUG_DIRECTORY, "FAILED_UPLOADS_{}.txt".format(formatted_time)) if args.log_upload else DEBUG_FILE_NAME, convert_to_hex=False)
    else:
        print(f"Unexpected response: {parse_response['result']}")


def read_lines_from_file(file_path):
    """
    Reads lines from the specified file and returns a generator.
    """
    with open(file_path, 'r', encoding='latin-1') as file:
        for line in file:
            yield line.strip()


"""
Purpose: Sends data and filters to parser and registers a callback to process the response
Parameters: 
    message - raw byte data to be parsed on parser side
    live_filters - filters for which messages to live stream to Grafana
    log_filters - filters for which messages to log to file
    args - the arguments passed to ./link_telemetry.py
    parser_endpoint - the endpoint to send the data to
Returns: None
"""
def sendToParser(message: str, live_filters: list, log_filters: list, args: list, parser_endpoint: str):
    payload = {
        "message" : message,
        "live_filters" : live_filters,
        "log_filters" : log_filters
    }
    
    # submit to thread pool
    future = executor.submit(parser_request, payload, parser_endpoint)

    # register done callback with future (lambda function to pass in arguments) 
    future.add_done_callback(lambda future: process_response(future, args))


def upload_logs(args, live_filters, log_filters, endpoint):
    # Call the memorator log uploader function
    memorator_upload_script(sendToParser, live_filters, log_filters, args, endpoint) 


"""
Purpose: Processes the message by splitting it into parts and returning the parts and the buffer
Parameters: 
    message - The total chunk read from the serial stream
    buffer - the buffer to be added to the start of the message
Returns (tuple):
    parts - the fully complete messages of the total chunk read
    buffer - leftover chunk that is not a message
"""
def process_message(message: str, buffer: str = "") -> list:
    
    # Add buffer to the start of the message
    message = buffer + message

    pattern = '(?=7E....88|7E....97|7E....10)'
    parts = re.split(pattern, message)

    if len(parts) > 1:
        buffer = parts.pop()

    return [bytes.fromhex(part).decode('latin-1') for part in parts], buffer

def atDiagnosticCommand(command_list):
    lock.acquire()
    while True:
        for command in command_list:
                serial.write(command)
        time.sleep(AT_COMMAND_FREQUENCY)
    lock.release()

def main():
    """
    Main telemetry link entrypoint.
    """
    ##lock for access to serial stream to manage writing AT commands and reading API frames
    lock = threading.Lock()
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
    write_group.add_argument("--table-on", action="store_true",
                             help=("Will display pretty tables. Normally off and parse fails only show"))
    write_group.add_argument("--no-write", action="store_true",
                             help=(("Requests parser to skip writing to the InfluxDB bucket and streaming"
                                   "to Grafana. Cannot be used with --debug and --prod options.")))
    source_group.add_argument("-p", "--port", action="store",
                              help=("Specifies the serial port to read radio data from. "
                                    "Typical values include: COM5, /dev/ttyUSB0, etc."))
    source_group.add_argument("-b", "--baudrate", action="store", type=int,
                              help=("Specifies the baudrate for the serial port specified. "
                                    "Typical values include: 9600, 115200, 230400, etc."))

    source_group.add_argument("-r", "--randomList", nargs='+',
                              help=("Allows using the telemetry link with "
                                    "chosen randomly generated message types rather than "
                                    "a real radio telemetry stream. do -r can gps imu"))

    source_group.add_argument("--live-off", action="store_true",
                              help=("Will not stream any data to grafana"))
    
    source_group.add_argument("-l", "--log", nargs='+',
                              help=("Args create a list of message classes or ID's to pretty log to a file. no args for all, all for all"))
    
    source_group.add_argument("--live-on", nargs='+',
                              help=("Args create a list of message classes or ID's to stream to grafana. no args for all, all for all"))
    
    source_group.add_argument("-u", "--log-upload", action="store_true",
                            help=("Will attempt to upload each line of each file in the logfiles directory "
                                "If upload does not succeed then these lines will be stored "
                                "in a file named `FAILED_UPLOADS.txt in the logfiles directory`"))

    source_group.add_argument("-o", "--offline", action="store_true",
                              help=("Allows using the telemetry link with "
                                    "the data recieved directly from the CAN bus "))
    
    source_group.add_argument("--force-random", action="store_true",
                            help=("allows randomization with production bucket. Please user carefully and locally "))
    
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

    validate_args(parser, args)


    # build the correct URL to make POST request to
    if args.prod or args.offline:
        PARSER_ENDPOINT = PROD_WRITE_ENDPOINT
    elif args.debug:
        PARSER_ENDPOINT = DEBUG_WRITE_ENDPOINT
    else:
        PARSER_ENDPOINT = NO_WRITE_ENDPOINT

    # Check if logging is selected
    global LOG_FILE
    global LOG_DIRECTORY
    global FAIL_DIRECTORY
    global DEBUG_DIRECTORY
    LOG_FILE = ''
    LOG_DIRECTORY = './logfiles/'
    FAIL_DIRECTORY = './failfiles/'
    DEBUG_DIRECTORY = './dbgfiles/'

    global current_log_time
    current_log_time = datetime.now()
    formatted_time = current_log_time.strftime('%Y-%m-%d_%H:%M:%S')
    LOG_FILE = Path('link_telemetry_log_{}.txt'.format(formatted_time))

    # compute the period to generate random messages at
    period_s = 1 / args.frequency_hz
    
    # <----- Change DBC file based on args ----->
    if (args.dbc):
        parameters.DBC_FILE = Path(args.dbc)
        parameters.CAR_DBC  = cantools.database.load_file(parameters.DBC_FILE)


    # <----- Define Can Bus for Offline Mode ----->
    if args.offline:
        # Defining the Can bus
        can_bus = can.interface.Bus(bustype='socketcan', channel=OFFLINE_CAN_CHANNEL, bitrate=OFFLINE_CAN_BITRATE)

    # <----- Define Live Filters ----->
    live_filters = args.live_on
    if args.live_on and args.live_on[0].upper() == "ALL":
        live_filters = ["ALL"]
    elif args.live_off or not args.live_on:
        live_filters = ["NONE"]

    # <----- Define Log Filters ----->
    log_filters = args.log
    if args.log and args.log[0].upper() == "ALL":
        log_filters = ["ALL"]
    elif not args.log:
        log_filters = ["NONE"]

    # <----- Configuration confirmation ----->
    if not args.log_upload:
        print_config_table(args, live_filters)
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
    if LOG_FILE and not os.path.exists(FAIL_DIRECTORY):
        os.makedirs(FAIL_DIRECTORY)
    if LOG_FILE and not os.path.exists(DEBUG_DIRECTORY):
        os.makedirs(DEBUG_DIRECTORY)

    global LOG_FILE_NAME 
    global FAIL_FILE_NAME
    global DEBUG_FILE_NAME
    LOG_FILE_NAME = os.path.join(LOG_DIRECTORY, LOG_FILE)
    FAIL_FILE_NAME = os.path.join(FAIL_DIRECTORY, LOG_FILE)
    DEBUG_FILE_NAME = os.path.join(DEBUG_DIRECTORY, LOG_FILE)
    
    if args.log_upload:
        upload_logs(args, live_filters, log_filters, LOG_WRITE_ENDPOINT)
        return 0

    future = executor.submit(atDiagnosticCommand, command_list)

    while True:
        message: bytes

        if args.randomList:
            try:
                message = RandomMessage().random_message_str(args.randomList)
            except Exception as e:
                print(f"Failed to generate random message: {e}")
                continue
            
            time.sleep(period_s)

        elif args.offline:     
            # read in bytes from CAN bus
            can_bytes = can_bus.recv()          

            # partition string into pieces
            epoch_time = time.time()                            # epoch time as float
            timestamp_bytes = struct.pack('>d', epoch_time)
            timestamp_str = timestamp_bytes.decode('latin-1')

            id: int = can_bytes.arbitration_id                    # int
            id_str = id.to_bytes(4, 'big').decode('latin-1')

            data_bytes = can_bytes.data
            data_pad = data_bytes.ljust(8, b'\0')
            data_str = data_pad.decode('latin-1')                                    # string 

            data_len: str = str(can_bytes.dlc)                    # string

            message = timestamp_str + "#" + id_str + data_str + data_len

        else:
            buffer = ""
            with serial.Serial() as ser:
               
                # <----- Configure COM port ----->
                ser.baudrate = args.baudrate
                ser.port = args.port
                ser.open()

                while True:
                    lock.acquire()
                    # read in bytes from COM port
                    chunk = ser.read(CHUNK_SIZE)
                    chunk = chunk.hex()
                    parts, buffer = process_message(chunk, buffer)
                    lock.release()

                    for part in parts:
                        sendToParser(part, live_filters, log_filters, args, PARSER_ENDPOINT)

        sendToParser(message, live_filters, log_filters, args, PARSER_ENDPOINT)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, sigint_handler)
    main()
   

