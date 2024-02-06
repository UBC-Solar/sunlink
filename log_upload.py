"""
ASSUMPTIONS:
    log file is in the SAME directory as this script
"""
"""
CREDIT: Mihir. N for the following implementations
    -TOML config file reading
    -global PARSER_URL, SECRET_KEY, OFFLINE_CAN_CHANNEL, OFFLINE_CAN_BITRATE variables
    -SIGINT_RECVD flag
    -ANSI sequences
    -sigint_handler function
    -parser_request function
    -process_response function
"""

import concurrent.futures
from pathlib import Path
import sys
import toml
from toml import TomlDecodeError
from typing import Dict
from datetime import datetime
import signal
import argparse
import requests
import glob
import os

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

# global flag that indicates whether a SIGINT signal was received
SIGINT_RECVD = False

# ANSI sequences
ANSI_ESCAPE = "\033[0m"
ANSI_RED = "\033[1;31m"
ANSI_GREEN = "\033[1;32m"
ANSI_YELLOW = "\033[1;33m"
ANSI_BOLD = "\033[1m"

DEFAULT_MAX_WORKERS = 32
__PROGRAM__ = "log_upload"

# header to provide with each HTTP request to the parser for API authorization
AUTH_HEADER = {"Authorization": f"Bearer {SECRET_KEY}"}

# Endpoints for CAN, GPS, and IMU messages
CAN_WRITE_ENDPOINT = f"{PARSER_URL}/api/v1/parse/write/debug"
GPS_WRITE_ENDPOINT = f"{PARSER_URL}/api/v1/parse/write/debug"
IMU_WRITE_ENDPOINT = f"{PARSER_URL}/api/v1/parse/write/debug"

# Lengths of messages for differentiating message types
CAN_LENGTH_MIN      = 20
CAN_LENGTH_MAX      = 23
GPS_LENGTH_MIN      = 117
GPS_LENGTH_MAX      = 128
IMU_LENGTH_MIN      = 15
IMU_LENGTH_MAX      = 17


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
        print(f"CALLBACK RECEIVED: {parse_response['type']} message with id={parse_response['id']}")
    elif parse_response["result"] == "PARSE_FAIL":
        print(f"Failed to parse message with id={parse_response['id']}!")
    elif parse_response["result"] == "INFLUX_WRITE_FAIL":
        print(f"Failed to write measurements for {parse_response['type']} message with id={parse_response['id']} to InfluxDB!")
    else:
        print(f"Unexpected response: {parse_response['result']}")

    print()


def parser_request(payload: Dict, url: str):
    """
    Makes a parse request to the given `url`.
    """
    try:
        r = requests.post(url=url, json=payload, timeout=5.0, headers=AUTH_HEADER)
    except requests.ConnectionError:
        print(f"Unable to make POST request to {url=}!\n")
    except requests.Timeout:
        print(f"Connection timeout when making request to {url=}!\n")
    else:
        return r

def read_lines_from_file(file_path):
    """
    Reads lines from the specified file and returns a generator.
    """
    with open(file_path, 'r', encoding='latin-1') as file:
        for line in file:
            yield line.strip()

def main():
    # # Argument parsing
    # parser = argparse.ArgumentParser(description="Link raw radio stream to telemetry cluster.", prog=__PROGRAM__)

    # parser.add_argument("--log-file", dest="log_file", action="store", required=True,
    #                     help="Specify the name of the log file to read lines from.")

    # args = parser.parse_args()

    # Create the thread pool
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=DEFAULT_MAX_WORKERS)

    print(f"{ANSI_GREEN}Log Uploader is Up!{ANSI_ESCAPE}")

    # Get the path to the logfiles directory
    logfiles_dir = "./logfiles"

    # Get a list of all .txt files in the logfiles directory
    txt_files = glob.glob(logfiles_dir + '/*.txt')
    print(f"Found {len(txt_files)} .txt files in {logfiles_dir}")

    # Iterate over each .txt file
    for file_path in txt_files:
        print(f"Reading file {file_path}...")
        message_generator = read_lines_from_file(file_path)

        while True:
            try:
                log_line = next(message_generator)
            except StopIteration:
                break

            # Create payload
            payload = {"message": log_line}

            for i in range(len(log_line)):
                print(log_line[i], end=' ')

            # Submit to thread pool BASED ON length of line in the file 
            if CAN_LENGTH_MIN <= len(log_line) <= CAN_LENGTH_MAX:
                future = executor.submit(parser_request, payload, CAN_WRITE_ENDPOINT)
            elif GPS_LENGTH_MIN <= len(log_line) <= GPS_LENGTH_MAX:
                future = executor.submit(parser_request, payload, GPS_WRITE_ENDPOINT)
            elif IMU_LENGTH_MIN <= len(log_line) <= IMU_LENGTH_MAX:
                future = executor.submit(parser_request, payload, IMU_WRITE_ENDPOINT)
            else:
                print(f"Message length is not a valid length for any message type: {len(log_line)}, {log_line}")
                continue
            
            # Register done callback with future
            future.add_done_callback(process_response)

        print(f"Done reading {file_path}")

if __name__ == "__main__":
    signal.signal(signal.SIGINT, sigint_handler)
    main()
