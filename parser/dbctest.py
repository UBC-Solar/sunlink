import cantools
from pathlib import Path
import os
import concurrent.futures
from prettytable import PrettyTable
from pathlib import Path
import sys
import toml
from toml import TomlDecodeError
from typing import Dict
from datetime import datetime
import signal
import argparse
import requests


# my_dict = {
#     'key1': [1, 2, 3, 4],
#     'key2': [5, 6, 7, 8],
#     'key3': [9, 10, 11, 12],
#     'key4': [13, 14, 15, 16],
#     'key5': [17, 18, 19, 20]
# }

# result_list = []

# for i in range(4):  # assuming the loop runs 4 times
#     sublist = [my_dict[key][i] for key in my_dict]
#     result_list.append(sublist)


# for i in range(len(my_dict[list(my_dict.keys())[0]])):
#     name = my_dict["key1"][i]
#     source = my_dict["key2"][i]
#     m_class = my_dict["key3"][i]
#     value = my_dict["key4"][i]


#     print(name, source, m_class, value)



# dbc = cantools.database.load_file(str(Path(os.getcwd()) / "dbc" / "brightside.dbc"))
# msg = RandomMessage().random_can_str(dbc)
# print(msg)
# can = create_message(msg)
# print(can.extract_measurements(dbc))

# gps = RandomMessage().random_gps_str()
# print(gps)
# gps = create_message(gps)
# print(gps.extract_measurements())

# imu = RandomMessage().random_imu_str()
# print(imu)
# imu = create_message(imu)
# print(imu.extract_measurements())

__PROGRAM__ = "dbctest"


def read_lines_from_file(file_path):
    """
    Reads lines from the specified file and returns a generator.
    """
    with open(file_path, 'r') as file:
        for line in file:
            yield line.strip()

def main():
    # Argument parsing
    parser = argparse.ArgumentParser(description="Link raw radio stream to telemetry cluster.", prog=__PROGRAM__)

    parser.add_argument("--log-file", dest="log_file", action="store", required=True,
                        help="Specify the name of the log file to read lines from.")

    args = parser.parse_args()

    # Process messages from the specified log file
    file_path = args.log_file
    message_generator = read_lines_from_file(file_path)

    while True:
        try:
            log_line = next(message_generator)
        except StopIteration:
            print("End of file reached. Exiting.")
            break

        # Create payload
        payload = {"message": log_line}

        print(payload)
