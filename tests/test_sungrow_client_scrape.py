# tests/test_sungrow_client_scrape.py
"""Characterization tests for SungrowClient.scrape."""
from unittest.mock import MagicMock
from datetime import datetime

from client.sungrow_client import SungrowClient


def make_client(**overrides):
    defaults = {
        'host': '192.168.1.1', 'port': 502, 'timeout': 10,
        'retries': 3, 'slave': 0x01, 'scan_interval': 30,
        'connection': 'modbus', 'model': 'SG10KTL',
        'serial_number': 'TEST123', 'level': 1,
        'use_local_time': False, 'smart_meter': False,
    }
    defaults.update(overrides)
    return SungrowClient(defaults)


class TestScrapeTimestamp:
    """Timestamp assembly from register values."""

    def test_uses_local_time_when_configured(self):
        client = make_client(use_local_time=True)
        client.register_ranges = [
            {'type': 'read', 'start': 5000, 'range': 40}
        ]

        def fake_load(_reg_type, _start, _count):
            client.latest_scrape.update({
                'year': 2026, 'month': 3, 'day': 28,
                'hour': 12, 'minute': 30, 'second': 0,
                'start_stop': 'Start', 'work_state_1': 'Run',
                'total_active_power': 5000, 'meter_power': -2000,
                'load_power': 3000,
            })
            return True

        client.load_registers = MagicMock(side_effect=fake_load)

        result = client.scrape()

        assert result is True
        assert 'timestamp' in client.latest_scrape
        ts = client.latest_scrape['timestamp']
        parsed = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        assert parsed.year == datetime.now().year

    def test_uses_inverter_time_when_not_local(self):
        client = make_client(use_local_time=False)
        client.register_ranges = [
            {'type': 'read', 'start': 5000, 'range': 40}
        ]

        def fake_load(_reg_type, _start, _count):
            client.latest_scrape.update({
                'year': 2026, 'month': 1, 'day': 15,
                'hour': 10, 'minute': 5, 'second': 30,
                'start_stop': 'Start', 'work_state_1': 'Run',
                'total_active_power': 5000, 'meter_power': -2000,
                'load_power': 3000,
            })
            return True

        client.load_registers = MagicMock(side_effect=fake_load)

        result = client.scrape()

        assert result is True
        assert client.latest_scrape['timestamp'] == '2026-1-15 10:05:30'


class TestScrapeGridPower:
    """Virtual registers for grid import/export."""

    def test_export_to_grid_when_meter_power_negative(self):
        client = make_client(use_local_time=True, level=1)
        client.register_ranges = [
            {'type': 'read', 'start': 5000, 'range': 40}
        ]
        client.registers = [
            {'name': 'meter_power', 'type': 'read',
             'address': 5010, 'datatype': 'S32'},
        ]

        def fake_load(_reg_type, _start, _count):
            client.latest_scrape.update({
                'year': 2026, 'month': 3, 'day': 28,
                'hour': 12, 'minute': 0, 'second': 0,
                'meter_power': -2000,
                'start_stop': 'Start', 'work_state_1': 'Run',
                'total_active_power': 5000,
                'load_power': 3000,
            })
            return True

        client.load_registers = MagicMock(side_effect=fake_load)

        client.scrape()

        assert client.latest_scrape['export_to_grid'] == 2000
        assert client.latest_scrape['import_from_grid'] == 0

    def test_import_from_grid_when_meter_power_positive(self):
        client = make_client(use_local_time=True, level=1)
        client.register_ranges = [
            {'type': 'read', 'start': 5000, 'range': 40}
        ]
        client.registers = [
            {'name': 'meter_power', 'type': 'read',
             'address': 5010, 'datatype': 'S32'},
        ]

        def fake_load(_reg_type, _start, _count):
            client.latest_scrape.update({
                'year': 2026, 'month': 3, 'day': 28,
                'hour': 12, 'minute': 0, 'second': 0,
                'meter_power': 1500,
                'start_stop': 'Start', 'work_state_1': 'Run',
                'total_active_power': 5000,
                'load_power': 6500,
            })
            return True

        client.load_registers = MagicMock(side_effect=fake_load)

        client.scrape()

        assert client.latest_scrape['export_to_grid'] == 0
        assert client.latest_scrape['import_from_grid'] == 1500


class TestScrapeDisconnectOnFailure:
    """Scrape should disconnect when all register loads fail."""

    def test_disconnects_when_all_scrapes_fail(self):
        client = make_client(use_local_time=True)
        client.register_ranges = [
            {'type': 'read', 'start': 5000, 'range': 40},
        ]
        client.load_registers = MagicMock(return_value=False)
        client.disconnect = MagicMock()

        result = client.scrape()

        assert result is False
        client.disconnect.assert_called_once()

    def test_succeeds_when_some_scrapes_fail(self):
        client = make_client(use_local_time=True)
        client.register_ranges = [
            {'type': 'read', 'start': 5000, 'range': 40},
            {'type': 'hold', 'start': 5099, 'range': 10},
        ]

        call_count = 0

        def fake_load(_reg_type, _start, _count):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                client.latest_scrape.update({
                    'year': 2026, 'month': 3, 'day': 28,
                    'hour': 12, 'minute': 0, 'second': 0,
                    'start_stop': 'Start',
                    'work_state_1': 'Run',
                    'total_active_power': 5000,
                    'meter_power': 0,
                    'load_power': 5000,
                })
                return True
            return False

        client.load_registers = MagicMock(side_effect=fake_load)

        result = client.scrape()

        assert result is True


class TestScrapeRunStateContainsBug:
    """Characterize the .contains() bug in run_state computation.

    The original code at sungrow_client.py:450 calls:
        self.latest_scrape.get('work_state_1', False).contains('Run')
    But Python strings have no .contains() method. This raises
    AttributeError, which is silently swallowed by except Exception: pass.
    As a result, run_state retains its persisted default value 'ON'
    regardless of the actual inverter state.
    """

    def test_run_state_retains_default_due_to_contains_bug(self):
        client = make_client(use_local_time=True)
        client.register_ranges = [
            {'type': 'read', 'start': 5000, 'range': 40}
        ]

        def fake_load(_reg_type, _start, _count):
            client.latest_scrape.update({
                'year': 2026, 'month': 3, 'day': 28,
                'hour': 12, 'minute': 0, 'second': 0,
                'start_stop': 'Start',
                'work_state_1': 'Run',
                'total_active_power': 5000,
                'meter_power': 0,
                'load_power': 5000,
            })
            return True

        client.load_registers = MagicMock(side_effect=fake_load)

        client.scrape()

        # BUG: run_state should be re-evaluated based on start_stop
        # and work_state_1, but .contains() raises AttributeError
        # which is silently swallowed. run_state retains persisted
        # default "ON" regardless of actual state.
        assert client.latest_scrape['run_state'] == 'ON'


class TestScrapeHelperMethods:
    """Test validateRegister, getRegisterValue, etc."""

    def test_validate_register_returns_true_for_known(self):
        client = make_client()
        client.registers = [
            {'name': 'daily_power_yields', 'type': 'read',
             'address': 5003}
        ]
        assert client.validateRegister('daily_power_yields') is True

    def test_validate_register_returns_true_for_custom(self):
        client = make_client()
        assert client.validateRegister('run_state') is True

    def test_validate_register_returns_false_for_unknown(self):
        client = make_client()
        assert client.validateRegister('nonexistent') is False

    def test_get_register_value(self):
        client = make_client()
        client.latest_scrape = {'test_reg': 42}
        assert client.getRegisterValue('test_reg') == 42

    def test_get_register_value_returns_false_for_missing(self):
        client = make_client()
        client.latest_scrape = {}
        assert client.getRegisterValue('missing') is False

    def test_get_register_unit(self):
        client = make_client()
        client.registers = [
            {'name': 'power', 'type': 'read',
             'address': 1, 'unit': 'W'}
        ]
        assert client.getRegisterUnit('power') == 'W'

    def test_get_register_address(self):
        client = make_client()
        client.registers = [
            {'name': 'power', 'type': 'read', 'address': 5008}
        ]
        assert client.getRegisterAddress('power') == 5008

    def test_get_inverter_model_clean(self):
        client = make_client(model='SH10.RT-V2')
        assert client.getInverterModel(clean=True) == 'SH10RTV2'

    def test_get_inverter_model_raw(self):
        client = make_client(model='SH10.RT-V2')
        assert client.getInverterModel() == 'SH10.RT-V2'
