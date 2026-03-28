from datetime import datetime, timedelta
from http.server import HTTPServer
from io import BytesIO
from unittest.mock import patch, MagicMock
import pytest

from exports.webserver import export_webserver, MyServer


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
    original_send_response = MyServer.send_response

    def capture_response(self, code, message=None):
        nonlocal response_code
        response_code = code

    handler.send_response = lambda code, message=None: capture_response(
        handler, code, message
    )
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()
    handler.wfile = BytesIO()

    handler.do_GET()
    return response_code


class TestHealthEndpointNeverScraped:
    def test_returns_200_when_never_scraped(self):
        """Before any scrape, /health should return 200 (startup/night)."""
        export_webserver.last_successful_scrape = None
        export_webserver.scan_interval = 30
        code = make_request('/health')
        assert code == 200


class TestHealthEndpointFreshData:
    def test_returns_200_when_data_is_fresh(self):
        """/health should return 200 when last scrape is recent."""
        export_webserver.last_successful_scrape = datetime.now()
        export_webserver.scan_interval = 30
        code = make_request('/health')
        assert code == 200


class TestHealthEndpointStaleData:
    def test_returns_503_when_data_is_stale(self):
        """/health should return 503 when last scrape is too old."""
        export_webserver.last_successful_scrape = (
            datetime.now() - timedelta(seconds=200)
        )
        export_webserver.scan_interval = 30  # 3 * 30 = 90 seconds threshold
        code = make_request('/health')
        assert code == 503


class TestHealthEndpointEdgeCases:
    def test_returns_200_just_below_threshold(self):
        """/health should return 200 when just below the 3x threshold."""
        export_webserver.scan_interval = 30
        export_webserver.last_successful_scrape = (
            datetime.now() - timedelta(seconds=89)
        )
        code = make_request('/health')
        assert code == 200

    def test_returns_503_just_past_boundary(self):
        """/health should return 503 just past the threshold."""
        export_webserver.scan_interval = 30
        export_webserver.last_successful_scrape = (
            datetime.now() - timedelta(seconds=91)
        )
        code = make_request('/health')
        assert code == 503


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
