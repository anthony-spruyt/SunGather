# pylint: disable=import-outside-toplevel
from unittest.mock import patch, MagicMock

from client.sungrow_modbus_tcp_client import SungrowModbusTcpClient


class TestSungrowModbusTcpClientInit:
    def test_extends_modbus_tcp_client(self):
        """SungrowModbusTcpClient should extend pymodbus ModbusTcpClient."""
        from pymodbus.client import ModbusTcpClient
        assert issubclass(SungrowModbusTcpClient, ModbusTcpClient)

    @patch('client.sungrow_modbus_tcp_client.ModbusTcpClient.__init__',
           return_value=None)
    def test_init_sets_cipher_off(self, _mock_init):
        """Init should start with cipher disabled."""
        client = SungrowModbusTcpClient.__new__(SungrowModbusTcpClient)
        client.__init__(host='192.168.1.1')  # pylint: disable=unnecessary-dunder-call
        assert client._use_cipher is False
        assert client._key is None
        assert client._aes_ecb is None


class TestEncryptionSetupRestore:
    @patch('client.sungrow_modbus_tcp_client.ModbusTcpClient.__init__',
           return_value=None)
    def test_setup_enables_cipher_flag(self, _mock_init):
        """After _setup(), _use_cipher should be True."""
        client = SungrowModbusTcpClient.__new__(SungrowModbusTcpClient)
        client._priv_key = b'Grow#0*2Sun68CbE'
        client._pub_key = b'\x01' * 16
        client._fifo = bytes()
        client._use_cipher = False

        client._setup()

        assert client._use_cipher is True
        assert client._key is not None
        assert client._aes_ecb is not None

    @patch('client.sungrow_modbus_tcp_client.ModbusTcpClient.__init__',
           return_value=None)
    def test_restore_disables_cipher_flag(self, _mock_init):
        """After _restore(), _use_cipher should be False."""
        client = SungrowModbusTcpClient.__new__(SungrowModbusTcpClient)
        client._priv_key = b'Grow#0*2Sun68CbE'
        client._pub_key = b'\x01' * 16
        client._fifo = bytes()
        client._use_cipher = False

        client._setup()
        assert client._use_cipher is True

        client._restore()
        assert client._use_cipher is False
        assert client._key is None
        assert client._aes_ecb is None

    @patch('client.sungrow_modbus_tcp_client.ModbusTcpClient.__init__',
           return_value=None)
    def test_send_delegates_to_cipher_when_enabled(self, _mock_init):
        """send() should call _send_cipher when cipher is active."""
        client = SungrowModbusTcpClient.__new__(SungrowModbusTcpClient)
        client._use_cipher = True
        client._send_cipher = MagicMock(return_value=10)

        result = client.send(b'\x00\x01\x00\x00\x00\x06\x01\x04\x00\x00\x00\x01')
        client._send_cipher.assert_called_once()
        assert result == 10

    @patch('client.sungrow_modbus_tcp_client.ModbusTcpClient.__init__',
           return_value=None)
    @patch('client.sungrow_modbus_tcp_client.ModbusTcpClient.send',
           return_value=12)
    def test_send_delegates_to_parent_when_cipher_off(self, mock_send, _mock_init):
        """send() should call parent send when cipher is inactive."""
        client = SungrowModbusTcpClient.__new__(SungrowModbusTcpClient)
        client._use_cipher = False

        request = b'\x00\x01\x00\x00\x00\x06\x01\x04\x00\x00\x00\x01'
        result = client.send(request)
        mock_send.assert_called_once_with(request, None)
        assert result == 12
