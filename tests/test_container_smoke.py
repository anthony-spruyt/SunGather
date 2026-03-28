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
        check=False,
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
@pytest.mark.skipif(
    not _inverter_reachable(),
    reason=f'Inverter not reachable at {INVERTER_HOST}:{INVERTER_PORT}'
)
class TestContainerSmoke:
    """Smoke test: build prod image, run --runonce, assert clean exit with data."""

    @classmethod
    def setup_class(cls):
        """Build the production Docker image and run one scrape cycle."""
        build = subprocess.run(
            ['docker', 'build', '-t', IMAGE_TAG, '.'],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=300,
            check=False,
        )
        assert build.returncode == 0, (
            f"Docker build failed:\nstdout: {build.stdout}\nstderr: {build.stderr}"
        )

        cls.result = subprocess.run(
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
            check=False,
        )
        cls.combined_output = cls.result.stdout + cls.result.stderr

    def test_exits_cleanly(self):
        """Container should exit 0 after one scrape cycle."""
        assert self.result.returncode == 0, (
            f"Container exited with code {self.result.returncode}:\n"
            f"{self.combined_output}"
        )

    def test_no_tracebacks(self):
        """Container output should not contain Python tracebacks."""
        assert 'Traceback' not in self.combined_output, (
            f"Traceback found in container output:\n{self.combined_output}"
        )

    def test_scrape_succeeded(self):
        """Container should have scraped registers and logged them to console."""
        has_logged = 'Logged' in self.combined_output
        has_registers = 'registers to Console' in self.combined_output
        assert has_logged and has_registers, (
            f"No evidence of successful scrape in output:\n{self.combined_output}"
        )
