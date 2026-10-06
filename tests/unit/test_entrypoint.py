import importlib
import sys
from pathlib import Path

import pytest

from sungather import __version__


def test_module_imports_without_exiting():
    module = importlib.import_module("sungather.sungather")
    assert callable(module.main)


def test_help_prints_version_and_exits_cleanly(capsys, monkeypatch):
    module = importlib.import_module("sungather.sungather")
    monkeypatch.setattr(sys, "argv", ["sungather", "-h"])
    with pytest.raises(SystemExit) as exc:
        module.main()
    assert exc.value.code is None
    assert f"SunGather {__version__}" in capsys.readouterr().out


def test_default_registers_file_ships_with_the_package(monkeypatch):
    module = importlib.import_module("sungather.sungather")
    monkeypatch.setattr(sys, "argv", ["sungather"])
    _config, registers, *_ = module._parse_args()
    assert Path(registers).is_file()
