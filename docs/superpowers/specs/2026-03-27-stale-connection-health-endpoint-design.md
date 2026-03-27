# Stale Modbus Connection & Health Endpoint

**Issue:** [#75](https://github.com/anthony-spruyt/SunGather/issues/75)
**Date:** 2026-03-27

## Problem

SunGather's Modbus TCP connection to Sungrow inverters goes stale (half-open TCP socket).
`SungrowClient.checkConnection()` reports the connection as healthy because `is_socket_open()`
only checks local socket state, not an actual round-trip. The K8s liveness probe
(`tcp-socket :8099`) checks the webserver thread, which runs independently of the polling loop.
The pod stays "healthy" while data collection is dead.

Additionally, the `SungrowClient` dependency uses pymodbus 2.x (`pymodbus.client.sync`),
which has known CVEs and a legacy reconnection API.

## Solution

Two workstreams:

1. **Data-freshness health endpoint** -- honestly report whether the app is collecting data,
   letting infrastructure (K8s, Docker) handle restarts.
2. **Vendor SungrowClient & upgrade pymodbus to 3.x** -- bring the client code in-repo
   and resolve CVEs.

## Design

### 1. Vendor SungrowClient

Copy the three upstream client packages into `SunGather/client/`, including supporting files:

```text
SunGather/client/
  __init__.py
  sungrow_client.py            (from SungrowClient/SungrowClient.py)
  sungrow_modbus_tcp_client.py (from SungrowModbusTcpClient/SungrowModbusTcpClient.py)
  sungrow_modbus_web_client.py (from SungrowModbusWebClient/SungrowModbusWebClient.py)
```

Version constants from upstream `version.py` files (`SungrowClient` and
`SungrowModbusWebClient` each have one) will be inlined into the vendored files or
imported from the project's own `version.py`.

#### Vendored import changes

Update imports in `sungather.py`:

```python
# Before
from SungrowClient import SungrowClient
# After
from client.sungrow_client import SungrowClient
```

Update internal cross-imports within the vendored `sungrow_client.py`:

```python
# Before (upstream SungrowClient.py lines 1-3)
from SungrowModbusTcpClient import SungrowModbusTcpClient
from SungrowModbusWebClient import SungrowModbusWebClient
from pymodbus.client.sync import ModbusTcpClient

# After
from .sungrow_modbus_tcp_client import SungrowModbusTcpClient
from .sungrow_modbus_web_client import SungrowModbusWebClient
from pymodbus.client import ModbusTcpClient
```

#### Dependency changes

Remove from `requirements.txt` and `setup.py`:

- `SungrowClient>=0.1.0`
- `SungrowModbusTcpClient>=0.0.1`
- `SungrowModbusWebClient>=0.0.3`

Add explicit dependencies that were previously transitive:

- `pycryptodomex` (used by `SungrowModbusTcpClient` for AES encryption)
- `websocket-client>=1.2.1` (already in `setup.py`, add to `requirements.txt`)
- `pymodbus>=3.6.0,<4.0.0` (already in `setup.py`, add to `requirements.txt`)

### 2. Pymodbus 2.x to 3.x Migration

**Dependency:** Replace `pymodbus>=2.3.0` with `pymodbus>=3.6.0,<4.0.0`.

The upper bound `<4.0.0` guards against future breaking changes. Within 3.x, the `slave=`
parameter is stable (3.7+ also accepts `device_id=` as an alias but `slave=` still works).

#### Import changes

| pymodbus 2.x | pymodbus 3.6.x |
| --- | --- |
| `from pymodbus.client.sync import ModbusTcpClient` | `from pymodbus.client import ModbusTcpClient` |
| `from pymodbus.client.sync import BaseModbusClient` | `from pymodbus.client import ModbusBaseSyncClient` |
| `from pymodbus.transaction import ModbusSocketFramer` | `from pymodbus.framer import Framer` |
| `from pymodbus.factory import ClientDecoder` | Removed (framer handles decoding) |
| `from pymodbus.exceptions import ConnectionException` | `from pymodbus.exceptions import ConnectionException` (unchanged) |

#### API changes

| 2.x | 3.6.x |
| --- | --- |
| `client.is_socket_open()` | `client.connected` (property) |
| `read_input_registers(addr, count=N, unit=X)` | `read_input_registers(addr, count=N, slave=X)` |
| `read_holding_registers(addr, count=N, unit=X)` | `read_holding_registers(addr, count=N, slave=X)` |
| `RetryOnEmpty` client kwarg | Removed |
| `_send()` / `_recv()` internal methods | `send()` / `recv()` (no underscore) |
| `ModbusTcpClient(**config_dict)` | `ModbusTcpClient(host, **rest)` (`host` is positional) |

#### sungrow_client.py

- `checkConnection()`: `self.client.is_socket_open()` -> `self.client.connected`
- `load_registers()`: `unit=self.inverter_config['slave']` -> `slave=self.inverter_config['slave']`
- `connect()`: Remove `RetryOnEmpty` from `client_config`
- `connect()`: `host` must be passed positionally to `ModbusTcpClient`:

```python
# Before
self.client = ModbusTcpClient(**self.client_config)
# After
host = self.client_config['host']
config = {k: v for k, v in self.client_config.items() if k != 'host'}
self.client = ModbusTcpClient(host, **config)
```

- Import path: `from pymodbus.client.sync import ModbusTcpClient` ->
  `from pymodbus.client import ModbusTcpClient`
- Internal imports: relative imports for sibling modules (see Section 1)

#### sungrow_modbus_tcp_client.py

This class uses a **dynamic method-swapping pattern** for AES encryption that needs
careful migration.

Import changes:

- `from pymodbus.client.sync import ModbusTcpClient` -> `from pymodbus.client import ModbusTcpClient`

Constructor changes:

- `ModbusTcpClient.__init__(self, **kwargs)` -> `super().__init__(host, **rest)`
  where `host` is extracted from kwargs (same positional requirement as above)

Method renaming -- the class dynamically swaps between encrypted and unencrypted
`send`/`recv`. All references must be updated:

```python
# __init__: store original methods
self._orig_recv = self.recv      # was self._recv
self._orig_send = self.send      # was self._send

# _setup(): swap to cipher methods
self.send = self._send_cipher    # was self._send = self._send_cipher
self.recv = self._recv_decipher  # was self._recv = self._recv_decipher

# _restore(): swap back to original
self.send = self._orig_send      # was self._send = self._orig_send
self.recv = self._orig_recv      # was self._recv = self._orig_recv

# _getkey(): calls unencrypted send/recv before key exchange
self._orig_send(GET_KEY)         # was self._send(GET_KEY)
self._key_packet = self._orig_recv(25)  # was self._recv(25)

# _send_cipher(): delegate to parent's send
return super().send(encrypted_request)  # was ModbusTcpClient._send(self, ...)

# _recv_decipher(): delegate to parent's recv
header = super().recv(4)                # was ModbusTcpClient._recv(self, 4)
encrypted_packet = super().recv(length) # was ModbusTcpClient._recv(self, length)
```

Note: `super().send(...)` and `super().recv(...)` are used inside cipher methods
to bypass the instance-level overrides and call the parent class methods directly.

Connection and close:

- `ModbusTcpClient.connect(self)` -> `super().connect()`
- `ModbusTcpClient.close(self)` -> `super().close()`

#### sungrow_modbus_web_client.py

Import changes:

- `from pymodbus.client.sync import BaseModbusClient` -> `from pymodbus.client import ModbusBaseSyncClient`
- `from pymodbus.transaction import ModbusSocketFramer, ModbusBinaryFramer` -> `from pymodbus.framer import Framer`
- `from pymodbus.factory import ClientDecoder` -> removed

Constructor changes:

```python
# Before
BaseModbusClient.__init__(self, framer(ClientDecoder(), self), **kwargs)
# After
super().__init__(framer=Framer.SOCKET, **kwargs)
```

Method renaming:

- `_send` -> `send`
- `_recv` -> `recv`

Short read handling:

- `self._handle_abrupt_socket_close(size, data, duration)` no longer exists in 3.x.
  Replace with raising `ConnectionException` when fewer bytes are received than requested:

```python
if int(counter) < int(size):
    raise ConnectionException(f"Short read: got {counter} bytes, expected {size}")
```

Property:

- `is_socket_open()` -> `connected` property override

### 3. Health Endpoint

#### State tracking

Add class-level attributes to `export_webserver`:

```python
class export_webserver(object):
    last_successful_scrape = None  # datetime or None
    scan_interval = 30             # default, updated in configure()
```

#### Storing scan_interval

Store `scan_interval` as a class attribute during `configure()`:

```python
def configure(self, config, inverter):
    export_webserver.scan_interval = inverter.inverter_config['scan_interval']
    # ... existing setup
```

#### Updating the timestamp

Each export's `publish()` method is only called on successful scrapes
(see `sungather.py` line 164-166). Update `last_successful_scrape` inside
`export_webserver.publish()`:

```python
def publish(self, inverter):
    export_webserver.last_successful_scrape = datetime.now()
    # ... existing publish logic
```

This avoids coupling `sungather.py` to the webserver export. The timestamp updates
naturally as part of the existing publish flow. If the webserver export isn't enabled,
there's no health endpoint to serve anyway.

#### /health endpoint logic

In `MyServer.do_GET`:

```python
if self.path == '/health':
    if export_webserver.last_successful_scrape is None:
        # Never scraped -- nighttime start or still initializing
        self.send_response(200)
    elif (datetime.now() - export_webserver.last_successful_scrape).total_seconds() \
            < export_webserver.scan_interval * 3:
        # Fresh data (3x interval allows for processing time and jitter)
        self.send_response(200)
    else:
        # Had data, now stale -- connection likely dead
        self.send_response(503)
    self.end_headers()
    return
```

The threshold uses `3 * scan_interval` rather than `2x` to allow for processing
time and system clock jitter without false positives.

#### Behaviour matrix

| Scenario | `last_successful_scrape` | Response | K8s action |
| --- | --- | --- | --- |
| Pod just started, no scrape yet | `None` | 200 | None |
| Pod started at night, inverter off | `None` | 200 | None |
| Actively scraping | Recent | 200 | None |
| Connection went stale | Old | 503 | Restart after `failureThreshold` |
| Pod restarted at night after stale | `None` (fresh process) | 200 | None |

#### Infrastructure changes

K8s liveness probe (user's Helm values):

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8099
  initialDelaySeconds: 60
  periodSeconds: 30
  failureThreshold: 3
```

Docker HEALTHCHECK (Dockerfile):

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8099/health')" \
  || exit 1
```

Uses Python (guaranteed available) instead of `curl` (not in slim images).

## Testing

- Unit tests for health endpoint logic (mock `last_successful_scrape` and `scan_interval`,
  assert correct HTTP status codes for all behaviour matrix scenarios)
- Unit tests for pymodbus 3.x migration (mock modbus client, verify correct method names
  and parameters are used)
- Unit tests for `SungrowModbusTcpClient` method-swapping pattern with pymodbus 3.x
- Integration test: verify `sungather.py` import path change works with vendored client
- Manual test against real inverter (required for pymodbus migration confidence)

## Out of scope

- In-process reconnection logic (infrastructure handles restarts)
- Async pymodbus API (keep synchronous to minimize migration risk)
- Refactoring SungrowClient beyond what's needed for the migration
