import cantools
from pathlib import Path
import os
from randomizer import RandomMessage
from create_message import create_message

dbc = cantools.database.load_file(str(Path(os.getcwd()) / "dbc" / "brightside.dbc"))
msg = RandomMessage().random_can_str(dbc)
print(msg)
can = create_message(msg)
print(can.extract_measurements(dbc))

gps = RandomMessage().random_gps_str()
print(gps)
gps = create_message(gps)
print(gps.extract_measurements())

imu = RandomMessage().random_imu_str()
print(imu)
imu = create_message(imu)
print(imu.extract_measurements())
