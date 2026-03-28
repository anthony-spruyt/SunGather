# Pylint Zero & Comprehensive Test Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 487 pylint errors across the codebase, refactor complex functions into SOLID units, add proper type hints, and build comprehensive BDD test coverage — bringing the pylint score from 6.16/10 to 10.0/10.

**Architecture:** Phase 1 locks in current behavior with characterization tests. Phase 2 fixes mechanical lint issues (imports, formatting, logging). Phase 3 refactors complex functions into smaller, testable units with BDD tests. Phase 4 cleans up test-specific lint and finalizes.

**Tech Stack:** Python 3.10+, pytest, pylint 4.0.5, pymodbus 3.x, paho-mqtt 2.x

**Principles:** BDD, SOLID, TDD (red-green-refactor), lazy logging (`%s` style)

---

## File Structure

### Files to modify - source
- `SunGather/client/sungrow_client.py` — 150 errors, needs major refactoring
- `SunGather/client/sungrow_modbus_tcp_client.py` — 3 errors, minor fixes
- `SunGather/client/sungrow_modbus_web_client.py` — 29 errors, moderate fixes
- `SunGather/sungather.py` — 78 errors, needs major refactoring
- `SunGather/exports/mqtt.py` — 63 errors, moderate fixes + refactoring
- `SunGather/exports/pvoutput.py` — 82 errors, moderate fixes + refactoring
- `SunGather/exports/influxdb.py` — 16 errors, minor fixes
- `SunGather/exports/console.py` — 8 errors, minor fixes
- `setup.py` — 6 errors, minor fixes
- `.pylintrc` — update thresholds where justified

### Files to modify - tests
- `tests/test_container_smoke.py` — 5 errors
- `tests/test_import_integration.py` — 6 errors
- `tests/test_log_injection.py` — 2 errors
- `tests/test_sungather_cli.py` — 3 errors
- `tests/test_sungrow_client.py` — 1 error
- `tests/test_sungrow_modbus_tcp_client.py` — 33 errors (protected-access in tests)
- `tests/test_sungrow_modbus_web_client.py` — 2 errors

### Files to create - tests
- `tests/test_sungrow_client_registers.py` — characterization tests for register config
- `tests/test_sungrow_client_load_registers.py` — characterization + refactored unit tests
- `tests/test_sungrow_client_scrape.py` — characterization + refactored unit tests
- `tests/test_sungather_main.py` — tests for refactored main() components
- `tests/test_export_mqtt.py` — BDD tests for MQTT export
- `tests/test_export_pvoutput.py` — BDD tests for PVOutput export
- `tests/test_export_influxdb.py` — BDD tests for InfluxDB export
- `tests/test_export_console.py` — BDD tests for console export
- `tests/fixtures/registers-test.yaml` — minimal register file for tests

---

## Phase 1: Characterization Tests (Safety Net)

### Task 1: Create test fixtures

**Files:**
- Create: `tests/fixtures/registers-test.yaml`

- [ ] **Step 1: Write minimal registers fixture**

```yaml
# tests/fixtures/registers-test.yaml
# Minimal register file for unit tests
version: 0.0.1
vendor: TestVendor
registers:
  - read:
      - name: "device_type_code"
        level: 0
        address: 5000
        datatype: "U16"
      - name: "serial_number"
        level: 0
        address: 5001
        datatype: "UTF-8"
      - name: "daily_power_yields"
        level: 1
        address: 5003
        datatype: "U16"
        unit: "kWh"
        accuracy: 0.1
      - name: "total_active_power"
        level: 1
        address: 5008
        datatype: "S32"
        unit: "W"
      - name: "meter_power"
        level: 1
        address: 5010
        datatype: "S32"
        unit: "W"
        smart_meter: true
        models: ["SG10KTL"]
      - name: "start_stop"
        level: 1
        address: 5012
        datatype: "U16"
        datarange:
          - response: 0xCF
            value: "Start"
          - response: 0xCE
            value: "Stop"
      - name: "work_state_1"
        level: 1
        address: 5013
        datatype: "U16"
        datarange:
          - response: 0
            value: "Run"
          - response: 2
            value: "Stop"
      - name: "load_power"
        level: 1
        address: 5014
        datatype: "S32"
        unit: "W"
      - name: "export_power_hybrid"
        level: 1
        address: 5016
        datatype: "S32"
        unit: "W"
        models: ["SH10RT"]
      - name: "year"
        level: 1
        address: 5020
        datatype: "U16"
      - name: "month"
        level: 1
        address: 5021
        datatype: "U16"
      - name: "day"
        level: 1
        address: 5022
        datatype: "U16"
      - name: "hour"
        level: 1
        address: 5023
        datatype: "U16"
      - name: "minute"
        level: 1
        address: 5024
        datatype: "U16"
      - name: "second"
        level: 1
        address: 5025
        datatype: "U16"
      - name: "pid_alarm_code"
        level: 2
        address: 5030
        datatype: "U16"
      - name: "alarm_time_year"
        level: 2
        address: 5031
        datatype: "U16"
      - name: "alarm_time_month"
        level: 2
        address: 5032
        datatype: "U16"
      - name: "alarm_time_day"
        level: 2
        address: 5033
        datatype: "U16"
      - name: "alarm_time_hour"
        level: 2
        address: 5034
        datatype: "U16"
      - name: "alarm_time_minute"
        level: 2
        address: 5035
        datatype: "U16"
      - name: "alarm_time_second"
        level: 2
        address: 5036
        datatype: "U16"
  - hold:
      - name: "max_power"
        level: 1
        address: 5100
        datatype: "U16"
        unit: "W"
scan:
  - read:
      - start: 4999
        range: 40
        type: read
  - hold:
      - start: 5099
        range: 10
        type: hold
```

