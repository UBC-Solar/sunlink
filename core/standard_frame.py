from typing import Iterable
from dataclasses import dataclass
from typing import Union, List


@dataclass
class Measurement:
    """
    Encapsulates a single measurement parsed from a given CAN message.
    A single CAN message can be parsed into multiple measurements.
    """

    # the name of the value being measured
    name: str

    # category that the measurement falls under
    m_class: str

    # source CAN node of the message that contained the measurement
    source: str

    # value of the measurement
    value: Union[int, float, bool]


class StandardFrame:
    EXPECTED_CAN_MSG_LENGTH = 30

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

        self.data = list(self.chunks(data, 2))            # 16 bytes

        # separated into bytes (each byte represented in decimal)
        self.data = list(map(lambda x: int(x, 16), self.data))

        # use this to decode the message
        self.data_bytes: bytes = bytearray(self.data)

        self.hex_data = list(map(lambda x: hex(x), self.data))

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

        # decode message using DBC file
        measurements = dbc.decode_message(self.identifier, self.data_bytes)

        # TODO: wrap in try-except
        message = dbc.get_message_by_frame_id(self.identifier)

        # where the data came from
        sources: list = message.senders
        source: str = sources[0]

        measurement_list: List[Measurement] = list()

        for name, data in measurements.items():
            # build Measurement object
            new_measurement = Measurement(name=name, m_class=message.name, source=source, value=data)

            # append measurement to list
            measurement_list.append(new_measurement)

        return measurement_list

    @staticmethod
    def chunks(lst: Iterable, n: int) -> Iterable[str]:
        """Yield successive n-sized chunks from list."""

        for i in range(0, len(lst), n):
            yield lst[i: i+n]
