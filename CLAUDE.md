# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SunGather collects data from Sungrow inverters via ModbusTCP and exports to various destinations (MQTT, InfluxDB, PVOutput, Home Assistant). It auto-detects inverter models and retrieves appropriate register configurations.

## Development Commands

```bash
# Install dependencies (uv.lock is the source of truth)
uv sync

# Run the application
uv run sungather -c config.yaml

# Run with options
uv run sungather -c /path/config.yaml -v 10  # Debug logging
uv run sungather --runonce                    # Single scrape then exit

# Linting (pre-commit hooks)
pre-commit run --all-files

# Full linting with MegaLinter (requires Docker)
./lint.sh

# Build Docker image
docker build -t sungather .
```

## Testing

```bash
# Run all unit tests (tests/unit)
uv run pytest

# Run a specific test file
uv run pytest tests/unit/test_sungather_cli.py -v

# Run e2e integration test (requires Docker + a reachable real inverter)
SUNGATHER_TEST_INVERTER_HOST=<inverter-ip> uv run pytest tests/integration -m integration -v
```

Unit tests cover core scraping logic, register configuration, the CLI entrypoint, and export modules. Integration tests are excluded by default (`-m 'not integration'` in pyproject.toml).

**Before declaring a PR ready to merge**, always run the e2e integration test locally if the inverter is reachable. It builds the Docker image, runs `--runonce` against the real inverter, and validates a successful scrape cycle. Set `SUNGATHER_TEST_INVERTER_HOST` to your inverter's address — the test skips without it. Never commit a real inverter address.

## CI/CD

The workflows in `.github/workflows/` call repo-operator's shared workflows (the `python-image` group):

- `ci.yaml` - Lint (MegaLinter), run the uv test suite, build the image and smoke-test it
- `release-please.yaml` - Runs on every push to `main`. Maintains a release PR from conventional commits; merging it creates the `vX.Y.Z` tag, builds and pushes the image to GHCR, and publishes the GitHub Release.
- `rebuild-release.yaml` - Manual rebuild of an existing release's image
- `trivy-scan.yaml` - Daily vulnerability scan of published container images

### Releasing

Releases are fully automated by [release-please](https://github.com/googleapis/release-please):

1. Land a releasable conventional commit on `main`
2. release-please opens or updates a release PR titled `chore: release main`, bumping `pyproject.toml`, `uv.lock`, `.release-please-manifest.json`, and `CHANGELOG.md`
3. Mergify auto-merges that PR (it carries the `autorelease: pending` label)
4. Merging cuts the tag `vX.Y.Z`, pushes `ghcr.io/anthony-spruyt/sungather:X.Y.Z`, `:X.Y` and `:latest`, and flips the draft release to published

Note the tag carries a leading `v`; the image tag does not.

**Never manually create git tags or GitHub Releases, and never hand-edit the version in `pyproject.toml`.** release-please owns all three. The app reads its version from the installed package metadata.

#### Commit convention

The version bump and changelog are derived from commit prefixes:

| Prefix      | Changelog section        | Bump  |
| ----------- | ------------------------ | ----- |
| `feat:`     | Features                 | minor |
| `fix:`      | Bug Fixes                | patch |
| `perf:`     | Performance Improvements | patch |
| `refactor:` | Code Refactoring         | patch |
| `revert:`   | Reverts                  | patch |

`feat!:` or a `BREAKING CHANGE:` footer forces a major bump. `chore:`, `build:`, `ci:`, `docs:`, `style:` and `test:` are hidden and cut no release. Renovate dependency bumps use `fix(deps):` so they release.

#### Release scope

The release package is the repo root, minus `.claude`, `.devcontainer`, `.github`, `.vscode`, `docs` and `img`, so config sync, CI and doc changes don't produce empty releases.

To force a release without an in-scope change — say, rebuilding for a base image CVE — use a `Release-As:` footer:

```text
chore: rebuild for base image CVE

Release-As: 2.0.1
```

## Architecture

### Core Flow

[sungather.py](src/sungather/sungather.py) is the entry point, installed as the `sungather` console script:

1. Loads config YAML and register definitions (the packaged `registers-sungrow.yaml` unless `-r` is given)
2. Connects to inverter via vendored `SungrowClient` (`src/sungather/client/`)
3. Calls `inverter.configure_registers()` to set up model-specific registers
4. Loads enabled export modules dynamically via `importlib`
5. Runs polling loop: `inverter.scrape()` → `export.publish()` for each export

### Vendored Client Libraries

Located in [src/sungather/client/](src/sungather/client/). These were previously external packages, now bundled in-repo:

- `sungrow_client.py` - Base Modbus client (uses pymodbus 3.x)
- `sungrow_modbus_tcp_client.py` - Direct Modbus TCP connection
- `sungrow_modbus_web_client.py` - HTTP/WebSocket-based connection

### Export Modules

Located in [src/sungather/exports/](src/sungather/exports/). Each export implements:

- `configure(config, inverter)` - Setup with config dict and inverter reference
- `publish(inverter)` - Called each scrape cycle to export data

Exports: `console`, `webserver`, `mqtt`, `influxdb`, `pvoutput`

### Configuration

- [config-example.yaml](src/sungather/config-example.yaml) - Main config template
- [registers-sungrow.yaml](src/sungather/registers-sungrow.yaml) - Register definitions per model with address, datatype, and model compatibility

### Key Concepts

- **Register levels**: 0=basic, 1=useful (default), 2=all supported, 3=everything
- **Connection types**: `modbus` (direct), `sungrow` (SungrowModbusTcpClient), `http` (SungrowModbusWebClient)
- **smart_meter**: Enables grid consumption registers for SG\* models (hybrid models have this built-in)
- **Health endpoint**: `/health` on the webserver export — returns connection status and staleness info, used by Docker HEALTHCHECK
