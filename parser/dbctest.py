import cantools
from pathlib import Path
import os


my_dict = {
    'key1': [1, 2, 3, 4],
    'key2': [5, 6, 7, 8],
    'key3': [9, 10, 11, 12],
    'key4': [13, 14, 15, 16],
    'key5': [17, 18, 19, 20]
}

result_list = []

for i in range(4):  # assuming the loop runs 4 times
    sublist = [my_dict[key][i] for key in my_dict]
    result_list.append(sublist)

print(str(my_dict))


# dbc = cantools.database.load_file(str(Path(os.getcwd()) / "dbc" / "brightside.dbc"))
# msg = RandomMessage().random_can_str(dbc)
# print(msg)
# can = create_message(msg)
# print(can.extract_measurements(dbc))

# gps = RandomMessage().random_gps_str()
# print(gps)
# gps = create_message(gps)
# print(gps.extract_measurements())

# imu = RandomMessage().random_imu_str()
# print(imu)
# imu = create_message(imu)
# print(imu.extract_measurements())
