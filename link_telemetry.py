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
import subprocess

from datetime import datetime 
from toml.decoder import TomlDecodeError
from pathlib import Path
from prettytable import PrettyTable
from typing import Dict
from parser.randomizer import RandomMessage
import parser.parameters as parameters
from beautifultable import BeautifulTable
import warnings
import threading

import concurrent.futures
from tools.MemoratorUploader import memorator_upload_script
from parser.create_message import create_message
from LINK_CONSTANTS import *
from dotenv import dotenv_values
from websockets.sync.client import connect
import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS


__PROGRAM__ = "link_telemetry"
__VERSION__ = "0.4"

# <----- Supress Beatiful Table Warnings ----->
warnings.simplefilter(action='ignore', category=FutureWarning)

# paths are relative to project root
ENV_FILE = Path(".env")
if not ENV_FILE.is_file():
    sys.exit(1)
ENV_CONFIG = dotenv_values(ENV_FILE)
GRAFANA_URL = "http://grafana:3000/"
GRAFANA_TOKEN = ENV_CONFIG["GRAFANA_TOKEN"]
GRAFANA_URL_NAME = Path(GRAFANA_URL).name

# <----- InfluxDB constants ----->

INFLUX_URL = "http://localhost:8086/"
INFLUX_TOKEN = ENV_CONFIG["INFLUX_TOKEN"]

INFLUX_ORG = ENV_CONFIG["INFLUX_ORG"]


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
CHUNK_SIZE = 24 * 21        # 21 CAN messages from serial at a time.

num_processed_msgs = 0

batch_to_write = []
client = influxdb_client.InfluxDBClient(
    url=INFLUX_URL, org=INFLUX_ORG, token=INFLUX_TOKEN)
write_api = client.write_api(write_options=SYNCHRONOUS)

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


    
def filter_stream(parse_response, filter_list):  
    data_dict = parse_response['message']
    return _filter_stream(data_dict, filter_list)

def _filter_stream(data_dict, filter_list, type="CAN"):
    if "ALL" in filter_list:
        return True
    elif "NONE" in filter_list:
        return False
      
    for filter in filter_list:
        if len(filter) > 2 and filter[:2] == "0x":
            in_table_data = data_dict['COL']
            for data_list in in_table_data.values():
                if filter in data_list:
                    return True
        if filter.isdigit():
            class_name = data_dict["Class"][0]

            # try if it is CAN message
            can_message = None
            try:
                can_message = parameters.CAR_DBC.get_message_by_name(class_name)
            except:
                continue

            id = can_message.frame_id

            if int(filter) == id:
                return True
            else:
                continue
        if filter.isalpha():
            if filter.upper() == type.upper():
                return True
            continue

    return False


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


# If the number of lines is more than 1000000 then write to new file
num_fail_chars = 0
num_log_chars = 0
num_dbg_chars = 0
def write_to_log_file(message: str, log_file_name: str, type: str, convert_to_hex=True):
    global num_fail_chars
    global num_log_chars 
    global num_dbg_chars

    if type == "fail":
        num_fail_chars += len(str(message))
        _doWrite(message, log_file_name, int(num_fail_chars / parameters.MAX_FILE_CHARS), convert_to_hex)
    elif type == "log":
        num_log_chars += len(str(message))
        _doWrite(message, log_file_name, int(num_log_chars / parameters.MAX_FILE_CHARS), convert_to_hex)
    elif type == "dbg":
        num_dbg_chars += len(str(message))
        _doWrite(message, log_file_name, int(num_dbg_chars / parameters.MAX_FILE_CHARS), convert_to_hex)


def _doWrite(message: str, log_file_name: str, suffix: str, convert_to_hex=True):
    # Message encoded to hex to ensure all characters stay
    new_file_name = f"{log_file_name}_{suffix}"
    if convert_to_hex:
        with open(new_file_name, "a", encoding='latin-1') as output_log_file:
            output_log_file.write(message.encode('latin-1').hex() + '\n')
    else:
        with open(new_file_name, "a") as output_log_file:
            print(message, file=output_log_file)



