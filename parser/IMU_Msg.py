import struct

"""
Subclass IMU implements the extract_measurements and getter
methods from the interface Message. Assumes message parameter in 
constructor is a UART message from the Radio Receiver (serial.readLine())
Data fields are below:

REQUIRED FIELDS:
    "Source": (list) "IMU"
    "Class": (list) A or G (for Accelerometer or Gyroscope)
    "Measurment": (list) X, Y, or Z (for the axis of the IMU)
    "Value": (list) value of the IMU message (rounded to 6 decimal places)
    "ID": Chosen to be 'Type + Dimension'

DISPLAY FIELDS DICT:
    "display_data" : {
        "Type": (list) type of the IMU message (A or G),
        "Dimension": (list) dimension of the IMU message (X, Y, or Z),
        "Value": (list) value of the IMU message (rounded to 6 decimal places),
        "Timestamp": (list) timestamp of the IMU message (All D's right now)
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
    Extracts measurements from a IMU message based on a specified format
    Keys of the dict are column headings. Values are data (as strings) in column.
    
    Parameters:
        format_specifier: None for IMU messages (as of now)
        
    Returns:
        display_data dictionary with the form outlined in the class description
    """
    def extract_measurements(self, format_specifier=None) -> dict:
        # Extract the parts of the message
        timestamp = self.message[:8]
        id = self.message[9:11]      # skip the @
        val = self.message[11:]

        # Convert the val part to a 32-bit float
        value = struct.unpack('>f', bytearray(val.encode('latin-1')))[0]

        data = {}
        
        # REQUIRED FIELDS
        data["Source"] = ["IMU"]
        data["Class"] = [id[0]]
        data["Measurement"] = [id[1]]
        data["Value"] = [round(value, 6)]
        data["ID"] = id

        # DISPLAY FIELDS
        data["display_data"] = {
            "Type": [id[0]],
            "Dimension": [id[1]],
            "Value": [round(value, 6)],
            "Timestamp": [int(timestamp, 16)],
        }
        
        return data


    def data(self) -> dict:
        return self.data

    def type(self) -> str:
        return self.type
        