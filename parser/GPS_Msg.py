import re

"""
GPS message wrapper class. GPS.data[''] fields are:

"Latitude": degrees + latside (N or S)
"Longitude": degrees + longside (E or W)
"Altitude": meters
"HDOP": horizontal dilution of precision
"Satellites": number of satellites
"Fix": 0 or 1 -- 0 = no fix, 1 = fix
"Time": seconds since last measurement
"ID":  ID of GPS messages chosen to be the timestamp of the message (Time field)

self.type = "GPS"
"""
class GPS:
    def __init__(self, message: str, format_specifier=None) -> None:   
        # Parse all data fields and set type
        self.message = message
        self.data = self.extract_measurements()
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
        pattern = (
            r"Latitude: (?P<Latitude>-?\d+\.\d+) (?P<latSide>[NS]), "
            r"Longitude: (?P<Longitude>-?\d+\.\d+) (?P<longSide>[EW]), "
            r"Altitude: (?P<Altitude>-?\d+\.\d+) meters, "
            r"HDOP: (?P<HDOP>-?\d+\.\d+), "
            r"Satellites: (?P<Satellites>\d+), "
            r"Fix: (?P<Fix>\d+), "
            r"Time: (?P<Timestamp>\d+\.\d+)"
        )
        match = re.search(pattern, self.message)
        
        if match:
            gps_data = match.groupdict()
            gps_data['Latitude'] = [str(float(gps_data['Latitude'])) + " " + gps_data['latSide']] 
            gps_data['Longitude'] = [str(float(gps_data['Longitude'])) + " " + gps_data['longSide']] 
            gps_data['Altitude'] = [str(float(gps_data['Altitude']))]
            gps_data['HDOP'] = [str(float(gps_data['HDOP']))]
            gps_data['Satellites'] = [str(int(gps_data['Satellites']))]
            gps_data['Fix'] = [str(int(gps_data['Fix']))]
            gps_data['Timestamp'] = [str(float(gps_data['Timestamp']))]
            
            return gps_data
        else:
            return None

    def data(self) -> dict:
        return self.data

    def type(self) -> str:
        return self.type
        