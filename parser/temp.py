"""
CAN message wrapper class. CAN.data[''] fields are:

"Hex_ID": Hex identifier of the CAN message
"Source": Source board. Ex. 'MCU', 'BMS', etc.
"Class": Class of the CAN message. Ex. 'BMS Status', etc.
"Measurment": The specifc name of the measurment at a specifc bit range. Ex. BMS Self Test Fault
"Value": The value of the measurment
"ID": Field used to ID every type of message. For CAN: Hex_ID

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

        # Create dictionary for data and set the type
        self.data = self.extract_measurements(format_specifier)
        self.type = "CAN"


    """
    CREDIT: Mihir. N and Aarjav. J
    Will create a dictionary whose keys are the column headings to the pretty table
    and whose values are data in those columns. Dictionary is string to list.
    The list will be the same length as the number of rows in the pretty table.
    This is done to match list length to number of measurement in CAN message to list
    
    Parameters:
        format_specifier: object or file path 
        
    Returns:
        dictionary with the following form
        {
            "Hex_ID": [hex id1, hex id1, hex id1, ...],
            "Source": [source1, source1, source1, ...],
            "Class": [class1, class1, class1, ...],
            "Measurment": [measurement1, measurement2, measurement3, ...],
            "Value": [value1, value2, value3, ...]
            "ID": hex id1
        }
    """
    def extract_measurements(self, format_specifier=None) -> dict:
        measurements = format_specifier.decode_message(int(self.message[8:12], 16), bytearray(map(lambda x: ord(x), self.message[12:20])))
        message = format_specifier.get_message_by_frame_id(int(self.message[8:12], 16))
        hex_id = "0x" + hex(self.message[8:12])[2:].upper()

        # where the data came from
        sources: list = message.senders

        source: str
        if len(sources) == 0:
            source = "UNKNOWN"
        else:
            source = sources[0]

        # Initilization
        display_data = {
            "Hex_ID": [],
            "Source": [],
            "Class": [],
            "Measurement": [],
            "Value": [],
            "ID": hex_id
        }

        # Now add each field to the list
        for name, data in measurements.items():
            display_data["Hex_ID"].append(hex_id)
            display_data["Source"].append(source)
            display_data["Class"].append(message.name)
            display_data["Measurement"].append(name)
            display_data["Value"].append(data)
        
        return display_data

    def data(self) -> dict:
        return self.data

    def type(self) -> str:
        return self.type














import re

"""
GPS message wrapper class. GPS.data[''] fields are:

'latitude':   (double) degrees
'latside':    (char) N or S
'longitude':  (double) degrees
'longside':   (char) E or W
'altitude':   (double) meters
'hdop':       (double) horizontal dilution of precision
'satellites': (int) number of satellites
'fix':        (int) 0 or 1 -- 0 = no fix, 1 = fix
'timestamp':       (double) seconds since last measurement

self.type = "GPS"
"""
class GPS:
    def __init__(self, message: str) -> None:   
        # Parse all data fields and set type
        self.data = self.parseGPS_str(message)
        self.type = "GPS"


    """
    Extracts measurements from a GPS message based on a specified format
    Keys of the dict are column headings. Values are data (as strings) in column.

    Parameters:
        format_specifier: None for GPS messages (as of now)
        
    Returns:
        display_data dictionary with the following form
        {
            "Latitude": [val + latside],
            "Longitude": [val + longside],
            "Altitude": [],
            "HDOP": [],
            "Satellites": [],
            "Fix": [],
            "Time": []
            "ID": 
        }
    """
    def extract_measurements(self, format_specifier=None) -> dict:
        display_data = {
            "Latitude": [str(self.data['latitude']) + " " + self.data['latSide']],
            "Longitude": [str(self.data['longitude']) + " " + self.data['lonSide']],
            "Altitude": [str(self.data['altitude'])],
            "HDOP": [str(self.data['hdop'])],
            "Satellites": [str(self.data['satelliteCount'])],
            "Fix": [str(self.data['fix'])],
            "Time": [str(self.data['lastMeasure'])],
            "ID": str(self.data['lastMeasure'])
        }

        return display_data

    """
    Parses a GPS message string into a dictionary of fields using regex
    
    Parameters:
        str_msg: the GPS message as a string

    Returns:
        a dictionary containing the data fields of the GPS message
    """
    def parseGPS_str(self, str_msg: str) -> dict:
        pattern = (
            r"Latitude: (?P<latitude>-?\d+\.\d+) (?P<latSide>[NS]), "
            r"Longitude: (?P<longitude>-?\d+\.\d+) (?P<lonSide>[EW]), "
            r"Altitude: (?P<altitude>-?\d+\.\d+) meters, "
            r"HDOP: (?P<hdop>-?\d+\.\d+), "
            r"Satellites: (?P<satelliteCount>\d+), "
            r"Fix: (?P<fix>\d+), "
            r"Time: (?P<lastMeasure>\d+\.\d+)"
        )
        match = re.search(pattern, str_msg)
        
        if match:
            gps_data = match.groupdict()
            gps_data['latitude'] = float(gps_data['latitude'])
            gps_data['longitude'] = float(gps_data['longitude'])
            gps_data['altitude'] = float(gps_data['altitude'])
            gps_data['hdop'] = float(gps_data['hdop'])
            gps_data['satelliteCount'] = int(gps_data['satelliteCount'])
            gps_data['fix'] = int(gps_data['fix'])
            gps_data['timestamp'] = float(gps_data['lastMeasure'])
            
            return gps_data
        else:
            return None

    def data(self) -> dict:
        return self.data

    def type(self) -> str:
        return self.type





import struct

"""
IMU message wrapper class. IMU.data[''] fields are:


'timestamp': (string) timestamp of the IMU message (All D's right now)
'identifier':        (string) ID of the IMU message
'value':     (float) value of the IMU message (rounded to 6 decimal places)
'type':      (string) type of the IMU message (A or G)
'dimension': (string) dimension of the IMU message (X, Y, or Z)

"Type": type of the IMU message (A or G)
"Dimension": dimension of the IMU message (X, Y, or Z)
"Value": value of the IMU message (rounded to 6 decimal places)
"Timestamp": timestamp of the IMU message (All D's right now)
"ID": ID of the IMU message chosen to be 'Type + Dimension'

self.type = "IMU"
"""
class IMU:
    def __init__(self, message: str, format_specifier=None) -> None:   
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
        dictionary with the following form
        {
            "Type": [],
            "Dimension": [],
            "Value": [],
            "Timestamp": []
            "ID":
        }
    """
    def extract_measurements(self, format_specifier=None) -> dict:
        # Extract the parts of the message
        timestamp = self.message[:8]
        id = self.message[9:11]      # skip the @
        data = self.message[11:]

        # Convert the data part to a 32-bit float
        value = struct.unpack('>f', bytearray(data.encode('latin1')))[0]

        output = {
            "Type": [id[0]],
            "Dimension": [id[1]],
            "Value": [str(round(value, 6))],
            "Timestamp": [str(timestamp)],
            "ID": id
        }
        return output

    def data(self) -> dict:
        return self.data

    def type(self) -> str:
        return self.type
        