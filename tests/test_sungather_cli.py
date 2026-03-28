import ast
import os


SUNGATHER_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'SunGather', 'sungather.py'
)


def _parse_sungather():
    with open(SUNGATHER_PATH) as f:
        return ast.parse(f.read())


def test_runonce_not_checked_via_locals():
    """runonce should be initialized, not checked via 'in locals()'."""
    with open(SUNGATHER_PATH) as f:
        source = f.read()
    assert "'runonce' in locals()" not in source, (
        "runonce is checked via 'in locals()' — initialize it at the top of main() instead"
    )


def test_loglevel_not_checked_via_locals():
    """loglevel should be initialized, not checked via 'in locals()'."""
    with open(SUNGATHER_PATH) as f:
        source = f.read()
    assert "'loglevel' in locals()" not in source, (
        "loglevel is checked via 'in locals()' — initialize it at the top of main() instead"
    )
