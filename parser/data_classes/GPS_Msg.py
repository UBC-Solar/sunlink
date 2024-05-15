import re
import time
from time import strftime, localtime
from datetime import datetime
from parser.parameters import ANSI_RED, ANSI_ESCAPE


SECONDS_IN_DAY       = 86400


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
        "ROW": {
            "Raw Hex": (list) raw hex data of the GPS message
        },
        "COL": {
            "Latitude": (list) Latitude of the GPS message
            "Longitude": (list) Longitude of the GPS message
            "Altitude": (list) Altitude of the GPS message
            "HDOP": (list) HDOP of the GPS message
            "Satellites": (list) Number of satellites of the GPS message
            "Fix": (list) Fix of the GPS message
            "Time": (list) Time of the GPS message
        }
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
    Given a GPS timestamp formatted as HHMMSS converts it to an epoch
    timestamp by getting the current day and adding on the GPS timestamp.
    
    Parameters:
        timestamp (str): GPS timestamp in the form HHMMSS (ex. 093021 is 9:31 am 21 seconds
    Returns: 
        (str) epoch timestamp in seconds
    """
    def getEpochTS(self, timestamp: str) -> str:
        epoch_time = time.time()
        epoch_day = epoch_time - (epoch_time % SECONDS_IN_DAY)
        epoch_offset = int(timestamp[:2]) * 3600 + int(timestamp[2:4]) * 60 + int(timestamp[4:])
        return str(epoch_day + epoch_offset)
    

    """
    Formats an epoch timestamp to a human readable format
    of YYYY-MM-DD HH:MM:SS.mmm

    Parameters:
        timestamp (str): epoch timestamp in seconds
    
    Returns:
        (str) human readable timestamp in the form YYYY-MM-DD HH:MM:SS.mmm
    """
    def formatEpochTS(self, timestamp: str) -> str:
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    

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

            epochTSFloat = float(self.getEpochTS(gps_data['Timestamp']))
            formattedTS = self.formatEpochTS(epochTSFloat)
            
            # REQUIRED FIELDS
            data["Source"] = ["GPS"] * len(gps_data.keys())
            data["Class"] = ["Latitudes", "Latsides", "Longitudes", "Longsides", "Altitudes", "HDOPs", "Satellites_Counts", "Fixs", "Timestamps"]
            data["Measurement"] = ["Latitude", "Latside", "Longitude", "Longside", "Altitude", "HDOP", "Satellites", "Fix", "Timestamp"]
            data["Value"] = []
            data["Timestamp"] = []
            for key in data["Measurement"]:
                data["Value"].append(self.getType(key, gps_data[key]))
                data["Timestamp"].append(epochTSFloat)

            # DISPLAY FIELDS
            data["display_data"] = {
                "ROW": {
                    "Raw Hex": [self.message.encode('latin-1').hex()]
                },
                "COL": {
                    "Latitude": [gps_data['Latitude'] + " " + gps_data['Latside']],
                    "Longitude": [gps_data['Longitude'] + " " + gps_data['Longside']],
                    "Altitude": [gps_data['Altitude']],
                    "HDOP": [gps_data['HDOP']],
                    "Satellites": [gps_data['Satellites']],
                    "Fix": [gps_data['Fix']],
                    "Time": [formattedTS]
                }
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
    