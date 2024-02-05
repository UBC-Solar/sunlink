import cantools
from pathlib import Path
import os
from CAN_Msg import CAN
from GPS_Msg import GPS
from IMU_Msg import IMU
from randomizer import RandomMessage
import json

# dbc = cantools.database.load_file(str(Path(os.getcwd()) / "dbc" / "brightside.dbc"))
# msg = RandomMessage().random_can_str(dbc)
# print(msg)
# can = CAN(msg)
# print(can.extract_measurements(dbc))

# gps = RandomMessage().random_gps_str()
# print(gps)
# gps = GPS(gps)
# print(gps.extract_measurements())

# imu = RandomMessage().random_imu_str()
# print(imu)
# imu = IMU(imu)
# print(imu.extract_measurements())

# Assume `payload` is your original payload
payload = {
    "timestamp": 123456789,
}

# Encode the payload using latin-1
encoded_payload = payload.encode('latin-1')

# Decode it back to string
decoded_payload = encoded_payload.decode('utf-8')

# Try to convert it to JSON
try:
    json_payload = json.loads(decoded_payload)
    print("Payload is valid JSON")
except json.JSONDecodeError:
    print("Payload is not valid JSON")

