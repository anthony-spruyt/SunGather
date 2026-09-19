"""BDD tests for the console export module."""
from exports.console import export_console

from tests.inverter_stub import make_inverter


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
