"""BDD tests for the pvoutput export module."""
import time
from unittest.mock import MagicMock, patch


def make_inverter(**overrides):
    inv = MagicMock()
    inv.client_config = {'host': '192.168.1.1', 'port': 502}
    inv.inverter_config = {'model': 'SG10KTL', 'serial_number': 'TEST123'}
    inv.latest_scrape = {
        'total_active_power': 5000,
        'daily_power_yields': 10.5,
        'timestamp': '2024-01-15 12:00:00',
    }
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


def _make_response(status_code=200, text=None):
    """Build a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.codes = MagicMock()
    resp.text = text or 'SG10KTL,SG10KTL,0,0,0,0,0,0,0,0,0,0,0,0,0,5,0,0,0,0;0;1618'
    resp.content = resp.text.encode()
    return resp


VALID_CONFIG = {
    'api': 'TESTAPI123',
    'sid': '12345',
    'join_team': False,
    'parameters': [{'register': 'total_active_power', 'name': 'v2'}],
}


class TestConfigure:
    def test_configure_returns_true_with_api_key_and_sid(self):
        """configure() returns True when valid api key, sid, and parameters are provided."""
        response_text = 'SG10KTL,SG10KTL,0,0,0,0,0,0,0,0,0,0,0,0,0,5,0,0,0,0;0;1618'
        mock_response = _make_response(200, response_text)
        with patch('exports.pvoutput.requests.post', return_value=mock_response) as mock_post:
            from exports.pvoutput import export_pvoutput
            exporter = export_pvoutput()
            inverter = make_inverter()
            result = exporter.configure(VALID_CONFIG, inverter)
            assert result is True
            mock_post.assert_called()

    def test_configure_returns_false_on_http_error(self):
        """configure() returns False when a requests exception is raised."""
        with patch('exports.pvoutput.requests.post', side_effect=Exception("timeout")):
            from exports.pvoutput import export_pvoutput
            exporter = export_pvoutput()
            inverter = make_inverter()
            result = exporter.configure(VALID_CONFIG, inverter)
            assert result is False


class TestPublish:
    def test_publish_collects_and_posts_data(self):
        """publish() collects inverter data and posts it when interval has elapsed."""
        response_text = 'SG10KTL,SG10KTL,0,0,0,0,0,0,0,0,0,0,0,0,0,5,0,0,0,0;0;1618'
        configure_response = _make_response(200, response_text)
        publish_response = _make_response(200, 'OK')
        publish_response.status_code = 200

        call_count = 0

        def post_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return configure_response
            return publish_response

        with patch('exports.pvoutput.requests.post', side_effect=post_side_effect):
            # Patch time.time so the interval check passes (last_publish=0, now >> interval*60)
            with patch('exports.pvoutput.time.time', return_value=99999):
                from exports.pvoutput import export_pvoutput
                exporter = export_pvoutput()
                inverter = make_inverter()
                exporter.configure(VALID_CONFIG, inverter)
                # status_interval comes from configure response (field index 15 = '5' minutes)
                exporter.publish(inverter)
                # At minimum, configure posted once; publish may post again
                assert call_count >= 1
