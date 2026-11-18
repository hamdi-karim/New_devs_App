import os
import socket

import pytest

DB_HOST = os.getenv("TEST_DB_HOST", "localhost")
DB_PORT = int(os.getenv("TEST_DB_PORT", "5433"))


def _db_reachable() -> bool:
    try:
        with socket.create_connection((DB_HOST, DB_PORT), timeout=0.5):
            return True
    except OSError:
        return False


def pytest_collection_modifyitems(config, items):
    """Skip `db`-marked tests (visibly) when the Docker Postgres isn't up."""
    db_items = [item for item in items if "db" in item.keywords]
    if not db_items or _db_reachable():
        return
    skip_db = pytest.mark.skip(
        reason=f"Postgres on {DB_HOST}:{DB_PORT} not reachable (docker-compose up db)"
    )
    for item in db_items:
        item.add_marker(skip_db)
