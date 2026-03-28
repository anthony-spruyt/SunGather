from unittest.mock import patch, MagicMock
import pytest

from client.sungrow_modbus_tcp_client import SungrowModbusTcpClient


class TestSungrowModbusTcpClientInit:
    def test_extends_modbus_tcp_client(self):
        """SungrowModbusTcpClient should extend pymodbus ModbusTcpClient."""
        from pymodbus.client import ModbusTcpClient
        assert issubclass(SungrowModbusTcpClient, ModbusTcpClient)

    @patch('client.sungrow_modbus_tcp_client.ModbusTcpClient.__init__',
           return_value=None)
    def test_init_stores_original_send_recv(self, mock_init):
        """Init should store references to the original send/recv methods."""
        client = SungrowModbusTcpClient.__new__(SungrowModbusTcpClient)
        # Manually set attributes that __init__ would set via super()
        client.send = MagicMock(name='original_send')
        client.recv = MagicMock(name='original_recv')
        client.__init__(host='192.168.1.1')
        assert client._orig_send is not None
        assert client._orig_recv is not None


class TestEncryptionSetupRestore:
    @patch('client.sungrow_modbus_tcp_client.ModbusTcpClient.__init__',
           return_value=None)
    def test_setup_swaps_to_cipher_methods(self, mock_init):
        """After _setup(), send/recv should point to cipher methods."""
        client = SungrowModbusTcpClient.__new__(SungrowModbusTcpClient)
        client.send = MagicMock(name='original_send')
        client.recv = MagicMock(name='original_recv')
        client._orig_send = client.send
        client._orig_recv = client.recv
        client._priv_key = b'Grow#0*2Sun68CbE'
        client._pub_key = b'\x01' * 16
        client._fifo = bytes()

        client._setup()

        assert client.send == client._send_cipher
        assert client.recv == client._recv_decipher

    @patch('client.sungrow_modbus_tcp_client.ModbusTcpClient.__init__',
           return_value=None)
    def test_restore_swaps_back_to_original(self, mock_init):
        """After _restore(), send/recv should point back to originals."""
        client = SungrowModbusTcpClient.__new__(SungrowModbusTcpClient)
        orig_send = MagicMock(name='original_send')
        orig_recv = MagicMock(name='original_recv')
        client.send = orig_send
        client.recv = orig_recv
        client._orig_send = orig_send
        client._orig_recv = orig_recv
        client._priv_key = b'Grow#0*2Sun68CbE'
        client._pub_key = b'\x01' * 16
        client._fifo = bytes()

        client._setup()
        client._restore()

        assert client.send == orig_send
        assert client.recv == orig_recv
