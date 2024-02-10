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
            "Latitude": [str(self.data['Latitude']) + " " + self.data['latSide']],
            "Longitude": [str(self.data['Longitude']) + " " + self.data['lonSide']],
            "Altitude": [str(self.data['Altitude'])],
            "HDOP": [str(self.data['HDOP'])],
            "Satellites": [str(self.data['Satellites'])],
            "Fix": [str(self.data['Fix'])],
            "Time": [str(self.data['Timestamp'])],
            "ID": str(self.data['Timestamp'])
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
            r"Latitude: (?P<Latitude>-?\d+\.\d+) (?P<latSide>[NS]), "
            r"Longitude: (?P<Longitude>-?\d+\.\d+) (?P<lonSide>[EW]), "
            r"Altitude: (?P<Altitude>-?\d+\.\d+) meters, "
            r"HDOP: (?P<HDOP>-?\d+\.\d+), "
            r"Satellites: (?P<Satellites>\d+), "
            r"Fix: (?P<Fix>\d+), "
            r"Time: (?P<Timestamp>\d+\.\d+)"
        )
        match = re.search(pattern, str_msg)
        
        if match:
            gps_data = match.groupdict()
            gps_data['Latitude'] = [str(float(gps_data['Latitude'])) + " " + gps_data['latSide']]
            gps_data['Longitude'] = [str(float(gps_data['Longitude'])) + " " + float(gps_data['lonSide'])]
            gps_data['Altitude'] = [str(float(gps_data['Altitude']))]
            gps_data['HDOP'] = [str(float(gps_data['HDOP']))]
            gps_data['Satellites'] = [str(int(gps_data['Satellites']))]
            gps_data['Fix'] = [str(int(gps_data['Fix']))]
            gps_data['timestamp'] = str(float(gps_data['Timestamp']))

            # gps_data['ID'] = str(float(gps_data['Timestamp']))


            self.display_data = {
                "Latitude": [str(float(gps_data['Latitude'])) + " " + gps_data['latSide']],
                "Longitude": [str(float(gps_data['Longitude'])) + " " + float(gps_data['lonSide'])],
                "Altitude": [str(float(gps_data['Altitude']))],
                "HDOP": [str(float(gps_data['HDOP']))],
                "Satellites": [str(int(gps_data['Satellites']))],
                "Fix": [str(int(gps_data['Fix']))],
                "Time": [str(float(gps_data['Timestamp']))],
                "ID": str(float(gps_data['Timestamp']))
             }

            
            return gps_data
        else:
            return None

    def data(self) -> dict:
        return self.data

    def type(self) -> str:
        return self.type
        