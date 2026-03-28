from unittest.mock import patch, MagicMock, PropertyMock
import pytest

from client.sungrow_client import SungrowClient


def make_config(**overrides):
    defaults = {
        'host': '192.168.1.1',
        'port': 502,
        'timeout': 10,
        'retries': 3,
        'slave': 0x01,
        'scan_interval': 30,
        'connection': 'modbus',
        'model': None,
        'serial_number': None,
        'level': 1,
        'use_local_time': False,
        'smart_meter': False,
    }
    defaults.update(overrides)
    return defaults


class TestSungrowClientInit:
    def test_init_stores_config(self):
        """Init should store client and inverter config from input."""
        config = make_config()
        client = SungrowClient(config)
        assert client.client_config['host'] == '192.168.1.1'
        assert client.client_config['port'] == 502
        assert client.inverter_config['connection'] == 'modbus'

    def test_init_does_not_include_retry_on_empty(self):
        """pymodbus 3.x removed RetryOnEmpty -- should not be in config."""
        config = make_config()
        client = SungrowClient(config)
        assert 'RetryOnEmpty' not in client.client_config


class TestSungrowClientConnect:
    @patch('client.sungrow_client.ModbusTcpClient')
    def test_connect_modbus_passes_host_positionally(self, MockClient):
        """ModbusTcpClient must receive host as first positional arg."""
        mock_instance = MagicMock()
        mock_instance.connect.return_value = True
        MockClient.return_value = mock_instance

        config = make_config(connection='modbus')
        client = SungrowClient(config)
        result = client.connect()

        MockClient.assert_called_once()
        args, kwargs = MockClient.call_args
        assert args[0] == '192.168.1.1'
        assert 'host' not in kwargs
        assert result is True

    @patch('client.sungrow_client.SungrowModbusTcpClient')
    def test_connect_sungrow_passes_host_positionally(self, MockClient):
        """SungrowModbusTcpClient must also receive host positionally."""
        mock_instance = MagicMock()
        mock_instance.connect.return_value = True
        MockClient.return_value = mock_instance

        config = make_config(connection='sungrow')
        client = SungrowClient(config)
        result = client.connect()

        MockClient.assert_called_once()
        args, kwargs = MockClient.call_args
        assert args[0] == '192.168.1.1'
        assert 'host' not in kwargs
        assert result is True

    @patch('client.sungrow_client.SungrowModbusWebClient')
    def test_connect_http_passes_host_as_keyword_and_overrides_port(self, MockClient):
        """SungrowModbusWebClient must receive host as keyword arg, port=8082."""
        mock_instance = MagicMock()
        mock_instance.connect.return_value = True
        MockClient.return_value = mock_instance

        config = make_config(connection='http')
        client = SungrowClient(config)
        result = client.connect()

        MockClient.assert_called_once()
        args, kwargs = MockClient.call_args
        assert args == ()
        assert kwargs['host'] == '192.168.1.1'
        assert kwargs['port'] == 8082
        assert result is True


class TestSungrowClientCheckConnection:
    def test_check_connection_uses_connected_property(self):
        """checkConnection should use client.connected (not is_socket_open)."""
        config = make_config()
        client = SungrowClient(config)
        client.client = MagicMock()
        connected_prop = PropertyMock(return_value=True)
        type(client.client).connected = connected_prop

        result = client.checkConnection()

        assert result is True
        connected_prop.assert_called()


class TestSungrowClientLoadRegisters:
    def test_load_registers_uses_device_id_param(self):
        """load_registers should pass device_id= (not unit=) to pymodbus."""
        config = make_config()
        client = SungrowClient(config)
        client.client = MagicMock()
        mock_response = MagicMock()
        mock_response.isError.return_value = False
        mock_response.registers = [100]
        client.client.read_input_registers.return_value = mock_response

        client.registers = [
            {'name': 'test_reg', 'type': 'read', 'address': 1, 'datatype': 'U16'}
        ]
        client.load_registers('read', 0, 1)

        client.client.read_input_registers.assert_called_once_with(
            0, count=1, device_id=0x01
        )

    def test_load_registers_hold_uses_device_id_param(self):
        """load_registers for hold type should also use device_id=."""
        config = make_config()
        client = SungrowClient(config)
        client.client = MagicMock()
        mock_response = MagicMock()
        mock_response.isError.return_value = False
        mock_response.registers = [200]
        client.client.read_holding_registers.return_value = mock_response

        client.registers = [
            {'name': 'test_hold', 'type': 'hold', 'address': 1,
             'datatype': 'U16'}
        ]
        client.load_registers('hold', 0, 1)

        client.client.read_holding_registers.assert_called_once_with(
            0, count=1, device_id=0x01
        )