- [ ] **Step 2: Commit**

```bash
git add tests/fixtures/registers-test.yaml
git commit -m "test: add minimal registers fixture for unit tests"
```

### Task 2: Characterization tests for SungrowClient.configure_registers

**Files:**
- Create: `tests/test_sungrow_client_registers.py`

- [ ] **Step 1: Write characterization tests for configure_registers**

```python
# tests/test_sungrow_client_registers.py
"""Characterization tests for SungrowClient.configure_registers.

These lock in current behavior before refactoring.
"""
import os
from unittest.mock import MagicMock

import yaml

from client.sungrow_client import SungrowClient


FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')


def load_test_registers():
    path = os.path.join(FIXTURES, 'registers-test.yaml')
    with open(path, encoding='utf-8') as f:
        return yaml.safe_load(f)


def make_client(**overrides):
    defaults = {
        'host': '192.168.1.1', 'port': 502, 'timeout': 10,
        'retries': 3, 'slave': 0x01, 'scan_interval': 30,
        'connection': 'modbus', 'model': None,
        'serial_number': None, 'level': 1,
        'use_local_time': False, 'smart_meter': False,
    }
    defaults.update(overrides)
    return SungrowClient(defaults)


class TestConfigureRegistersWithKnownModel:
    """When model is pre-configured, skip model detection."""

    def test_skips_model_detection_when_model_set(self):
        client = make_client(model='SG10KTL')
        registersfile = load_test_registers()
        client.load_registers = MagicMock(return_value=True)

        result = client.configure_registers(registersfile)

        assert result is True
        assert client.inverter_config['model'] == 'SG10KTL'

    def test_loads_level_1_read_registers(self):
        client = make_client(model='SG10KTL', level=1)
        registersfile = load_test_registers()
        client.load_registers = MagicMock(return_value=True)

        client.configure_registers(registersfile)

        register_names = [r['name'] for r in client.registers]
        assert 'daily_power_yields' in register_names
        assert 'total_active_power' in register_names

    def test_loads_hold_registers_at_level_1(self):
        client = make_client(model='SG10KTL', level=1)
        registersfile = load_test_registers()
        client.load_registers = MagicMock(return_value=True)

        client.configure_registers(registersfile)

        hold_names = [
            r['name'] for r in client.registers if r.get('type') == 'hold'
        ]
        assert 'max_power' in hold_names

    def test_register_ranges_populated(self):
        client = make_client(model='SG10KTL', level=1)
        registersfile = load_test_registers()
        client.load_registers = MagicMock(return_value=True)

        client.configure_registers(registersfile)

        assert len(client.register_ranges) > 0

    def test_smart_meter_registers_loaded_when_enabled(self):
        client = make_client(model='SG10KTL', level=1, smart_meter=True)
        registersfile = load_test_registers()
        client.load_registers = MagicMock(return_value=True)

        client.configure_registers(registersfile)

        register_names = [r['name'] for r in client.registers]
        assert 'meter_power' in register_names

    def test_smart_meter_registers_skipped_when_disabled(self):
        client = make_client(
            model='UNKNOWN_MODEL', level=1, smart_meter=False
        )
        registersfile = load_test_registers()
        client.load_registers = MagicMock(return_value=True)

        client.configure_registers(registersfile)

        register_names = [r['name'] for r in client.registers]
        assert 'meter_power' not in register_names


class TestConfigureRegistersModelDetection:
    """When model is None, auto-detect from inverter."""

    def test_detects_model_from_device_type_code(self):
        client = make_client(model=None)
        registersfile = load_test_registers()

        def fake_load_registers(reg_type, start, count):
            client.latest_scrape['device_type_code'] = 'SG10KTL'
            return True

        client.load_registers = MagicMock(
            side_effect=fake_load_registers
        )

        client.configure_registers(registersfile)

        assert client.inverter_config['model'] == 'SG10KTL'

    def test_handles_failed_model_detection(self):
        client = make_client(model=None)
        registersfile = load_test_registers()
        client.load_registers = MagicMock(return_value=False)

        result = client.configure_registers(registersfile)

        assert result is True
        assert client.inverter_config['model'] is None
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `python -m pytest tests/test_sungrow_client_registers.py -v`
Expected: All PASS (characterizing existing behavior)

- [ ] **Step 3: Commit**

```bash
git add tests/test_sungrow_client_registers.py
git commit -m "test: add characterization tests for configure_registers"
```

### Task 3: Characterization tests for SungrowClient.load_registers

**Files:**
- Create: `tests/test_sungrow_client_load_registers.py`

- [ ] **Step 1: Write characterization tests for load_registers**

```python
# tests/test_sungrow_client_load_registers.py
"""Characterization tests for SungrowClient.load_registers."""
from unittest.mock import MagicMock

