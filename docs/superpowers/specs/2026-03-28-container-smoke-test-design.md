# Container Smoke Test

## Problem

The pymodbus 3.x migration shipped a broken import that crashed the container on startup. Existing unit tests didn't catch it because they never exercise the container or the `sungather.py` entrypoint as a process.

## Goal

A pytest integration test that builds the production Docker image, runs it with `--runonce`, and verifies the container completes a scrape cycle without crashing.

## Design

### Fixture config: `tests/fixtures/config-smoke.yaml`

Minimal config with only inverter + console export:

```yaml
inverter:
  host: "192.168.30.95"
  port: 502
  connection: "sungrow"
  smart_meter: True
  model: "SG5K-D"
  slave: 0x01
  level: 1
  scan_interval: 30
  timeout: 10
  retries: 3
  log_console: "DEBUG"
  log_file: "OFF"
  use_local_time: True
exports:
  - name: "console"
    enabled: True
```

No MQTT, no webserver, no credentials. Console export only so we can see output.

### Test: `tests/test_container_smoke.py`

Single test function:

1. **Skip conditions** (via `pytest.mark.skipif`):
   - Docker not available (no `docker` binary or daemon not running)
   - Inverter not reachable (`socket.connect_ex` to host:port fails)

2. **Marker**: `@pytest.mark.integration` so it doesn't run with `pytest tests/ -v` by default.

3. **Test body**:
   - Build the production Docker image: `docker build -t sungather:smoke-test .`
   - Run the container with the fixture config mounted and `--runonce`:
     ```bash
     docker run --rm --network host \
       -v tests/fixtures/config-smoke.yaml:/config/config.yaml:ro \
       sungather:smoke-test \
       /opt/virtualenv/bin/python sungather.py -c /config/config.yaml --runonce
     ```
   - `--network host` so the container can reach the inverter on the LAN.
   - Assert exit code is 0.
   - Assert no `Traceback` or `Error` in stderr/stdout (allowing `log_console: DEBUG` output).

4. **Timeout**: `subprocess.run` with a 60-second timeout. If the container hangs, the test fails rather than blocking forever.

### pytest configuration

Register the `integration` marker in `pyproject.toml` or `pytest.ini` (whichever exists) so pytest doesn't warn about unknown markers.

### What this catches

- Broken imports (the exact bug that prompted this)
- Missing dependencies in the prod image
- Dockerfile COPY/path errors
- Entrypoint crashes
- Config parsing failures
- Connection setup crashes

### What this does NOT catch (yet — future emulation work)

- CI runs (needs pymodbus emulator, separate task)
- Export failures beyond console
- Register scraping edge cases

### Fix: `runonce` and `loglevel` locals() checks

`sungather.py` uses `'runonce' in locals()` (line 175) and `'loglevel' in locals()` (line 98) to check whether CLI flags were passed. This works by accident — the variables only exist if the corresponding `elif` branch executed. It's fragile: a refactor that initializes either variable would silently change behavior.

Fix: initialize both at the top of `main()` with sensible defaults:

```python
runonce = False
loglevel = None
```

Then replace:
- `'runonce' in locals()` → `runonce` (truthy check)
- `'loglevel' in locals()` → `loglevel is not None`

This is a two-line init change and two one-line replacements. Tests cover `--runonce` via the container smoke test (exit code 0 proves it worked).

## Files

| File                               | Action                                                                |
| ---------------------------------- | --------------------------------------------------------------------- |
| `tests/fixtures/config-smoke.yaml` | Create — minimal inverter + console config                            |
| `tests/test_container_smoke.py`    | Create — integration smoke test                                       |
| `tests/fixtures/config.yaml`       | Delete — replaced by config-smoke.yaml                                |
| `pyproject.toml` or `pytest.ini`   | Edit — register `integration` marker                                  |
| `SunGather/sungather.py`           | Edit — initialize `runonce`/`loglevel`, replace `in locals()` checks  |
