import struct
from parser.parameters import ANSI_BOLD
from parser.parameters import ANSI_ESCAPE
from parser.parameters import ANSI_RED

"""
IMU Message data class. Assumes message parameter in constructor is a latin-1 decoded string.
Data fields are below:

REQUIRED (INFLUX) FIELDS:
    "Source": (list) "IMU"
    "Class": (list) A or G (for Accelerometer or Gyroscope)
    "Measurment": (list) X, Y, or Z (for the axis of the IMU)
    "Value": (list) value of the IMU message (rounded to 6 decimal places)
    "Timestamp": (list) timestamp of the IMU message 

DISPLAY FIELDS DICT:
    "display_data" : {
        "Type": (list) type of the IMU message (A or G),
        "Dimension": (list) dimension of the IMU message (X, Y, or Z),
        "Value": (list) value of the IMU message (rounded to 6 decimal places),
        "Timestamp": (list) timestamp of the IMU message
    }

self.type = "IMU"
"""
class IMU:
    def __init__(self, message: str) -> None:   
        # Parse all data fields and set type
        self.message = message
        self.data = self.extract_measurements()
        self.type = "IMU"


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
            exec_info = e.__traceback__.tb_lineno
            exec_file = e.__traceback__.tb_frame.f_code.co_filename
            raise Exception(
                f"{ANSI_BOLD}{exec_file} -> Failed at Line: {exec_info} in get_timestamp(){ANSI_ESCAPE}: \n"
                f"      Caught Exception = {e}, \n"
                f"      len(message_timestamp) = {len(message_timestamp)}"
            )
        

    """
    Gets the value of the message as a float

    Parameters:
        message_val - the value of the message as a latin-1 string
    
    Returns:
        float - the value of the message
    """
    def get_value(self, message_val) -> float:
        try:
            val = struct.unpack('>f', bytearray(message_val.encode('latin-1')))[0]
            float_val = float(val)

            return float_val
        except Exception as e:
            exec_info = e.__traceback__.tb_lineno
            exec_file = e.__traceback__.tb_frame.f_code.co_filename
            raise Exception(
                f"{ANSI_BOLD}{exec_file} -> Failed at Line: {exec_info} in get_value(){ANSI_ESCAPE}: \n"
                f"      Caught Exception = {e}, \n"
                f"      len(message_val) = {len(message_val)}"
            )
        
    """
    Extracts measurements from a IMU message based on a specified format
    Keys of the display_dict inside data dict are column headings.
    Values are data in columns.
    
    Parameters:
        None
                
    Returns:
        display_data dictionary with the form outlined in the class description
    """
    def extract_measurements(self,) -> dict:
        timestamp = None
        value = None
        id = None
        try:      
            timestamp = self.get_timestamp(self.message[:8])
            value = self.get_value(self.message[11:15])
            id = self.message[9:11]      # skip the @
        except Exception as e:
            raise Exception(
                f"Could not extract {ANSI_BOLD}IMU{ANSI_ESCAPE} message with properties: \n"
                f"      Message Length = {len(self.message)} \n"
                f"      Message Hex Data = {self.message.encode().hex()} \n"
                f"      {ANSI_RED}Error{ANSI_ESCAPE}: \n"
                f"      {e} \n"
                f"      {ANSI_BOLD}Function Call Details:{ANSI_ESCAPE} \n"
                f"        {ANSI_BOLD}get_timestamp( message[:8] = {self.message[:8].encode().hex()} ){ANSI_ESCAPE}, \n"
                f"          - Converts latin-1 arg to a 64 bit double \n"
                f"        {ANSI_BOLD}get_value( message[11:] = {self.message[11:15].encode().hex()} ){ANSI_ESCAPE},\n"
                f"          - Converts latin-1 arg to a 32 bit float \n"
                f"      {ANSI_BOLD}id (self.message[9:11]){ANSI_ESCAPE} = {self.message[9:11].encode().hex()}, \n"
            )

        data = {}
        
        # REQUIRED FIELDS
        data["Source"] = ["IMU"]
        data["Class"] = [id[0]]
        data["Measurement"] = [id[1]]
        data["Value"] = [round(value, 6)]
        data["Timestamp"] = [round(timestamp, 3)]

        # DISPLAY FIELDS
        data["display_data"] = {
            "Type": [id[0]],
            "Dimension": [id[1]],
            "Value": [round(value, 6)],
            "Timestamp": [round(timestamp, 3)],
        }
        
        return data