from client.sungrow_client import SungrowClient


def make_client(**overrides):
    defaults = {
        'host': '192.168.1.1', 'port': 502, 'timeout': 10,
        'retries': 3, 'slave': 0x01, 'scan_interval': 30,
        'connection': 'modbus', 'model': 'SG10KTL',
        'serial_number': 'TEST123', 'level': 1,
        'use_local_time': False, 'smart_meter': False,
    }
    defaults.update(overrides)
    return SungrowClient(defaults)


def make_mock_response(registers, is_error=False):
    resp = MagicMock()
    resp.isError.return_value = is_error
    resp.registers = registers
    return resp


class TestLoadRegistersU16:
    """U16 register type decoding."""

    def test_u16_normal_value(self):
        client = make_client()
        client.client = MagicMock()
        client.registers = [
            {'name': 'test_u16', 'type': 'read',
             'address': 1, 'datatype': 'U16'}
        ]
        client.client.read_input_registers.return_value = (
            make_mock_response([500])
        )

        result = client.load_registers('read', 0, 1)

        assert result is True
        assert client.latest_scrape['test_u16'] == 500

    def test_u16_ffff_becomes_zero(self):
        client = make_client()
        client.client = MagicMock()
        client.registers = [
            {'name': 'test_u16', 'type': 'read',
             'address': 1, 'datatype': 'U16'}
        ]
        client.client.read_input_registers.return_value = (
            make_mock_response([0xFFFF])
        )

        client.load_registers('read', 0, 1)

        assert client.latest_scrape['test_u16'] == 0

    def test_u16_mask_applied(self):
        client = make_client()
        client.client = MagicMock()
        client.registers = [
            {'name': 'test_mask', 'type': 'read',
             'address': 1, 'datatype': 'U16', 'mask': 0x01}
        ]
        client.client.read_input_registers.return_value = (
            make_mock_response([0x03])
        )

        client.load_registers('read', 0, 1)

        assert client.latest_scrape['test_mask'] == 1

    def test_u16_mask_zero_when_no_match(self):
        # BUG: Due to Python operator precedence, the mask code at line 249:
        #   register_value = 1 if register_value & register.get('mask') != 0 else 0
        # parses as: register_value & (register.get('mask') != 0)
        # NOT as: (register_value & register.get('mask')) != 0
        # So 0x03 & (0x04 != 0) => 0x03 & True => 0x03 & 1 => 1
        # This means the mask NEVER returns 0 when register_value is odd.
        client = make_client()
        client.client = MagicMock()
        client.registers = [
            {'name': 'test_mask', 'type': 'read',
             'address': 1, 'datatype': 'U16', 'mask': 0x04}
        ]
        client.client.read_input_registers.return_value = (
            make_mock_response([0x03])
        )

        client.load_registers('read', 0, 1)

        assert client.latest_scrape['test_mask'] == 1  # buggy: should be 0


