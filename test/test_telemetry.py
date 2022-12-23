from link_telemetry import StandardFrame
from pathlib import Path
import pprint
import yaml
import pytest
import cantools

DBC_FILE = Path("./dbc/daybreak.dbc")

# <---- helper functions ---->

def check_equality(first: float, second: float, threshold=0.1):
    return abs(first - second) <= threshold

# <---- test fixtures ---->

@pytest.fixture
def dbc():
    # read in the DBC file
    dbc = cantools.database.load_file(DBC_FILE)
    return dbc

# <---- tests ---->


class TestSpeedControllerMessages:
    def test_speed_ctrl(self, dbc):
        # instantiate StandardFrame
        timestamp = b"0000A1FB"
        id = b"0401"
        payload = b"66662a42" + b"3333e341"
        size = b"8"

        msg = StandardFrame(timestamp + id + payload + size + b"\n")

        # extract messages
        measurements = msg.extract_measurements(dbc)

        # checking 0x422a6666
        assert check_equality(measurements["desired_velocity"]["value"], 42.6)

        # checking 0x41e33333
        assert check_equality(measurements["current_setpoint"]["value"], 28.4)


class TestMotorMessages:
    def test_motor_state(self, dbc):
        timestamp = b"0000A1FB"
        id = b"0501"
        payload = b"0223FAAB" + b"00000000"
        size = b"7"

        msg = StandardFrame(timestamp + id + payload + size + b"\n")

        # extract messages
        measurements = msg.extract_measurements(dbc)

        # byte 0
        assert measurements["bridge_pwm_flag"]["value"] == False
        assert measurements["motor_current_flag"]["value"] == True
        assert measurements["velocity_flag"]["value"] == False
        assert measurements["bus_current_flag"]["value"] == False
        assert measurements["bus_voltage_upper_limit_flag"]["value"] == False
        assert measurements["bus_voltage_lower_limit_flag"]["value"] == False
        assert measurements["heat_sink_temp_flag"]["value"] == False

        # byte 2
        assert measurements["hw_overcurrent"]["value"] == False
        assert measurements["sw_overcurrent"]["value"] == True
        assert measurements["dc_bus_overvoltage"]["value"] == False
        assert measurements["bad_hall_sequence"]["value"] == True
        assert measurements["watchdog_reset"]["value"] == True
        assert measurements["config_read_error"]["value"] == True
        assert measurements["undervoltage_lockout"]["value"] == True

    def test_motor_bus(self, dbc):
        msg = StandardFrame(b"0000A1FB0502cdcc52429a9999417\n")

        measurements = msg.extract_measurements(dbc)

        # check 0x4252cccd
        assert check_equality(measurements["bus_voltage"]["value"], 52.7)
        # check 0x4199999a
        assert check_equality(measurements["bus_current"]["value"], 19.2)

    def test_motor_vel(self, dbc):
        msg = StandardFrame(b"0000A1FB05030000b441cdcc87427\n")

        measurements = msg.extract_measurements(dbc)

        # check 0x41b40000
        assert check_equality(measurements["motor_velocity"]["value"], 22.5)
        # check 0x4287cccd
        assert check_equality(measurements["vehicle_velocity"]["value"], 67.9)

    def test_motor_phase_current(self, dbc):
        msg = StandardFrame(b"0000A1FB05049a99b24200003e427\n")

        measurements = msg.extract_measurements(dbc)

        # check 0x42b2999a
        assert check_equality(measurements["phase_b_current"]["value"], 89.3)
        # check 0x423e0000
        assert check_equality(measurements["phase_a_current"]["value"], 47.5)

    def test_motor_temp(self, dbc):
        msg = StandardFrame(b"0000A1FB050B6766b242c3759c428\n")

        measurements = msg.extract_measurements(dbc)

        # check 0x42b26667
        assert check_equality(measurements["motor_temperature"]["value"], 89.2)
        # check 0x429c75c3
        assert check_equality(measurements["heatsink_temperature"]["value"], 78.23)


class TestBatteryMessages:
    def test_battery_state(self, dbc):
        msg = StandardFrame(b"0000A1FB06229800196D45920C007\n")

        measurements = msg.extract_measurements(dbc)

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

    def test_battery_voltages(self, dbc):
        msg = StandardFrame(b"0000A1FB0623001919F1A66215917\n")

        measurements = msg.extract_measurements(dbc)

        assert measurements["pack_voltage"]["value"] == 25
        assert measurements["min_voltage"]["value"] == 2.5
        assert measurements["min_voltage_idx"]["value"] == 241
        assert measurements["max_voltage"]["value"] == 16.6
        assert measurements["max_voltage_idx"]["value"] == 98

    def test_battery_currents(self, dbc):
        msg = StandardFrame(b"0000A1FB0624FFE70015002C00FF7\n")

        measurements = msg.extract_measurements(dbc)

        assert measurements["current"]["value"] == -25
        assert measurements["charge_limit"]["value"] == 21
        assert measurements["discharge_limit"]["value"] == 44

    def test_battery_metadata(self, dbc):
        msg = StandardFrame(b"0000A1FB062645000000000000007\n")

        measurements = msg.extract_measurements(dbc)

        assert measurements["state_of_charge"]["value"] == 69

    def test_battery_temp(self, dbc):
        msg = StandardFrame(b"0000A1FB06275500322D5A5F00FF7\n")

        measurements = msg.extract_measurements(dbc)

        assert measurements["temperature"]["value"] == 85
        assert measurements["min_temperature"]["value"] == 50
        assert measurements["min_temperature_idx"]["value"] == 45
        assert measurements["max_temperature"]["value"] == 90
        assert measurements["max_temperature_idx"]["value"] == 95
