# Stale Connection Fix & Pymodbus Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix stale Modbus connections by adding a data-freshness health endpoint,
and resolve pymodbus CVEs by vendoring SungrowClient and upgrading to pymodbus 3.x.

**Architecture:** Vendor the three upstream client packages (`SungrowClient`,
`SungrowModbusTcpClient`, `SungrowModbusWebClient`) into `SunGather/client/`,
migrate all pymodbus 2.x API calls to 3.x, add a `/health` endpoint to the
existing webserver export, and update the Dockerfile HEALTHCHECK.

**Tech Stack:** Python 3.14, pymodbus 3.x, pycryptodomex, websocket-client, pytest

**Spec:** `docs/superpowers/specs/2026-03-27-stale-connection-health-endpoint-design.md`

---

## Tasks

### Task 1: Project setup -- test infrastructure and dependency updates

**Files:**

- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `SunGather/client/__init__.py`
- Modify: `requirements.txt`
- Modify: `setup.py`

- [ ] **Step 1: Create test directory and conftest**

Create `tests/__init__.py` (empty) and `tests/conftest.py`:

```python
import sys
import os

# Add SunGather directory to path so imports work like they do at runtime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'SunGather'))
```

- [ ] **Step 2: Create empty client package**

Create `SunGather/client/__init__.py` (empty file).

- [ ] **Step 3: Update requirements.txt**

Replace contents with:

```text
PyYAML~=6.0
paho-mqtt~=2.0
requests~=2.0
influxdb-client~=1.0
pymodbus>=3.6.0,<4.0.0
pycryptodomex
websocket-client>=1.2.1
```

- [ ] **Step 4: Update setup.py**

Replace `install_requires` block:

```python
install_requires=[
    'pymodbus>=3.6.0,<4.0.0',
    'websocket-client>=1.2.1',
    'pycryptodomex',
],
```

- [ ] **Step 5: Install updated dependencies**

Run: `pip install --upgrade -r requirements.txt`
Run: `pip install pytest`

Expected: All packages install successfully, pymodbus 3.x is installed.

- [ ] **Step 6: Verify pymodbus 3.x is available**

Run: `python3 -c "from pymodbus.client import ModbusTcpClient; print('ok')"`

Expected: `ok`

- [ ] **Step 7: Commit**

```bash
git add tests/__init__.py tests/conftest.py SunGather/client/__init__.py \
  requirements.txt setup.py
git commit -m "chore: set up test infrastructure and update dependencies for pymodbus 3.x"
```

---

### Task 2: Vendor and migrate sungrow_modbus_tcp_client.py

This is the AES encryption client that extends `ModbusTcpClient`. It has the most
complex migration due to dynamic method swapping.

**Files:**

- Create: `SunGather/client/sungrow_modbus_tcp_client.py`
- Create: `tests/test_sungrow_modbus_tcp_client.py`

**Upstream source:**
`/usr/local/python/current/lib/python3.14/site-packages/SungrowModbusTcpClient/SungrowModbusTcpClient.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_sungrow_modbus_tcp_client.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /workspaces/SunGather && python3 -m pytest tests/test_sungrow_modbus_tcp_client.py -v`

Expected: FAIL (module `client.sungrow_modbus_tcp_client` not found)

- [ ] **Step 3: Vendor and migrate the module**

Create `SunGather/client/sungrow_modbus_tcp_client.py`:

```python
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
        self._orig_recv = self.recv
        self._orig_send = self.send
        self._key_date = date.today()

    def _setup(self):
        self._key = bytes(a ^ b for (a, b) in zip(self._pub_key, self._priv_key))
        self._aes_ecb = AES.new(self._key, AES.MODE_ECB)
        self._key_date = date.today()
        self.send = self._send_cipher
        self.recv = self._recv_decipher
        self._fifo = bytes()

    def _restore(self):
        self._key = None
        self._aes_ecb = None
        self.send = self._orig_send
        self.recv = self._orig_recv
        self._fifo = bytes()

    def _getkey(self):
        if (self._key is None) or (self._key_date != date.today()):
            self._restore()
            self._orig_send(GET_KEY)
            self._key_packet = self._orig_recv(25)
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /workspaces/SunGather && python3 -m pytest tests/test_sungrow_modbus_tcp_client.py -v`

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add SunGather/client/sungrow_modbus_tcp_client.py \
  tests/test_sungrow_modbus_tcp_client.py