class TestLoadRegistersS16:
    """S16 register type decoding."""

    def test_s16_positive_value(self):
        client = make_client()
        client.client = MagicMock()
        client.registers = [
            {'name': 'test_s16', 'type': 'read',
             'address': 1, 'datatype': 'S16'}
        ]
        client.client.read_input_registers.return_value = (
            make_mock_response([100])
        )

        client.load_registers('read', 0, 1)

        assert client.latest_scrape['test_s16'] == 100

    def test_s16_negative_value(self):
        client = make_client()
        client.client = MagicMock()
        client.registers = [
            {'name': 'test_s16', 'type': 'read',
             'address': 1, 'datatype': 'S16'}
        ]
        client.client.read_input_registers.return_value = (
            make_mock_response([65535])
        )

        client.load_registers('read', 0, 1)

        # 0xFFFF is sentinel, treated as 0
        assert client.latest_scrape['test_s16'] == 0

    def test_s16_large_negative(self):
        client = make_client()
        client.client = MagicMock()
        client.registers = [
            {'name': 'test_s16', 'type': 'read',
             'address': 1, 'datatype': 'S16'}
        ]
        client.client.read_input_registers.return_value = (
            make_mock_response([32768])
        )

        client.load_registers('read', 0, 1)

        assert client.latest_scrape['test_s16'] == -32768


class TestLoadRegistersU32:
    """U32 register type decoding."""

    def test_u32_normal_value(self):
        client = make_client()
        client.client = MagicMock()
        client.registers = [
            {'name': 'test_u32', 'type': 'read',
             'address': 1, 'datatype': 'U32'}
        ]
        # low=100, high=1 => 100 + 1 * 0x10000 = 65636
        client.client.read_input_registers.return_value = (
            make_mock_response([100, 1])
        )

        client.load_registers('read', 0, 2)

        assert client.latest_scrape['test_u32'] == 65636

    def test_u32_ffff_ffff_becomes_zero(self):
        client = make_client()
        client.client = MagicMock()
        client.registers = [
            {'name': 'test_u32', 'type': 'read',
             'address': 1, 'datatype': 'U32'}
        ]
        client.client.read_input_registers.return_value = (
            make_mock_response([0xFFFF, 0xFFFF])
        )

        client.load_registers('read', 0, 2)

        assert client.latest_scrape['test_u32'] == 0


class TestLoadRegistersS32:
    """S32 register type decoding."""

    def test_s32_positive_value(self):
        client = make_client()
        client.client = MagicMock()
        client.registers = [
            {'name': 'test_s32', 'type': 'read',
             'address': 1, 'datatype': 'S32'}
        ]
        client.client.read_input_registers.return_value = (
            make_mock_response([100, 1])
        )

        client.load_registers('read', 0, 2)

        assert client.latest_scrape['test_s32'] == 65636

    def test_s32_negative_value(self):
        client = make_client()
        client.client = MagicMock()
        client.registers = [
            {'name': 'test_s32', 'type': 'read',
             'address': 1, 'datatype': 'S32'}
        ]
        client.client.read_input_registers.return_value = (
            make_mock_response([0, 0xFFFF])
        )

        client.load_registers('read', 0, 2)

        assert client.latest_scrape['test_s32'] == -65536


class TestLoadRegistersDatarange:
    """Datarange (enum) mapping."""

    def test_datarange_maps_response_to_value(self):
        client = make_client()
        client.client = MagicMock()
        client.registers = [
            {'name': 'test_enum', 'type': 'read', 'address': 1,
             'datatype': 'U16',
             'datarange': [
                 {'response': 1, 'value': 'Running'},
                 {'response': 0, 'value': 'Stopped'},
             ]}
        ]
        client.client.read_input_registers.return_value = (
            make_mock_response([1])
        )

        client.load_registers('read', 0, 1)

        assert client.latest_scrape['test_enum'] == 'Running'

    def test_datarange_uses_default_on_no_match(self):
        client = make_client()
        client.client = MagicMock()
        client.registers = [
            {'name': 'test_enum', 'type': 'read', 'address': 1,
             'datatype': 'U16', 'default': 'Unknown',
             'datarange': [
                 {'response': 1, 'value': 'Running'},
             ]}
        ]
        client.client.read_input_registers.return_value = (
            make_mock_response([99])
        )

        client.load_registers('read', 0, 1)

        assert client.latest_scrape['test_enum'] == 'Unknown'


class TestLoadRegistersAccuracy:
    """Accuracy multiplier."""

    def test_accuracy_multiplier_applied(self):
        client = make_client()
        client.client = MagicMock()
        client.registers = [
            {'name': 'test_acc', 'type': 'read', 'address': 1,
             'datatype': 'U16', 'accuracy': 0.1}
        ]
        client.client.read_input_registers.return_value = (
            make_mock_response([500])
        )

        client.load_registers('read', 0, 1)

        assert client.latest_scrape['test_acc'] == 50.0


