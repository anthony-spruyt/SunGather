# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SunGather collects data from Sungrow inverters via ModbusTCP and exports to various destinations (MQTT, InfluxDB, PVOutput, Home Assistant). It auto-detects inverter models and retrieves appropriate register configurations.

## Development Commands

```bash
# Install dependencies
pip3 install --upgrade -r requirements.txt

# Run the application
cd SunGather && python3 sungather.py -c config.yaml

# Run with options
python3 sungather.py -c /path/config.yaml -v 10  # Debug logging
python3 sungather.py --runonce                    # Single scrape then exit

# Linting (pre-commit hooks)
pre-commit run --all-files

# Full linting with MegaLinter (requires Docker)
./lint.sh

# Build Docker image
docker build -t sungather .
```

## Testing

```bash
# Run all unit tests
python -m pytest tests/ -v

# Run a specific test file
python -m pytest tests/test_sungather.py -v

# Run e2e integration test (requires Docker + real inverter at 192.168.30.95:502)
python -m pytest tests/test_container_smoke.py -m integration -v
```

104 unit tests covering core scraping logic, register configuration, and export modules. Integration tests are excluded by default (`-m 'not integration'` in pyproject.toml).

**Before declaring a PR ready to merge**, always run the e2e integration test locally if the inverter is reachable. It builds the Docker image, runs `--runonce` against the real inverter, and validates a successful scrape cycle.

## CI/CD

Three GitHub Actions workflows in `.github/workflows/`:

- `ci.yaml` - Lint (pre-commit), build Docker image, run tests, Trivy scan on PRs
- `release.yaml` - **Workflow dispatch only.** Computes the next semver, builds and pushes the Docker image (amd64) to GHCR, creates the git tag, and creates the GitHub Release — all automatically. **Do NOT manually create tags or GitHub Releases; the workflow handles everything.**
- `trivy-scan.yaml` - Daily vulnerability scan of published container images

### Releasing

Releases are done **exclusively** via the `release.yaml` workflow dispatch in GitHub Actions:

1. Go to Actions → Release → Run workflow
2. Select the bump type (patch / minor / major)
3. The workflow computes the version, runs tests, builds the image, pushes it, creates the git tag, and creates the GitHub Release

**Never manually create git tags or GitHub Releases.** Tags are immutable — a manual tag will conflict with the automated workflow and cannot be reused.

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