git commit -m "feat: vendor and migrate SungrowModbusTcpClient to pymodbus 3.x"
```

---

### Task 3: Vendor and migrate sungrow_modbus_web_client.py

This is the HTTP/WebSocket client for the WiNet-S dongle. The upstream extends
`BaseModbusClient`, but in pymodbus 3.x `ModbusBaseSyncClient.__init__` requires
6 positional arguments and can't be called simply. Instead, extend `ModbusTcpClient`
which provides a user-friendly constructor, and override `connect()`, `send()`,
`recv()`, and `close()`.

**Files:**

- Create: `SunGather/client/sungrow_modbus_web_client.py`
- Create: `tests/test_sungrow_modbus_web_client.py`

**Upstream source:**
`/usr/local/python/current/lib/python3.14/site-packages/SungrowModbusWebClient/SungrowModbusWebClient.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_sungrow_modbus_web_client.py`:

```python
from unittest.mock import patch, MagicMock
import pytest

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /workspaces/SunGather && python3 -m pytest tests/test_sungrow_modbus_web_client.py -v`

Expected: FAIL (module not found)

- [ ] **Step 3: Vendor and migrate the module**

Create `SunGather/client/sungrow_modbus_web_client.py`:

```python
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ConnectionException
from websocket import create_connection

from version import __version__

import requests
import logging
import json
import time