class TestLoadRegistersErrorHandling:
    """Error paths in load_registers."""

    def test_returns_false_on_exception(self):
        client = make_client()
        client.client = MagicMock()
        client.client.read_input_registers.side_effect = (
            Exception("connection lost")
        )

        result = client.load_registers('read', 0, 1)

        assert result is False

    def test_returns_false_on_modbus_error(self):
        client = make_client()
        client.client = MagicMock()
        client.client.read_input_registers.return_value = (
            make_mock_response([], is_error=True)
        )

        result = client.load_registers('read', 0, 1)

        assert result is False

    def test_returns_false_on_count_mismatch(self):
        client = make_client()
        client.client = MagicMock()
        resp = make_mock_response([1])
        client.client.read_input_registers.return_value = resp

        result = client.load_registers('read', 0, 2)

        assert result is False

    def test_hold_type_uses_holding_registers(self):
        client = make_client()
        client.client = MagicMock()
        client.registers = [
            {'name': 'test_hold', 'type': 'hold',
             'address': 1, 'datatype': 'U16'}
        ]
        client.client.read_holding_registers.return_value = (
            make_mock_response([42])
        )

        client.load_registers('hold', 0, 1)

        assert client.latest_scrape['test_hold'] == 42
        client.client.read_holding_registers.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `python -m pytest tests/test_sungrow_client_load_registers.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_sungrow_client_load_registers.py
git commit -m "test: add characterization tests for load_registers data types"
```

### Task 4: Characterization tests for SungrowClient.scrape

**Files:**
- Create: `tests/test_sungrow_client_scrape.py`

- [ ] **Step 1: Write characterization tests for scrape**

