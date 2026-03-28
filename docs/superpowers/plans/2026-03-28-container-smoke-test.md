# Container Smoke Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a pytest integration test that builds and runs the production Docker container with `--runonce` against a real inverter, verifying the full startup-scrape-exit path works.

**Architecture:** A single pytest test with skip guards (no Docker, no inverter) builds the prod image, runs it with a minimal config fixture mounted, and asserts clean exit. The `runonce`/`loglevel` locals() fragility in `sungather.py` is fixed as a prerequisite.

**Tech Stack:** pytest, subprocess, Docker CLI, socket (for skip checks)

---

## File Structure

| File                               | Responsibility                                                   |
| ---------------------------------- | ---------------------------------------------------------------- |
| `SunGather/sungather.py`           | Fix `runonce`/`loglevel` initialization                          |
| `tests/fixtures/config-smoke.yaml` | Minimal inverter + console config for smoke test                 |
| `tests/test_container_smoke.py`    | Integration test: build image, run container, assert clean exit  |
| `pyproject.toml`                   | Register `integration` marker, exclude it from default test runs |

---

### Task 1: Fix `runonce` and `loglevel` locals() checks

**Files:**
- Modify: `SunGather/sungather.py:16-19` (add initializers)
- Modify: `SunGather/sungather.py:98` (replace loglevel check)
- Modify: `SunGather/sungather.py:175` (replace runonce check)
- Test: `tests/test_sungather_cli.py`

- [ ] **Step 1: Write failing tests for runonce and loglevel initialization**

Create `tests/test_sungather_cli.py`:

```python
import ast
import os


SUNGATHER_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'SunGather', 'sungather.py'
)


def _parse_sungather():
    with open(SUNGATHER_PATH) as f:
        return ast.parse(f.read())


def test_runonce_not_checked_via_locals():
    """runonce should be initialized, not checked via 'in locals()'."""
    with open(SUNGATHER_PATH) as f:
        source = f.read()
    assert "'runonce' in locals()" not in source, (
        "runonce is checked via 'in locals()' — initialize it at the top of main() instead"
    )


def test_loglevel_not_checked_via_locals():
    """loglevel should be initialized, not checked via 'in locals()'."""
    with open(SUNGATHER_PATH) as f:
        source = f.read()
    assert "'loglevel' in locals()" not in source, (
        "loglevel is checked via 'in locals()' — initialize it at the top of main() instead"
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_sungather_cli.py -v`
Expected: both FAIL because `sungather.py` still uses `in locals()`

- [ ] **Step 3: Initialize `runonce` and `loglevel` at top of `main()`**

In `SunGather/sungather.py`, after line 18 (`logfolder = ''`), add:

```python
    runonce = False
    loglevel = None
```

- [ ] **Step 4: Replace `'loglevel' in locals()` check**

In `SunGather/sungather.py`, line 98, change:

```python
    if 'loglevel' in locals():
```

to:

```python
    if loglevel is not None:
```

- [ ] **Step 5: Replace `'runonce' in locals()` check**

In `SunGather/sungather.py`, line 175, change:

```python
        if 'runonce' in locals():
```

to:

```python
        if runonce:
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_sungather_cli.py tests/test_import_integration.py -v`
Expected: all PASS

- [ ] **Step 7: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: all pass (no regressions)

- [ ] **Step 8: Commit**

```bash
git add SunGather/sungather.py tests/test_sungather_cli.py
git commit -m "fix: replace fragile 'in locals()' checks with proper initialization"
```

---

### Task 2: Create minimal smoke test config fixture

**Files:**
- Create: `tests/fixtures/config-smoke.yaml`
- Delete: `tests/fixtures/config.yaml`

- [ ] **Step 1: Create `tests/fixtures/config-smoke.yaml`**

```yaml
inverter:
  host: "192.168.30.95"
  port: 502
  connection: "sungrow"
  smart_meter: true
  model: "SG5K-D"
  slave: 0x01
  level: 1
  scan_interval: 30
  timeout: 10
  retries: 3
  log_console: "DEBUG"
  log_file: "OFF"
  use_local_time: true
exports:
  - name: "console"
    enabled: true
```

- [ ] **Step 2: Delete `tests/fixtures/config.yaml`**

```bash
git rm tests/fixtures/config.yaml
```

- [ ] **Step 3: Commit**

```bash
git add tests/fixtures/config-smoke.yaml
git commit -m "test: add minimal smoke test config fixture"
```

---

### Task 3: Register `integration` marker and exclude from default runs