class SungrowModbusWebClient(ModbusTcpClient):
    """Modbus over Sungrow HTTP client for WiNet-S Dongle."""

    # Parameters accepted by ModbusTcpClient.__init__
    _ACCEPTED_KWARGS = {
        'framer', 'port', 'name', 'source_address',
        'reconnect_delay', 'reconnect_delay_max', 'timeout',
        'retries', 'trace_packet', 'trace_pdu', 'trace_connect',
    }

    def __init__(self, host='127.0.0.1', port=8082, **kwargs):
        self.dev_host = host
        self.ws_port = port
        self.timeout = kwargs.get('timeout', '5')
        self.ws_socket = None

        # Filter to only params ModbusTcpClient accepts
        filtered = {k: v for k, v in kwargs.items()
                    if k in self._ACCEPTED_KWARGS}
        super().__init__(host, port=port, **filtered)

        self.ws_endpoint = (
            "ws://" + str(self.dev_host) + ":" + str(self.ws_port) +
            "/ws/home/overview"
        )
        self.ws_token = ""
        self.dev_type = ""
        self.dev_code = ""

    def connect(self):
        if self.ws_token:
            return True

        try:
            self.ws_socket = create_connection(
                self.ws_endpoint, timeout=self.timeout
            )
        except Exception as err:
            logging.debug(
                f"Connection to websocket server failed: "
                f"{self.ws_endpoint}, Message: {err}"
            )
            return None

        logging.debug(
            "Connection to websocket server established: " + self.ws_endpoint
        )

        self.ws_socket.send(json.dumps({
            "lang": "en_us", "token": self.ws_token, "service": "connect"
        }))
        try:
            result = self.ws_socket.recv()
        except Exception as err:
            result = ""
            raise ConnectionException(f"Websocket error: {str(err)}")

        try:
            payload_dict = json.loads(result)
            logging.debug(payload_dict)
        except Exception as err:
            raise ConnectionException(
                f"Data error: {str(result)}\n\t\t\t\t{str(err)}"
            )

        if payload_dict['result_msg'] == 'success':
            self.ws_token = payload_dict['result_data']['token']
            logging.info("Token Retrieved: " + self.ws_token)
        else:
            self.ws_token = ""
            raise ConnectionException(
                f"Connection Failed {payload_dict['result_msg']}"
            )

        logging.debug("Requesting Device Information")
        self.ws_socket.send(json.dumps({
            "lang": "en_us", "token": self.ws_token,
            "service": "devicelist", "type": "0", "is_check_token": "0"
        }))
        result = self.ws_socket.recv()
        payload_dict = json.loads(result)
        logging.debug(payload_dict)

        if payload_dict['result_msg'] == 'success':
            self.dev_type = payload_dict['result_data']['list'][0]['dev_type']
            self.dev_code = payload_dict['result_data']['list'][0]['dev_code']
            logging.debug(
                "Retrieved: dev_type = " + str(self.dev_type) +
                ", dev_code = " + str(self.dev_code)
            )
        else:
            logging.warning("Connection Failed", payload_dict['result_msg'])
            raise ConnectionException(self.__str__())

        return self.ws_socket is not None

    def close(self):
        return self.ws_socket is None

    @property
    def connected(self):
        return self.ws_socket is not None

    def send(self, request, addr=None):
        if not self.ws_token:
            self.connect()

        self.header = request

        if str(request[7]) == '4':
            param_type = 0
        elif str(request[7]) == '3':
            param_type = 1

        address = (256 * request[8] + request[9]) + 1
        count = 256 * request[10] + request[11]
        dev_id = str(request[6])
        self.payload_modbus = ""

        logging.debug(
            "param_type: " + str(param_type) +
            ", start_address: " + str(address) +
            ", count: " + str(count) +
            ", dev_id: " + str(dev_id)
        )
        url = (
            f'http://{str(self.dev_host)}/device/getParam?'
            f'dev_id={dev_id}&dev_type={str(self.dev_type)}'
            f'&dev_code={str(self.dev_code)}&type=3'
            f'&param_addr={address}&param_num={count}'
            f'&param_type={str(param_type)}&token={self.ws_token}'
            f'&lang=en_us&time123456={str(int(time.time()))}'
        )
        logging.debug(f'Calling: {url}')
        try:
            r = requests.get(url, timeout=self.timeout)
        except Exception as err:
            raise ConnectionException(f"HTTP Request failed: {str(err)}")

        logging.debug("HTTP Status code " + str(r.status_code))
        if str(r.status_code) == '200':
            self.payload_dict = json.loads(str(r.text))
            logging.debug(
                "Payload Status code " +
                str(self.payload_dict.get('result_code', "N/A"))
            )
            logging.debug("Payload Dict: " + str(self.payload_dict))
            if self.payload_dict.get('result_code', 0) == 1:
                modbus_data = (
                    self.payload_dict['result_data']['param_value'].split(' ')
                )
                modbus_data.pop()
                data_len = int(len(modbus_data))
                logging.debug("Data length: " + str(data_len))
                self.payload_modbus = [
                    '00', format(request[1], '02x'),
                    '00', '00', '00', format((data_len + 3), '02x'),
                    format(request[6], '02x'), format(request[7], '02x'),
                    format(data_len, '02x')
                ]
                self.payload_modbus.extend(modbus_data)
                return self.payload_modbus
            elif self.payload_dict.get('result_code', 0) == 106:
                self.ws_token = ""
                raise ConnectionException(
                    f"Token Expired: "
                    f"{str(self.payload_dict.get('result_code'))}:"
                    f"{str(self.payload_dict.get('result_msg'))} "
                )
            else:
                raise ConnectionException(
                    f"Connection Failed: "
                    f"{str(self.payload_dict.get('result_code'))}:"
                    f"{str(self.payload_dict.get('result_msg'))} "
                )
        else:
            raise ConnectionException(
                f"Connection Failed: "
                f"{str(self.payload_dict.get('result_code'))}:"
                f"{str(self.payload_dict.get('result_msg'))} "
            )

    def recv(self, size):
        if not self.payload_modbus:
            logging.error("Receive Failed: payload is empty")
            raise ConnectionException(self.__str__())

        if size is None:
            recv_size = 4096
        else:
            recv_size = size

        data = []
        counter = 0
        time_ = time.time()

        logging.debug("Modbus payload: " + str(self.payload_modbus))

        for temp_byte in self.payload_modbus:
            if temp_byte:
                data.append(bytes.fromhex(temp_byte))
                time_ = time.time()

            counter += 1
            if counter == recv_size:
                break

        del self.payload_modbus[0:counter]

        logging.debug(
            "Requested Size: " + str(size) +
            ", Returned Size: " + str(counter)
        )

        if int(counter) < int(size):
            raise ConnectionException(
                f"Short read: got {counter} bytes, expected {size}"
            )

        return b"".join(data)

    def __str__(self):
        return "SungrowModbusWebClient_%s(%s:%s)" % (
            __version__, self.dev_host, self.ws_port
        )

    def __repr__(self):
        return (
            "<{} at {} socket={self.ws_socket}, ipaddr={self.dev_host}, "
            "port={self.ws_port}, timeout={self.timeout}>"
        ).format(self.__class__.__name__, hex(id(self)), self=self)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /workspaces/SunGather && python3 -m pytest tests/test_sungrow_modbus_web_client.py -v`

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add SunGather/client/sungrow_modbus_web_client.py \
  tests/test_sungrow_modbus_web_client.py
git commit -m "feat: vendor and migrate SungrowModbusWebClient to pymodbus 3.x"
```

