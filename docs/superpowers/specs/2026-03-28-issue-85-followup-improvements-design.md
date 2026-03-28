# Issue #85: Follow-up Improvements from Stale Connection Fix

**Date:** 2026-03-28
**Related:** [#85](https://github.com/anthony-spruyt/SunGather/issues/85), [#84](https://github.com/anthony-spruyt/SunGather/pull/84), [#75](https://github.com/anthony-spruyt/SunGather/issues/75)
**Priority:** Low — no production impact; all existing functionality is correct

---

## Overview

Four quality improvements identified during post-merge review of PR #84 (stale Modbus connections and pymodbus 3.x upgrade). All items are independent and can be implemented in any order.

---

## 1. Add `http` Connection Type Test

**File:** `tests/test_sungrow_client.py`
**Class:** `TestSungrowClientConnect`

### Problem: Missing http Test

The test suite covers `modbus` and `sungrow` connection types but not `http` (`SungrowModbusWebClient`). The `http` path has two differences from the others: `host` is passed as a keyword argument, and `port` is overridden to `8082`.

### Solution: Add http Connection Test

Add `test_connect_http_passes_host_as_keyword_and_overrides_port`:

- Patch `client.sungrow_client.SungrowModbusWebClient`
- Create `SungrowClient` with `connection='http'`
- Call `connect()`
- Assert `host` is passed as a keyword argument (`kwargs['host'] == '192.168.1.1'`)
- Assert `host` is NOT passed positionally (`assert args == ()` — mirrors the inverse pattern used in `modbus`/`sungrow` tests)
- Assert `port` is overridden to `8082` (`kwargs['port'] == 8082`)
- Assert `connect()` returns `True`

Mirrors the structure of the existing `test_connect_modbus_passes_host_positionally` and `test_connect_sungrow_passes_host_positionally` tests.

---

## 2. Fix HTTPServer Thread Leak Warning

**File:** `tests/test_health_endpoint.py`
**Class:** `TestConfigureStoresScanInterval`

### Problem: Leaked HTTPServer State

The test patches `HTTPServer.__init__` with `return_value=None`, which prevents the server from starting but leaves a partially-initialized `HTTPServer` object. During garbage collection, Python may access uninitialized internal attributes (e.g., `_BaseServer__is_shut_down`), producing `AttributeError` warnings. This creates CI noise and would break if `filterwarnings("error")` is enabled.

### Solution: Patch at Module Level

Replace:

```python
with patch.object(HTTPServer, '__init__', return_value=None):
    with patch('threading.Thread') as mock_thread:
        mock_thread.return_value = MagicMock()
        ws.configure(config, inverter)
```

With:

```python
with patch('exports.webserver.HTTPServer'):
    with patch('exports.webserver.Thread'):
        ws.configure(config, inverter)
```

This patches the classes at the module level where they're imported, so `configure()` receives fully-mocked objects with no real server or thread state. The test only verifies that `scan_interval` is stored — it doesn't need any real `HTTPServer` internals.

---

## 3. Health Endpoint JSON Response Body

**File:** `SunGather/exports/webserver.py` — `MyServer.do_GET`, `/health` branch

### Problem: No Diagnostic Body

The `/health` endpoint returns only an HTTP status code (200 or 503) with no body and no `Content-Type` header. While sufficient for K8s liveness probes, it provides no diagnostic information when debugging pod restarts.

### Solution: Add JSON Response Body

Return a JSON response body for all three health states:

**No scrape attempted** — `200`:

```json
{"status": "ok", "last_scrape_age_seconds": null, "threshold_seconds": 90}
```

**Fresh data** — `200`:

```json
{"status": "ok", "last_scrape_age_seconds": 15.3, "threshold_seconds": 90}
```

**Stale data** — `503`:

```json
{"status": "stale", "last_scrape_age_seconds": 120.5, "threshold_seconds": 90}
```

All three states return the same schema (`status`, `last_scrape_age_seconds`, `threshold_seconds`) so consumers can rely on a single response shape. `last_scrape_age_seconds` is `null` when no scrape has been attempted, otherwise rounded to 1 decimal place. `threshold_seconds` is `scan_interval * 3` (integer).

All responses include `Content-Type: application/json` header.

The `json` module is already imported in `webserver.py`.

### Test Updates

**File:** `tests/test_health_endpoint.py`

- Update `make_request()` helper to return a 3-tuple of `(status_code, body_dict, handler)`:
  - After `handler.do_GET()`, seek `handler.wfile` to position 0 and read the bytes
  - Parse the bytes as JSON via `json.loads()`
  - Return `(response_code, parsed_body, handler)` — `handler` is needed for header assertions
- Verify `Content-Type` header by checking `handler.send_header.call_args_list` includes `("Content-type", "application/json")`
- Update all existing health endpoint tests to destructure the return tuple and assert both status code and body content
- Add an `autouse` fixture to `TestHealthEndpointNeverScraped` (or a module-level one) that resets `export_webserver.last_successful_scrape = None` and `export_webserver.scan_interval = 30` before each test to prevent order-dependent state leakage
- Existing test classes and method names remain the same; assertions are extended

---

## 4. Clarifying Comment for `host` Passing

**File:** `SunGather/client/sungrow_client.py`, line 65

### Problem: Inconsistent Constructor Calls

The three connection types handle `host` differently: `http` passes it as a keyword argument, while `sungrow` and `modbus` pass it positionally. This is correct (`SungrowModbusWebClient` declares `host` with a default value) but could confuse future maintainers.

### Solution: Add Explanatory Comment

Add a comment above the `http` branch:

```python
# host passed as keyword — SungrowModbusWebClient declares it with a default, unlike the other clients
self.client = SungrowModbusWebClient(host=host, **config)
```

No functional change.

---

## Scope

- All 4 items are independent
- No changes to config schema, register definitions, or external interfaces
- No new dependencies
- Backwards compatible — health endpoint callers checking only status codes are unaffected
