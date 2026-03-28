"""Tests for the /health endpoint and webserver export."""

from datetime import datetime, timedelta
from http.server import HTTPServer
from io import BytesIO
from unittest.mock import patch, MagicMock
import json

import pytest  # pylint: disable=import-error

# pylint: disable=import-error
from exports.webserver import (
    export_webserver,
    MyServer,
    check_inverter_reachable,
)


@pytest.fixture(autouse=True)
def reset_webserver_state():
    """Reset class-level state before each test to prevent leakage."""
    export_webserver.last_successful_scrape = None
    export_webserver.inverter_host = '192.168.1.100'
    export_webserver.inverter_port = 502
    export_webserver.scan_interval = 30


def make_request(path, inverter_reachable=True):
    """Create a mock GET request and capture the response."""
    server = MagicMock(spec=HTTPServer)

    handler = MyServer.__new__(MyServer)
    handler.server = server
    handler.path = path
    handler.headers = {}
    handler.requestline = f'GET {path} HTTP/1.1'
    handler.request_version = 'HTTP/1.1'
    handler.command = 'GET'

    response_code = None

    def capture_response(code, _message=None):
        nonlocal response_code
        response_code = code

    handler.send_response = capture_response
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()
    handler.wfile = BytesIO()

    with patch(
        'exports.webserver.check_inverter_reachable',
        return_value=inverter_reachable,
    ):
        handler.do_GET()

    handler.wfile.seek(0)
    raw = handler.wfile.read()
    body = json.loads(raw) if raw else None

    return response_code, body, handler


class TestHealthInverterOffline:
    """Inverter is off (night) - always 200."""

    def test_startup_inverter_off(self):
        """Health returns 200 when inverter is unreachable."""
        code, body, _ = make_request(
            '/health', inverter_reachable=False
        )
        assert code == 200
        assert body['status'] == 'ok'
        assert body['detail'] == 'inverter_offline'
        assert body['inverter_reachable'] is False

    def test_night_after_day_scraping(self):
        """Stale timestamp ignored when inverter is off."""
        export_webserver.last_successful_scrape = (
            datetime.now() - timedelta(seconds=200)
        )
        code, body, _ = make_request(
            '/health', inverter_reachable=False
        )
        assert code == 200
        assert body['detail'] == 'inverter_offline'

    def test_never_scraped_inverter_off(self):
        """No scrape age reported when inverter is off."""
        code, body, _ = make_request(
            '/health', inverter_reachable=False
        )
        assert code == 200
        assert body['last_scrape_age_seconds'] is None


class TestHealthFreshData:
    """Inverter on, data fresh - 200."""

    def test_returns_200_when_data_is_fresh(self):
        """Recent scrape returns 200 with age."""
        export_webserver.last_successful_scrape = datetime.now()
        code, body, _ = make_request(
            '/health', inverter_reachable=True
        )
        assert code == 200
        assert body['detail'] == 'fresh'
        assert body['inverter_reachable'] is True
        assert body['last_scrape_age_seconds'] < 2.0

    def test_returns_200_just_below_threshold(self):
        """Scrape just under 3x threshold returns 200."""
        export_webserver.last_successful_scrape = (
            datetime.now() - timedelta(seconds=89)
        )
        code, body, _ = make_request(
            '/health', inverter_reachable=True
        )
        assert code == 200
        assert body['detail'] == 'fresh'


class TestHealthStaleData:
    """Inverter on, data stale - 503 (restart me)."""

    def test_returns_503_when_stale(self):
        """Stale scrape with reachable inverter returns 503."""
        export_webserver.last_successful_scrape = (
            datetime.now() - timedelta(seconds=200)
        )
        code, body, _ = make_request(
            '/health', inverter_reachable=True
        )
        assert code == 503
        assert body['status'] == 'stale'
        assert body['detail'] == 'scrape_failing'
        assert body['last_scrape_age_seconds'] >= 199.0

    def test_returns_503_just_past_boundary(self):
        """Scrape just over 3x threshold returns 503."""
        export_webserver.last_successful_scrape = (
            datetime.now() - timedelta(seconds=91)
        )
        code, body, _ = make_request(
            '/health', inverter_reachable=True
        )
        assert code == 503
        assert body['detail'] == 'scrape_failing'


