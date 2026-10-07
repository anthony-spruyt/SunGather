from unittest.mock import MagicMock, patch

import pytest

from sungather.client.sungrow_modbus_tcp_client import SungrowModbusTcpClient


class TestSungrowModbusTcpClientInit:
    def test_extends_modbus_tcp_client(self):
        """SungrowModbusTcpClient should extend pymodbus ModbusTcpClient."""
        from pymodbus.client import ModbusTcpClient

        assert issubclass(SungrowModbusTcpClient, ModbusTcpClient)

    @patch("sungather.client.sungrow_modbus_tcp_client.ModbusTcpClient.__init__", return_value=None)
    def test_init_sets_cipher_off(self, mock_init):
        """Init should start with cipher disabled."""
        client = SungrowModbusTcpClient.__new__(SungrowModbusTcpClient)
        client.__init__(host="192.0.2.1")
        assert client._use_cipher is False
        assert client._key is None
        assert client._aes_ecb is None


class TestEncryptionSetupRestore:
    @patch("sungather.client.sungrow_modbus_tcp_client.ModbusTcpClient.__init__", return_value=None)
    def test_setup_enables_cipher_flag(self, mock_init):
        """After _setup(), _use_cipher should be True."""
        client = SungrowModbusTcpClient.__new__(SungrowModbusTcpClient)
        client._priv_key = b"Grow#0*2Sun68CbE"
        client._pub_key = b"\x01" * 16
        client._fifo = b""
        client._use_cipher = False

        client._setup()

        assert client._use_cipher is True
        assert client._key is not None
        assert client._aes_ecb is not None

    @patch("sungather.client.sungrow_modbus_tcp_client.ModbusTcpClient.__init__", return_value=None)
    def test_restore_disables_cipher_flag(self, mock_init):
        """After _restore(), _use_cipher should be False."""
        client = SungrowModbusTcpClient.__new__(SungrowModbusTcpClient)
        client._priv_key = b"Grow#0*2Sun68CbE"
        client._pub_key = b"\x01" * 16
        client._fifo = b""
        client._use_cipher = False

        client._setup()
        assert client._use_cipher is True

        client._restore()
        assert client._use_cipher is False
        assert client._key is None
        assert client._aes_ecb is None

    @patch("sungather.client.sungrow_modbus_tcp_client.ModbusTcpClient.__init__", return_value=None)
    def test_send_delegates_to_cipher_when_enabled(self, mock_init):
        """send() should call _send_cipher when cipher is active."""
        client = SungrowModbusTcpClient.__new__(SungrowModbusTcpClient)
        client._use_cipher = True
        client._send_cipher = MagicMock(return_value=10)

        result = client.send(b"\x00\x01\x00\x00\x00\x06\x01\x04\x00\x00\x00\x01")
        client._send_cipher.assert_called_once()
        assert result == 10

    @patch("sungather.client.sungrow_modbus_tcp_client.ModbusTcpClient.__init__", return_value=None)
    @patch("sungather.client.sungrow_modbus_tcp_client.ModbusTcpClient.send", return_value=12)
    def test_send_delegates_to_parent_when_cipher_off(self, mock_send, mock_init):
        """send() should call parent send when cipher is inactive."""
        client = SungrowModbusTcpClient.__new__(SungrowModbusTcpClient)
        client._use_cipher = False

        request = b"\x00\x01\x00\x00\x00\x06\x01\x04\x00\x00\x00\x01"
        result = client.send(request)
        mock_send.assert_called_once_with(request, None)
        assert result == 12

    @patch("sungather.client.sungrow_modbus_tcp_client.ModbusTcpClient.__init__", return_value=None)
    def test_send_cipher_pads_with_0xff_and_encrypts(self, mock_init):
        """_send_cipher() should prefix a crypto header and AES-encrypt the 0xFF-padded frame."""
        client = SungrowModbusTcpClient.__new__(SungrowModbusTcpClient)
        client._priv_key = b"Grow#0*2Sun68CbE"
        client._pub_key = b"\x01" * 16
        client._use_cipher = False
        client._setup()

        request = b"\x00\x01\x00\x00\x00\x06\x01\x04\x00\x00\x00\x01"
        with patch("sungather.client.sungrow_modbus_tcp_client.ModbusTcpClient.send", side_effect=len) as mock_send:
            result = client._send_cipher(request)

        sent = mock_send.call_args.args[0]
        assert sent[:4] == bytes([1, 0, 12, 4])
        plain = client._aes_ecb.decrypt(sent[4:])
        assert plain == b"\x68\x68" + request[2:] + b"\xff" * 4
        assert client._transactionID == request[:2]
        assert result == len(request)


