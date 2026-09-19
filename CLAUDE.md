# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SunGather collects data from Sungrow inverters via ModbusTCP and exports to various destinations (MQTT, InfluxDB, PVOutput, Home Assistant). It auto-detects inverter models and retrieves appropriate register configurations.

## Development Commands

```bash
# Install dependencies
pip3 install --upgrade -r SunGather/requirements.txt

# Run the application
cd SunGather && python3 sungather.py -c config.yaml

# Run with options
python3 sungather.py -c /path/config.yaml -v 10  # Debug logging
python3 sungather.py --runonce                    # Single scrape then exit

# Linting (pre-commit hooks)
pre-commit run --all-files

# Full linting with MegaLinter (requires Docker)
./lint.sh

# Build Docker image (context stays at the repo root)
docker build -f SunGather/Dockerfile -t sungather .
```

## Testing

```bash
# Run all unit tests
python -m pytest tests/ -v

# Run a specific test file
python -m pytest tests/test_sungather.py -v

# Run e2e integration test (requires Docker + a reachable real inverter)
SUNGATHER_TEST_INVERTER_HOST=<inverter-ip> python -m pytest tests/test_container_smoke.py -m integration -v
```

104 unit tests covering core scraping logic, register configuration, and export modules. Integration tests are excluded by default (`-m 'not integration'` in pyproject.toml).

**Before declaring a PR ready to merge**, always run the e2e integration test locally if the inverter is reachable. It builds the Docker image, runs `--runonce` against the real inverter, and validates a successful scrape cycle. Set `SUNGATHER_TEST_INVERTER_HOST` to your inverter's address — the test skips without it. Never commit a real inverter address.

## CI/CD

Three GitHub Actions workflows in `.github/workflows/`:

- `ci.yaml` - Lint (pre-commit), build Docker image, run tests, Trivy scan on PRs
- `release-please.yaml` - Runs on every push to `main`. Maintains a release PR from conventional commits; merging it creates the `vX.Y.Z` tag, builds and pushes the image (amd64) to GHCR, and publishes the GitHub Release.
- `trivy-scan.yaml` - Daily vulnerability scan of published container images

### Releasing

Releases are fully automated by [release-please](https://github.com/googleapis/release-please):

1. Land a conventional commit on `main` that touches `SunGather/**`
2. release-please opens or updates a release PR titled `chore: release main`, bumping `SunGather/version.py`, `.release-please-manifest.json`, and `CHANGELOG.md`
3. Mergify auto-merges that PR (it carries the `autorelease: pending` label)
4. Merging cuts the tag `vX.Y.Z`, pushes `ghcr.io/anthony-spruyt/sungather:X.Y.Z` and `:latest`, and flips the draft release to published

Note the tag carries a leading `v`; the image tag does not.

**Never manually create git tags or GitHub Releases, and never hand-edit `SunGather/version.py`.** release-please owns all three.

#### Commit convention

The version bump and changelog are derived from commit prefixes:

| Prefix      | Changelog section        | Bump  |
| ----------- | ------------------------ | ----- |
| `feat:`     | Features                 | minor |
| `fix:`      | Bug Fixes                | patch |
| `perf:`     | Performance Improvements | patch |
| `refactor:` | Code Refactoring         | patch |
| `chore:`    | Dependencies             | patch |
| `docs:`     | Documentation            | patch |
| `ci:`       | Continuous Integration   | patch |

`feat!:` or a `BREAKING CHANGE:` footer forces a major bump. Any other prefix is omitted from the changelog entirely.

#### Release scope

Only commits touching `SunGather/**` cut a release. That directory holds the app code, the `Dockerfile`, and `requirements.txt` — everything that goes into the image. Config sync, Renovate dotfile bumps, docs, and CI changes are deliberately invisible to release-please so they don't produce empty releases.

To force a release without an in-scope change — say, rebuilding for a base image CVE — use a `Release-As:` footer:

```text
chore: rebuild for base image CVE

Release-As: 2.0.1
```

## Architecture

### Core Flow

[sungather.py](SunGather/sungather.py) is the entry point:

1. Loads config YAML and register definitions
2. Connects to inverter via vendored `SungrowClient` (`SunGather/client/`)
3. Calls `inverter.configure_registers()` to set up model-specific registers
4. Loads enabled export modules dynamically via `importlib`
5. Runs polling loop: `inverter.scrape()` → `export.publish()` for each export

### Vendored Client Libraries

Located in [SunGather/client/](SunGather/client/). These were previously external packages, now bundled in-repo:

- `sungrow_client.py` - Base Modbus client (uses pymodbus 3.x)
- `sungrow_modbus_tcp_client.py` - Direct Modbus TCP connection
- `sungrow_modbus_web_client.py` - HTTP/WebSocket-based connection

### Export Modules

Located in [SunGather/exports/](SunGather/exports/). Each export implements:

- `configure(config, inverter)` - Setup with config dict and inverter reference
- `publish(inverter)` - Called each scrape cycle to export data

Exports: `console`, `webserver`, `mqtt`, `influxdb`, `pvoutput`

### Configuration

- [config-example.yaml](SunGather/config-example.yaml) - Main config template
- [registers-sungrow.yaml](SunGather/registers-sungrow.yaml) - Register definitions per model with address, datatype, and model compatibility

### Key Concepts

- **Register levels**: 0=basic, 1=useful (default), 2=all supported, 3=everything
- **Connection types**: `modbus` (direct), `sungrow` (SungrowModbusTcpClient), `http` (SungrowModbusWebClient)
- **smart_meter**: Enables grid consumption registers for SG\* models (hybrid models have this built-in)
- **Health endpoint**: `/health` on the webserver export — returns connection status and staleness info, used by Docker HEALTHCHECK
