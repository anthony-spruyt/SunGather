from pymodbus.client import ModbusTcpClient
from Cryptodome.Cipher import AES
from datetime import date

PRIV_KEY = b'Grow#0*2Sun68CbE'
NO_CRYPTO1 = b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
NO_CRYPTO2 = b'\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff'
GET_KEY = b'\x68\x68\x00\x00\x00\x06\xf7\x04\x0a\xe7\x00\x08'
HEADER = bytes([0x68, 0x68])


class SungrowModbusTcpClient(ModbusTcpClient):
    def __init__(self, host, priv_key=PRIV_KEY, **kwargs):
        super().__init__(host, **kwargs)
        self._fifo = bytes()
        self._priv_key = priv_key
        self._key = None
        self._aes_ecb = None
        self._use_cipher = False
        self._key_date = date.today()

    def _setup(self):
        self._key = bytes(a ^ b for (a, b) in zip(self._pub_key, self._priv_key))
        self._aes_ecb = AES.new(self._key, AES.MODE_ECB)
        self._key_date = date.today()
        self._use_cipher = True
        self._fifo = bytes()

    def _restore(self):
        self._key = None
        self._aes_ecb = None
        self._use_cipher = False
        self._fifo = bytes()

    def _getkey(self):
        if (self._key is None) or (self._key_date != date.today()):
            self._restore()
            super().send(GET_KEY)
            self._key_packet = super().recv(25)
            self._pub_key = self._key_packet[9:]
            if (len(self._pub_key) == 16) and \
               (self._pub_key != NO_CRYPTO1) and \
               (self._pub_key != NO_CRYPTO2):
                self._setup()
            else:
                self._key = b'no encryption'
                self._key_date = date.today()

    def connect(self):
        self.close()
        result = super().connect()
        if not result:
            self._restore()
        else:
            self._getkey()
            if self._key is not None:
                self.close()
                result = super().connect()
        return result

    def close(self):
        super().close()
        self._fifo = bytes()

    def send(self, request, addr=None):
        if self._use_cipher:
            return self._send_cipher(request, addr)
        return super().send(request, addr)

    def recv(self, size):
        if self._use_cipher:
            return self._recv_decipher(size)
        return super().recv(size)

    def _send_cipher(self, request, addr=None):
        self._fifo = bytes()
        length = len(request)
        padding = 16 - (length % 16)
        self._transactionID = request[:2]
        request = HEADER + bytes(request[2:]) + bytes([0xff for i in range(0, padding)])
        crypto_header = bytes([1, 0, length, padding])
        encrypted_request = crypto_header + self._aes_ecb.encrypt(request)
        return super().send(encrypted_request) - len(crypto_header) - padding

    def _recv_decipher(self, size):
        if len(self._fifo) == 0:
            header = super().recv(4)
            if header and len(header) == 4:
                packet_len = int(header[2])
                padding = int(header[3])
                length = packet_len + padding
                encrypted_packet = super().recv(length)
                if encrypted_packet and len(encrypted_packet) == length:
                    packet = self._aes_ecb.decrypt(encrypted_packet)
                    packet = self._transactionID + packet[2:]
                    self._fifo = self._fifo + packet[:packet_len]

        if size is None:
            recv_size = 1
        else:
            recv_size = size

        recv_size = min(recv_size, len(self._fifo))
        result = self._fifo[:recv_size]
        self._fifo = self._fifo[recv_size:]
        return result