def process_response(future: concurrent.futures.Future, args, display_filters: list):
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

    all_responeses = parse_response['all_responses']    

    for response in all_responeses:
        if response["result"] == "OK":
            table = handle_message_from_response(response["message"], display_filters, args)

            if response["logMessage"] and table is not None:
                write_to_log_file(table, LOG_FILE_NAME, "log", convert_to_hex=False)
    
        elif response["result"] == "PARSE_FAIL":
            fail_msg = f"{ANSI_RED}PARSE_FAIL{ANSI_ESCAPE}: \n" + f"{response['error']}"
            print(fail_msg)

            # If log upload AND parse fails then log again to the FAILED_UPLOADS.txt file. If no log upload do normal
            write_to_log_file(response['message'], os.path.join(FAIL_DIRECTORY, "FAILED_UPLOADS_{}.txt".format(formatted_time)) if args.log_upload else FAIL_FILE_NAME, "fail")
            write_to_log_file(fail_msg + '\n', os.path.join(DEBUG_DIRECTORY, "FAILED_UPLOADS_{}.txt".format(formatted_time)) if args.log_upload else DEBUG_FILE_NAME, "dbg", convert_to_hex=False)
        elif response["result"] == "INFLUX_WRITE_FAIL":
            fail_msg = f"{ANSI_RED}INFLUX_WRITE_FAIL{ANSI_ESCAPE}: \n" + f"{response['error']}"
            print(f"Failed to write measurements for {response['type']} message to InfluxDB!")
            print(response)

            # If log upload AND INFLUX_WRITE_FAIL fails then log again to the FAILED_UPLOADS.txt file. If no log upload do normal
            write_to_log_file(response['message'], os.path.join(FAIL_DIRECTORY, "FAILED_UPLOADS_{}.txt".format(formatted_time)) if args.log_upload else FAIL_FILE_NAME, "fail")
            write_to_log_file(fail_msg + '\n', os.path.join(DEBUG_DIRECTORY, "FAILED_UPLOADS_{}.txt".format(formatted_time)) if args.log_upload else DEBUG_FILE_NAME, "dbg", convert_to_hex=False)
        else:
            print(f"Unexpected response: {response['result']}")

def handle_message_from_response(display_dict, display_filters, args):
    global num_processed_msgs
    num_processed_msgs += 1                             # A call back is received so our request was processed
    
    table = None
    do_display_table = _filter_stream(display_dict, display_filters)
    if args.log is not None or do_display_table:
        # Create a table
        table = BeautifulTable()

        # Set the table title
        table.set_style(BeautifulTable.STYLE_RST)
        table.column_widths = [110]
        table.width_exceed_policy = BeautifulTable.WEP_WRAP

        # Title
        table.rows.append([f"{ANSI_GREEN}CAN{ANSI_ESCAPE}"])

        # Add columns as subtable
        subtable = BeautifulTable()
        subtable.set_style(BeautifulTable.STYLE_GRID)

        cols = display_dict["COL"]
        subtable.rows.append(cols.keys())
        for i in range(len(list(cols.values())[0])):
            subtable.rows.append([val[i] for val in cols.values()]) 

        table.rows.append([subtable])

        # Add rows
        rows = display_dict["ROW"]
        for row_head, row_data in rows.items():
            table.rows.append([f"{ANSI_BOLD}{row_head}{ANSI_ESCAPE}"])
            table.rows.append(row_data)
        
    if do_display_table:
        print(table)
        return table
    else:
        return None




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
    display_filters - filters for which messages to display in terminal
    args - the arguments passed to ./link_telemetry.py
    parser_endpoint - the endpoint to send the data to
