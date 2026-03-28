# Issue #85 Follow-up Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement four quality improvements identified in issue #85 from the post-merge review of PR #84.

**Architecture:** Four independent changes: one new test, one test fix, one production code change (health endpoint JSON body), and one comment addition. All changes are backwards-compatible.

**Tech Stack:** Python 3, pytest, unittest.mock, json, http.server

**Spec:** `docs/superpowers/specs/2026-03-28-issue-85-followup-improvements-design.md`

**Worktree:** `.worktrees/issue-85` (branch `issue-85-followup-improvements`)

**Baseline:** 24 tests passing, 1 warning (the HTTPServer leak — item #2 fixes this)

**Run tests from repo root:** `python3 -m pytest tests/ -v --tb=short`

---

## File Map

| Action | File                                        | Purpose                                      |
| ------ | ------------------------------------------- | -------------------------------------------- |
| Modify | `tests/test_sungrow_client.py`              | Add http connection type test                |
| Modify | `tests/test_health_endpoint.py`             | Fix HTTPServer leak, update for JSON body    |
| Modify | `SunGather/exports/webserver.py`            | Add JSON response body to /health endpoint   |
| Modify | `SunGather/client/sungrow_client.py`        | Add clarifying comment for host passing      |

---

## Task 1: Add `http` Connection Type Test

**Files:**

- Modify: `tests/test_sungrow_client.py:42-75` (add new test to `TestSungrowClientConnect`)

**Note:** The production code's `connect()` method calls `time.sleep(3)` after a successful connection. This test will take ~3 seconds to run. The existing `modbus` and `sungrow` tests have the same delay. Do not mock `time.sleep` — keep consistent with the existing test pattern.

- [ ] **Step 1: Write the test**

Add the following test to the `TestSungrowClientConnect` class in `tests/test_sungrow_client.py`, after the `test_connect_sungrow_passes_host_positionally` method (after line 75):

```python
    @patch('client.sungrow_client.SungrowModbusWebClient')
    def test_connect_http_passes_host_as_keyword_and_overrides_port(self, MockClient):
        """SungrowModbusWebClient must receive host as keyword arg, port=8082."""
        mock_instance = MagicMock()
        mock_instance.connect.return_value = True
        MockClient.return_value = mock_instance

        config = make_config(connection='http')
        client = SungrowClient(config)
        result = client.connect()

        MockClient.assert_called_once()
        args, kwargs = MockClient.call_args
        assert args == ()
        assert kwargs['host'] == '192.168.1.1'
        assert kwargs['port'] == 8082
        assert result is True
```

- [ ] **Step 2: Run test to verify it passes**

This test covers an existing code path (not new behavior), so it should pass immediately.

Run: `cd /workspaces/SunGather/.worktrees/issue-85 && python3 -m pytest tests/test_sungrow_client.py::TestSungrowClientConnect::test_connect_http_passes_host_as_keyword_and_overrides_port -v --tb=short`

Expected: PASS

- [ ] **Step 3: Run full test suite to confirm no regressions**

Run: `cd /workspaces/SunGather/.worktrees/issue-85 && python3 -m pytest tests/ -v --tb=short`

Expected: 25 passed (was 24), 1 warning

- [ ] **Step 4: Commit**

```bash
cd /workspaces/SunGather/.worktrees/issue-85
git add tests/test_sungrow_client.py
git commit -m "test(client): add http connection type test for SungrowModbusWebClient

Verifies host is passed as keyword argument and port is overridden
to 8082, matching the behavior differences from modbus/sungrow paths.

Closes part of #85 (item 1)

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Fix HTTPServer Thread Leak Warning

**Files:**

- Modify: `tests/test_health_endpoint.py:123-126` (only the `with patch...` block inside `test_configure_stores_scan_interval`)

**Important:** Do NOT change imports in this task. The `HTTPServer` import on line 2 is still needed by `make_request()` on line 12 (`MagicMock(spec=HTTPServer)`). Import changes happen in Task 3.

- [ ] **Step 1: Update the patch lines**

Replace only lines 123-126 in `tests/test_health_endpoint.py` (the `with patch...` block inside `test_configure_stores_scan_interval`):

Old code:

```python
        with patch.object(HTTPServer, '__init__', return_value=None):
            with patch('threading.Thread') as mock_thread:
                mock_thread.return_value = MagicMock()
                ws.configure(config, inverter)
```

New code:

```python
        with patch('exports.webserver.HTTPServer'):
            with patch('exports.webserver.Thread'):
                ws.configure(config, inverter)
```

- [ ] **Step 2: Run the updated test**

Run: `cd /workspaces/SunGather/.worktrees/issue-85 && python3 -m pytest tests/test_health_endpoint.py::TestConfigureStoresScanInterval -v --tb=short`

Expected: PASS

- [ ] **Step 3: Run full test suite to confirm warning is gone**

Run: `cd /workspaces/SunGather/.worktrees/issue-85 && python3 -m pytest tests/ -v --tb=short`

Expected: 25 passed, 0 warnings. The `PytestUnhandledThreadExceptionWarning` about `_BaseServer__is_shut_down` should be gone. Note: the warning is caused by `TestConfigureStoresScanInterval` but pytest may report it against a different test (e.g., `test_import_integration.py`) because thread exceptions are caught asynchronously during garbage collection.

- [ ] **Step 4: Commit**

```bash
cd /workspaces/SunGather/.worktrees/issue-85
git add tests/test_health_endpoint.py
git commit -m "fix(tests): patch HTTPServer at module level to prevent leak warning

Patching HTTPServer.__init__ left a partially-initialized object that
caused AttributeError warnings during garbage collection. Patching
the class at the module import site prevents any real server state.

Closes part of #85 (item 2)

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Add JSON Response Body to Health Endpoint

This task has two phases: update the tests first (red), then update the production code (green).

**Files:**

- Modify: `tests/test_health_endpoint.py` (update imports, add fixture, rewrite `make_request` and all health tests)
- Modify: `SunGather/exports/webserver.py:85-94` (`MyServer.do_GET` health branch)

### Phase A: Update tests to expect JSON body (Red)

- [ ] **Step 1: Update imports, add autouse fixture, and rewrite `make_request` helper**

Update the imports at the top of `tests/test_health_endpoint.py` to add `json`:

```python
from datetime import datetime, timedelta
from http.server import HTTPServer
from io import BytesIO
from unittest.mock import patch, MagicMock
import json
import pytest

from exports.webserver import export_webserver, MyServer
```

Then insert the autouse fixture before `make_request` (before line 10), and replace the entire `make_request` function (lines 10-40):

```python
@pytest.fixture(autouse=True)
def reset_webserver_state():
    """Reset class-level state before each test to prevent leakage."""
    export_webserver.last_successful_scrape = None
    export_webserver.scan_interval = 30


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

    def capture_response(code, message=None):
        nonlocal response_code
        response_code = code

    handler.send_response = capture_response
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()
    handler.wfile = BytesIO()

    handler.do_GET()

    # Parse JSON body from wfile
    handler.wfile.seek(0)
    raw = handler.wfile.read()
    body = json.loads(raw) if raw else None

    return response_code, body, handler
```

- [ ] **Step 2: Update all health test classes**

Replace ALL health test classes (everything from `TestHealthEndpointNeverScraped` through `TestHealthEndpointEdgeCases`) and add the new `TestHealthEndpointContentType` class. The `TestPublishUpdatesTimestamp` and `TestConfigureStoresScanInterval` classes remain unchanged.

```python
class TestHealthEndpointNeverScraped:
    def test_returns_200_when_never_scraped(self):
        """Before any scrape, /health should return 200 with null age."""
        code, body, _ = make_request('/health')
        assert code == 200
        assert body['status'] == 'ok'
        assert body['last_scrape_age_seconds'] is None
        assert body['threshold_seconds'] == 90


class TestHealthEndpointFreshData:
    def test_returns_200_when_data_is_fresh(self):
        """/health should return 200 with age when last scrape is recent."""
        export_webserver.last_successful_scrape = datetime.now()
        code, body, _ = make_request('/health')
        assert code == 200
        assert body['status'] == 'ok'
        assert body['last_scrape_age_seconds'] < 2.0
        assert body['threshold_seconds'] == 90


class TestHealthEndpointStaleData:
    def test_returns_503_when_data_is_stale(self):
        """/health should return 503 with stale status when too old."""
        export_webserver.last_successful_scrape = (
            datetime.now() - timedelta(seconds=200)
        )
        code, body, _ = make_request('/health')
        assert code == 503
        assert body['status'] == 'stale'
        assert body['last_scrape_age_seconds'] >= 199.0
        assert body['threshold_seconds'] == 90


class TestHealthEndpointEdgeCases:
    def test_returns_200_just_below_threshold(self):
        """/health should return 200 when just below the 3x threshold."""
        export_webserver.last_successful_scrape = (
            datetime.now() - timedelta(seconds=89)
        )
        code, body, _ = make_request('/health')
        assert code == 200
        assert body['status'] == 'ok'
        assert body['threshold_seconds'] == 90

    def test_returns_503_just_past_boundary(self):
        """/health should return 503 just past the threshold."""
        export_webserver.last_successful_scrape = (
            datetime.now() - timedelta(seconds=91)
        )
        code, body, _ = make_request('/health')
        assert code == 503
        assert body['status'] == 'stale'
        assert body['threshold_seconds'] == 90


class TestHealthEndpointContentType:
    def test_health_returns_json_content_type(self):
        """/health should set Content-Type: application/json."""
        _, _, handler = make_request('/health')
        handler.send_header.assert_any_call("Content-type", "application/json")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /workspaces/SunGather/.worktrees/issue-85 && python3 -m pytest tests/test_health_endpoint.py -v --tb=short`

Expected: FAIL — the health endpoint tests will fail for two reasons:

1. The production code writes no body to `wfile`, so `raw` is `b''` (falsy).
   The guard `json.loads(raw) if raw else None` sets `body = None`.
   Then `body['status']` raises `TypeError: 'NoneType' object is not subscriptable`.
2. `TestHealthEndpointContentType` fails with `AssertionError` because
   `send_header` is never called for `/health` in the current production code.

The `TestPublishUpdatesTimestamp` and `TestConfigureStoresScanInterval` tests
should still PASS since they don't use `make_request`.

### Phase B: Implement JSON response body (Green)

- [ ] **Step 4: Update the health endpoint in webserver.py**

Replace lines 85-94 in `SunGather/exports/webserver.py` (the `/health` branch in `do_GET`):

Old code:

```python
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
```

New code:

```python
        if self.path == '/health':
            threshold = export_webserver.scan_interval * 3
            if export_webserver.last_successful_scrape is None:
                status = 200
                body = {"status": "ok", "last_scrape_age_seconds": None,
                        "threshold_seconds": threshold}
            else:
                age = (datetime.now() - export_webserver.last_successful_scrape
                       ).total_seconds()
                if age < threshold:
                    status = 200
                    body = {"status": "ok",
                            "last_scrape_age_seconds": round(age, 1),
                            "threshold_seconds": threshold}
                else:
                    status = 503
                    body = {"status": "stale",
                            "last_scrape_age_seconds": round(age, 1),
                            "threshold_seconds": threshold}
            self.send_response(status)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(bytes(json.dumps(body), "utf-8"))
            return
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /workspaces/SunGather/.worktrees/issue-85 && python3 -m pytest tests/test_health_endpoint.py -v --tb=short`

Expected: All PASS

- [ ] **Step 6: Run full test suite**

Run: `cd /workspaces/SunGather/.worktrees/issue-85 && python3 -m pytest tests/ -v --tb=short`

Expected: 26 passed (25 + new Content-Type test), 0 warnings

- [ ] **Step 7: Commit**

```bash
cd /workspaces/SunGather/.worktrees/issue-85
git add SunGather/exports/webserver.py tests/test_health_endpoint.py
git commit -m "feat(health): add JSON response body to /health endpoint

Returns consistent schema with status, last_scrape_age_seconds, and
threshold_seconds for all health states. Adds Content-Type header.
Adds autouse fixture to reset class-level state between tests.

Closes part of #85 (item 3)

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Add Clarifying Comment for `host` Passing

**Files:**

- Modify: `SunGather/client/sungrow_client.py:63-65`

- [ ] **Step 1: Add the comment**

In `SunGather/client/sungrow_client.py`, add a comment above line 65 (the `SungrowModbusWebClient` constructor call). The lines should read:

```python
        if self.inverter_config['connection'] == "http":
            config['port'] = 8082
            # host passed as keyword — SungrowModbusWebClient declares it with a default, unlike the other clients
            self.client = SungrowModbusWebClient(host=host, **config)
```

- [ ] **Step 2: Run full test suite to confirm no regressions**

Run: `cd /workspaces/SunGather/.worktrees/issue-85 && python3 -m pytest tests/ -v --tb=short`

Expected: 26 passed, 0 warnings

- [ ] **Step 3: Commit**

```bash
cd /workspaces/SunGather/.worktrees/issue-85
git add SunGather/client/sungrow_client.py
git commit -m "docs(client): clarify why http connection passes host as keyword

SungrowModbusWebClient declares host with a default value, unlike
ModbusTcpClient and SungrowModbusTcpClient which take it positionally.

Closes #85

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Final Verification

- [ ] **Run full test suite one last time**

Run: `cd /workspaces/SunGather/.worktrees/issue-85 && python3 -m pytest tests/ -v --tb=short`

Expected: 26 passed, 0 warnings

- [ ] **Run pre-commit hooks**

Run: `cd /workspaces/SunGather/.worktrees/issue-85 && pre-commit run --all-files`

Expected: All passed

- [ ] **Review git log**

Run: `cd /workspaces/SunGather/.worktrees/issue-85 && git log --oneline -7`

Expected: 6 commits on `issue-85-followup-improvements` branch ahead of main: 4 implementation commits, 1 plan commit, and 1 spec commit. The spec (`eb385c4`) and plan commits should already exist before implementation begins.
