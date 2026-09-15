#!/usr/bin/env bash
# shellcheck disable=SC2034 # Variables used by sourcing script (lint.sh)
# Lint configuration - customize per repository
# This file is sourced by lint.sh for both local and CI runs

# MegaLinter Docker image (use digest for reproducibility)
# renovate: datasource=docker depName=ghcr.io/anthony-spruyt/megalinter-sungather
MEGALINTER_IMAGE="ghcr.io/anthony-spruyt/megalinter-sungather:1.0.20@sha256:d8a86401335ed749ae2fe2fdd9bb37080eaa9157c92568c13dc1a3f18c7e67d9"

# Skip linting for renovate/dependabot commits in CI
SKIP_BOT_COMMITS=false

# MegaLinter flavor (use "all" for custom images to bypass flavor validation)
MEGALINTER_FLAVOR="all"
