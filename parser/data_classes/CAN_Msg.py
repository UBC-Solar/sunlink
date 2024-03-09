import struct
from parser.parameters import CAR_DBC
from parser.parameters import ANSI_BOLD
from parser.parameters import ANSI_ESCAPE
from parser.parameters import ANSI_RED

"""
CAN Message data class. Data fields are:

REQUIRED (INFLUX) FIELDS:
    "Source": (list) The board which the message came from
    "Class": (list) The class of the message (Ex. Voltage Sensors Data)
    "Measurment": (list) Specifc measurement name in this class (Ex. Volt Sensor 1, Volt Sensor 2)
    "Value": (list) The value of the associated measurement
    "Timestamp": (list) The time the message was sent

DISPLAY FIELDS:
    "display_data" : {
        "Hex_ID": (list) The ID of the CAN message in hex
        "Source": (list) The board which the message came from
        "Class": (list) The class of the message (Ex. Voltage Sensors Data)
        "Measurment": (list) Specifc measurement name in this class (Ex. Volt Sensor 1, Volt Sensor 2)
        "Value": (list) The value of the associated measurement
    }

self.type = "CAN"
"""
class CAN:
    """
    CREDIT: Mihir. N for his implementation
    CHANGES:
        data field is now 8 bytes (Before: FF is sent as 2 letter Fs, now it is sent as 1 byte char with value 255)
    """
    def __init__(self, message: str) -> None: 
        self.message = message  
        self.data = self.extract_measurements()
        self.type = "CAN"


    """
    Gets the timestamp of the message as a float

    Parameters:
        message_timestamp - the timestamp of the message as a latin-1 string
    
    Returns:
        float - the timestamp of the message
    """
    def get_timestamp(self, message_timestamp) -> float:
        try:
            timestamp = struct.unpack('>d', message_timestamp.encode('latin-1'))[0]
            float_timestamp = float(timestamp)

            return float_timestamp
        except Exception as e:
            raise Exception(
                f"{ANSI_BOLD}Failed TIMESTAMP{ANSI_ESCAPE}. -> {e}, "
                f"input = {message_timestamp}, "
                f"len(input) = {len(message_timestamp)}"
            )
        

    """
    Gets the hex id of the message
    
    Parameters:
        message_id - the id of the message as a latin-1 string
    
    Returns:
        string - the id of the message in hex
    """
    def get_hex_id(self, message_id) -> str:
        try:
            identifier = int.from_bytes(message_id.encode('latin-1'), 'big')
            hex_id = "0x" + hex(identifier)[2:].upper()

            return hex_id
        except Exception as e:
            raise Exception(
                f"{ANSI_BOLD}Failed HEX_ID{ANSI_ESCAPE}. -> {e}, "
                f"input = {message_id}, "
                f"len(input) = {len(message_id)}"
            )
        
    
    """
    Converts the message data to a bytearray
    
    Parameters:
        message_data - the data of the message as a latin-1 string
    
    Returns:
        bytearray - the data of the message as a bytearray
    """
    def get_data_bytes(self, message_data) -> bytearray:
        try:
            data_bytes = bytearray(map(lambda x: ord(x), message_data))

            return data_bytes   
        except Exception as e:
            raise Exception(
                f"{ANSI_BOLD}Failed DATA_BYTES{ANSI_ESCAPE}. -> {e}, "
                f"input = {message_data}, "
                f"len(input) = {len(message_data)}"
            )

    """
    Try to decode the message using the DBC file
    
    Parameters:
        identifier - the integer id of the message
        data_bytes - the data of the message as a byte array
        
    Returns:
        cantools measurements object
    """    
    def get_measurements(self, identifier, data_bytes):
        try:
            measurements = CAR_DBC.decode_message(identifier, data_bytes)
            return measurements
        except Exception as e:
            raise Exception(
                f"{ANSI_BOLD}Failed decode_message{ANSI_ESCAPE}. -> {e}, "
                f"input.databytes = {data_bytes}, input.identifier = {identifier},"
                f"len(input.databytes) = {len(data_bytes)}, len(input.identifier) = {len(identifier)}"
            )
        

    """
    Try to get the message from the DBC file
    
    Parameters:
        identifier - the integer id of the message
    
    Returns:
        cantools message object
    """
    def get_message(self, identifier):
        try:
            message = CAR_DBC.get_message_by_frame_id(identifier)
            return message
        except Exception as e:
            raise Exception(
                f"{ANSI_BOLD}Failed get_message_by_frame_id{ANSI_ESCAPE}. -> {e}, "
                f"input = {identifier}, "
                f"len(input) = {len(identifier)}"
            )

    """
    CREDIT: Mihir. N and Aarjav. J
    Will create a dictionary whose display_dict key is another dictionary.
    This nested dictionary contains are the column headings to the pretty table
    and whose values are data in those columns. 
    The list will be the same length as the number of rows in the pretty table.
    This is done to match list length to number of measurement in CAN message to list
    
    Parameters:
        None
        
    Returns:
        display_data dictionary with form outlined in the class description
    """
    def extract_measurements(self) -> dict:
        try:      
            timestamp = self.get_timestamp(self.message[:8])
            hex_id = self.get_hex_id(self.message[9:13])
            data_bytes = self.get_data_bytes(self.message[13:21])
            measurements = self.get_measurements(int(hex_id, 16), data_bytes)
            message = self.get_message(int(hex_id, 16))
        except Exception as e:
            raise Exception(
                f"Could not extract {ANSI_BOLD}CAN{ANSI_ESCAPE} message \n"
                f"    Length = {len(self.message)}) {self.message.encode().hex()} \n"
                f"    Hex Data = {self.message.encode().hex()} \n"
                f"    {ANSI_RED}Error{ANSI_ESCAPE}: \n {e}"
                f"      {e}"
            )
        
        # where the data came from
        sources: list = message.senders

        source: str
        if len(sources) == 0:
            source = "UNKNOWN"
        else:
            source = sources[0]

        # Initilization
        data = {
            "Source": [],
            "Class": [],
            "Measurement": [],
            "Value": [],
            "Timestamp": [],
            "display_data": {   
                "Hex_ID": [],
                "Source": [],
                "Class": [],
                "Measurement": [],
                "Value": [],
                "Timestamp": []
            }
        }

        # Now add each field to the list
        for name, dbc_data in measurements.items():
            # REQUIRED FIELDS
            data["Source"].append(source)
            data["Class"].append(message.name)
            data["Measurement"].append(name)
            data["Value"].append(dbc_data)
            data["Timestamp"].append(round(timestamp, 3))
        
            # DISPLAY FIELDS
            data["display_data"]["Hex_ID"].append(hex_id)
            data["display_data"]["Source"].append(source)
            data["display_data"]["Class"].append(message.name)
            data["display_data"]["Measurement"].append(name)
            data["display_data"]["Timestamp"].append(round(timestamp, 3))
            data["display_data"]["Value"].append(dbc_data)

        return data

