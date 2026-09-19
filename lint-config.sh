#!/usr/bin/env bash
# shellcheck disable=SC2034 # Variables used by sourcing script (lint.sh)
# Lint configuration - customize per repository
# This file is sourced by lint.sh for both local and CI runs

# MegaLinter Docker image (use digest for reproducibility)
# renovate: datasource=docker depName=ghcr.io/anthony-spruyt/megalinter-sungather
MEGALINTER_IMAGE="ghcr.io/anthony-spruyt/megalinter-sungather:2.0.0@sha256:f391a54244ffd1d2d0dde6c8c4f49a1dedd2eb5fc554b1eb5dc28c2bb442118f"

# Skip linting for renovate/dependabot commits in CI
SKIP_BOT_COMMITS=false

# MegaLinter flavor (use "all" for custom images to bypass flavor validation)
MEGALINTER_FLAVOR="all"