```python
# tests/test_sungrow_client_scrape.py
"""Characterization tests for SungrowClient.scrape."""
from unittest.mock import MagicMock
from datetime import datetime

from client.sungrow_client import SungrowClient


def make_client(**overrides):
    defaults = {
        'host': '192.168.1.1', 'port': 502, 'timeout': 10,
        'retries': 3, 'slave': 0x01, 'scan_interval': 30,
        'connection': 'modbus', 'model': 'SG10KTL',
        'serial_number': 'TEST123', 'level': 1,
        'use_local_time': False, 'smart_meter': False,
    }
    defaults.update(overrides)
    return SungrowClient(defaults)


class TestScrapeTimestamp:
    """Timestamp assembly from register values."""

    def test_uses_local_time_when_configured(self):
        client = make_client(use_local_time=True)
        client.register_ranges = [
            {'type': 'read', 'start': 5000, 'range': 40}
        ]

        def fake_load(reg_type, start, count):
            client.latest_scrape.update({
                'year': 2026, 'month': 3, 'day': 28,
                'hour': 12, 'minute': 30, 'second': 0,
                'start_stop': 'Start', 'work_state_1': 'Run',
                'total_active_power': 5000, 'meter_power': -2000,
                'load_power': 3000,
            })
            return True

        client.load_registers = MagicMock(side_effect=fake_load)

        result = client.scrape()

        assert result is True
        assert 'timestamp' in client.latest_scrape
        ts = client.latest_scrape['timestamp']
        parsed = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        assert parsed.year == datetime.now().year

    def test_uses_inverter_time_when_not_local(self):
        client = make_client(use_local_time=False)
        client.register_ranges = [
            {'type': 'read', 'start': 5000, 'range': 40}
        ]

        def fake_load(reg_type, start, count):
            client.latest_scrape.update({
                'year': 2026, 'month': 1, 'day': 15,
                'hour': 10, 'minute': 5, 'second': 30,
                'start_stop': 'Start', 'work_state_1': 'Run',
                'total_active_power': 5000, 'meter_power': -2000,
                'load_power': 3000,
            })
            return True

        client.load_registers = MagicMock(side_effect=fake_load)

        result = client.scrape()

        assert result is True
        assert client.latest_scrape['timestamp'] == '2026-1-15 10:05:30'


class TestScrapeGridPower:
    """Virtual registers for grid import/export."""

    def test_export_to_grid_when_meter_power_negative(self):
        client = make_client(use_local_time=True, level=1)
        client.register_ranges = [
            {'type': 'read', 'start': 5000, 'range': 40}
        ]
        client.registers = [
            {'name': 'meter_power', 'type': 'read',
             'address': 5010, 'datatype': 'S32'},
        ]

        def fake_load(reg_type, start, count):
            client.latest_scrape.update({
                'year': 2026, 'month': 3, 'day': 28,
                'hour': 12, 'minute': 0, 'second': 0,
                'meter_power': -2000,
                'start_stop': 'Start', 'work_state_1': 'Run',
                'total_active_power': 5000,
                'load_power': 3000,
            })
            return True

        client.load_registers = MagicMock(side_effect=fake_load)

        client.scrape()

        assert client.latest_scrape['export_to_grid'] == 2000
        assert client.latest_scrape['import_from_grid'] == 0

    def test_import_from_grid_when_meter_power_positive(self):
        client = make_client(use_local_time=True, level=1)
        client.register_ranges = [
            {'type': 'read', 'start': 5000, 'range': 40}
        ]
        client.registers = [
            {'name': 'meter_power', 'type': 'read',
             'address': 5010, 'datatype': 'S32'},
        ]

        def fake_load(reg_type, start, count):
            client.latest_scrape.update({
                'year': 2026, 'month': 3, 'day': 28,
                'hour': 12, 'minute': 0, 'second': 0,
                'meter_power': 1500,
                'start_stop': 'Start', 'work_state_1': 'Run',
                'total_active_power': 5000,
                'load_power': 6500,
            })
            return True

        client.load_registers = MagicMock(side_effect=fake_load)

        client.scrape()

        assert client.latest_scrape['export_to_grid'] == 0
        assert client.latest_scrape['import_from_grid'] == 1500


class TestScrapeDisconnectOnFailure:
    """Scrape should disconnect when all register loads fail."""

    def test_disconnects_when_all_scrapes_fail(self):
        client = make_client(use_local_time=True)
        client.register_ranges = [
            {'type': 'read', 'start': 5000, 'range': 40},
        ]
        client.load_registers = MagicMock(return_value=False)
        client.disconnect = MagicMock()

        result = client.scrape()

        assert result is False
        client.disconnect.assert_called_once()

    def test_succeeds_when_some_scrapes_fail(self):
        client = make_client(use_local_time=True)
        client.register_ranges = [
            {'type': 'read', 'start': 5000, 'range': 40},
            {'type': 'hold', 'start': 5099, 'range': 10},
        ]

        call_count = 0

        def fake_load(reg_type, start, count):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                client.latest_scrape.update({
                    'year': 2026, 'month': 3, 'day': 28,
                    'hour': 12, 'minute': 0, 'second': 0,
                    'start_stop': 'Start',
                    'work_state_1': 'Run',
                    'total_active_power': 5000,
                    'meter_power': 0,
                    'load_power': 5000,
                })
                return True
            return False

        client.load_registers = MagicMock(side_effect=fake_load)

        result = client.scrape()

        assert result is True


class TestScrapeRunStateContainsBug:
    """Characterization test for the .contains() bug in _compute_run_state.

    The source code at line 450 calls:
        self.latest_scrape.get('work_state_1', False).contains('Run')
    Python strings have no .contains() method, so this raises
    AttributeError. The broad `except Exception: pass` at line 456
    swallows the error, leaving run_state unset.
    This test documents the current broken behavior.
    """

    def test_run_state_not_set_due_to_contains_bug(self):
        client = make_client(use_local_time=True)
        client.register_ranges = [
            {'type': 'read', 'start': 5000, 'range': 40}
        ]

        def fake_load(reg_type, start, count):
            client.latest_scrape.update({
                'year': 2026, 'month': 3, 'day': 28,
                'hour': 12, 'minute': 0, 'second': 0,
                'start_stop': 'Start', 'work_state_1': 'Run',
                'total_active_power': 5000, 'meter_power': 0,
                'load_power': 5000,
            })
            return True

        client.load_registers = MagicMock(side_effect=fake_load)

        client.scrape()

        # BUG: run_state should be "ON" but .contains() raises
        # AttributeError which is silently swallowed, so run_state
        # is never set in latest_scrape.
        assert 'run_state' not in client.latest_scrape


class TestScrapeHelperMethods:
    """Test validateRegister, getRegisterValue, etc."""

    def test_validate_register_returns_true_for_known(self):
        client = make_client()
        client.registers = [
            {'name': 'daily_power_yields', 'type': 'read',
             'address': 5003}
        ]
        assert client.validateRegister('daily_power_yields') is True

    def test_validate_register_returns_true_for_custom(self):
        client = make_client()
        assert client.validateRegister('run_state') is True

    def test_validate_register_returns_false_for_unknown(self):
        client = make_client()
        assert client.validateRegister('nonexistent') is False

    def test_get_register_value(self):
        client = make_client()
        client.latest_scrape = {'test_reg': 42}
        assert client.getRegisterValue('test_reg') == 42

    def test_get_register_value_returns_false_for_missing(self):
        client = make_client()
        client.latest_scrape = {}
        assert client.getRegisterValue('missing') is False

    def test_get_register_unit(self):
        client = make_client()
        client.registers = [
            {'name': 'power', 'type': 'read',
             'address': 1, 'unit': 'W'}
        ]
        assert client.getRegisterUnit('power') == 'W'

    def test_get_register_address(self):
        client = make_client()
        client.registers = [
            {'name': 'power', 'type': 'read', 'address': 5008}
        ]
        assert client.getRegisterAddress('power') == 5008

    def test_get_inverter_model_clean(self):
        client = make_client(model='SH10.RT-V2')
        assert client.getInverterModel(clean=True) == 'SH10RTV2'

    def test_get_inverter_model_raw(self):
        client = make_client(model='SH10.RT-V2')
        assert client.getInverterModel() == 'SH10.RT-V2'
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/test_sungrow_client_scrape.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_sungrow_client_scrape.py
git commit -m "test: add characterization tests for scrape and helper methods"
```

