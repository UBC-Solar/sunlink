import re

"""
Subclass GPS implements the extract_measurements and getter
methods from the interface Message. Assumes message parameter in 
constructor is a UART message from the Radio Receiver (serial.readLine())
Data fields are below:

REQUIRED FIELDS:
    "Source": "GPS" 
    "Class": Types of measurments like Latitude, Longitude, etc. No latside or longside here
    "Measurment": Like Latitude, Longitude, etc but WITH latside and longside
    "Value": Value of the latitude, longitude, measurments.
    "ID": ID of GPS is chosen to be the timestamp of the message

DISPLAY FIELDS:
    "display_data" : {
        "Latitude": degrees + latside (N or S)
        "Longitude": degrees + longside (E or W)
        "Altitude": meters
        "HDOP": horizontal dilution of precision
        "Satellites": number of satellites
        "Fix": 0 or 1 -- 0 = no fix, 1 = fix
        "Time": seconds since last measurement
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
    Keys of the dict are column headings. Values are data (as strings) in column.

    Parameters:
        format_specifier: None for GPS messages (as of now)
        
    Returns:
        display_data dictionary with the form outlined in the class description 
    """
    def extract_measurements(self, format_specifier=None) -> dict:
        pattern = (
            r"Latitude: (?P<Latitude>-?\d+\.\d+) (?P<Latside>[NS]), "
            r"Longitude: (?P<Longitude>-?\d+\.\d+) (?P<Longside>[EW]), "
            r"Altitude: (?P<Altitude>-?\d+\.\d+) meters, "
            r"HDOP: (?P<HDOP>-?\d+\.\d+), "
            r"Satellites: (?P<Satellites>\d+), "
            r"Fix: (?P<Fix>\d+), "
            r"Time: (?P<Timestamp>\d+\.\d+)"
        )
        match = re.search(pattern, self.message)
        
        if match:
            data = {}
            gps_data = match.groupdict()
            
            # REQUIRED FIELDS
            data["Source"] = ["GPS"] * len(gps_data.keys())
            data["Class"] = ["Latitudes", "Latsides", "Longitudes", "Longsides", "Altitudes", "HDOPs", "Satellites_Counts", "Fixs", "Timestamps"]
            data["Measurement"] = list(gps_data.keys())
            data["Value"] = []
            for key in data["Measurement"]:
                data["Value"].append(gps_data[key])
            data['ID'] = gps_data['Timestamp']

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

        return data

    def data(self) -> dict:
        return self.data

    def type(self) -> str:
        return self.type
        