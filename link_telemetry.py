import serial
import sys
import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS
from pathlib import Path
import yaml
import pprint
import struct
import random
import time
import argparse

# <----- Constants ----->

SERVER_NAME = "http://localhost:3000"
YAML_FILE = Path("can.yaml")
CAR_NAME = "Daybreak"

# <----- InfluxDB constants ----->

BUCKET = "Telemetry"
ORG = "UBC Solar"
TOKEN = "PZreIdWtOD02sk3RQTraXtCkazjI7VPPw8E_1NSPe_9TVt9JwjbW5h3xSNj5N9uoevmXMs8gAQrMrhqH57AKhQ=="
URL = "http://localhost:8086"

# <----- Server start-ups ----->

# TODO: start InfluxDB server here
# TODO: start Grafana server here

# <----- Class definitions ------>


class CANMessage:
    EXPECTED_CAN_MSG_LENGTH = 30

    def __init__(self, raw_string: bytes):
        assert len(raw_string) == CANMessage.EXPECTED_CAN_MSG_LENGTH, \
            f"raw_string not expected length of {EXPECTED_CAN_MSG_LENGTH}"

        self.timestamp = int(raw_string[0:8].decode(), 16)        # 8 bytes
        self.identifier = int(raw_string[8:12].decode(), 16)      # 4 bytes
        self.data_len = int(raw_string[28:29].decode(), 16)       # 1 byte

        self.hex_identifier = "0x" + hex(self.identifier)[2:].upper()

        data = list(self.chunks(raw_string[12:28], 2))            # 16 bytes
        data = list(map(bytes.decode, data))

        # separated into bytes (each byte represented in decimal)
        self.data = list(map(lambda x: int(x, 16), data))

        # separated into bytes (each byte represented in binary)
        self.bytestream = list(map(lambda x: "{0:08b}".format(x), self.data))

        # single binary number representing the CAN message data
        self.bitstream = "".join(self.bytestream)

    def __repr__(self):
        """ Provides a string representation of the CAN message """

        repr_str = str()

        repr_str += f"{self.hex_identifier=}\n"
        repr_str += f"{self.timestamp=}\n"
        repr_str += f"{self.data_len=}\n"
        repr_str += f"{self.data=}\n"
        repr_str += f"{self.bytestream=}\n"
        repr_str += f"{self.bitstream=}\n"

        return repr_str

    def extract_measurements(self, schema: dict):
        """
        Extracts measurements from the CAN message depending on the entries in
        the `schema` dict. Returns a measurement dict with the key as the measurement name
        and the value as a dict containing data about the given measurement.

        Raises exception if schema does not contain key entry that matches `self.identifier`.
        """

        # retrieve schema data for CAN ID
        schema_data = schema.get(self.hex_identifier)

        if schema_data is None:
            raise ValueError(
                f"WARNING: Schema not found for id={self.hex_identifier}, make entry in {YAML_FILE}\n")

        measurements = schema_data.get("measurements")

        # where the data came from
        source = schema_data.get("source")

        # the "name" of the CAN message
        measurement_class = schema_data.get("name")

        measurement_dict = dict()

        for name, data in measurements.items():
            bits = data["bits"]
            measurement_type = data["type"]

            measurement_dict[name] = dict()

            # extract measurement from CAN message bitstream

            # if only a single bound is provided, extract single bit
            if len(bits) == 1:
                bit_index = bits[0]
                extracted_value = self.bitstream[bit_index]

            # if both bounds are provided, extract range of bits
            if len(bits) == 2:
                lower = bits[0]
                upper = bits[1]

                # lower and upper are both inclusive bounds
                extracted_value = self.bitstream[lower:upper+1]

            # convert binary bitstream values to integers
            processing_fn = TYPE_PROCESSING_MAP.get(measurement_type)

            if processing_fn is None:
                raise ValueError(
                    f"WARNING: no entry for {measurement_type} found in {TYPE_PROCESSING_MAP=}\n")

            processed_value = processing_fn(extracted_value)

            # place into measurement dictionary
            measurement_dict[name]["source"] = source
            measurement_dict[name]["class"] = measurement_class
            measurement_dict[name]["value"] = processed_value

        return measurement_dict

    @staticmethod
    def chunks(lst, n):
        """Yield successive n-sized chunks from list."""

        for i in range(0, len(lst), n):
            yield lst[i: i+n]

    @staticmethod
    def twos_complement8(byte: str):
        """
        Interprets byte as two's complement signed integer.
        NOTE: Byte is assumed to be big-endian (MSB first)
        """

        assert len(byte) == 8, "`byte` argument must be length 8"

        sign = int(byte[0], 2)
        tail = int(byte[1:], 2)

        # if number is negative
        if sign == 1:
            # invert and add one
            invert_tail = 127 - tail
            value = invert_tail + 1
            return -1 * value

        return tail

    @staticmethod
    def twos_complement16(word: str):
        """
        Interprets word as two's complement signed integer.
        NOTE: Word is assumed to be big-endian (MSB first)
        """

        assert len(word) == 16, "`word` argument must be length 16"

        sign = int(word[0], 2)
        tail = int(word[1:], 2)

        # if number is negative
        if sign == 1:
            # invert and add one
            invert_tail = 32767 - tail
            value = invert_tail + 1
            return -1 * value

        return tail

    @staticmethod
    def ieee32_to_float(dword: str):
        i = int(dword, 2)
        return struct.unpack("f", struct.pack("I", i))[0]