---

### Task 4: Vendor and migrate sungrow_client.py

The main client class that orchestrates connection, register loading, and scraping.

**Files:**

- Create: `SunGather/client/sungrow_client.py`
- Create: `tests/test_sungrow_client.py`

**Upstream source:**
`/usr/local/python/current/lib/python3.14/site-packages/SungrowClient/SungrowClient.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_sungrow_client.py`:

```python
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


class TestSungrowClientCheckConnection:
    def test_check_connection_uses_connected_property(self):
        """checkConnection should use client.connected (not is_socket_open)."""
        config = make_config()
        client = SungrowClient(config)
        client.client = MagicMock()
        type(client.client).connected = PropertyMock(return_value=True)

        result = client.checkConnection()

        assert result is True
        type(client.client).connected.assert_called()


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /workspaces/SunGather && python3 -m pytest tests/test_sungrow_client.py -v`

Expected: FAIL (module not found)

- [ ] **Step 3: Vendor and migrate the module**

Create `SunGather/client/sungrow_client.py`. This is the largest file -- copy the
upstream source from
`/usr/local/python/current/lib/python3.14/site-packages/SungrowClient/SungrowClient.py`
and apply these changes:

1. **Imports** (top of file):

```python
# Replace these lines:
#   from SungrowModbusTcpClient import SungrowModbusTcpClient
#   from SungrowModbusWebClient import SungrowModbusWebClient
#   from pymodbus.client.sync import ModbusTcpClient
# With:
from .sungrow_modbus_tcp_client import SungrowModbusTcpClient
from .sungrow_modbus_web_client import SungrowModbusWebClient
from pymodbus.client import ModbusTcpClient
```

2. **Remove `from .version import __version__`** -- replace with inline constant
   or import from project's `version.py`:

```python
from version import __version__
```

3. **Remove `RetryOnEmpty`** from `__init__`:

```python
# Remove this line from self.client_config:
#   "RetryOnEmpty": False,
```

4. **Fix `connect()` method** -- pass `host` positionally:

```python
def connect(self):
    if self.client:
        try: self.client.connect()
        except: return False
        return True

    host = self.client_config['host']
    config = {k: v for k, v in self.client_config.items() if k != 'host'}

    if self.inverter_config['connection'] == "http":
        config['port'] = 8082
        self.client = SungrowModbusWebClient(host=host, **config)
    elif self.inverter_config['connection'] == "sungrow":
        self.client = SungrowModbusTcpClient(host, **config)
    elif self.inverter_config['connection'] == "modbus":
        self.client = ModbusTcpClient(host, **config)
    else:
        logging.warning(
            f"Inverter: Unknown connection type "
            f"{self.inverter_config['connection']}, "
            f"Valid options are http, sungrow or modbus"
        )
        return False
    logging.info("Connection: " + str(self.client))

    try: self.client.connect()
    except: return False

    time.sleep(3)
    return True
```

5. **Fix `checkConnection()`** -- use `connected` property:

```python
def checkConnection(self):
    logging.debug("Checking Modbus Connection")
    if self.client:
        if self.client.connected:
            logging.debug("Modbus, Session is still connected")
            return True
        else:
            logging.info('Modbus, Connecting new session')
            return self.connect()
    else:
        logging.info('Modbus client is not connected, attempting to reconnect')
        return self.connect()
```

6. **Fix `load_registers()`** -- use `device_id=`:

```python
# In load_registers(), change both register read calls:
# Before:
#   rr = self.client.read_input_registers(start, count=count,
#       unit=self.inverter_config['slave'])
#   rr = self.client.read_holding_registers(start, count=count,
#       unit=self.inverter_config['slave'])
# After:
rr = self.client.read_input_registers(
    start, count=count, device_id=self.inverter_config['slave']
)
rr = self.client.read_holding_registers(
    start, count=count, device_id=self.inverter_config['slave']
)
```

All other methods (`configure_registers`, `scrape`, `validateRegister`,
`getRegisterAddress`, `getRegisterUnit`, `getRegisterValue`, `getHost`,
`getInverterModel`, `getSerialNumber`, `validateLatestScrape`) remain unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /workspaces/SunGather && python3 -m pytest tests/test_sungrow_client.py -v`

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add SunGather/client/sungrow_client.py tests/test_sungrow_client.py
git commit -m "feat: vendor and migrate SungrowClient to pymodbus 3.x"
```

