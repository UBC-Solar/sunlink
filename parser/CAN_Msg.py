"""
Subclass CAN implements the extract_measurements and getter
methods from the interface Message. Data fields are:

'timestamp':      the timestamp of the CAN message (All D's right now)
'identifier':     the ID of the CAN message in decimal
'data_len':       the number of valid bytes in the CAN message payload (0-8)
'hex_identifier': the ID of the CAN message in hex (0x000 - 0x7ff)
'data_list':      the payload of the CAN message as a list of ints
'data_bytes':     the payload of the CAN message as a bytearray
'hex_data':       the payload of the CAN message separated into bytes (hex)
'bytestream':     the payload of the CAN message separated into bytes (binary)
'bitstream':      the payload of the CAN message as a single binary number

self.type = "CAN"
"""
class CAN:
    """
    CREDIT: Mihir. N for his implementation
    CHANGES:
        data field is now 8 bytes (Before: FF is sent as 2 letter Fs, now it is sent as 1 byte char with value 255)
    """
    def __init__(self, message: str, format_specifier=None) -> None:    
        self.message = message  
        self.data2 = self.extract_measurements(format_specifier)
        self.type = "CAN"


    """
    CREDIT: Mihir. N and Aarjav. J
    Will create a dictionary whose keys are the column headings to the pretty table
    and whose values are data in those columns. Dictionary is string to list.
    The list will be the same length as the number of rows in the pretty table.
    This is done to match list length to number of measurement in CAN message to list
    
    Parameters:
        format_specifier: file path to a file containing a format specifier
        
    Returns:
        display_data dictionary with the following form
        {
            "Hex ID": [hex id1, hex id1, hex id1, ...],
            "Source": [source1, source1, source1, ...],
            "Class": [class1, class1, class1, ...],
            "Measurment": [measurement1, measurement2, measurement3, ...],
            "Value": [value1, value2, value3, ...]
            "ID": hex id1
        }
    """
    def extract_measurements(self, format_specifier=None) -> dict:      
        timestamp: str = self.message[0:8]
        id: str = self.message[8:12]
        data: str = self.message[12:20]
        data_len: str = self.message[20:21]

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
            "data_bytes": self.data_bytes,
            "hex_data": self.hex_data,
            "bytestream": self.bytestream,
            "bitstream": self.bitstream
        }

        measurements = format_specifier.decode_message(self.data["identifier"], self.data["data_bytes"])
        message = format_specifier.get_message_by_frame_id(self.data["identifier"])

        # where the data came from
        sources: list = message.senders

        source: str
        if len(sources) == 0:
            source = "UNKNOWN"
        else:
            source = sources[0]

        # Initilization
        display_data = {
            "Hex ID": [],
            "Source": [],
            "Class": [],
            "Measurement": [],
            "Value": [],
            "ID": self.data["hex_identifier"]
        }

        # Now add each field to the list
        for name, data in measurements.items():
            display_data["Hex ID"].append(self.data["hex_identifier"])
            display_data["Source"].append(source)
            display_data["Class"].append(message.name)
            display_data["Measurement"].append(name)
            display_data["Value"].append(data)
        
        return display_data

    def data(self) -> dict:
        return self.data

    def type(self) -> str:
        return self.type
