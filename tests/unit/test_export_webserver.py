"""Tests for the HTML pages built by the webserver export."""

import json
from html.parser import HTMLParser
from unittest.mock import patch

import pytest

from sungather.exports.webserver import ExportWebserver, _build_config_rows
from tests.inverter_stub import make_inverter


def special(label):
    """A text containing every character HTML treats specially."""
    return f"{label}\"><b class='x'>&amp;</b>"


class _Page(HTMLParser):
    """Collects tags, their attribute names and the text of each table cell."""

    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.cells = []
        self._cell = None
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, attrs))
        if tag == "td":
            self._cell = ""

    def handle_data(self, data):
        if self._cell is not None:
            self._cell += data

    def handle_endtag(self, tag):
        if tag == "td" and self._cell is not None:
            self.cells.append(self._cell)
            self._cell = None

    def shape(self):
        return [(tag, sorted(name for name, _ in attrs)) for tag, attrs in self.tags]


@pytest.fixture(autouse=True)
def reset_webserver_state(monkeypatch):
    """Restore the class-level state that publish and configure write."""
    monkeypatch.setattr(ExportWebserver, "main", "", raising=False)
    monkeypatch.setattr(ExportWebserver, "json", "", raising=False)
    monkeypatch.setattr(ExportWebserver, "config", "", raising=False)
    monkeypatch.setattr(ExportWebserver, "metrics", "")
    monkeypatch.setattr(ExportWebserver, "last_successful_scrape", None)
    monkeypatch.setattr(ExportWebserver, "scan_interval", 30)
    monkeypatch.setattr(ExportWebserver, "inverter_host", None)
    monkeypatch.setattr(ExportWebserver, "inverter_port", 502)


def _inverter(scrape, addr, unit, client, inverter):
    inv = make_inverter(
        latest_scrape=dict([scrape]),
        client_config={client[0]: client[1]},
        inverter_config={inverter[0]: inverter[1], "scan_interval": 30},
    )
    inv.getRegisterAddress.return_value = addr
    inv.getRegisterUnit.return_value = unit
    return inv


def _markup_inverter():
    return _inverter(
        (special("reg"), special("val")),
        special("addr"),
        special("unit"),
        (special("client_s"), special("client_v")),
        (special("inv_s"), special("inv_v")),
    )


def _benign_inverter():
    return _inverter(("reg", "val"), "addr", "unit", ("cs", "cv"), ("is", "iv"))


class TestConfigRows:
    def test_setting_and_value_are_shown_as_plain_text(self):
        """Setting names and values come out of the form fields unchanged."""
        setting, value = special("setting"), special("value")

        page = _Page(_build_config_rows([(setting, value)]))

        label = dict(next(a for t, a in page.tags if t == "label"))
        text_input, checkbox = (dict(a) for t, a in page.tags if t == "input")
        assert label["for"] == setting
        assert (text_input["id"], text_input["name"]) == (setting, setting)
        assert text_input["value"] == value
        assert checkbox["id"] == checkbox["name"] == f"update_{setting}"
        assert page.cells[0] == f"{setting}:"

    def test_markup_structure_does_not_depend_on_the_values(self):
        """Values with special characters and plain values give the same tags and attributes."""
        plain = _Page(_build_config_rows([("setting", "value")]))
        special_page = _Page(_build_config_rows([(special("setting"), special("value"))]))

        assert special_page.shape() == plain.shape()


class TestMainPage:
    def test_register_and_config_values_are_shown_as_plain_text(self):
        """Every register and config value is a cell of text."""
        ExportWebserver().publish(_markup_inverter())

        page = _Page(ExportWebserver.main)

        assert page.cells == [
            special("addr"),
            special("reg"),
            f"{special('val')} {special('unit')}",
            special("client_s"),
            special("client_v"),
            special("inv_s"),
            special("inv_v"),
            "scan_interval",
            "30",
        ]

    def test_markup_structure_does_not_depend_on_the_values(self):
        """Values with special characters and plain values give the same tags and attributes."""
        ExportWebserver().publish(_benign_inverter())
        plain = _Page(ExportWebserver.main)
        ExportWebserver().publish(_markup_inverter())
        special_page = _Page(ExportWebserver.main)

        assert special_page.shape() == plain.shape()


class TestConfigPage:
    def test_configure_shows_client_and_inverter_config_as_plain_text(self):
        """The config page lists both config blocks as text and form values."""
        inv = _markup_inverter()

        with (
            patch("sungather.exports.webserver.HTTPServer"),
            patch("sungather.exports.webserver.Thread"),
        ):
            assert ExportWebserver().configure({}, inv) is True

        page = _Page(ExportWebserver.config)
        fields = [dict(a) for t, a in page.tags if t == "input"]
        values = [f.get("value") for f in fields if f.get("type") == "text"]
        assert values == [special("client_v"), special("inv_v"), "30"]


class TestMachineReadableOutputs:
    def test_json_and_metrics_keep_the_raw_values(self):
        """JSON and metrics carry the values exactly as scraped."""
        ExportWebserver().publish(_markup_inverter())

        reg, val = special("reg"), special("val")
        addr, unit = special("addr"), special("unit")
        assert ExportWebserver.metrics == (f'{reg}{{address="{addr}", unit="{unit}"}} {val}\n')
        assert ExportWebserver.json == json.dumps(
            {
                "registers": {addr: {"register": reg, "value": val, "unit": unit}},
                "client_config": {special("client_s"): special("client_v")},
                "inverter_config": {
                    special("inv_s"): special("inv_v"),
                    "scan_interval": "30",
                },
            }
        )
