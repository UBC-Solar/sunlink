import cantools
from pathlib import Path
import os
from CAN_Msg import CAN
from GPS_Msg import GPS
from IMU_Msg import IMU
from randomizer import RandomMessage

# dbc = cantools.database.load_file(str(Path(os.getcwd()) / "dbc" / "brightside.dbc"))
# msg = RandomMessage().random_can_str(dbc)
# print(msg)
# can = CAN(msg)
# print(can.extract_measurements(dbc))

# gps = RandomMessage().random_gps_str()
# print(gps)
# gps = GPS(gps)
# print(gps.extract_measurements())

imu = RandomMessage().random_imu_str()
print(imu)
imu = IMU(imu)
print(imu.extract_measurements())
