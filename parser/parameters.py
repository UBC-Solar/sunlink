import cantools
from pathlib import Path
import sys    

#  <----- Lengths of messages for differentiating message types ----->
CAN_LENGTH_MIN      = 20
CAN_LENGTH_MAX      = 26
GPS_LENGTH_MIN      = 122
GPS_LENGTH_MAX      = 133
IMU_LENGTH_MIN      = 15
IMU_LENGTH_MAX      = 17


# <----- DBC Variables (Can be changed by user arguement in Link Tel) ----->
DBC_FILE = Path("./dbc/brightside.dbc")

if not DBC_FILE.is_file():
    print(f"Unable to find expected existing DBC file: \"{DBC_FILE.absolute()}\"")
    sys.exit(1)
    
CAR_DBC = cantools.database.load_file(DBC_FILE)