Returns: None
"""
def sendToParser(message: str, live_filters: list, log_filters: list, display_filters: list, args: list, parser_endpoint: str):
        payload = {
            "message" : message,
            "live_filters" : live_filters,
            "log_filters" : log_filters,
        }
    
        # submit to thread pool
        
        future = executor.submit(parser_request, payload, parser_endpoint)
        
        # register done callback with future (lambda function to pass in arguments) 
        future.add_done_callback(lambda future: process_response(future, args, display_filters))


def upload_logs(args, live_filters, log_filters, display_filters, csv_file_f):
    # Call the memorator log uploader function
    memorator_upload_script(create_message, live_filters, log_filters, display_filters, args, csv_file_f) 


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
    # Remove 00 0a from the start if present
    if message.startswith("000a"):
        message = message[4:]
    elif message.startswith("0a"):
        message = message[2:]
    
    # Add buffer to the start of the message
    message = buffer + message

    # Split the message by 0d 0a. TEL board sends messages ending with \r\n which is 0d0a in hex. Use as delimeter
    parts = message.split("0d0a")

    if len(parts[-1]) != 30 or len(parts[-1]) != 396 or len(parts[-1]) != 44:
        buffer = parts.pop()

    try:
        parts = [part + "0d0a" for part in parts if len(part) == 30 or len(part) == 396 or len(part) == 44]
    except ValueError as e:
        print(f"{ANSI_RED}Failed to split message: {str([part for part in parts])}{ANSI_ESCAPE}"
              f"    ERROR: {e}")
        return [], buffer
    return [bytes.fromhex(part).decode('latin-1') for part in parts] , buffer


"""
Continously prints the runtime, current time, and messages processed
"""
def displaySunlinkTracking():
    while True:
        current_datetime = datetime.now()
        sunlink_runtime = current_datetime - start_time
        current_formatted_time = current_datetime.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        # 1ms precisios
        sunlink_formatted_runtime = str(sunlink_runtime)[:-3]
        msg = f"LINK_TELEMETRY: Proccessed {num_processed_msgs} Messages in {sunlink_formatted_runtime}. Current Time: {current_formatted_time}"

        sys.stdout.write(parameters.ANSI_SAVE_CURSOR)  # Save cursor position
        sys.stdout.write(f"{parameters.ANSI_YELLOW}{msg}{ANSI_ESCAPE}")  # Yellow text
        sys.stdout.write(parameters.ANSI_RESTORE_CURSOR)  # Restore cursor position
        sys.stdout.flush()
        time.sleep(parameters.DISPLAY_RATE)
    

BATCH_SIZE = 1

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
    write_group.add_argument("--table-on", nargs='+',
                             help=("Will display pretty tables. Choose what to show like --log option"))
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
    
    source_group.add_argument("--raw", action="store_true",
                              help=("Will enable displaying of raw data coming from serial stream AFTER cutting algorithm"))
    
    source_group.add_argument("--rawest", action="store_true",
                            help=("Will enable displaying of raw data coming from serial stream in chunk size"))
    
    source_group.add_argument("-l", "--log", nargs='+',
                              help=("Args create a list of message classes or ID's to pretty log to a file. no args for all, all for all"))
    
    source_group.add_argument("--live-on", nargs='+',
                              help=("Args create a list of message classes or ID's to stream to grafana. no args for all, all for all"))
    
    source_group.add_argument("-u", "--log-upload", nargs='+',
                            help=("Will attempt to upload each line of each file in the logfiles directory "
                                "If upload does not succeed then these lines will be stored "
                                "in a file named `FAILED_UPLOADS.txt in the logfiles directory`"))

    source_group.add_argument("-o", "--offline", action="store_true",
                              help=("Allows using the telemetry link with "
                                    "the data recieved directly from the CAN bus "))
    
    source_group.add_argument("-t", "--track", action="store_true",
                            help=("Prints Sunlink runtime, current time, num messages processed"))
    
    source_group.add_argument("--force-random", action="store_true",
                            help=("allows randomization with production bucket. Please user carefully and locally "))
    
    source_group.add_argument("--dbc", action="store",
                              help="Specifies the dbc file to use. For example: ./dbc/brightside.dbc"
                              "Default: ./dbc/brightside.dbc")

    source_group.add_argument("-f", "--frequency-hz", action="store", default=DEFAULT_RANDOM_FREQUENCY_HZ, type=int,
                              help=((f"Specifies the frequency (in Hz) for random message generation. \
                                    Default value is {DEFAULT_RANDOM_FREQUENCY_HZ}Hz. Values above 1kHz \
                                    are discouraged.")))
    
    source_group.add_argument("--batch-size", action="store", default=BATCH_SIZE, type=int,
                              help=((f"The number of parsed messages to send to InfluxDB at a time (Chunking). \
                                    Default value is {BATCH_SIZE}. Improves performance to chunk high data rates")))
    
    source_group.add_argument("--local", action="store_true",
                              help=((f"Will parse messages without using the parser docker container. Generally faster and useful for high data rates")))

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

    # <----- Define Display Table Filters ----->
    display_filters = args.table_on
    if args.table_on and args.table_on[0].upper() == "ALL":
        display_filters = ["ALL"]
    elif not args.table_on:
        display_filters = ["NONE"]

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


    # Start Sunlink Runtime counter display
    if args.track or (not args.table_on and not args.log and not args.log_upload):
        time_thread = threading.Thread(target=displaySunlinkTracking, daemon=True)
        time_thread.start()


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
        global csv_file
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        csv_file_name = CSV_NAME + timestamp + ".csv"
        csv_file = open(csv_file_name, "w")
        csv_file.write(INFLUX_CSV_HEADING + '\n')
        upload_logs(args, live_filters, log_filters, display_filters, csv_file)

        #Calling the bash script
        csv_file.close()
        subprocess.run(["chmod", "+x", "./scripts/csv_upload.sh"])
        subprocess.run(["bash", "./scripts/csv_upload.sh", csv_file_name])

        return

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
                    # read in bytes from COM port
                    chunk = ser.read(CHUNK_SIZE)
                    chunk = chunk.hex()

                    if args.rawest:
                        print(chunk)
                        
                    parts, buffer = process_message(chunk, buffer)

                    for part in parts:
                        if args.raw:
                            print(part.encode('latin-1').hex())

                        if (args.local):
                            handle_raw_message(part, display_filters, args)
                        else:
                            sendToParser(part, live_filters, log_filters, display_filters, args, PARSER_ENDPOINT)


        if (args.local):
            handle_raw_message(message, display_filters, args)
        else:
            sendToParser(message, live_filters, log_filters, display_filters, args, PARSER_ENDPOINT)




def handle_raw_message(raw_message, display_filters, args):
    parsed_message = safe_create_message(raw_message)
    if (parsed_message is not None):
        handle_message_from_response(parsed_message.data["display_data"], display_filters, args)
        write_to_influx(parsed_message, "_test" if args.debug else "_prod", args.batch_size)

def write_to_influx(parsed_message, bucket, batch_size):
    for i in range(len(parsed_message.data[list(parsed_message.data.keys())[0]])):
        # REQUIRED FIELDS
        name = parsed_message.data["Measurement"][i]
        source = parsed_message.data["Source"][i]
        m_class = parsed_message.data["Class"][i]
        value = parsed_message.data["Value"][i]
        
        timestamp = parsed_message.data.get("Timestamp", ["NA"])[i]

        point = influxdb_client.Point(source).tag("car", CAR_NAME).tag(
            "class", m_class).field(name, value)
        
        
        if timestamp != "NA":
            point.time(int(timestamp * 1e9))
        
        global batch_to_write
        batch_to_write.append(point)

        # write to InfluxDB
        if len(batch_to_write) >= batch_size:    # CREDIT: Mridul Singh for Batch Writing Optimization!
            try:
                write_api.write(bucket=parsed_message.type + bucket, org=INFLUX_ORG, record=batch_to_write)
                write_api.close()
                batch_to_write = []
            except Exception as e:
                print("INFLUX_WRITE_ERROR", e)
                continue
            

def safe_create_message(msg):
    try:
        message = create_message(msg)
    except Exception as e:
        print(e)
        return None
    
    return message


if __name__ == "__main__":
    signal.signal(signal.SIGINT, sigint_handler)
    main()
   

