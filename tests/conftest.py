"""Fixtures for Pocket Money Tracker tests."""
import pytest
import pytest_socket

pytest_plugins = "pytest_homeassistant_custom_component"

# pytest-homeassistant-custom-component calls
# pytest_socket.disable_socket(allow_unix_socket=True) before every test,
# assuming asyncio's internal self-pipe uses a real Unix socket (true on
# Linux/macOS). On Windows, socket.socketpair() falls back to a loopback
# AF_INET pair, which isn't a Unix socket, so the guard blocks event-loop
# creation itself before any test code runs. None of these tests do real
# network I/O, so neutralizing the guard at import time (before that hook
# ever fires) is safe.
pytest_socket.disable_socket = lambda *args, **kwargs: None


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield
