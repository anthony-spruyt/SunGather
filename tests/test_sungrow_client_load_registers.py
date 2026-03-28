# tests/test_sungrow_client_load_registers.py
"""Characterization tests for SungrowClient.load_registers."""
from unittest.mock import MagicMock

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


def make_mock_response(registers, is_error=False):
    resp = MagicMock()
    resp.isError.return_value = is_error
    resp.registers = registers
    return resp


class TestLoadRegistersU16:
    """U16 register type decoding."""

    def test_u16_normal_value(self):
        client = make_client()
        client.client = MagicMock()
        client.registers = [
            {'name': 'test_u16', 'type': 'read',
             'address': 1, 'datatype': 'U16'}
        ]
        client.client.read_input_registers.return_value = (
            make_mock_response([500])
        )

        result = client.load_registers('read', 0, 1)

        assert result is True
        assert client.latest_scrape['test_u16'] == 500

    def test_u16_ffff_becomes_zero(self):
        client = make_client()
        client.client = MagicMock()
        client.registers = [
            {'name': 'test_u16', 'type': 'read',
             'address': 1, 'datatype': 'U16'}
        ]
        client.client.read_input_registers.return_value = (
            make_mock_response([0xFFFF])
        )

        client.load_registers('read', 0, 1)

        assert client.latest_scrape['test_u16'] == 0

    def test_u16_mask_applied(self):
        client = make_client()
        client.client = MagicMock()
        client.registers = [
            {'name': 'test_mask', 'type': 'read',
             'address': 1, 'datatype': 'U16', 'mask': 0x01}
        ]
        client.client.read_input_registers.return_value = (
            make_mock_response([0x03])
        )

        client.load_registers('read', 0, 1)

        assert client.latest_scrape['test_mask'] == 1

    def test_u16_mask_zero_when_no_match(self):
        # The mask code at line 249:
        #   register_value = 1 if register_value & register.get('mask') != 0 else 0
        # In Python, & has higher precedence than !=, so this correctly parses as:
        #   (register_value & register.get('mask')) != 0
        # So 0x03 & 0x04 => 0 => register_value = 0
        client = make_client()
        client.client = MagicMock()
        client.registers = [
            {'name': 'test_mask', 'type': 'read',
             'address': 1, 'datatype': 'U16', 'mask': 0x04}
        ]
        client.client.read_input_registers.return_value = (
            make_mock_response([0x03])
        )

        client.load_registers('read', 0, 1)

        assert client.latest_scrape['test_mask'] == 0


class TestLoadRegistersS16:
    """S16 register type decoding."""

    def test_s16_positive_value(self):
        client = make_client()
        client.client = MagicMock()
        client.registers = [
            {'name': 'test_s16', 'type': 'read',
             'address': 1, 'datatype': 'S16'}
        ]
        client.client.read_input_registers.return_value = (
            make_mock_response([100])
        )

        client.load_registers('read', 0, 1)

        assert client.latest_scrape['test_s16'] == 100

    def test_s16_negative_value(self):
        client = make_client()
        client.client = MagicMock()
        client.registers = [
            {'name': 'test_s16', 'type': 'read',
             'address': 1, 'datatype': 'S16'}
        ]
        client.client.read_input_registers.return_value = (
            make_mock_response([65535])
        )

        client.load_registers('read', 0, 1)

        # 0xFFFF is sentinel, treated as 0
        assert client.latest_scrape['test_s16'] == 0

    def test_s16_large_negative(self):
        client = make_client()
        client.client = MagicMock()
        client.registers = [
            {'name': 'test_s16', 'type': 'read',
             'address': 1, 'datatype': 'S16'}
        ]
        client.client.read_input_registers.return_value = (
            make_mock_response([32768])
        )

        client.load_registers('read', 0, 1)

        assert client.latest_scrape['test_s16'] == -32768


class TestLoadRegistersU32:
    """U32 register type decoding."""

    def test_u32_normal_value(self):
        client = make_client()
        client.client = MagicMock()
        client.registers = [
            {'name': 'test_u32', 'type': 'read',
             'address': 1, 'datatype': 'U32'}
        ]
        # low=100, high=1 => 100 + 1 * 0x10000 = 65636
        client.client.read_input_registers.return_value = (
            make_mock_response([100, 1])
        )

        client.load_registers('read', 0, 2)

        assert client.latest_scrape['test_u32'] == 65636

    def test_u32_ffff_ffff_becomes_zero(self):
        client = make_client()
        client.client = MagicMock()
        client.registers = [
            {'name': 'test_u32', 'type': 'read',
             'address': 1, 'datatype': 'U32'}
        ]
        client.client.read_input_registers.return_value = (
            make_mock_response([0xFFFF, 0xFFFF])
        )

        client.load_registers('read', 0, 2)

        assert client.latest_scrape['test_u32'] == 0


