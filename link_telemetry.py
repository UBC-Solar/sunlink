import serial
import cantools
import influxdb_client
from influxdb_client.client.write_api import ASYNCHRONOUS
from pathlib import Path
import pprint
import random
import time
import argparse

import asyncio
import websockets

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


async def main():

    # <----- Argument parsing ----->

    parser = argparse.ArgumentParser(
        description="Link raw radio stream to frontend telemetry interface.")

    normal_group = parser.add_argument_group("Normal operation")
    debug_group = parser.add_argument_group("Debug operation")

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

    args = parser.parse_args()

    # <----- Argument validation ----->

    if args.debug:
        if args.port or args.baudrate:
            parser.error("-d cannot be used with -p and -b options")
    else:
        if not (args.port and args.baudrate):
            parser.error("-p and -b options must both be specified")

    pp = pprint.PrettyPrinter(indent=1)

    # <----- InfluxDB object set-up ----->

    client = influxdb_client.InfluxDBClient(
        url=INFLUX_URL, org=INFLUX_ORG, token=INFLUX_TOKEN)
    write_api = client.write_api(write_options=ASYNCHRONOUS)

    # <----- Read in DBC file ----->

    daybreak_dbc = cantools.database.load_file(DBC_FILE)

    while True:
        if args.debug:
            message = random_can_str(daybreak_dbc)
            message = message.encode(encoding="UTF-8")
            time.sleep(0.5)
        else:
            with serial.Serial() as ser:
                # <----- Configure COM port ----->
                ser.baudrate = args.baudrate
                ser.port = args.port
                ser.open()

                # read in bytes from COM port
                message = ser.readline()

                if len(message) != StandardFrame.EXPECTED_CAN_MSG_LENGTH:
                    print(
                        f"WARNING: got message length {len(message)}, expected {StandardFrame.EXPECTED_CAN_MSG_LENGTH}. Dropping message...")
                    print(message)
                    continue

        can_msg = StandardFrame(raw_string=message)

        # extract measurements from CAN message
        try:
            extracted_measurements = can_msg.extract_measurements(daybreak_dbc)
            print(can_msg)
            pp.pprint(extracted_measurements)
        except ValueError as exc:
            print(exc)
            continue

        for measurement, data in extracted_measurements.items():
            source = data["source"]
            m_class = data["class"]
            value = data["value"]

            # compute Grafana websocket URL to livestream measurement
            endpoint_name = "_".join([CAR_NAME, source, m_class, measurement])
            websocket_url = f"ws://{GRAFANA_URL_NAME}/api/live/push/{endpoint_name}"

            if args.no_write is False:
                # live-stream measurements to Grafana Live
                async with websockets.connect(websocket_url, extra_headers={'Authorization': f'Bearer {GRAFANA_TOKEN}'}) as websocket:
                    current_time = time.time_ns()
                    message = f"test value={value} {current_time}"
                    await websocket.send(message)

                # write measurements to InfluxDB
                p = influxdb_client.Point(source).tag("car", CAR_NAME).tag(
                    "class", m_class).field(measurement, value)
                # print(p)
                write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=p)

        print()


if __name__ == "__main__":
    asyncio.run(main())
