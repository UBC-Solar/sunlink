# Superclass import
from Message import Message, Measurement


"""
Subclass CAN implements the extract_measurements and getter
methods from the interface Message. Data fields are:

'timestamp':      the timestamp of the CAN message (All D's right now)
'identifier':     the ID of the CAN message (0x000 - 0x7ff)
'data_len':       the number of valid bytes in the CAN message payload (0-8)
'hex_identifier': the ID of the CAN message in hex
'data_list':      the payload of the CAN message as a list of ints
'data_bytes':     the payload of the CAN message as a bytearray
'hex_data':       the payload of the CAN message separated into bytes (hex)
'bytestream':     the payload of the CAN message separated into bytes (binary)
'bitstream':      the payload of the CAN message as a single binary number

self.type = "CAN"
"""
class CAN(Message):
    """
    CREDIT: Mihir. N for his implementation
    CHANGES:
        data field is now 8 bytes (Before: FF is sent as 2 letter Fs, now it is sent as 1 byte char with value 255)
    """
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

        self.data_list = list(map(lambda x: ord(x), data))            # 16 bytes
        self.hex_data = list(map(lambda x: hex(x), self.data_list))
        # separated into bytes (each byte represented in decimal)

        self.data_bytes: bytes = bytearray(map(lambda x: ord(x), data))

        # separated into bytes (each byte represented in binary)
        self.bytestream = list(map(lambda x: "{0:08b}".format(ord(x)), data))

        # single binary number representing the CAN message data
        self.bitstream = "".join(self.bytestream)

        # Create dictionary for data and set the type
        self.data = {
            "timestamp": self.timestamp,
            "identifier": self.identifier,
            "data_len": self.data_len,
            "hex_identifier": self.hex_identifier,
            "data_list": self.data_list,
            "data_bytes": self.data_bytes.hex(),
            "hex_data": self.hex_data,
            "bytestream": self.bytestream,
            "bitstream": self.bitstream
        }

        self.type = "CAN"


    """
    CREDIT: Mihir. N for this method's implementation

    Extracts measurements from the CAN message depending on the entries in
    the provided DBC file. Returns a list of measurement objects.
    """
    def extract_measurements(self, format_specifier) -> list[Measurement]:
        # TODO: make this raise a custom exception

        # decode message using DBC file
        measurements = format_specifier.decode_message(self.identifier, self.data_bytes)

        message = format_specifier.get_message_by_frame_id(self.identifier)

        # where the data came from
        sources: list = message.senders

        source: str
        if len(sources) == 0:
            source = "UNKNOWN"
        else:
            source = sources[0]

        measurement_list: list[Measurement] = list()

        for name, data in measurements.items():
            # build Measurement object
            new_measurement = Measurement(name=name, m_class=message.name, source=source, value=data)

            # append measurement to list
            measurement_list.append(new_measurement)

        return measurement_list

    def data(self) -> dict:
        return self.data

    def type(self) -> str:
        return self.type
