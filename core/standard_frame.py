from typing import Iterable


class StandardFrame:
    EXPECTED_CAN_MSG_LENGTH = 30

    def __init__(self, id: str, data: str, timestamp: str, data_len: str):
        self.timestamp = int(timestamp, 16)     # 8 bytes
        self.identifier = int(id, 16)           # 4 bytes
        self.data_len = int(data_len, 16)       # 1 byte

        self.hex_identifier = "0x" + hex(self.identifier)[2:].upper()

        self.data = list(self.chunks(data, 2))            # 16 bytes
        # self.data = list(map(bytes.decode, self.data))

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

    def extract_measurements(self, dbc):
        """
        Extracts measurements from the CAN message depending on the entries in
        the `schema` dict. Returns a measurement dict with the key as the measurement name
        and the value as a dict containing data about the given measurement.

        Raises exception if schema does not contain key entry that matches `self.identifier`.
        """

        # decode message using DBC file
        measurements = dbc.decode_message(self.identifier, self.data_bytes)

        message = dbc.get_message_by_frame_id(self.identifier)

        # where the data came from
        sources: list = message.senders
        source: str = sources[0]

        measurement_dict = dict()

        for name, data in measurements.items():
            measurement_dict[name] = dict()
            measurement_dict[name]["class"] = message.name
            measurement_dict[name]["source"] = source
            measurement_dict[name]["value"] = data

        return measurement_dict

    @staticmethod
    def chunks(lst: Iterable, n: int) -> Iterable[str]:
        """Yield successive n-sized chunks from list."""

        for i in range(0, len(lst), n):
            yield lst[i: i+n]
