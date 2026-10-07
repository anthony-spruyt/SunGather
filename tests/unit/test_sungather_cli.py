import ast
import importlib
import logging
import os
from unittest.mock import MagicMock

import pytest

SUNGATHER_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "src", "sungather", "sungather.py")


def _parse_sungather():
    with open(SUNGATHER_PATH, encoding="utf-8") as f:
        return ast.parse(f.read())


def test_runonce_not_checked_via_locals():
    """runonce should be initialized, not checked via 'in locals()'."""
    with open(SUNGATHER_PATH, encoding="utf-8") as f:
        source = f.read()
    assert "'runonce' in locals()" not in source, (
        "runonce is checked via 'in locals()' — initialize it at the top of main() instead"
    )


def test_loglevel_not_checked_via_locals():
    """loglevel should be initialized, not checked via 'in locals()'."""
    with open(SUNGATHER_PATH, encoding="utf-8") as f:
        source = f.read()
    assert "'loglevel' in locals()" not in source, (
        "loglevel is checked via 'in locals()' — initialize it at the top of main() instead"
    )


def test_load_exports_logs_traceback_when_export_fails(caplog):
    """A failing export should be skipped and logged with its traceback."""
    module = importlib.import_module("sungather.sungather")
    config = {"exports": [{"name": "does_not_exist", "enabled": True}]}
    with caplog.at_level(logging.ERROR):
        assert module._load_exports(config, MagicMock()) == []
    record = next(r for r in caplog.records if "Failed loading export" in r.getMessage())
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None


def test_verbose_accepts_levels_up_to_critical(monkeypatch):
    module = importlib.import_module("sungather.sungather")
    monkeypatch.setattr(module.sys, "argv", ["sungather", "-v", "50"])
    assert module._parse_args()[3] == logging.CRITICAL


def test_verbose_rejects_levels_above_critical(monkeypatch):
    module = importlib.import_module("sungather.sungather")
    monkeypatch.setattr(module.sys, "argv", ["sungather", "-v", "51"])
    with pytest.raises(SystemExit) as exc:
        module._parse_args()
    assert exc.value.code == 2
