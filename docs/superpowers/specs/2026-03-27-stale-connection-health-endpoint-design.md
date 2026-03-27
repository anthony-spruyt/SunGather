# Stale Modbus Connection & Health Endpoint

**Issue:** [#75](https://github.com/anthony-spruyt/SunGather/issues/75)
**Date:** 2026-03-27

## Problem

SunGather's Modbus TCP connection to Sungrow inverters goes stale (half-open TCP socket).
`SungrowClient.checkConnection()` reports the connection as healthy because `is_socket_open()`
only checks local socket state, not an actual round-trip. The K8s liveness probe
(`tcp-socket :8099`) checks the webserver thread, which runs independently of the polling loop.
The pod stays "healthy" while data collection is dead.

Additionally, the `SungrowClient` dependency uses pymodbus 2.x (`pymodbus.client.sync`), which has known CVEs and a legacy reconnection API.

## Solution

Two workstreams:

1. **Data-freshness health endpoint** -- honestly report whether the app is collecting data, letting infrastructure (K8s, Docker) handle restarts.
2. **Vendor SungrowClient & upgrade pymodbus to 3.x** -- bring the client code in-repo and resolve CVEs.

## Design

### 1. Vendor SungrowClient

Copy the three upstream client packages into `SunGather/client/`:

```text
SunGather/client/
  __init__.py
  sungrow_client.py          (from SungrowClient)
  sungrow_modbus_tcp_client.py (from SungrowModbusTcpClient)
  sungrow_modbus_web_client.py (from SungrowModbusWebClient)
```

Update imports in `sungather.py`:

```python
# Before
from SungrowClient import SungrowClient
# After
from client.sungrow_client import SungrowClient
```

Remove from `requirements.txt` / `setup.py`:
- `SungrowClient>=0.1.0`
- `SungrowModbusTcpClient>=0.0.1`
- `SungrowModbusWebClient>=0.0.3`

The public API of all three classes remains unchanged. No other files need import changes.

### 2. Pymodbus 2.x to 3.x Migration

**Dependency:** Replace `pymodbus>=2.3.0` with `pymodbus>=3.6.0`.

#### Import changes

| pymodbus 2.x | pymodbus 3.x |
| --- | --- |
| `from pymodbus.client.sync import ModbusTcpClient` | `from pymodbus.client import ModbusTcpClient` |
| `from pymodbus.client.sync import BaseModbusClient` | `from pymodbus.client import ModbusBaseClient` |
| `from pymodbus.transaction import ModbusSocketFramer` | `from pymodbus.framer import FramerType` |
| `from pymodbus.factory import ClientDecoder` | Removed (framer handles decoding) |

#### API changes

| 2.x | 3.x |
| --- | --- |
| `client.is_socket_open()` | `client.connected` (property) |
| `read_input_registers(addr, count=N, unit=X)` | `read_input_registers(addr, count=N, slave=X)` |
| `read_holding_registers(addr, count=N, unit=X)` | `read_holding_registers(addr, count=N, slave=X)` |
| `RetryOnEmpty` client kwarg | Removed |
| `_send()` / `_recv()` internal methods | `send()` / `recv()` (no underscore) |

#### sungrow_client.py

- `checkConnection()`: `self.client.is_socket_open()` -> `self.client.connected`
- `load_registers()`: `unit=self.inverter_config['slave']` -> `slave=self.inverter_config['slave']`
- `connect()`: Remove `RetryOnEmpty` from `client_config`
- Import path update

#### sungrow_modbus_tcp_client.py

- Extends `ModbusTcpClient` (import path changes)
- `ModbusTcpClient.__init__(self, **kwargs)` -> `super().__init__(**kwargs)`
- `self._recv` / `self._send` -> override `recv` / `send` (pymodbus 3.x public method names)
- `ModbusTcpClient._send(self, ...)` -> `super().send(...)`
- `ModbusTcpClient._recv(self, ...)` -> `super().recv(...)`
- `ModbusTcpClient.connect(self)` -> `super().connect()`
- `ModbusTcpClient.close(self)` -> `super().close()`

#### sungrow_modbus_web_client.py

- `BaseModbusClient` -> `ModbusBaseClient`
- Framer setup: `framer(ClientDecoder(), self)` -> `FramerType.SOCKET` (passed as parameter)
- `_send` / `_recv` -> `send` / `recv`
- `_handle_abrupt_socket_close` -> handle short reads directly
- `is_socket_open()` -> `connected` property

### 3. Health Endpoint

#### State tracking

Add a class-level attribute to `export_webserver`:

```python
class export_webserver(object):
    last_successful_scrape = None  # datetime or None
```

#### Storing scan_interval

Store `scan_interval` as a class attribute during `configure()`:

```python
def configure(self, config, inverter):
    export_webserver.scan_interval = inverter.inverter_config['scan_interval']
    # ... existing setup
```

#### Updating the timestamp

Each export's `publish()` method is only called on successful scrapes (see `sungather.py` line 164-166). Update `last_successful_scrape` inside `export_webserver.publish()`:

```python
def publish(self, inverter):
    export_webserver.last_successful_scrape = datetime.now()
    # ... existing publish logic
```

This avoids coupling `sungather.py` to the webserver export. The timestamp updates naturally as part of the existing publish flow. If the webserver export isn't enabled, there's no health endpoint to serve anyway.

#### /health endpoint logic

In `MyServer.do_GET`:

```python
if self.path == '/health':
    if export_webserver.last_successful_scrape is None:
        # Never scraped -- nighttime start or still initializing
        self.send_response(200)
    elif (datetime.now() - export_webserver.last_successful_scrape).total_seconds() < export_webserver.scan_interval * 2:
        # Fresh data
        self.send_response(200)
    else:
        # Had data, now stale -- connection likely dead
        self.send_response(503)
    self.end_headers()
    return
```

#### Behaviour matrix

| Scenario | `last_successful_scrape` | Response | K8s action |
| --- | --- | --- | --- |
| Pod just started, no scrape yet | `None` | 200 | None |
| Pod started at night, inverter off | `None` | 200 | None |
| Actively scraping | Recent | 200 | None |
| Connection went stale | Old | 503 | Restart after `failureThreshold` |
| Pod restarted at night after prior day's stale detection | `None` (fresh process) | 200 | None |

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
  CMD curl -f http://localhost:8099/health || exit 1
```

## Testing

- Unit tests for health endpoint logic (mock `last_successful_scrape` and `scan_interval`, assert correct HTTP status codes)
- Unit tests for pymodbus 3.x migration (mock modbus client, verify correct method names and parameters are used)
- Integration test: verify `sungather.py` import path change works with vendored client
- Manual test against real inverter (required for pymodbus migration confidence)

## Out of scope

- In-process reconnection logic (infrastructure handles restarts)
- Async pymodbus API (keep synchronous to minimize migration risk)
- Refactoring SungrowClient beyond what's needed for the migration
