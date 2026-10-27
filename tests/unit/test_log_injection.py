"""Tests for the webserver export's log sanitizer and its /config and POST handlers."""

import json
from http.server import HTTPServer
from io import BytesIO
from unittest.mock import MagicMock

import pytest

from sungather.exports.webserver import MyServer, export_webserver, sanitize_for_log


@pytest.fixture(autouse=True)
def reset_webserver_state(monkeypatch):
    """Reset class-level state before each test."""
    monkeypatch.setattr(export_webserver, "config", "<p>config</p>", raising=False)


def make_handler(method, path, body=b""):
    """Create a handler whose response goes to a BytesIO and a mock."""
    handler = MyServer.__new__(MyServer)
    handler.server = MagicMock(spec=HTTPServer)
    handler.path = path
    handler.headers = {"Content-Length": str(len(body))}
    handler.requestline = f"{method} {path} HTTP/1.1"
    handler.request_version = "HTTP/1.1"
    handler.command = method
    handler.send_response = MagicMock()
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()
    handler.rfile = BytesIO(body)
    handler.wfile = BytesIO()
    return handler


class TestSanitizeForLog:
    """The sanitize_for_log helper must strip control characters."""

    def test_removes_newline(self):
        assert "\n" not in sanitize_for_log("hello\nworld")

    def test_removes_carriage_return(self):
        assert "\r" not in sanitize_for_log("hello\rworld")

    def test_removes_crlf(self):
        result = sanitize_for_log("line1\r\nline2")
        assert "\r" not in result
        assert "\n" not in result

    def test_preserves_normal_text(self):
        assert sanitize_for_log("normal text") == "normal text"


class TestGetConfig:
    def test_responds_200_and_writes_the_config_page(self):
        handler = make_handler("GET", "/config?key=value%0aINJECTED")

        handler.do_GET()

        handler.send_response.assert_called_once_with(200)
        assert handler.wfile.getvalue() == b"<p>config</p>"


class TestPost:
    def test_writes_the_decoded_form_body_as_json(self):
        handler = make_handler("POST", "/config", b"key=value%0aINJECTED")

        handler.do_POST()

        expected = json.dumps({"key": ["value\nINJECTED"]}).encode()
        assert handler.wfile.getvalue() == expected
