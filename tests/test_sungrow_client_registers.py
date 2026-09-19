# tests/test_sungrow_client_registers.py
"""Characterization tests for SungrowClient.configure_registers.

These lock in current behavior before refactoring.
"""
import os
from unittest.mock import MagicMock

import yaml

from client.sungrow_client import SungrowClient


FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')


def load_test_registers():
    path = os.path.join(FIXTURES, 'registers-test.yaml')
    with open(path, encoding='utf-8') as f:
        return yaml.safe_load(f)


def make_client(**overrides):
    defaults = {
        'host': '192.168.1.1', 'port': 502, 'timeout': 10,
        'retries': 3, 'slave': 0x01, 'scan_interval': 30,
        'connection': 'modbus', 'model': None,
        'serial_number': None, 'level': 1,
        'use_local_time': False, 'smart_meter': False,
    }
    defaults.update(overrides)
    return SungrowClient(defaults)


class TestConfigureRegistersWithKnownModel:
    """When model is pre-configured, skip model detection."""

    def test_skips_model_detection_when_model_set(self):
        client = make_client(model='SG10KTL')
        registersfile = load_test_registers()
        client.load_registers = MagicMock(return_value=True)

        result = client.configure_registers(registersfile)

        assert result is True
        assert client.inverter_config['model'] == 'SG10KTL'

    def test_loads_level_1_read_registers(self):
        client = make_client(model='SG10KTL', level=1)
        registersfile = load_test_registers()
        client.load_registers = MagicMock(return_value=True)

        client.configure_registers(registersfile)

        register_names = [r['name'] for r in client.registers]
        assert 'daily_power_yields' in register_names
        assert 'total_active_power' in register_names

    def test_loads_hold_registers_at_level_1(self):
        client = make_client(model='SG10KTL', level=1)
        registersfile = load_test_registers()
        client.load_registers = MagicMock(return_value=True)

        client.configure_registers(registersfile)

        hold_names = [
            r['name'] for r in client.registers if r.get('type') == 'hold'
        ]
        assert 'max_power' in hold_names

    def test_register_ranges_populated(self):
        client = make_client(model='SG10KTL', level=1)
        registersfile = load_test_registers()
        client.load_registers = MagicMock(return_value=True)

        client.configure_registers(registersfile)

        assert len(client.register_ranges) > 0

    def test_smart_meter_registers_loaded_when_enabled(self):
        client = make_client(model='SG10KTL', level=1, smart_meter=True)
        registersfile = load_test_registers()
        client.load_registers = MagicMock(return_value=True)

        client.configure_registers(registersfile)

        register_names = [r['name'] for r in client.registers]
        assert 'meter_power' in register_names

    def test_smart_meter_registers_skipped_when_disabled(self):
        client = make_client(
            model='UNKNOWN_MODEL', level=1, smart_meter=False
        )
        registersfile = load_test_registers()
        client.load_registers = MagicMock(return_value=True)

        client.configure_registers(registersfile)

        register_names = [r['name'] for r in client.registers]
        assert 'meter_power' not in register_names


class TestConfigureRegistersModelDetection:
    """When model is None, auto-detect from inverter."""

    def test_detects_model_from_device_type_code(self):
        client = make_client(model=None)
        registersfile = load_test_registers()

        def fake_load_registers(_reg_type, _start, _count):
            client.latest_scrape['device_type_code'] = 'SG10KTL'
            return True

        client.load_registers = MagicMock(
            side_effect=fake_load_registers
        )

        client.configure_registers(registersfile)

        assert client.inverter_config['model'] == 'SG10KTL'

    def test_handles_failed_model_detection(self):
        client = make_client(model=None)
        registersfile = load_test_registers()
        client.load_registers = MagicMock(return_value=False)

        result = client.configure_registers(registersfile)

        assert result is True
        assert client.inverter_config['model'] is None