class TestLoadRegistersS32:
    """S32 register type decoding."""

    def test_s32_positive_value(self):
        client = make_client()
        client.client = MagicMock()
        client.registers = [
            {'name': 'test_s32', 'type': 'read',
             'address': 1, 'datatype': 'S32'}
        ]
        client.client.read_input_registers.return_value = (
            make_mock_response([100, 1])
        )

        client.load_registers('read', 0, 2)

        assert client.latest_scrape['test_s32'] == 65636

    def test_s32_negative_value(self):
        client = make_client()
        client.client = MagicMock()
        client.registers = [
            {'name': 'test_s32', 'type': 'read',
             'address': 1, 'datatype': 'S32'}
        ]
        client.client.read_input_registers.return_value = (
            make_mock_response([0, 0xFFFF])
        )

        client.load_registers('read', 0, 2)

        assert client.latest_scrape['test_s32'] == -65536


class TestLoadRegistersDatarange:
    """Datarange (enum) mapping."""

    def test_datarange_maps_response_to_value(self):
        client = make_client()
        client.client = MagicMock()
        client.registers = [
            {'name': 'test_enum', 'type': 'read', 'address': 1,
             'datatype': 'U16',
             'datarange': [
                 {'response': 1, 'value': 'Running'},
                 {'response': 0, 'value': 'Stopped'},
             ]}
        ]
        client.client.read_input_registers.return_value = (
            make_mock_response([1])
        )

        client.load_registers('read', 0, 1)

        assert client.latest_scrape['test_enum'] == 'Running'

    def test_datarange_uses_default_on_no_match(self):
        client = make_client()
        client.client = MagicMock()
        client.registers = [
            {'name': 'test_enum', 'type': 'read', 'address': 1,
             'datatype': 'U16', 'default': 'Unknown',
             'datarange': [
                 {'response': 1, 'value': 'Running'},
             ]}
        ]
        client.client.read_input_registers.return_value = (
            make_mock_response([99])
        )

        client.load_registers('read', 0, 1)

        assert client.latest_scrape['test_enum'] == 'Unknown'


class TestLoadRegistersAccuracy:
    """Accuracy multiplier."""

    def test_accuracy_multiplier_applied(self):
        client = make_client()
        client.client = MagicMock()
        client.registers = [
            {'name': 'test_acc', 'type': 'read', 'address': 1,
             'datatype': 'U16', 'accuracy': 0.1}
        ]
        client.client.read_input_registers.return_value = (
            make_mock_response([500])
        )

        client.load_registers('read', 0, 1)

        assert client.latest_scrape['test_acc'] == 50.0


class TestLoadRegistersErrorHandling:
    """Error paths in load_registers."""

    def test_returns_false_on_exception(self):
        client = make_client()
        client.client = MagicMock()
        client.client.read_input_registers.side_effect = (
            Exception("connection lost")
        )

        result = client.load_registers('read', 0, 1)

        assert result is False

    def test_returns_false_on_modbus_error(self):
        client = make_client()
        client.client = MagicMock()
        client.client.read_input_registers.return_value = (
            make_mock_response([], is_error=True)
        )

        result = client.load_registers('read', 0, 1)

        assert result is False

    def test_returns_false_on_count_mismatch(self):
        client = make_client()
        client.client = MagicMock()
        resp = make_mock_response([1])
        client.client.read_input_registers.return_value = resp

        result = client.load_registers('read', 0, 2)

        assert result is False

    def test_hold_type_uses_holding_registers(self):
        client = make_client()
        client.client = MagicMock()
        client.registers = [
            {'name': 'test_hold', 'type': 'hold',
             'address': 1, 'datatype': 'U16'}
        ]
        client.client.read_holding_registers.return_value = (
            make_mock_response([42])
        )

        client.load_registers('hold', 0, 1)

        assert client.latest_scrape['test_hold'] == 42
        client.client.read_holding_registers.assert_called_once()
