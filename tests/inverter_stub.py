"""Stub inverter shared by the export module tests."""
from unittest.mock import MagicMock


def make_inverter(**overrides):
    inv = MagicMock()
    inv.client_config = {'host': '192.0.2.1', 'port': 502}
    inv.inverter_config = {'model': 'SG10KTL', 'serial_number': 'TEST123'}
    inv.latest_scrape = {'total_active_power': 5000, 'daily_power_yields': 10.5}
    inv.getInverterModel.return_value = 'SG10KTL'
    inv.getSerialNumber.return_value = 'TEST123'
    inv.getHost.return_value = '192.0.2.1'
    inv.validateRegister.return_value = True
    inv.validateLatestScrape.return_value = True
    inv.getRegisterValue.side_effect = lambda r: inv.latest_scrape.get(r, 0)
    inv.getRegisterAddress.return_value = 5000
    inv.getRegisterUnit.return_value = 'W'
    for k, v in overrides.items():
        setattr(inv, k, v)
    return inv
