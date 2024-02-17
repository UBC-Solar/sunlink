import cantools
from pathlib import Path
import sys    

# <----- DBC constants ----->
DBC_FILE = Path("./dbc/brightside.dbc")

if not DBC_FILE.is_file():
    print(f"Unable to find expected existing DBC file: \"{DBC_FILE.absolute()}\"")
    sys.exit(1)
    
CAR_DBC = cantools.database.load_file(DBC_FILE)

def change():
    print("Done fore")
    CAR_DBC = 1

    