import struct

"""
Subclass IMU implements the extract_measurements and getter
methods from the interface Message. Assumes message parameter in 
constructor is a UART message from the Radio Receiver (serial.readLine())
Data fields are below:

'timestamp': (string) timestamp of the IMU message (All D's right now)
'identifier':        (string) ID of the IMU message
'value':     (float) value of the IMU message (rounded to 6 decimal places)
'type':      (string) type of the IMU message (A or G)
'dimension': (string) dimension of the IMU message (X, Y, or Z)

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
        display_data dictionary with the following form
        {
            "Type": [],
            "Dimension": [],
            "Value": [],
            "ID":
        }
    """
    def extract_measurements(self, format_specifier=None) -> dict:
        # Extract the parts of the message
        timestamp = self.message[:8]
        id = self.message[9:11]      # skip the @
        data = self.message[11:]

        # Convert the data part to a 32-bit float
        value = struct.unpack('>f', bytearray(data.encode('latin-1')))[0]

        display_data = {
            "Type": [id[0]],
            "Dimension": [id[1]],
            "Value": [round(value, 6)],
            "Timestamp": [int(timestamp, 16)],
            "ID": id
        }

        return display_data


    def data(self) -> dict:
        return self.data

    def type(self) -> str:
        return self.type
        