def test_vendored_client_exposes_expected_api():
    """Vendored client package should expose all required methods."""
    from client.sungrow_client import SungrowClient
    assert SungrowClient is not None
    assert hasattr(SungrowClient, 'checkConnection')
    assert hasattr(SungrowClient, 'scrape')
    assert hasattr(SungrowClient, 'connect')
    assert hasattr(SungrowClient, 'disconnect')
