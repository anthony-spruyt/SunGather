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

## Architecture

### Core Flow

[sungather.py](SunGather/sungather.py) is the entry point:

1. Loads config YAML and register definitions
2. Connects to inverter via `SungrowClient` (external package)
3. Calls `inverter.configure_registers()` to set up model-specific registers
4. Loads enabled export modules dynamically via `importlib`
5. Runs polling loop: `inverter.scrape()` → `export.publish()` for each export

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
