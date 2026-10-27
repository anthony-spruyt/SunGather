"""Tests for log injection sanitization in webserver export."""

from sungather.exports.webserver import sanitize_for_log


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
