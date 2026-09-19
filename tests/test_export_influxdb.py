"""BDD tests for the influxdb export module."""
# pylint: disable=import-outside-toplevel
import sys
from unittest.mock import MagicMock, patch

from tests.inverter_stub import make_inverter


def _make_influxdb_mock():
    """Return a mock influxdb_client module."""
    mock_module = MagicMock()
    mock_client_instance = MagicMock()
    mock_client_instance.url = 'http://localhost:8086'
    mock_client_instance.org = 'myorg'
    mock_write_api = MagicMock()
    mock_client_instance.write_api.return_value = mock_write_api
    mock_module.InfluxDBClient.return_value = mock_client_instance
    mock_module.Point = MagicMock(side_effect=lambda name: MagicMock())
    mock_module.client = MagicMock()
    mock_module.client.write_api = MagicMock()
    mock_module.client.write_api.SYNCHRONOUS = MagicMock()
    return mock_module, mock_client_instance, mock_write_api


VALID_CONFIG = {
    'url': 'http://localhost:8086',
    'token': 'mytoken',
    'org': 'myorg',
    'bucket': 'mybucket',
    'measurements': [{'register': 'total_active_power', 'point': 'power'}],
}


class TestConfigure:
    def test_configure_returns_false_without_required_fields(self):
        """configure() returns False when org, bucket, or token are missing."""
        # Patch influxdb_client before importing so the module-level import is mocked
        mock_module, _, _ = _make_influxdb_mock()
        with patch.dict(sys.modules, {
            'influxdb_client': mock_module,
            'influxdb_client.client': mock_module.client,
            'influxdb_client.client.write_api': mock_module.client.write_api,
        }):
            from exports.influxdb import export_influxdb
            exporter = export_influxdb()
            inverter = make_inverter()
            # No org, bucket, or token
            result = exporter.configure(
                {'url': 'http://localhost:8086', 'measurements': []}, inverter
            )
            assert result is False

    def test_configure_with_token_auth(self):
        """configure() returns True when valid config with token is provided."""
        mock_module, _, _ = _make_influxdb_mock()
        with patch.dict(sys.modules, {
            'influxdb_client': mock_module,
            'influxdb_client.client': mock_module.client,
            'influxdb_client.client.write_api': mock_module.client.write_api,
        }):
            from exports.influxdb import export_influxdb
            exporter = export_influxdb()
            inverter = make_inverter()
            result = exporter.configure(VALID_CONFIG, inverter)
            assert result is True
            mock_module.InfluxDBClient.assert_called_once()


class TestPublish:
    def _configured_exporter(self, mock_module):
        """Helper: return a configured exporter using the given mock module."""
        with patch.dict(sys.modules, {
            'influxdb_client': mock_module,
            'influxdb_client.client': mock_module.client,
            'influxdb_client.client.write_api': mock_module.client.write_api,
        }):
            from exports.influxdb import export_influxdb
            exporter = export_influxdb()
            inverter = make_inverter()
            exporter.configure(VALID_CONFIG, inverter)
            return exporter

    def test_publish_writes_point_sequence(self):
        """publish() calls write_api.write() with a sequence of Points."""
        mock_module, _mock_client_instance, mock_write_api = _make_influxdb_mock()
        with patch.dict(sys.modules, {
            'influxdb_client': mock_module,
            'influxdb_client.client': mock_module.client,
            'influxdb_client.client.write_api': mock_module.client.write_api,
        }):
            from exports.influxdb import export_influxdb
            exporter = export_influxdb()
            inverter = make_inverter()
            exporter.configure(VALID_CONFIG, inverter)
            result = exporter.publish(inverter)
            assert result is True
            mock_write_api.write.assert_called_once()

    def test_publish_handles_connection_error(self):
        """publish() catches write errors and still returns True."""
        mock_module, _mock_client_instance, mock_write_api = _make_influxdb_mock()
        mock_write_api.write.side_effect = Exception("connection refused")
        with patch.dict(sys.modules, {
            'influxdb_client': mock_module,
            'influxdb_client.client': mock_module.client,
            'influxdb_client.client.write_api': mock_module.client.write_api,
        }):
            from exports.influxdb import export_influxdb
            exporter = export_influxdb()
            inverter = make_inverter()
            exporter.configure(VALID_CONFIG, inverter)
            # Should not raise; exception is caught internally
            result = exporter.publish(inverter)
            assert result is True
