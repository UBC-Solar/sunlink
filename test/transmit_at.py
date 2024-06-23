import serial
import cantools
from pathlib import Path
import sys  
import time  

#  <----- Multi-Class Functions  ----->
"""
Generates a custom exception based on the caught exception and the function name

Parameters:
    e: The caught exception
    func_name: The name of the function that caught the exception

Returns:
    Exception with the custom message
"""
def generate_exception(e: Exception, func_name: str) -> Exception:
    exec_info = e.__traceback__.tb_lineno
    exec_file = e.__traceback__.tb_frame.f_code.co_filename
    raise Exception(
        f"{ANSI_BOLD}{exec_file} -> Failed at Line: {exec_info} in {func_name}(){ANSI_ESCAPE}: \n"
        f"      Caught Exception = {e}, \n"
    )


#  <----- Lengths of messages for differentiating message types ----->
CAN_LENGTH_MIN      = 21
CAN_LENGTH_MAX      = 25
GPS_LENGTH_MIN      = 110
GPS_LENGTH_MAX      = 205
IMU_LENGTH_MIN      = 15
IMU_LENGTH_MAX      = 17

CAN_MSG_LENGTH = 24
IMU_MSG_LENGTH = 17
GPS_MSG_LENGTH = 200 ##Figure Out


# <----- DBC Variables (Can be changed by user arguement in Link Tel) ----->
DBC_FILE = Path("./dbc/brightside.dbc")
if not DBC_FILE.is_file():
    print(f"Unable to find expected existing DBC file: \"{DBC_FILE.absolute()}\"")
    sys.exit(1)
CAR_DBC = cantools.database.load_file(DBC_FILE)


# <----- \ANSI SEQUENCES ----->
ANSI_ESCAPE = "\033[0m"
ANSI_RED = "\033[1;31m"
ANSI_GREEN = "\033[1;32m"
ANSI_YELLOW = "\033[1;33m"
ANSI_BOLD = "\033[1m"


# <----- Bytes used to Indicate Message Types --->
CAN_BYTE = '00'
IMU_BYTE = '01'
GPS_BYTE = '02'
LOCAL_AT_BYTE = '03'
REMOTE_AT_BYTE = '04'
UNKNOWN_BYTE = '05'



#<----- AT Command Parameters --->
AT_COMMAND_FREQUENCY = 1 #Time in seconds between each batch of AT Commands
ENERGY_DETECT_TIME = '01' #Time energy detect command spends cycling through channels

DB = bytes.fromhex("7E00040801444270") #RSSI
ER = bytes.fromhex("7E0004080145525F") #Error Count
GD = bytes.fromhex("7E0004080147446B") #Good Packets Receieved
##ED = bytes.fromhex("7E 00 05 08 01 45 44" + ENERGY_DETECT_TIME + "3C") #Energy detect

command_list = [DB, ER, GD]
hex_commandlist = ["4442", "4552", "4744" ] #same order as abobe


with serial.Serial() as ser:
    ser.baudrate = args.baudrate
    ser.port = args.port
    ser.open()
    while True:
        for command in command_list:
         serial.write(command)
        #lock.release()
        time.sleep(AT_COMMAND_FREQUENCY)