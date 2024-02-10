import re

"""
Subclass GPS implements the extract_measurements and getter
methods from the interface Message. Assumes message parameter in 
constructor is a UART message from the Radio Receiver (serial.readLine())
Data fields are below:

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
        self.message = message
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
        