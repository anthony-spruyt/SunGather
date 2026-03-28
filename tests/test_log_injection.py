"""Tests for log injection sanitization in webserver export."""
import logging
import urllib.parse
from io import BytesIO
from http.server import HTTPServer
from unittest.mock import MagicMock, patch

import pytest

from exports.webserver import MyServer, export_webserver, sanitize_for_log


@pytest.fixture(autouse=True)
def reset_webserver_state():
    """Reset class-level state before each test."""
    export_webserver.last_successful_scrape = None
    export_webserver.scan_interval = 30
    export_webserver.config = "<p>config</p>"


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

    def test_handles_dict_with_newlines(self):
        data = {"key": ["value\nINJECTED"]}
        result = sanitize_for_log(str(data))
        assert "\n" not in result


class TestGetConfigLogSanitized:
    """Alert #3: GET /config must sanitize query data before logging."""

    def test_config_query_logged_via_sanitize(self, caplog):
        """Logging from /config must not contain raw newlines."""
        handler = MyServer.__new__(MyServer)
        handler.server = MagicMock(spec=HTTPServer)
        handler.path = "/config?key=value%0aINJECTED"
        handler.headers = {}
        handler.requestline = "GET /config?key=value%0aINJECTED HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.command = "GET"
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.wfile = BytesIO()

        with caplog.at_level(logging.INFO):
            handler.do_GET()

        for record in caplog.records:
            assert "\n" not in record.message
            assert "\r" not in record.message


class TestPostLogSanitized:
    """Alert #4: POST handler must sanitize body before logging."""

    def test_post_body_logged_without_newlines(self, caplog):
        """POST logging must not contain raw newlines from body."""
        body = b"key=value%0aINJECTED"
        handler = MyServer.__new__(MyServer)
        handler.server = MagicMock(spec=HTTPServer)
        handler.path = "/config"
        handler.headers = {"Content-Length": str(len(body))}
        handler.requestline = "POST /config HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.command = "POST"
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler.rfile = BytesIO(body)
        handler.wfile = BytesIO()

        with caplog.at_level(logging.INFO):
            handler.do_POST()

        for record in caplog.records:
            assert "\n" not in record.message
            assert "\r" not in record.message