### Task 5: BDD tests for export modules

**Files:**
- Create: `tests/test_export_console.py`
- Create: `tests/test_export_influxdb.py`
- Create: `tests/test_export_mqtt.py`
- Create: `tests/test_export_pvoutput.py`

- [ ] **Step 1: Write all export tests**

Create each file with tests covering configure() and publish() for every export. Each test class should cover:
- `configure()` with valid config returns True
- `configure()` with missing required fields returns False
- `publish()` sends data correctly
- Error handling paths

- [ ] **Step 2: Run all new tests**

Run: `python -m pytest tests/test_export_*.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_export_console.py tests/test_export_influxdb.py tests/test_export_mqtt.py tests/test_export_pvoutput.py
git commit -m "test: add BDD tests for all export modules"
```

### Task 6: Run full test suite to establish baseline

- [ ] **Step 1: Run all tests**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All tests pass

- [ ] **Step 2: Run pylint to capture baseline**

Run: `python -m pylint --rcfile .pylintrc SunGather/ setup.py tests/ 2>&1 | tail -5`
Expected: Score around 6.16/10

### Task 7: Update .pylintrc for justified exceptions

**Files:** `.pylintrc`

- [ ] **Step 1: Update pylintrc**

Add to disable: `protected-access` (tests need it, MQTT callbacks need it).
Add design section: `max-args=6`, `max-positional-arguments=6`, `max-instance-attributes=15`.

- [ ] **Step 2: Commit**

---

## Phase 2: Mechanical Lint Fixes

### Task 8: Fix import ordering in all files

**Files:**
- Modify: `SunGather/client/sungrow_client.py:1-12`
- Modify: `SunGather/client/sungrow_modbus_tcp_client.py:1-3`
- Modify: `SunGather/client/sungrow_modbus_web_client.py:1-10`
- Modify: `SunGather/exports/influxdb.py:1-3`
- Modify: `SunGather/exports/pvoutput.py:1-4`
- Modify: `SunGather/sungather.py:1-13`

- [ ] **Step 1: Reorder all imports to stdlib/third-party/local**

