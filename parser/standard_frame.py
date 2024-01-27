from dataclasses import dataclass
from typing import Union, List, Sized, Iterable, Any, Dict


@dataclass
class Measurement:
    """
    Encapsulates a single measurement parsed from a given CAN message.
    A single CAN message can be parsed into multiple measurements.
    """

    # the name of the value being measured
    name: str

    # category that the measurement falls under; often a single CAN ID maps to a single measurement category
    m_class: str

    # source CAN node of the message that contained the measurement
    source: str

    # value of the measurement
    value: Union[int, float, bool]


class StandardFrame:
    def __init__(self, id: str, data: str, timestamp: str, data_len: str):
        """
        Encapsulates a single standard CAN frame.

        Parameters:
            id: the ID of the CAN message (0x000 - 0x7ff)
            data: the payload of the CAN message
            timestamp: the timestamp of the CAN message
            data_len: the number of valid bytes in the CAN message payload (0-8)
        """
        self.timestamp = int(timestamp, 16)     # 8 bytes
        self.identifier = int(id, 16)           # 4 bytes
        self.data_len = int(data_len, 16)       # 1 byte

        self.hex_identifier = "0x" + hex(self.identifier)[2:].upper()

        self.data = list(data)            # 16 bytes

        # use this to decode the message
        self.data_bytes: bytes = bytearray(self.data)

        self.hex_data = list(map(lambda x: hex(x), self.data))

        # separated into bytes (each byte represented in binary)
        self.bytestream = list(map(lambda x: "{0:08b}".format(x), self.data))

        # single binary number representing the CAN message data
        self.bitstream = "".join(self.bytestream)

    def __init__(self, id: str, data: str, timestamp: str, data_len: str):
        """
        Encapsulates a single standard CAN frame.

        Parameters:
            id: the ID of the CAN message (0x000 - 0x7ff)
            data: the payload of the CAN message
            timestamp: the timestamp of the CAN message
            data_len: the number of valid bytes in the CAN message payload (0-8)
        """
        self.timestamp = int(timestamp, 16)     # 8 bytes
        self.identifier = int(id, 16)           # 4 bytes
        self.data_len = int(data_len, 16)       # 1 byte

        self.hex_identifier = "0x" + hex(self.identifier)[2:].upper()

        self.data = list(map(lambda x: ord(x), data))            # 16 bytes
        self.hex_data = list(map(lambda x: hex(x), self.data))
        # separated into bytes (each byte represented in decimal)

        self.data_bytes: bytes = bytearray(map(lambda x: ord(x), data))

        # separated into bytes (each byte represented in binary)
        self.bytestream = list(map(lambda x: "{0:08b}".format(ord(x)), data))

        # single binary number representing the CAN message data
        self.bitstream = "".join(self.bytestream)

    def __repr__(self):
        """ Provides a string representation of the CAN message """

        repr_str = str()

        repr_str += f"{self.hex_identifier=}\n"
        repr_str += f"{self.timestamp=}\n"
        repr_str += f"{self.data_len=}\n"
        repr_str += f"{self.data=}\n"
        repr_str += f"{self.data_bytes.hex()=}\n"
        repr_str += f"{self.hex_data=}\n"
        repr_str += f"{self.bytestream=}\n"
        repr_str += f"{self.bitstream=}\n"

        return repr_str

    def extract_measurements(self, dbc) -> List[Measurement]:
        """
        Extracts measurements from the CAN message depending on the entries in
        the provided DBC file. Returns a list of measurement objects.
        """

        # TODO: make this raise a custom exception

        # decode message using DBC file
        measurements = dbc.decode_message(self.identifier, self.data_bytes)

        message = dbc.get_message_by_frame_id(self.identifier)

        # where the data came from
        sources: list = message.senders

        source: str
        if len(sources) == 0:
            source = "UNKNOWN"
        else:
            source = sources[0]

        measurement_list: List[Measurement] = list()

        for name, data in measurements.items():
            # build Measurement object
            new_measurement = Measurement(name=name, m_class=message.name, source=source, value=data)

            # append measurement to list
            measurement_list.append(new_measurement)

        return measurement_list

    def extract_measurements_dict(self, dbc) -> Dict:
        """
        Extracts measurements from the CAN message depending on the entries in
        the provided DBC file. Returns a dictionary with measurement names as keys.

        NOTE: This is the legacy `extract_measurements` function. It has been kept
        because changing this would mean considerable changes to the existing parser tests.
        """

        # decode message using DBC file
        measurements = dbc.decode_message(self.identifier, self.data_bytes)

        message = dbc.get_message_by_frame_id(self.identifier)

        # where the data came from
        sources: list = message.senders

        source: str
        if len(sources) == 0:
            source = "UNKNOWN"
        else:
            source = sources[0]

        measurement_dict: Dict = dict()

        for name, data in measurements.items():
            measurement_dict[name] = dict()
            measurement_dict[name]["class"] = message.name
            measurement_dict[name]["source"] = source
            measurement_dict[name]["value"] = data

        return measurement_dict

    @staticmethod
    def chunks(lst: Sized, n: int) -> Iterable[Any]:
        """Yield successive n-sized chunks from list."""

        for i in range(0, len(lst), n):
            yield lst[i: i + n]

hex_strings = ['0xDE', '0xAD', '0xBE', '0xEF', '0xDE', '0xAD', '0xBE', '0xEF']
char_string = ''.join(chr(int(hex_str, 16)) for hex_str in hex_strings)
can_msg = StandardFrame("111", char_string, "CCCCCCCC", "8")
print(can_msg)