TYPE_PROCESSING_MAP = {
    "bool": lambda x: True if int(x, 2) == 1 else False,
    "unsigned": lambda x: int(x, 2),
    "signed_8": CANMessage.twos_complement8,
    "signed_16": CANMessage.twos_complement16,
    "incremental": lambda x: int(x, 2) * 0.1,
    "ieee32_float": lambda x: round(CANMessage.ieee32_to_float(x), 2)
}


def random_can_str(can_schema) -> str:
    can_ids = list(can_schema.keys())

    # 0 to 2^32
    random_timestamp = random.randint(0, pow(2, 32))
    random_timestamp_str = "{0:0{1}x}".format(random_timestamp, 8)

    # random identifier
    random_identifier = int(random.choice(can_ids)[2:], 16)
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
        description="Link raw radio stream to frontend telemetry interface.")

    normal_group = parser.add_argument_group("Normal operation")
    debug_group = parser.add_argument_group("Debug operation")

    debug_group.add_argument("-d", "--debug", action="store_true", help=("Enables debug mode. This allows using the "
                                                                         "telemetry link with randomly generated CAN "
                                                                         "data rather using an actual radio telemetry stream"))

    normal_group.add_argument("-p", "--port", action="store",
                              help=("Specifies the serial port to read radio data from. "
                                    "Typical values include: COM5, /dev/ttyUSB0, etc."))
    normal_group.add_argument("-b", "--baudrate", action="store",
                              help=("Specifies the baudrate for the serial port specified. "
                                    "Typical values include: 9600, 115200, 230400, etc."))

    args = parser.parse_args()

    if args.debug:
        if args.port or args.baudrate:
            parser.error("-d cannot be used with -p and -b options")
    else:
        if not (args.port and args.baudrate):
            parser.error("-p and -b options must both be specified")

    pp = pprint.PrettyPrinter(indent=1)

    # <----- InfluxDB object set-up ----->

    client = influxdb_client.InfluxDBClient(url=URL, org=ORG, token=TOKEN)
    write_api = client.write_api(write_options=SYNCHRONOUS)

    # <----- Read in YAML CAN schema file ----->

    with open(YAML_FILE, "r") as f:
        can_schema: dict = yaml.safe_load(f)

    while True:
        if args.debug:
            message = random_can_str(can_schema)
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

                if len(message) != CANMessage.EXPECTED_CAN_MSG_LENGTH:
                    print(
                        f"WARNING: got message length {len(message)}, expected {CANMessage.EXPECTED_CAN_MSG_LENGTH}. Dropping message...")
                    print(message)
                    continue

        can_msg = CANMessage(raw_string=message)

        # extract measurements from CAN message
        try:
            extracted_measurements = can_msg.extract_measurements(can_schema)
            print(can_msg)
            pp.pprint(extracted_measurements)
        except ValueError as exc:
            print(exc)
            continue

        # write all measurements to InfluxDB database
        for measurement, data in extracted_measurements.items():
            source = data["source"]
            m_class = data["class"]
            value = data["value"]

            p = influxdb_client.Point(source).tag("car", CAR_NAME).tag(
                "class", m_class).field(measurement, value)
            print(p)

            write_api.write(bucket=BUCKET, org=ORG, record=p)

        print()


if __name__ == "__main__":
    main()