Follow isort convention: stdlib first, blank line, third-party, blank line, local.

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/ -v --tb=short`

- [ ] **Step 3: Commit**

```bash
git commit -am "fix(lint): reorder imports to stdlib/third-party/local"
```

### Task 9: Convert all logging to lazy % formatting

**Files:** All source files with logging calls

- [ ] **Step 1: Convert all `logging.xxx(f"...")` to `logging.xxx("... %s", var)`**

Also remove f-prefix from strings with no interpolation. Fix `logging.warn()` to `logging.warning()`.

- [ ] **Step 2: Run tests**

- [ ] **Step 3: Commit**

```bash
git commit -am "fix(lint): convert all logging to lazy % formatting"
```

### Task 10: Fix line-too-long (110 instances)

- [ ] **Step 1: Break all long lines to under 100 chars**

Key targets: mqtt.py line 12 (5403 chars!), long conditionals, log messages.

- [ ] **Step 2: Run tests and commit**

### Task 11: Fix all remaining mechanical issues

This task covers every remaining mechanical fix. Execute each sub-step, then run tests and commit in batches.

Sub-steps: superfluous-parens, consider-using-f-string, multiple-statements,
bare-except, unnecessary-dunder-call, consider-using-in, no-else-return,
raise-missing-from, unnecessary-pass, redefined-builtin, deprecated-method,
consider-using-with, unspecified-encoding, bad-indentation,
used-before-assignment, undefined-variable in setup.py, unused-variable,
unused-import, consider-using-sys-exit, inconsistent-return-statements,
unidiomatic-typecheck, subprocess-run-check,
use-implicit-booleaness-not-comparison, import-outside-toplevel.

- [ ] **Step 1-24: Fix each category as detailed above**
- [ ] **Step 25: Run tests**
- [ ] **Step 26: Commit**

---

## Phase 3: Structural Refactoring

### Task 12: Refactor SungrowClient.configure_registers

Extract into: `_filter_registers_by_level()`, `_detect_field()`, `_build_register_ranges()`.

- [ ] **Step 1-11: TDD cycle for each extraction** (see detailed steps above)

### Task 13: Refactor SungrowClient.scrape

Extract into: `_assemble_timestamp()`, `_assemble_alarm_timestamp()`, `_compute_run_state()`, `_compute_grid_power()`, `_compute_load_power()`, `_compute_daily_grid_totals()`.

Also fixes the `.contains()` bug (should be `in` operator).

- [ ] **Step 1-11: TDD cycle for each extraction** (see detailed steps above)

### Task 14: Fix the .contains() bug

Already addressed in Task 13's `_compute_run_state()` extraction.

### Task 15: Simplify helper methods

Replace iteration-based dict lookups with `in` / `.get()`.

### Task 16: Add type hints to eliminate no-member false positives

Add `list[dict[str, Any]]` type hints to `registers`, `register_ranges`, etc. Clean up the `[[]] + pop()` initialization pattern.

### Task 17-20: Fix remaining files

Fix web client, TCP client, MQTT, PVOutput, and all remaining files.

### Task 21: Fix sungather.py main()

Extract `_load_config()`, `_setup_logging()`, `_load_exports()` from main(). Fix all remaining mechanical issues.

---

## Phase 4: Validation

### Task 22: Final pylint validation

- [ ] **Step 1: Run pylint**

Run: `python -m pylint --rcfile .pylintrc SunGather/ setup.py tests/ 2>&1`
Expected: 10.0/10

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All PASS

- [ ] **Step 3: Run pre-commit hooks**

Run: `pre-commit run --all-files`
Expected: All PASS

### Task 23: Summary verification

- [ ] **Step 1: Count tests**

Run: `python -m pytest tests/ --co -q | tail -1`
Expected: 90+ tests (up from 47)

- [ ] **Step 2: Verify pylint score**

Run: `python -m pylint --rcfile .pylintrc SunGather/ setup.py tests/ 2>&1 | tail -1`
Expected: `Your code has been rated at 10.00/10`

---

## Error-to-Task Mapping

| Error | Count | Task |
| ----- | ----- | ---- |
| line-too-long | 110 | 10 |
| logging-fstring-interpolation | 88 | 9 |
| f-string-without-interpolation | 34 | 11 |
| protected-access | 29 | 7 (.pylintrc) |
| no-member | 25 | 16 (type hints) |
| unused-argument | 21 | 7 + inline |
| wrong-import-order | 20 | 8 |
| broad-exception-caught | 19 | 13 (refined) |
| logging-not-lazy | 17 | 9 |
| multiple-statements | 10 | 11 |
| consider-using-f-string | 10 | 11 |
| unnecessary-dunder-call | 8 | 11 |
| unused-variable | 7 | 11 |
| invalid-sequence-index | 7 | 16 (type hints) |
| unspecified-encoding | 6 | 11 |
| too-many-statements | 5 | 12, 13, 21 |
| too-many-branches | 5 | 12, 13, 21 |
| superfluous-parens | 5 | 11 |
| no-else-return | 5 | 11 |
| unused-import | 5 | 11 |
| import-outside-toplevel | 5 | 11 |
| too-many-instance-attributes | 4 | 7 (.pylintrc) |
| bare-except | 4 | 11 |
| too-many-positional-arguments | 3 | 7 (.pylintrc) |
| too-many-arguments | 3 | 7 (.pylintrc) |
| too-many-nested-blocks | 3 | 20 |
| subprocess-run-check | 3 | 11 |
| raise-missing-from | 3 | 11 |
| consider-using-with | 3 | 11 |
| consider-using-in | 3 | 11 |
| too-many-locals | 2 | 12, 13 |
| deprecated-method | 2 | 11 |
| bad-indentation | 2 | 11 |
| All remaining 1-count | 11 | 11, 17 |
