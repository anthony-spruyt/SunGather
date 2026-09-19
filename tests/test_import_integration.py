# pylint: disable=import-outside-toplevel
def test_vendored_client_exposes_expected_api():
    """Vendored client package should expose all required methods."""
    from client.sungrow_client import SungrowClient
    assert SungrowClient is not None
    assert hasattr(SungrowClient, 'checkConnection')
    assert hasattr(SungrowClient, 'scrape')
    assert hasattr(SungrowClient, 'connect')
    assert hasattr(SungrowClient, 'disconnect')


def test_sungather_calls_sungrow_client_as_class_not_module_attr():
    """sungather.py must call SungrowClient(config) directly.

    It must NOT call SungrowClient.SungrowClient(config).

    The import is 'from client.sungrow_client import SungrowClient' which gives
    us the class. Calling SungrowClient.SungrowClient() is an AttributeError.
    """
    import ast
    import os

    sungather_path = os.path.join(
        os.path.dirname(__file__), '..', 'SunGather', 'sungather.py'
    )
    with open(sungather_path, encoding='utf-8') as f:
        tree = ast.parse(f.read())

    # Find all attribute accesses of the form SungrowClient.SungrowClient
    bad_calls = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and node.attr == 'SungrowClient'
            and isinstance(node.value, ast.Name)
            and node.value.id == 'SungrowClient'
        ):
            bad_calls.append(node.lineno)

    assert not bad_calls, (
        f"sungather.py uses SungrowClient.SungrowClient on line(s) {bad_calls}. "
        f"SungrowClient is imported as a class, not a module — call it directly."
    )
