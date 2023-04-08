import serial
import cantools
import influxdb_client
from influxdb_client.client.write_api import ASYNCHRONOUS
from pathlib import Path
import pprint
import random
import pynmea2
from enum import Enum
from random import randrange
import time
from nmeasim.simulator import Simulator
import argparse

import asyncio
import websockets

from core.standard_frame import StandardFrame

from dotenv import dotenv_values

# <----- Msg Type ----->
class MsgType(Enum):
    MSG_TYPE_CAN = 0
    MSG_TYPE_IMU = 1
    MSG_TYPE_GPS = 2
        
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

sim = Simulator()
with sim.lock:
    sim.gps.output = ("GGA", "GLL")
    
# <----- Randomizer functions ------>
def random_imu_str(dbc) -> str:
    random_axis = random.choice(["A", "G"])
    random_type = random.choice(["X", "Y", "Z"])
    # random data
    random_data = random.randint(0, pow(2, 64))
    random_data_str = "{0:0{1}x}".format(random_data, 16)
    
    imu_str = "@" + random_type + random_axis + "," + random_data_str + "\n"
    return imu_str
    
def random_gps_str(dbc) -> str:
    return list(sim.get_output(1))[0]
    
    
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
    

# <---- msg parse functions --->

def can_parse(message, daybreak_dbc):
    can_msg = StandardFrame(raw_string=message)
    extracted_measurements = can_msg.extract_measurements(daybreak_dbc)
    return can_msg, extracted_measurements

def imu_parse(message, daybreak_dbc):
    extracted_measurements = dict()
    extracted_measurements["axis"] = message[1:2].decode('UTF-8')
    extracted_measurements["type"] = message[2:3].decode('UTF-8')
    extracted_measurements["value"] = float.fromhex(message[4:20].decode("utf-8"))
    return message, extracted_measurements
    
def gps_parse(message, daybreak_dbc):
    return message, pynmea2.parse(message.decode('UTF-8'))
    
# <---- msg misc functions ---->

MSG_TABLE = {
    MsgType.MSG_TYPE_CAN : (random_can_str, can_parse),
    MsgType.MSG_TYPE_IMU : (random_imu_str, imu_parse),
    MsgType.MSG_TYPE_GPS : (random_gps_str, gps_parse)
}

def random_str(dbc) -> str:  
    msg_type = random.choice(list(MsgType))
    return MSG_TABLE[msg_type][0](dbc)


def get_msg_type(msg) -> MsgType:
    if msg[0] == 64:
        return MsgType.MSG_TYPE_IMU
    elif msg[0] == 36:
        return MsgType.MSG_TYPE_GPS
    
    return MsgType.MSG_TYPE_CAN

def get_imu_field(axis, dev) -> str:
    print(axis + "_" + dev)
    return axis + "_" + dev
    
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
            message = random_str(daybreak_dbc)
            message = message.encode(encoding="UTF-8")
         #   time.sleep(0.5)
            input("Press Enter to continue...")
        else:
            with serial.Serial() as ser:
                # <----- Configure COM port ----->
                ser.baudrate = args.baudrate
                ser.port = args.port
                ser.open()

                # read in bytes from COM port
                message = ser.readline()

# stuff fro IMU messages and stuff? Nmea can have up to 128 characters...
# need better error handling
 #               for x in MSG_TABLE:
 #                   if len(message)
 #               print(
 #                   f"WARNING: got message length {len(message)}, expected {StandardFrame.EXPECTED_CAN_MSG_LENGTH}. Dropping message...")
 #               print(message)
 #               continue

        msg_type = get_msg_type(message)

        # extract measurements from CAN message
        try:
            msg, extracted_measurements = MSG_TABLE[msg_type][1](message, daybreak_dbc)
            
            print(msg_type)
            print(msg)
            pp.pprint(extracted_measurements)
            
        except ValueError as exc:
            print(exc)
            continue

        if msg_type == MsgType.MSG_TYPE_CAN:
            for measurement, data in extracted_measurements.items():
                source = data["source"]
                m_class = data["class"]
                value = data["value"]
          
                # write measurements to InfluxDB
                p = influxdb_client.Point(source).tag("car", CAR_NAME).tag(
                    "class", m_class).field(measurement, value)
                # print(p)
                write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=p)
        
        
        elif msg_type == MsgType.MSG_TYPE_IMU:
            p = influxdb_client.Point("imu").tag("car", CAR_NAME).field(get_imu_field(extracted_measurements["axis"], extracted_measurements["type"]), extracted_measurements["value"]) # extracted_measurements["value"]  
            #     measurement is field (x_accel), value is value, m_class is like imu or smth
            print(p)
            write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=p)
         # 
        elif msg_type == MsgType.MSG_TYPE_GPS:
            # pg 11 Any message type can be enabled
            parse = vars(extracted_measurements)
            print(parse["data"][0])
            #python link_telemetry.py -d

            # assume msg type is GGA, but CAN BE anything hence just hardcoded basic fields here
            if parse["sentence_type"] == 'GGA':
                #p = influxdb_client.Point("gps").tag("car", CAR_NAME).field("time", parse["data"][0]) # extracted_measurements["value"]
                p = influxdb_client.Point("gps").tag("car", CAR_NAME).tag("talker", parse["talker"]).tag("msg_type", parse["sentence_type"]).field("BYE", int(float(parse["data"][0])))
                #     measurement is field (x_accel), value is value, m_class is like imu or smth

                write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=p)
            

        print()
        


if __name__ == "__main__":
    asyncio.run(main())
