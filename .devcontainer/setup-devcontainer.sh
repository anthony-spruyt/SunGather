#!/bin/bash
set -euo pipefail

# Implement custom devcontainer setup here. This is run after the devcontainer has been created.

# Install Python LSP server for cclsp
# renovate: depName=python-lsp-server datasource=pypi
PYLSP_VERSION="1.14.0"

echo "Installing python-lsp-server ${PYLSP_VERSION}..."
pipx install "python-lsp-server==${PYLSP_VERSION}"

# Install cclsp (LSP-MCP bridge for AI coding agents)
# renovate: depName=cclsp datasource=npm
CCLSP_VERSION="0.7.0"

echo "Installing cclsp ${CCLSP_VERSION}..."
npm install -g "cclsp@${CCLSP_VERSION}"