**Files:**
- Create: `pyproject.toml`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[tool.pytest.ini_options]
markers = [
    "integration: container integration tests (require Docker and network access)",
]
addopts = "-m 'not integration'"
```

The `addopts` line means `pytest tests/ -v` skips integration tests by default. To run them explicitly: `pytest -m integration -v`.

- [ ] **Step 2: Verify marker is registered**

Run: `python -m pytest --markers | grep integration`
Expected: `@pytest.mark.integration: container integration tests (require Docker and network access)`

- [ ] **Step 3: Verify existing tests still run**

Run: `python -m pytest tests/ -v`
Expected: all 28+ tests pass, no unknown marker warnings

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "test: register integration marker, exclude from default runs"
```

---

### Task 4: Write the container smoke test

**Files:**
- Create: `tests/test_container_smoke.py`

- [ ] **Step 1: Write the smoke test**

```python
import os
import shutil
import socket
import subprocess

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CONFIG_PATH = os.path.join(REPO_ROOT, 'tests', 'fixtures', 'config-smoke.yaml')
IMAGE_TAG = 'sungather:smoke-test'
INVERTER_HOST = '192.168.30.95'
INVERTER_PORT = 502


def _docker_available():
    """Check Docker CLI exists and daemon is running."""
    if not shutil.which('docker'):
        return False
    result = subprocess.run(
        ['docker', 'info'],
        capture_output=True,
        timeout=10,
    )
    return result.returncode == 0


def _inverter_reachable():
    """Check if the inverter responds on its Modbus port."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3)
    try:
        return sock.connect_ex((INVERTER_HOST, INVERTER_PORT)) == 0
    finally:
        sock.close()


@pytest.mark.integration
@pytest.mark.skipif(not _docker_available(), reason='Docker not available')
@pytest.mark.skipif(not _inverter_reachable(), reason=f'Inverter not reachable at {INVERTER_HOST}:{INVERTER_PORT}')
class TestContainerSmoke:
    """Smoke test: build prod image, run --runonce, assert clean exit."""

    @classmethod
    def setup_class(cls):
        """Build the production Docker image once for all tests in this class."""
        result = subprocess.run(
            ['docker', 'build', '-t', IMAGE_TAG, '.'],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=300,
        )
        assert result.returncode == 0, (
            f"Docker build failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_runonce_exits_cleanly(self):
        """Container should complete one scrape cycle and exit 0."""
        result = subprocess.run(
            [
                'docker', 'run', '--rm', '--network', 'host',
                '-v', f'{CONFIG_PATH}:/config/config.yaml:ro',
                IMAGE_TAG,
                '/opt/virtualenv/bin/python', 'sungather.py',
                '-c', '/config/config.yaml', '--runonce',
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, (
            f"Container exited with code {result.returncode}:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_no_tracebacks_in_output(self):
        """Container output should not contain Python tracebacks."""
        result = subprocess.run(
            [
                'docker', 'run', '--rm', '--network', 'host',
                '-v', f'{CONFIG_PATH}:/config/config.yaml:ro',
                IMAGE_TAG,
                '/opt/virtualenv/bin/python', 'sungather.py',
                '-c', '/config/config.yaml', '--runonce',
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        combined = result.stdout + result.stderr
        assert 'Traceback' not in combined, (
            f"Traceback found in container output:\n{combined}"
        )
```

- [ ] **Step 2: Run the integration test**

Run: `python -m pytest tests/test_container_smoke.py -m integration -v`

Expected (if Docker and inverter available): both tests PASS
Expected (if not available): both tests SKIPPED with reason

- [ ] **Step 3: Verify default test run still excludes integration tests**

Run: `python -m pytest tests/ -v`
Expected: integration tests show as "deselected", all other tests pass

- [ ] **Step 4: Commit**

```bash
git add tests/test_container_smoke.py
git commit -m "test: add container smoke test with --runonce"
```

---

### Task 5: Pre-commit and final verification

- [ ] **Step 1: Run pre-commit hooks**

Run: `pre-commit run --all-files`
Expected: all pass

- [ ] **Step 2: Run full unit test suite**

Run: `python -m pytest tests/ -v`
Expected: all unit tests pass, integration tests deselected

- [ ] **Step 3: Run integration test**

Run: `python -m pytest -m integration -v`
Expected: PASS if Docker + inverter available, SKIP otherwise

- [ ] **Step 4: Force-push updated branch**

```bash
git push --force-with-lease
```
