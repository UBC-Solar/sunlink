import cantools
from pathlib import Path
import sys    

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
ANSI_SAVE_CURSOR = "\0337"
ANSI_RESTORE_CURSOR = "\0338"


# Log File Constants. 110,000,000 characters is around when the file crashes (with some leeway)
# However, when running the code with 100,000,00 set as the parameter we check the log file and it consistenly has 1.5 times the characters
# Thus, we will stop logging at 100,000,000 / 1.5 characters so that the logfile will end up with around 110,000,000 characters and not crash
# Then because of a range of computer capabiities we will set the max file size to be half this: 55,000,000 characters.
MAX_FILE_CHARS          = 36666666

# Sunlink Tracking Display Rate
DISPLAY_RATE            = 0.005

