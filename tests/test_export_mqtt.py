"""BDD tests for the mqtt export module."""
import sys
from unittest.mock import MagicMock, patch


def make_inverter(**overrides):
    inv = MagicMock()
    inv.client_config = {'host': '192.168.1.1', 'port': 502}
    inv.inverter_config = {'model': 'SG10KTL', 'serial_number': 'TEST123'}
    inv.latest_scrape = {'total_active_power': 5000, 'daily_power_yields': 10.5}
    inv.getInverterModel.return_value = 'SG10KTL'
    inv.getSerialNumber.return_value = 'TEST123'
    inv.getHost.return_value = '192.168.1.1'
    inv.validateRegister.return_value = True
    inv.validateLatestScrape.return_value = True
    inv.getRegisterValue.side_effect = lambda r: inv.latest_scrape.get(r, 0)
    inv.getRegisterAddress.return_value = 5000
    inv.getRegisterUnit.return_value = 'W'
    for k, v in overrides.items():
        setattr(inv, k, v)
    return inv


def _fresh_mqtt_export():
    """Remove cached mqtt export module to allow re-import with different mocks."""
    for key in list(sys.modules.keys()):
        if key in ('exports.mqtt', 'paho', 'paho.mqtt', 'paho.mqtt.client'):
            del sys.modules[key]


def _patched_mqtt_modules():
    """Return a patch.dict context and a way to get the mock client module."""
    mock_paho = MagicMock()
    mock_paho_mqtt = MagicMock()
    # Configure publish result with .mid
    publish_result = MagicMock()
    publish_result.mid = 1
    mock_paho_mqtt.client.Client.return_value.publish.return_value = publish_result
    mock_paho_mqtt.client.Client.return_value.is_connected.return_value = True
    return mock_paho, mock_paho_mqtt


VALID_CONFIG = {
    'host': 'localhost',
    'port': 1883,
}


class TestConfigure:
    def test_configure_returns_true_with_host(self):
        """configure() returns True when host is provided."""
        _fresh_mqtt_export()
        mock_paho, mock_paho_mqtt = _patched_mqtt_modules()
        with patch.dict(sys.modules, {
            'paho': mock_paho,
            'paho.mqtt': mock_paho_mqtt,
            'paho.mqtt.client': mock_paho_mqtt.client,
        }):
            from exports.mqtt import export_mqtt
            exporter = export_mqtt()
            inverter = make_inverter()
            result = exporter.configure(VALID_CONFIG, inverter)
            assert result is True

    def test_configure_returns_false_without_host(self):
        """configure() returns False when host is not provided."""
        _fresh_mqtt_export()
        mock_paho, mock_paho_mqtt = _patched_mqtt_modules()
        with patch.dict(sys.modules, {
            'paho': mock_paho,
            'paho.mqtt': mock_paho_mqtt,
            'paho.mqtt.client': mock_paho_mqtt.client,
        }):
            from exports.mqtt import export_mqtt
            exporter = export_mqtt()
            inverter = make_inverter()
            result = exporter.configure({}, inverter)
            assert result is False

    def test_configure_sets_auth_when_username_provided(self):
        """configure() calls username_pw_set when username and password are given."""
        _fresh_mqtt_export()
        mock_paho, mock_paho_mqtt = _patched_mqtt_modules()
        with patch.dict(sys.modules, {
            'paho': mock_paho,
            'paho.mqtt': mock_paho_mqtt,
            'paho.mqtt.client': mock_paho_mqtt.client,
        }):
            from exports.mqtt import export_mqtt
            exporter = export_mqtt()
            inverter = make_inverter()
            config = {**VALID_CONFIG, 'username': 'user', 'password': 'pass'}
            exporter.configure(config, inverter)
            # The mqtt_client is the instance returned by mqtt.Client() inside the module
            exporter.mqtt_client.username_pw_set.assert_called_once_with('user', 'pass')


class TestPublish:
    def test_publish_sends_register_values(self):
        """publish() calls mqtt_client.publish() with inverter data."""
        _fresh_mqtt_export()
        mock_paho, mock_paho_mqtt = _patched_mqtt_modules()
        with patch.dict(sys.modules, {
            'paho': mock_paho,
            'paho.mqtt': mock_paho_mqtt,
            'paho.mqtt.client': mock_paho_mqtt.client,
        }):
            from exports.mqtt import export_mqtt
            exporter = export_mqtt()
            inverter = make_inverter()
            exporter.configure(VALID_CONFIG, inverter)
            result = exporter.publish(inverter)
            assert result is True
            exporter.mqtt_client.publish.assert_called()
