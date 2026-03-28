from datetime import datetime, timedelta
from http.server import HTTPServer
from io import BytesIO
from unittest.mock import patch, MagicMock
import json
import pytest

from exports.webserver import export_webserver, MyServer


@pytest.fixture(autouse=True)
def reset_webserver_state():
    """Reset class-level state before each test to prevent leakage."""
    export_webserver.last_successful_scrape = None
    export_webserver.scan_interval = 30


def make_request(path):
    """Create a mock GET request to MyServer and capture the response."""
    server = MagicMock(spec=HTTPServer)
    request = MagicMock()
    request.makefile.return_value = BytesIO()

    handler = MyServer.__new__(MyServer)
    handler.server = server
    handler.path = path
    handler.headers = {}
    handler.requestline = f'GET {path} HTTP/1.1'
    handler.request_version = 'HTTP/1.1'
    handler.command = 'GET'

    # Capture response
    response_code = None

    def capture_response(code, message=None):
        nonlocal response_code
        response_code = code

    handler.send_response = capture_response
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()
    handler.wfile = BytesIO()

    handler.do_GET()

    # Parse JSON body from wfile
    handler.wfile.seek(0)
    raw = handler.wfile.read()
    body = json.loads(raw) if raw else None

    return response_code, body, handler


class TestHealthEndpointNeverScraped:
    def test_returns_200_when_never_scraped(self):
        """Before any scrape, /health should return 200 with null age."""
        code, body, _ = make_request('/health')
        assert code == 200
        assert body['status'] == 'ok'
        assert body['last_scrape_age_seconds'] is None
        assert body['threshold_seconds'] == 90


class TestHealthEndpointFreshData:
    def test_returns_200_when_data_is_fresh(self):
        """/health should return 200 with age when last scrape is recent."""
        export_webserver.last_successful_scrape = datetime.now()
        code, body, _ = make_request('/health')
        assert code == 200
        assert body['status'] == 'ok'
        assert body['last_scrape_age_seconds'] < 2.0
        assert body['threshold_seconds'] == 90


class TestHealthEndpointStaleData:
    def test_returns_503_when_data_is_stale(self):
        """/health should return 503 with stale status when too old."""
        export_webserver.last_successful_scrape = (
            datetime.now() - timedelta(seconds=200)
        )
        code, body, _ = make_request('/health')
        assert code == 503
        assert body['status'] == 'stale'
        assert body['last_scrape_age_seconds'] >= 199.0
        assert body['threshold_seconds'] == 90


class TestHealthEndpointEdgeCases:
    def test_returns_200_just_below_threshold(self):
        """/health should return 200 when just below the 3x threshold."""
        export_webserver.last_successful_scrape = (
            datetime.now() - timedelta(seconds=89)
        )
        code, body, _ = make_request('/health')
        assert code == 200
        assert body['status'] == 'ok'
        assert body['threshold_seconds'] == 90

    def test_returns_503_just_past_boundary(self):
        """/health should return 503 just past the threshold."""
        export_webserver.last_successful_scrape = (
            datetime.now() - timedelta(seconds=91)
        )
        code, body, _ = make_request('/health')
        assert code == 503
        assert body['status'] == 'stale'
        assert body['threshold_seconds'] == 90


class TestHealthEndpointContentType:
    def test_health_returns_json_content_type(self):
        """/health should set Content-Type: application/json."""
        _, _, handler = make_request('/health')
        handler.send_header.assert_any_call("Content-type", "application/json")


class TestPublishUpdatesTimestamp:
    def test_publish_sets_last_successful_scrape(self):
        """publish() should update last_successful_scrape timestamp."""
        export_webserver.last_successful_scrape = None
        ws = export_webserver()

        inverter = MagicMock()
        inverter.latest_scrape = {'test_register': 100}
        inverter.getRegisterAddress.return_value = '5000'
        inverter.getRegisterUnit.return_value = 'W'
        inverter.client_config = {}
        inverter.inverter_config = {}

        ws.publish(inverter)

        assert export_webserver.last_successful_scrape is not None
        age = (datetime.now() - export_webserver.last_successful_scrape)
        assert age.total_seconds() < 2


class TestConfigureStoresScanInterval:
    def test_configure_stores_scan_interval(self):
        """configure() should store scan_interval from inverter config."""
        export_webserver.scan_interval = 30  # default
        ws = export_webserver()

        inverter = MagicMock()
        inverter.inverter_config = {'scan_interval': 60}
        inverter.client_config = {}
        config = {'port': 8099, 'enabled': True, 'name': 'webserver'}

        with patch('exports.webserver.HTTPServer'):
            with patch('exports.webserver.Thread'):
                ws.configure(config, inverter)

        assert export_webserver.scan_interval == 60
