#!/usr/bin/env bash
# shellcheck disable=SC2034 # Variables used by sourcing script (lint.sh)
# Lint configuration - customize per repository
# This file is sourced by lint.sh for both local and CI runs

# MegaLinter Docker image (use digest for reproducibility)
# renovate: datasource=docker depName=ghcr.io/anthony-spruyt/megalinter-sungather
MEGALINTER_IMAGE="ghcr.io/anthony-spruyt/megalinter-sungather:2.0.2@sha256:19482a7fd72bb5eb7c62e03f1605f5c75d0bc5ba395c0b3ebf9f91be753c99a8"

# Skip linting for renovate/dependabot commits in CI
SKIP_BOT_COMMITS=false

# MegaLinter flavor (use "all" for custom images to bypass flavor validation)
MEGALINTER_FLAVOR="all"
