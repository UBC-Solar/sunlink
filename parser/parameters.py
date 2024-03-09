import cantools
from pathlib import Path
import sys    

#  <----- Lengths of messages for differentiating message types ----->
CAN_LENGTH_MIN      = 21
CAN_LENGTH_MAX      = 23
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

# ANSI sequences
ANSI_ESCAPE = "\033[0m"
ANSI_RED = "\033[1;31m"
ANSI_GREEN = "\033[1;32m"
ANSI_YELLOW = "\033[1;33m"
ANSI_BOLD = "\033[1m"
