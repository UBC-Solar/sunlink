import re

# Superclass import
from Message import Message, Measurement

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
'time':       (double) seconds since last measurement

self.type = "GPS"
"""
class GPS(Message):
    def __init__(self, message: bytes) -> None:   
        # Convert it to a string 
        str_msg = message.decode("latin-1")

        # Parse all data fields and set type
        self.data = self.parseGPS_str(str_msg)
        self.type = "GPS"


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
            
            return gps_data
        else:
            return None

    # TODO: Implement this method
    def extract_measurements(self, format_specifier) -> list[Measurement]:
        measurement_list: list[Measurement] = list()
        return measurement_list

    def data(self) -> dict:
        return self.data

    def type(self) -> str:
        return self.type
        