def _cipher_client():
    client = SungrowModbusTcpClient.__new__(SungrowModbusTcpClient)
    client._priv_key = b"Grow#0*2Sun68CbE"
    client._pub_key = b"\x01" * 16
    client._use_cipher = False
    client._setup()
    return client


class TestCipherFullBlockPadding:
    @pytest.mark.parametrize("length", [16, 32])
    @patch("sungather.client.sungrow_modbus_tcp_client.ModbusTcpClient.__init__", return_value=None)
    def test_send_cipher_adds_a_whole_0xff_block_to_a_block_aligned_frame(self, mock_init, length):
        client = _cipher_client()
        request = b"\x00\x07" + bytes(range(1, length - 1))

        with patch("sungather.client.sungrow_modbus_tcp_client.ModbusTcpClient.send", side_effect=len) as mock_send:
            result = client._send_cipher(request)

        sent = mock_send.call_args.args[0]
        assert sent[:4] == bytes([1, 0, length, 16])
        assert len(sent) == 4 + length + 16
        assert client._aes_ecb.decrypt(sent[4:]) == b"\x68\x68" + request[2:] + b"\xff" * 16
        assert result == length

    @pytest.mark.parametrize("length", [16, 32])
    @patch("sungather.client.sungrow_modbus_tcp_client.ModbusTcpClient.__init__", return_value=None)
    def test_recv_decipher_strips_a_whole_padding_block(self, mock_init, length):
        client = _cipher_client()
        client._fifo = b""
        client._transactionID = b"\x00\x07"
        response = b"\x68\x68" + bytes(range(1, length - 1))
        reply = [bytes([1, 0, length, 16]), client._aes_ecb.encrypt(response + b"\xff" * 16)]

        with patch(
            "sungather.client.sungrow_modbus_tcp_client.ModbusTcpClient.recv", side_effect=lambda size: reply.pop(0)
        ) as mock_recv:
            received = client._recv_decipher(length)

        assert [c.args[0] for c in mock_recv.call_args_list] == [4, length + 16]
        assert received == b"\x00\x07" + response[2:]
        assert client._fifo == b""


class TestGetKey:
    @pytest.mark.parametrize(
        ("pub_key", "use_cipher"),
        [
            (b"\x01" * 16, True),
            (b"\x00" * 16, False),
            (b"\xff" * 16, False),
            (b"\x01" * 15, False),
        ],
    )
    @patch("sungather.client.sungrow_modbus_tcp_client.ModbusTcpClient.__init__", return_value=None)
    def test_getkey_enables_cipher_only_for_a_real_16_byte_key(self, mock_init, pub_key, use_cipher):
        client = SungrowModbusTcpClient.__new__(SungrowModbusTcpClient)
        client._priv_key = b"Grow#0*2Sun68CbE"
        client._key = None
        client._fifo = b""

        with (
            patch("sungather.client.sungrow_modbus_tcp_client.ModbusTcpClient.send"),
            patch(
                "sungather.client.sungrow_modbus_tcp_client.ModbusTcpClient.recv", return_value=b"\x00" * 9 + pub_key
            ),
        ):
            client._getkey()

        assert client._use_cipher is use_cipher
        assert (client._key == b"no encryption") is not use_cipher
