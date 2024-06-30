# Parameter imports. ADD AND REMOVE AS NEEDED
from parser.parameters import *
import struct
#from time import strftime, localtime
import datetime
import time
"""
AT_Command_Return message data class. <AT_Command_Return>.data[''] fields are:



REQUIRED FILEDS
    "Source": (list) <ATL> 
    "Class": (list) <Whether the AT Command is a local or remote Command> 
    "Measurment": (list) <Specific AT Command Sent> 
    "Value": (list) <Value of associated Command> 
    "Timestamp": (list) >The time the message was sent>
    "Status": (list) <<The status of the AT Command ("0x00  = OK 0x01  = ERROR 0x02  = Invalid Command 0x03 =  Invalid Parameter")>
   

DISPLAY FIELDS
    "display_data" : {
        "ROW": {
            "Raw Hex": (list) raw hex data of the IMU message
        },
        "COL": {
            "Type": (list) <Whether the AT Command is a local or remote Command> 
            "Command": (list) <Specific AT Command Sent> 
            "Value": (list) <Value of associated Command>
            "Timestamp": (list) >The time the message was sent>
            "Status": (list) <The status of the AT Command ("0x00  = OK 0x01  = ERROR 0x02  = Invalid Command 0x03 =  Invalid Parameter")>
        }
    }
self.type = "<ATL>"
"""
class ATL:
    def __init__(self, message: str) -> None:      
        """
        In general, the init should set the data dictionary 
        based on parsing the message string. The type should be set to the name of the message.
        
        See 'CAN_Msg.py', 'GPS_Msg.py' and 'IMU_Msg.py' for good working examples.
        """

        self.message = message
        self.data = self.extract_measurements()
        self.type = "ATL"


    """
    Gets the value of the message as a float
    
    Parameters:
        message_val - the value of the message as a latin-1 string
    
    Returns:
        float_val - the value of the message
    """
    def get_value(self, message_val) -> int:
        try:
            val = struct.unpack('>i', bytearray(message_val.encode('latin-1')).rjust(4, b'\x00'))[0]
            int_val = int(val)
            return int_val
        except Exception as e:
            generate_exception(e, "get_value")


    """
    Gets the measurement/specific AT command of the message as a float
    
    Parameters:
        message_measurement - the value of the message as a latin-1 string
    
    Returns:
        float - the value of the message
    """
    def get_measurement(self, message_measurement) -> str:
        try:
            measurement = None
            if message_measurement == bytes.fromhex(hex_commandlist[0]).decode('latin-1'):
                measurement = "RSSI"
            elif message_measurement == bytes.fromhex(hex_commandlist[1]).decode('latin-1'):
                measurement = "Error Message Count"
            elif message_measurement == bytes.fromhex(hex_commandlist[2]).decode('latin-1'):
                measurement = "Good Packets Receieved Count"

            return measurement
        except Exception as e:
            generate_exception(e, "get_measurement")


    """
    Gets the status of the sent AT Command
    
    Parameters:
        message_status - the status code of the message as a latin-1 string
    
    Returns:
        float - the value of the message
    """
    def get_status(self, message_status) -> str:
        status = None
        try:
            if message_status == "\x00":
                status = "OK"
            elif message_status == "\x01":
                status = "ERROR"
            elif message_status == "\x02":
                status = "INVALID COMMAND"
            elif message_status == "\x03":
                status = "INVALID PARAMETER"

            return status
        except Exception as e:
            generate_exception(e, "get_status")





    """
    Will create a dictionary whose keys are the column headings to the pretty table
    and whose values are data in those columns. Table printed when processing response from parser
    in link_telemetry.py
    
    Parameters:
        None
        
    Returns:
        dictionary with the form outlined in the class description above
    """
    def extract_measurements(self) -> dict:
        # Set all fields to None initially
        measurement = None
        value = None
        status = None
        timestamp = None

        try:
            measurement = self.get_measurement(self.message[5:7])
            status = self.get_status(self.message[7])
            current_time = time.time()
            current_time_bytes = struct.pack('>d', current_time)
            timestamp = current_time_bytes.decode('latin-1')
            timestamp = struct.unpack('>d', timestamp.encode('latin-1'))[0]
            float_timestamp = float(timestamp)
            if (len(self.message)) < 9:
                value = "None"
            else:
                value = self.get_value(self.message[8:len(self.message)-1])




        except Exception as e:
            raise Exception(
                f"Could not extract {ANSI_BOLD}<Local_AT_Command_Return>{ANSI_ESCAPE} message with properties: \n"
                f"      Message Length = {len(self.message)} \n"
                f"      Message Hex Data = {self.message.encode('latin-1').hex()} \n\n"
                f"      {ANSI_RED}Error{ANSI_ESCAPE}: \n"
                f"      {e} \n"
                f"      {ANSI_GREEN}Function Call Details (self.message[] bytes -> hex numbers):{ANSI_ESCAPE} \n"
                f"        {ANSI_BOLD}get_value(message[8:len(message) -2]) = {self.message[8:len(self.message) -2].encode('latin-1').hex()} ) {ANSI_ESCAPE}, \n"
                f"          - gets the message value \n"
                f"        {ANSI_BOLD}get_value(message[5:6]) = {self.message[5:7].encode('latin-1').hex()} ) {ANSI_ESCAPE}, \n"
                f"          - gets the specific AT Command \n"
                f"        {ANSI_BOLD}get_value(message[7]) = {self.message[7].encode('latin-1').hex()} ) {ANSI_ESCAPE}, \n"
                f"          - gets the status of the AT command \n"
            )
        

        data = {}

        # SET REQUIRED FIELDS
        data["Source"] = ["AT"]
        data["Class"] = ["Local"]
        data["Measurement"] = [measurement]
        data["Value"] = [value]
        data["Timestamp"] = [float_timestamp]
        data["Status"] = [status]
     
         # DISPLAY FIELDS

        data["display_data"] = {
            "ROW": {
                "Raw Hex": [self.message.encode('latin-1').hex()]
                
            },
            "COL": {
                "Type": ["Local"],
            "Command": [measurement],
            "Value": [value],
            "Status": [status],
            "Timestamp": [datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]],
            }
        }
        return data
    
    