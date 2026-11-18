import socket

import pytest

from tests.conftest import DB_HOST, DB_PORT


@pytest.mark.db
def test_docker_postgres_port_is_open():
    """Placeholder proving the `db` marker; replaced by real DB tests in S6."""
    with socket.create_connection((DB_HOST, DB_PORT), timeout=0.5):
        pass
