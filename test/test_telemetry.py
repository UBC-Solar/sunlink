from link_telemetry import CANMessage
from pathlib import Path
import yaml
import pprint

YAML_FILE = Path("can.yaml")


def test_motor_state():
	# <----- setup ----->

	# instantiate CANMessage
	msg = CANMessage(b"0000A1FB05012F0F00FF00FF00FF7\n")

	# read in the schema file
	with open(YAML_FILE, "r") as f:
		can_schema: dict = yaml.safe_load(f)

		# <---- execution ---->

		# extract messages
		measurements = msg.extract_measurements(can_schema)

		pprint.pprint(measurements)

		assert measurements["bridge_pwm_flag"]["value"] == False
		assert measurements["motor_current_flag"]["value"] == False


def test_speed_ctrl():
	# <----- setup ----->

	# instantiate CANMessage
	msg = CANMessage(b"0000A1FB040166662a423333e3417\n")

	# read in the schema file
	with open(YAML_FILE, "r") as f:
		can_schema: dict = yaml.safe_load(f)

		# <---- execution ---->

		# extract messages
		measurements = msg.extract_measurements(can_schema)

		print(measurements)

		# checking 0x422a6666
		assert measurements["desired_velocity"]["value"] == 42.6
		# checking 0x41e33333
		assert measurements["current_setpoint"]["value"] == 28.4


def test_motor_bus():
	msg = CANMessage(b"0000A1FB0502cdcc52429a9999417\n")

	with open(YAML_FILE, "r") as f:
		can_schema: dict = yaml.safe_load(f)

		measurements = msg.extract_measurements(can_schema)

		print(measurements)

		# check 0x4252cccd
		assert measurements["bus_voltage"]["value"] == 52.7
		# check 0x4199999a
		assert measurements["bus_current"]["value"] == 19.2


def test_motor_vel():
	msg = CANMessage(b"0000A1FB05030000b441cdcc87427\n")

	with open(YAML_FILE, "r") as f:
		can_schema: dict = yaml.safe_load(f)

		measurements = msg.extract_measurements(can_schema)

		print(measurements)

		# check 0x41b40000
		assert measurements["motor_velocity"]["value"] == 22.5
		# check 0x4287cccd
		assert measurements["vehicle_velocity"]["value"] == 67.9


def test_motor_phase_current():
	msg = CANMessage(b"0000A1FB05049a99b24200003e427\n")

	with open(YAML_FILE, "r") as f:
		can_schema: dict = yaml.safe_load(f)

		measurements = msg.extract_measurements(can_schema)

		print(measurements)

		# check 0x42b2999a
		assert measurements["phase_b_current"]["value"] == 89.3
		# check 0x423e0000
		assert measurements["phase_a_current"]["value"] == 47.5


def test_motor_temp():
	msg = CANMessage(b"0000A1FB050B6766b242c3759c428\n")

	with open(YAML_FILE, "r") as f:
		can_schema: dict = yaml.safe_load(f)

		measurements = msg.extract_measurements(can_schema)

		print(measurements)

		# check 0x42b26667
		assert measurements["motor_temperature"]["value"] == 89.2
		# check 0x429c75c3
		assert measurements["heatsink_temperature"]["value"] == 78.23


def test_battery_state():
	msg = CANMessage(b"0000A1FB06229800196D45920C007\n")

	with open(YAML_FILE, "r") as f:
		can_schema: dict = yaml.safe_load(f)

		measurements = msg.extract_measurements(can_schema)

		assert measurements["fault_state"]["value"] == True
		assert measurements["contactor_k1"]["value"] == False
		assert measurements["contactor_k2"]["value"] == False
		assert measurements["contactor_k3"]["value"] == True
		assert measurements["relay_fault"]["value"] == True
		assert measurements["startup_time"]["value"] == 25
		assert measurements["source_power"]["value"] == False
		assert measurements["load_power"]["value"] == True
		assert measurements["interlock_tripped"]["value"] == True
		assert measurements["hard_wire_contact_request"]["value"] == False
		assert measurements["can_contactor_request"]["value"] == True
		assert measurements["hlim"]["value"] == True
		assert measurements["llim"]["value"] == False
		assert measurements["fan_on"]["value"] == True
		assert measurements["fault_code"]["value"] == 69
		assert measurements["driving_off"]["value"] == True
		assert measurements["communication_fault"]["value"] == False
		assert measurements["charge_overcurrent"]["value"] == True
		assert measurements["discharge_overcurrent"]["value"] == False
		assert measurements["over_temperature"]["value"] == False
		assert measurements["under_voltage"]["value"] == True
		assert measurements["over_voltage"]["value"] == False
		assert measurements["cold_temperature"]["value"] == True
		assert measurements["hot_temperature"]["value"] == True
		assert measurements["low_soh"]["value"] == False
		assert measurements["isolation_fault"]["value"] == False


def test_battery_voltages():

	msg = CANMessage(b"0000A1FB0623001919F1A66215917\n")

	with open(YAML_FILE, "r") as f:
		can_schema: dict = yaml.safe_load(f)

		measurements = msg.extract_measurements(can_schema)

		assert measurements["pack_voltage"]["value"] == 25
		assert measurements["min_voltage"]["value"] == 2.5
		assert measurements["min_voltage_idx"]["value"] == 241
		assert measurements["max_voltage"]["value"] == 16.6
		assert measurements["max_voltage_idx"]["value"] == 98


def test_battery_currents():

	msg = CANMessage(b"0000A1FB0624FFE70015002C00FF7\n")

	with open(YAML_FILE, "r") as f:
		can_schema: dict = yaml.safe_load(f)

		measurements = msg.extract_measurements(can_schema)

		assert measurements["current"]["value"] == -25
		assert measurements["charge_limit"]["value"] == 21
		assert measurements["discharge_limit"]["value"] == 44


def test_battery_metadata():

	msg = CANMessage(b"0000A1FB062645000000000000007\n")

	with open(YAML_FILE, "r") as f:
		can_schema: dict = yaml.safe_load(f)

		measurements = msg.extract_measurements(can_schema)

		assert measurements["state_of_charge"]["value"] == 69


def test_battery_temp():

	msg = CANMessage(b"0000A1FB06275500322D5A5F00FF7\n")

	with open(YAML_FILE, "r") as f:
		can_schema: dict = yaml.safe_load(f)

		measurements = msg.extract_measurements(can_schema)

		assert measurements["temperature"]["value"] == 85
		assert measurements["min_temperature"]["value"] == 50
		assert measurements["min_temperature_idx"]["value"] == 45
		assert measurements["max_temperature"]["value"] == 90
		assert measurements["max_temperature_idx"]["value"] == 95
