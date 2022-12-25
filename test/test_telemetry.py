from link_telemetry import StandardFrame
from pathlib import Path
import pprint
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
        """
        id: 0x401
        description: motor drive command
        """
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
        """
        id: 0x501
        description: motor status information
        """
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
        """
        id: 0x502
        description: motor bus measurement
        """
        msg = StandardFrame(b"0000A1FB0502cdcc52429a9999417\n")

        measurements = msg.extract_measurements(dbc)

        # check 0x4252cccd
        assert check_equality(measurements["bus_voltage"]["value"], 52.7)
        # check 0x4199999a
        assert check_equality(measurements["bus_current"]["value"], 19.2)

    def test_motor_vel(self, dbc):
        """
        id: 0x503
        description: motor velocity measurement
        """
        msg = StandardFrame(b"0000A1FB05030000b441cdcc87427\n")

        measurements = msg.extract_measurements(dbc)

        # check 0x41b40000
        assert check_equality(measurements["motor_velocity"]["value"], 22.5)
        # check 0x4287cccd
        assert check_equality(measurements["vehicle_velocity"]["value"], 67.9)

    def test_motor_phase_current(self, dbc):
        """
        id: 0x504
        description: motor phase current measurement
        """
        msg = StandardFrame(b"0000A1FB05049a99b24200003e427\n")

        measurements = msg.extract_measurements(dbc)

        # check 0x42b2999a
        assert check_equality(measurements["phase_b_current"]["value"], 89.3)
        # check 0x423e0000
        assert check_equality(measurements["phase_a_current"]["value"], 47.5)

    def test_motor_temp(self, dbc):
        """
        id: 0x50B
        description: sink & motor temperature measurement
        """
        msg = StandardFrame(b"0000A1FB050B6766b242c3759c428\n")

        measurements = msg.extract_measurements(dbc)

        # check 0x42b26667
        assert check_equality(measurements["motor_temperature"]["value"], 89.2)
        # check 0x429c75c3
        assert check_equality(measurements["heatsink_temperature"]["value"], 78.23)


class TestBatteryMessages:
    def test_battery_state(self, dbc):
        """
        id: 0x622
        description: battery state message (includes faults)
        """
        timestamp = b"0000FEE5"
        id = b"0622"
        payload = b"190019B6" + b"0A4B3D00"
        size = b"8"

        msg = StandardFrame(timestamp + id + payload + size + b"\n")

        measurements = msg.extract_measurements(dbc)

        # state of system: byte 0
        assert measurements["fault_state"]["value"] == True
        assert measurements["contactor_k1"]["value"] == False
        assert measurements["contactor_k2"]["value"] == False
        assert measurements["contactor_k3"]["value"] == True
        assert measurements["relay_fault"]["value"] == True

        # power-up time: byte 1-2
        assert measurements["startup_time"]["value"] == 25

        # byte of flags: byte 3
        assert measurements["source_power"]["value"] == False
        assert measurements["load_power"]["value"] == True
        assert measurements["interlock_tripped"]["value"] == True
        assert measurements["hard_wire_contactor_request"]["value"] == False
        assert measurements["can_contactor_request"]["value"] == True
        assert measurements["hlim_set"]["value"] == True
        assert measurements["llim_set"]["value"] == False
        assert measurements["fan_on"]["value"] == True

        # fault code: byte 4
        assert measurements["fault_code"]["value"] == 10

        # level faults: byte 5
        assert measurements["driving_off"]["value"] == True
        assert measurements["interlock_tripped"]["value"] == True
        assert measurements["communication_fault"]["value"] == False
        assert measurements["charge_overcurrent"]["value"] == True
        assert measurements["discharge_overcurrent"]["value"] == False
        assert measurements["over_temperature"]["value"] == False
        assert measurements["under_voltage"]["value"] == True
        assert measurements["over_voltage"]["value"] == False

        # warnings: byte 6
        assert measurements["low_voltage_warn"]["value"] == True
        assert measurements["high_voltage_warn"]["value"] == False
        assert measurements["charge_overcurrent_warn"]["value"] == True
        assert measurements["discharge_overcurrent_warn"]["value"] == True
        assert measurements["cold_temperature_warn"]["value"] == True
        assert measurements["hot_temperature_warn"]["value"] == True
        assert measurements["low_soh_warn"]["value"] == False
        assert measurements["isolation_fault_warn"]["value"] == False

    def test_battery_voltages(self, dbc):
        """
        id: 0x623
        description: battery voltages (pack, min, max)
        """
        msg = StandardFrame(b"0000A1FB0623001919F1A66215917\n")

        measurements = msg.extract_measurements(dbc)

        assert measurements["pack_voltage"]["value"] == 25
        assert measurements["min_voltage"]["value"] == 2.5
        assert measurements["min_voltage_idx"]["value"] == 241
        assert measurements["max_voltage"]["value"] == 16.6
        assert measurements["max_voltage_idx"]["value"] == 98

    def test_battery_currents(self, dbc):
        """
        id: 0x624
        description: battery currents (pack, min, max)
        """
        timestamp = b"0000A1FB"
        id = b"0624"
        payload = b"FFE71532" + b"0000A454"
        size = b"8"

        msg = StandardFrame(timestamp + id + payload + size + b"\n")

        measurements = msg.extract_measurements(dbc)

        assert measurements["pack_current"]["value"] == -25
        assert measurements["charge_limit"]["value"] == 5426
        assert measurements["discharge_limit"]["value"] == 0

    def test_battery_energies(self, dbc):
        """
        id: 0x625
        description: battery energy in and out
        """
        timestamp = b"929A288D"
        id = b"0625"
        payload = b"00871C65" + b"0054C8E6"
        size = b"8"

        msg = StandardFrame(timestamp + id + payload + size + b"\n")

        measurements = msg.extract_measurements(dbc)

        assert measurements["battery_energy_in"]["value"] == 8_854_629
        assert measurements["battery_energy_out"]["value"] == 5_556_454

    def test_battery_metadata(self, dbc):
        """
        id: 0x626
        description: battery metadata (SOC, SOC, DOD)
        """
        msg = StandardFrame(b"0000A1FB062645000000000000007\n")

        measurements = msg.extract_measurements(dbc)

        assert measurements["state_of_charge"]["value"] == 69

    def test_battery_temp(self, dbc):
        """
        id: 0x627
        description: battery temperature (pack, min, max)
        """
        msg = StandardFrame(b"0000A1FB06275500322D5A5F00FF7\n")

        measurements = msg.extract_measurements(dbc)

        assert measurements["pack_temperature"]["value"] == 85
        assert measurements["min_temperature"]["value"] == 50
        assert measurements["min_temperature_idx"]["value"] == 45
        assert measurements["max_temperature"]["value"] == 90
        assert measurements["max_temperature_idx"]["value"] == 95
