import cantools
from pathlib import Path
import sys    

global DBC_FILE
global CAR_DBC
    
def get_dbc(dbc_arguement):
    if (dbc_arguement):
        DBC_FILE = Path(dbc_arguement)
        CAR_DBC = cantools.database.load_file(DBC_FILE)
    else:
        DBC_FILE = Path("./dbc/brightside.dbc")
        CAR_DBC = cantools.database.load_file(DBC_FILE)
    
    if not DBC_FILE.is_file():
        print(f"Unable to find expected existing DBC file: \"{DBC_FILE.absolute()}\"")
        sys.exit(1)
        