class TestHealthConnectedNeverScraped:
    """Inverter on but never scraped (morning issue) - 503."""

    def test_reachable_but_never_scraped(self):
        """Reachable inverter with no scrape returns 503."""
        code, body, _ = make_request(
            '/health', inverter_reachable=True
        )
        assert code == 503
        assert body['detail'] == 'connected_not_scraping'
        assert body['inverter_reachable'] is True


class TestHealthNotConfigured:
    """Host not set - 503 with not_configured detail."""

    def test_host_none_returns_503(self):
        """Missing host config returns 503 error."""
        export_webserver.inverter_host = None
        code, body, _ = make_request(
            '/health', inverter_reachable=False
        )
        assert code == 503
        assert body['detail'] == 'not_configured'
        assert body['status'] == 'error'


class TestHealthContentType:
    """Verify response headers."""

    def test_health_returns_json_content_type(self):
        """Health endpoint sets application/json."""
        _, _, handler = make_request(
            '/health', inverter_reachable=False
        )
        handler.send_header.assert_any_call(
            "Content-type", "application/json"
        )


class TestCheckInverterReachable:
    """Unit tests for TCP reachability check."""

    def test_reachable(self):
        """Returns True when TCP connect succeeds."""
        with patch(
            'exports.webserver.socket.create_connection'
        ) as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock()
            assert check_inverter_reachable(
                '192.168.1.100', 502
            ) is True

    def test_unreachable(self):
        """Returns False when connection is refused."""
        with patch(
            'exports.webserver.socket.create_connection',
            side_effect=OSError,
        ):
            assert check_inverter_reachable(
                '192.168.1.100', 502
            ) is False

    def test_timeout(self):
        """Returns False on connection timeout."""
        with patch(
            'exports.webserver.socket.create_connection',
            side_effect=TimeoutError,
        ):
            assert check_inverter_reachable(
                '192.168.1.100', 502
            ) is False


class TestPublishUpdatesTimestamp:
    """Verify publish() updates scrape timestamp."""

    def test_publish_sets_last_successful_scrape(self):
        """publish() records current time."""
        wserver = export_webserver()
        inverter = MagicMock()
        inverter.latest_scrape = {'test_register': 100}
        inverter.getRegisterAddress.return_value = '5000'
        inverter.getRegisterUnit.return_value = 'W'
        inverter.client_config = {}
        inverter.inverter_config = {}
        wserver.publish(inverter)
        assert export_webserver.last_successful_scrape is not None
        age = (
            datetime.now() - export_webserver.last_successful_scrape
        )
        assert age.total_seconds() < 2


class TestConfigureStoresInverterInfo:
    """Verify configure() stores inverter connection details."""

    def test_configure_stores_scan_interval_and_host(self):
        """Modbus mode stores config port."""
        wserver = export_webserver()
        inverter = MagicMock()
        inverter.inverter_config = {
            'scan_interval': 60,
            'connection': 'modbus',
        }
        inverter.client_config = {
            'host': '10.0.0.1', 'port': 502
        }
        config = {
            'port': 8099, 'enabled': True, 'name': 'webserver'
        }
        with patch('exports.webserver.HTTPServer'):
            with patch('exports.webserver.Thread'):
                wserver.configure(config, inverter)
        assert export_webserver.scan_interval == 60
        assert export_webserver.inverter_host == '10.0.0.1'
        assert export_webserver.inverter_port == 502

    def test_configure_http_mode_uses_port_8082(self):
        """HTTP mode overrides port to 8082."""
        wserver = export_webserver()
        inverter = MagicMock()
        inverter.inverter_config = {
            'scan_interval': 30,
            'connection': 'http',
        }
        inverter.client_config = {
            'host': '10.0.0.1', 'port': 502
        }
        config = {
            'port': 8099, 'enabled': True, 'name': 'webserver'
        }
        with patch('exports.webserver.HTTPServer'):
            with patch('exports.webserver.Thread'):
                wserver.configure(config, inverter)
        assert export_webserver.inverter_port == 8082

    def test_configure_sungrow_mode_uses_config_port(self):
        """Sungrow mode uses the configured port."""
        wserver = export_webserver()
        inverter = MagicMock()
        inverter.inverter_config = {
            'scan_interval': 30,
            'connection': 'sungrow',
        }
        inverter.client_config = {
            'host': '10.0.0.1', 'port': 502
        }
        config = {
            'port': 8099, 'enabled': True, 'name': 'webserver'
        }
        with patch('exports.webserver.HTTPServer'):
            with patch('exports.webserver.Thread'):
                wserver.configure(config, inverter)
        assert export_webserver.inverter_port == 502
