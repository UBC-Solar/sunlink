import re
from parser.parameters import ANSI_RED, ANSI_ESCAPE

"""
GPS Message data class. Assumes message parameter in constructor is a latin-1 decoded string.
Data fields are below:

REQUIRED (INFLUX) FIELDS:
    "Source": (list) "GPS" 
    "Class": (list) Types of measurments like Latitude, Longitude, etc. No latside or longside here
    "Measurment": (list) Like Latitude, Longitude, etc but WITH latside and longside
    "Value": (list) Value of the latitude, longitude, measurments.
    "Timestamp": (list) The time the message was sent

DISPLAY FIELDS:
    "display_data" : {
        "Latitude": (list) degrees + latside (N or S)
        "Longitude": (list) degrees + longside (E or W)
        "Altitude": (list) meters
        "HDOP": (list) horizontal dilution of precision
        "Satellites": (list) number of satellites
        "Fix": (list) 0 or 1 -- 0 = no fix, 1 = fix
        "Time": (list) seconds since last measurement
    }

self.type = "GPS"
"""
class GPS:
    def __init__(self, message: str) -> None:   
        # Parse all data fields and set type
        self.message = message
        self.data = self.extract_measurements()
        self.type = "GPS"

    """
    Extracts measurements from a GPS message based on a specified format
    Keys of the display_dict in the data dict are column headings. 
    Values are data in columns.

    Parameters:
        None
        
    Returns:
        display_data dictionary with the form outlined in the class description 
    """
    def extract_measurements(self) -> dict:
        pattern = (
            r"Latitude: (?P<Latitude>-?\d+\.\d+) (?P<Latside>[NS]), "
            r"Longitude: (?P<Longitude>-?\d+\.\d+) (?P<Longside>[EW]), "
            r"Altitude: (?P<Altitude>-?\d+\.\d+) meters, "
            r"HDOP: (?P<HDOP>-?\d+\.\d+), "
            r"Satellites: (?P<Satellites>\d+), "
            r"Fix: (?P<Fix>\d+), "
            r"Time: (?P<Timestamp>\d+)"
        )
        match = re.search(pattern, self.message)
        
        data = {}
        if match:
            gps_data = match.groupdict()
            
            # REQUIRED FIELDS
            data["Source"] = ["GPS"] * len(gps_data.keys())
            data["Class"] = ["Latitudes", "Latsides", "Longitudes", "Longsides", "Altitudes", "HDOPs", "Satellites_Counts", "Fixs", "Timestamps"]
            data["Measurement"] = ["Latitude", "Latside", "Longitude", "Longside", "Altitude", "HDOP", "Satellites", "Fix", "Timestamp"]
            data["Value"] = []
            data["Timestamp"] = []
            for key in data["Measurement"]:
                data["Value"].append(self.getType(key, gps_data[key]))
                data["Timestamp"].append(float(gps_data['Timestamp']))

            # DISPLAY FIELDS
            data["display_data"] = {
                "Latitude": [gps_data['Latitude'] + " " + gps_data['Latside']],
                "Longitude": [gps_data['Longitude'] + " " + gps_data['Longside']],
                "Altitude": [gps_data['Altitude']],
                "HDOP": [gps_data['HDOP']],
                "Satellites": [gps_data['Satellites']],
                "Fix": [gps_data['Fix']],
                "Time": [gps_data['Timestamp']]
            }
        else:
            raise Exception(
                f"{ANSI_RED}Regex Match failed for GPS message with properties: {ANSI_ESCAPE}\n"
                f"      Message Length = {len(self.message)} \n"
                f"      Message Data = '{self.message}' \n"
            )

        return data


    """
    Determines the correct type conversion of a string value based on the key
    
    Parameters:
        key: The key telling what type of value it is
        value: The value to be converted

    Returns: 
        The value converted to the correct type
    """
    def getType(self, key, value):
        if key == "Latitude" or key == "Longitude" or key == "Altitude" or key == "HDOP" or key == "Time":
            return float(value)
        elif key == "Satellites" or key == "Fix":
            return int(value)
        else:
            return value
    