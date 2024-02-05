import cantools
from pathlib import Path
import os
from CAN_Msg import CAN
from GPS_Msg import GPS
from IMU_Msg import IMU
from randomizer import RandomMessage

# dbc = cantools.database.load_file(str(Path(os.getcwd()) / "dbc" / "brightside.dbc"))
# msg = RandomMessage().random_can_bytes(dbc)
# can = CAN(msg)
# print(can.extract_measurements(dbc))

# gps = RandomMessage().random_gps_bytes()
# print(gps)
# gps = GPS(gps)
# print(gps.extract_measurements())

# imu = RandomMessage().random_imu_bytes()
# print(imu)
# imu = IMU(imu)
# print(imu.extract_measurements())

my_dict = {'a': 1, 'b': 2, 'c': 3}
for key in my_dict.keys():
    print(key)