---

### Task 5: Update sungather.py imports and integration test

**Files:**

- Modify: `SunGather/sungather.py:3`
- Create: `tests/test_import_integration.py`

- [ ] **Step 1: Write failing integration test**

Create `tests/test_import_integration.py`:

```python
def test_sungather_imports_vendored_client():
    """sungather.py should import SungrowClient from the vendored client package."""
    from client.sungrow_client import SungrowClient
    assert SungrowClient is not None
    assert hasattr(SungrowClient, 'checkConnection')
    assert hasattr(SungrowClient, 'scrape')
    assert hasattr(SungrowClient, 'connect')
    assert hasattr(SungrowClient, 'disconnect')
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd /workspaces/SunGather && python3 -m pytest tests/test_import_integration.py -v`

Expected: PASS (client package already exists from previous tasks)

- [ ] **Step 3: Update sungather.py import**

In `SunGather/sungather.py`, line 3, change:

```python
# Before
from SungrowClient import SungrowClient
# After
from client.sungrow_client import SungrowClient
```

- [ ] **Step 4: Commit**

```bash
git add SunGather/sungather.py tests/test_import_integration.py
git commit -m "feat: update sungather.py to use vendored client package"
```

---

### Task 6: Health endpoint

**Files:**

- Modify: `SunGather/exports/webserver.py`
- Create: `tests/test_health_endpoint.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_health_endpoint.py`:

```python
from datetime import datetime, timedelta
from http.server import HTTPServer
from io import BytesIO
from unittest.mock import patch, MagicMock
import pytest

from exports.webserver import export_webserver, MyServer


def make_request(path):
    """Create a mock GET request to MyServer and capture the response."""
    server = MagicMock(spec=HTTPServer)
    request = MagicMock()
    request.makefile.return_value = BytesIO()

    handler = MyServer.__new__(MyServer)
    handler.server = server
    handler.path = path
    handler.headers = {}
    handler.requestline = f'GET {path} HTTP/1.1'
    handler.request_version = 'HTTP/1.1'
    handler.command = 'GET'

    # Capture response
    response_code = None
    original_send_response = MyServer.send_response

    def capture_response(self, code, message=None):
        nonlocal response_code
        response_code = code

    handler.send_response = lambda code, message=None: capture_response(
        handler, code, message
    )
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()
    handler.wfile = BytesIO()

    handler.do_GET()
    return response_code


class TestHealthEndpointNeverScraped:
    def test_returns_200_when_never_scraped(self):
        """Before any scrape, /health should return 200 (startup/night)."""
        export_webserver.last_successful_scrape = None
        export_webserver.scan_interval = 30
        code = make_request('/health')
        assert code == 200


class TestHealthEndpointFreshData:
    def test_returns_200_when_data_is_fresh(self):
        """/health should return 200 when last scrape is recent."""
        export_webserver.last_successful_scrape = datetime.now()
        export_webserver.scan_interval = 30
        code = make_request('/health')
        assert code == 200


class TestHealthEndpointStaleData:
    def test_returns_503_when_data_is_stale(self):
        """/health should return 503 when last scrape is too old."""
        export_webserver.last_successful_scrape = (
            datetime.now() - timedelta(seconds=200)
        )
        export_webserver.scan_interval = 30  # 3 * 30 = 90 seconds threshold
        code = make_request('/health')
        assert code == 503


class TestHealthEndpointEdgeCases:
    def test_returns_200_just_below_threshold(self):
        """/health should return 200 when just below the 3x threshold."""
        export_webserver.scan_interval = 30
        export_webserver.last_successful_scrape = (
            datetime.now() - timedelta(seconds=89)
        )
        code = make_request('/health')
        assert code == 200

    def test_returns_503_just_past_boundary(self):
        """/health should return 503 just past the threshold."""
        export_webserver.scan_interval = 30
        export_webserver.last_successful_scrape = (
            datetime.now() - timedelta(seconds=91)
        )
        code = make_request('/health')
        assert code == 503


class TestPublishUpdatesTimestamp:
    def test_publish_sets_last_successful_scrape(self):
        """publish() should update last_successful_scrape timestamp."""
        export_webserver.last_successful_scrape = None
        ws = export_webserver()

        inverter = MagicMock()
        inverter.latest_scrape = {'test_register': 100}
        inverter.getRegisterAddress.return_value = '5000'
        inverter.getRegisterUnit.return_value = 'W'
        inverter.client_config = {}
        inverter.inverter_config = {}

        ws.publish(inverter)

        assert export_webserver.last_successful_scrape is not None
        age = (datetime.now() - export_webserver.last_successful_scrape)
        assert age.total_seconds() < 2


class TestConfigureStoresScanInterval:
    def test_configure_stores_scan_interval(self):
        """configure() should store scan_interval from inverter config."""
        export_webserver.scan_interval = 30  # default
        ws = export_webserver()

        inverter = MagicMock()
        inverter.inverter_config = {'scan_interval': 60}
        inverter.client_config = {}
        config = {'port': 8099, 'enabled': True, 'name': 'webserver'}

        with patch.object(HTTPServer, '__init__', return_value=None):
            with patch('threading.Thread') as mock_thread:
                mock_thread.return_value = MagicMock()
                ws.configure(config, inverter)

        assert export_webserver.scan_interval == 60
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /workspaces/SunGather && python3 -m pytest tests/test_health_endpoint.py -v`

