from unittest.mock import MagicMock, patch

import pytest

from sungather.client.sungrow_modbus_web_client import SungrowModbusWebClient


class TestSungrowModbusWebClientInit:
    def test_extends_modbus_tcp_client(self):
        """SungrowModbusWebClient should extend pymodbus ModbusTcpClient."""
        from pymodbus.client import ModbusTcpClient

        assert issubclass(SungrowModbusWebClient, ModbusTcpClient)

    def test_init_sets_defaults(self):
        """Init should set default host, port, and endpoint."""
        client = SungrowModbusWebClient(host="192.0.2.1")
        assert client.dev_host == "192.0.2.1"
        assert client.ws_port == 8082
        assert "ws://192.0.2.1:8082" in client.ws_endpoint


class TestWebClientConnect:
    @patch("sungather.client.sungrow_modbus_web_client.create_connection")
    def test_connect_returns_true_if_already_has_token(self, mock_ws):
        """If token already exists, connect should return True without reconnecting."""
        client = SungrowModbusWebClient(host="192.0.2.1")
        client.ws_token = "existing_token"
        result = client.connect()
        assert result is True
        mock_ws.assert_not_called()


class TestWebClientConnectedProperty:
    def test_connected_false_when_no_socket(self):
        """connected should return False when ws_socket is None."""
        client = SungrowModbusWebClient(host="192.0.2.1")
        client.ws_socket = None
        assert client.connected is False

    def test_connected_true_when_socket_exists(self):
        """connected should return True when ws_socket is set."""
        client = SungrowModbusWebClient(host="192.0.2.1")
        client.ws_socket = MagicMock()
        assert client.connected is True


class TestWebClientSend:
    @patch("sungather.client.sungrow_modbus_web_client.requests.get")
    def test_expired_token_is_cleared_and_raised(self, mock_get):
        from pymodbus.exceptions import ConnectionException

        mock_get.return_value = MagicMock(status_code=200, text='{"result_code": 106, "result_msg": "expired"}')
        client = SungrowModbusWebClient(host="192.0.2.1")
        client.ws_token = "stale"

        with pytest.raises(ConnectionException, match="Token Expired"):
            client.send(bytes([0, 1, 0, 0, 0, 6, 1, 4, 0, 0, 0, 1]))
        assert client.ws_token == ""

    @patch("sungather.client.sungrow_modbus_web_client.requests.get")
    def test_other_result_code_is_a_connection_failure(self, mock_get):
        from pymodbus.exceptions import ConnectionException

        mock_get.return_value = MagicMock(status_code=200, text='{"result_code": 105, "result_msg": "nope"}')
        client = SungrowModbusWebClient(host="192.0.2.1")
        client.ws_token = "valid"

        with pytest.raises(ConnectionException, match="Connection Failed"):
            client.send(bytes([0, 1, 0, 0, 0, 6, 1, 4, 0, 0, 0, 1]))
        assert client.ws_token == "valid"
