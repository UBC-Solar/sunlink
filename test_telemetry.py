from link_telemetry import CANMessage
from pathlib import Path 
import yaml
import pprint

YAML_FILE = Path("can.yaml")

'''def test_motor_msg():
	# <----- setup ----->

	#instantiate CANMessage
	#msg = CANMessage(b"0000A1FB_0626_00FF_00FF_00FF_00FF7\n")
	msg = CANMessage(b"0000A1FB050100FF00FF00FF00FF7\n")

	#read in the schema file
	with open(YAML_FILE, "r") as f:
		can_schema: dict = yaml.safe_load(f)

		# <---- execution ----> 

		# extract messages
		measurements = msg.extract_measurements(can_schema)

		pprint.pprint(measurements)

		# checking
		assert measurements["motor_current_flag"]["value"] == False'''

def test_speed_ctrl():
	# <----- setup ----->

	#instantiate CANMessage
	#msg = CANMessage(b"0000A1FB_0626_00FF_00FF_00FF_00FF7\n")
	msg = CANMessage(b"0000A1FB040166662a423333e3417\n")

	#read in the schema file
	with open(YAML_FILE, "r") as f:
		can_schema: dict = yaml.safe_load(f)

		# <---- execution ----> 

		# extract messages
		measurements = msg.extract_measurements(can_schema)

		print(measurements)

		# checking 0x422a6666
		assert measurements["desired_velocity"]["value"] ==  42.6
		# checking 0x41e33333
		assert measurements["current_setpoint"]["value"] == 28.4	

'''def test_motor_bus():
	msg = CANMessage(b"0000A1FB050200FF00FF00FF00FF7\n")

	with open(YAML_FILE, "r") as f:
		can_schema: dict = yaml.safe_load(f)

		measurements = msg.extract_measurements(can_schema)

		print(measurements)

		assert measurements["bus_voltage"]["value"] == -1.714652191593956e+38

def test_motor_vel():
	msg = CANMessage(b"0000A1FB050300FF00FF00FF00FF7\n")

	with open(YAML_FILE, "r") as f:
		can_schema: dict = yaml.safe_load(f)

		measurements = msg.extract_measurements(can_schema)

		print(measurements)

		assert measurements["motor_velocity"]["value"] ==  -1.714652191593956e+38

def test_motor_phase_current():
	msg = CANMessage(b"0000A1FB050400FF00FF00FF00FF7\n")

	with open(YAML_FILE, "r") as f:
		can_schema: dict = yaml.safe_load(f)

		measurements = msg.extract_measurements(can_schema)

		print(measurements)

		assert measurements["phase_b_current"]["value"] == -1.714652191593956e+38'''

'''def test_motor_temp():
	msg = CANMessage(b"0000A1FB050B00001642c3759c428\n")

	with open(YAML_FILE, "r") as f:
		can_schema: dict = yaml.safe_load(f)

		measurements = msg.extract_measurements(can_schema)

		pprint.pprint(measurements)

		# assert measurements["heatsink_temperature"]

def test_battery_state():
	msg = CANMessage(b"0000A1FB062200FF00FF00FF00FF7\n")

	with open(YAML_FILE, "r") as f:
		can_schema: dict = yaml.safe_load(f)

		measurements = msg.extract_measurements(can_schema)

		print(measurements)

def test_battery_voltages():

	msg = CANMessage(b"0000A1FB062300FF00FF00FF00FF7\n")

	with open(YAML_FILE, "r") as f:
		can_schema: dict = yaml.safe_load(f)

		measurements = msg.extract_measurements(can_schema)

		print(measurements)

def test_battery_currents():

	msg= CANMessage(b"0000A1FB062400FF00FF00FF00FF7\n")

	with open(YAML_FILE, "r") as f:
		can_schema: dict = yaml.safe_load(f)

		measurements = msg.extract_measurements(can_schema)

		print(measurements)

def test_battery_metadata():

	msg= CANMessage(b"0000A1FB062600FF00FF00FF00FF7\n")

	with open(YAML_FILE, "r") as f:
		can_schema: dict = yaml.safe_load(f)

		measurements = msg.extract_measurements(can_schema)

		print(measurements)

def test_battery_temp():

	msg= CANMessage(b"0000A1FB062700FF00FF00FF00FF7\n")

	with open(YAML_FILE, "r") as f:
		can_schema: dict = yaml.safe_load(f)

		measurements = msg.extract_measurements(can_schema)

		print(measurements)

def test_battery_temp():

	msg= CANMessage(b"0000A1FB062700FF00FF00FF00FF7\n")

	with open(YAML_FILE, "r") as f:
		can_schema: dict = yaml.safe_load(f)

		measurements = msg.extract_measurements(can_schema)

		print(measurements)'''


def main():
	#test_motor_msg()
	test_speed_ctrl()
	#test_motor_bus()
	#test_motor_vel()
	#test_motor_phase_current()
	#test_motor_temp()
	# test_battery_state()
	# test_battery_voltages()
	# test_battery_currents()
	# test_battery_metadata()
	# test_battery_temp()

if __name__ == "__main__":
	main()