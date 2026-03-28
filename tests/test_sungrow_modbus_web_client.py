# pylint: disable=import-outside-toplevel
from unittest.mock import patch, MagicMock

from client.sungrow_modbus_web_client import SungrowModbusWebClient


class TestSungrowModbusWebClientInit:
    def test_extends_modbus_tcp_client(self):
        """SungrowModbusWebClient should extend pymodbus ModbusTcpClient."""
        from pymodbus.client import ModbusTcpClient
        assert issubclass(SungrowModbusWebClient, ModbusTcpClient)

    def test_init_sets_defaults(self):
        """Init should set default host, port, and endpoint."""
        client = SungrowModbusWebClient(host='192.168.1.1')
        assert client.dev_host == '192.168.1.1'
        assert client.ws_port == 8082
        assert 'ws://192.168.1.1:8082' in client.ws_endpoint


class TestWebClientConnect:
    @patch('client.sungrow_modbus_web_client.create_connection')
    def test_connect_returns_true_if_already_has_token(self, mock_ws):
        """If token already exists, connect should return True without reconnecting."""
        client = SungrowModbusWebClient(host='192.168.1.1')
        client.ws_token = "existing_token"
        result = client.connect()
        assert result is True
        mock_ws.assert_not_called()


class TestWebClientConnectedProperty:
    def test_connected_false_when_no_socket(self):
        """connected should return False when ws_socket is None."""
        client = SungrowModbusWebClient(host='192.168.1.1')
        client.ws_socket = None
        assert client.connected is False

    def test_connected_true_when_socket_exists(self):
        """connected should return True when ws_socket is set."""
        client = SungrowModbusWebClient(host='192.168.1.1')
        client.ws_socket = MagicMock()
        assert client.connected is True