Expected: FAIL (no `/health` handler, no `last_successful_scrape` attribute)

- [ ] **Step 3: Add class-level attributes to export_webserver**

In `SunGather/exports/webserver.py`, add to the class definition (after line 11):

```python
class export_webserver(object):
    html_body = "Pending Data Retrieval"
    metrics = ""
    last_successful_scrape = None
    scan_interval = 30
```

- [ ] **Step 4: Add datetime import**

Add to the top of `SunGather/exports/webserver.py`:

```python
from datetime import datetime
```

- [ ] **Step 5: Update configure() to store scan_interval**

In `export_webserver.configure()`, add as the first line of the method:

```python
def configure(self, config, inverter):
    export_webserver.scan_interval = inverter.inverter_config['scan_interval']
    # ... rest of existing method unchanged
```

- [ ] **Step 6: Update publish() to set timestamp**

In `export_webserver.publish()`, add as the first line of the method:

```python
def publish(self, inverter):
    export_webserver.last_successful_scrape = datetime.now()
    # ... rest of existing method unchanged
```

- [ ] **Step 7: Add /health handler to MyServer.do_GET**

In `MyServer.do_GET()`, add the `/health` handler as the **first** path check
(before the `/metrics` check):

```python
def do_GET(self):
    if self.path == '/health':
        if export_webserver.last_successful_scrape is None:
            self.send_response(200)
        elif (datetime.now() - export_webserver.last_successful_scrape
              ).total_seconds() < export_webserver.scan_interval * 3:
            self.send_response(200)
        else:
            self.send_response(503)
        self.end_headers()
        return
    if self.path.startswith('/metrics'):
        # ... existing handler
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd /workspaces/SunGather && python3 -m pytest tests/test_health_endpoint.py -v`

Expected: All tests PASS

- [ ] **Step 9: Commit**

```bash
git add SunGather/exports/webserver.py tests/test_health_endpoint.py
git commit -m "feat: add /health endpoint for data-freshness liveness probe"
```

---

### Task 7: Update Dockerfile HEALTHCHECK

**Files:**

- Modify: `Dockerfile:27-28`

- [ ] **Step 1: Update HEALTHCHECK**

In `Dockerfile`, replace the existing HEALTHCHECK (lines 27-28).
Note: port must match the configured webserver port (default 8080, commonly 8099):

```dockerfile
# Before
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
  CMD /opt/virtualenv/bin/python -c "print('ok')" || exit 1

# After
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD /opt/virtualenv/bin/python -c \
  "import urllib.request; urllib.request.urlopen('http://localhost:8099/health')" \
  || exit 1
```

- [ ] **Step 2: Commit**

```bash
git add Dockerfile
git commit -m "feat: update Dockerfile HEALTHCHECK to use /health endpoint"
```

---

### Task 8: Final cleanup and spec update commit

**Files:**

- Modify: `docs/superpowers/specs/2026-03-27-stale-connection-health-endpoint-design.md`

- [ ] **Step 1: Run all tests**

Run: `cd /workspaces/SunGather && python3 -m pytest tests/ -v`

Expected: All tests PASS

- [ ] **Step 2: Run linting**

Run: `pre-commit run --all-files`

Expected: All checks PASS

- [ ] **Step 3: Commit spec updates**

```bash
git add docs/superpowers/specs/2026-03-27-stale-connection-health-endpoint-design.md
git commit -m "docs(spec): update spec with verified pymodbus 3.x API details"
```
