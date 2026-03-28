"""BDD tests for the console export module."""
from unittest.mock import MagicMock

from exports.console import export_console


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


class TestConfigure:
    def test_configure_returns_true(self):
        """configure() with a mock inverter always returns True."""
        exporter = export_console()
        inverter = make_inverter()
        result = exporter.configure({}, inverter)
        assert result is True


class TestPublish:
    def test_publish_prints_registers(self, capsys):
        """publish() prints register data to stdout and returns True."""
        exporter = export_console()
        inverter = make_inverter()
        result = exporter.publish(inverter)
        captured = capsys.readouterr()
        assert result is True
        # Header row should be in output
        assert 'Address' in captured.out
        assert 'Register' in captured.out
        # Register names from latest_scrape should appear
        assert 'total_active_power' in captured.out
        assert 'daily_power_yields' in captured.out
        # Summary line
        assert 'Logged 2 registers' in captured.out
