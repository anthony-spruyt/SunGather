import os
import shutil
import socket
import subprocess

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CONFIG_PATH = os.path.join(REPO_ROOT, 'tests', 'fixtures', 'config-smoke.yaml')
IMAGE_TAG = 'sungather:smoke-test'
INVERTER_HOST = '192.168.30.95'
INVERTER_PORT = 502


def _docker_available():
    """Check Docker CLI exists and daemon is running."""
    if not shutil.which('docker'):
        return False
    result = subprocess.run(
        ['docker', 'info'],
        capture_output=True,
        timeout=10,
    )
    return result.returncode == 0


def _inverter_reachable():
    """Check if the inverter responds on its Modbus port."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3)
    try:
        return sock.connect_ex((INVERTER_HOST, INVERTER_PORT)) == 0
    finally:
        sock.close()


@pytest.mark.integration
@pytest.mark.skipif(not _docker_available(), reason='Docker not available')
@pytest.mark.skipif(not _inverter_reachable(), reason=f'Inverter not reachable at {INVERTER_HOST}:{INVERTER_PORT}')
class TestContainerSmoke:
    """Smoke test: build prod image, run --runonce, assert clean exit."""

    @classmethod
    def setup_class(cls):
        """Build the production Docker image once for all tests in this class."""
        result = subprocess.run(
            ['docker', 'build', '-t', IMAGE_TAG, '.'],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=300,
        )
        assert result.returncode == 0, (
            f"Docker build failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_runonce_exits_cleanly(self):
        """Container should complete one scrape cycle and exit 0."""
        result = subprocess.run(
            [
                'docker', 'run', '--rm', '--network', 'host',
                '-v', f'{CONFIG_PATH}:/config/config.yaml:ro',
                IMAGE_TAG,
                '/opt/virtualenv/bin/python', 'sungather.py',
                '-c', '/config/config.yaml', '--runonce',
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, (
            f"Container exited with code {result.returncode}:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_no_tracebacks_in_output(self):
        """Container output should not contain Python tracebacks."""
        result = subprocess.run(
            [
                'docker', 'run', '--rm', '--network', 'host',
                '-v', f'{CONFIG_PATH}:/config/config.yaml:ro',
                IMAGE_TAG,
                '/opt/virtualenv/bin/python', 'sungather.py',
                '-c', '/config/config.yaml', '--runonce',
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        combined = result.stdout + result.stderr
        assert 'Traceback' not in combined, (
            f"Traceback found in container output:\n{combined}"
        )
