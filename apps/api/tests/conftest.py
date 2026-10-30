from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from alembic import command


def _test_database_url() -> str | None:
    return os.getenv("WEAVE_TEST_DATABASE_URL")


@pytest.fixture(scope="session")
def postgres_engine() -> Iterator[Engine]:
    url = _test_database_url()
    if not url:
        pytest.skip("WEAVE_TEST_DATABASE_URL is not configured; PostgreSQL tests were not run")
    database_name = url.rsplit("/", 1)[-1].split("?", 1)[0]
    if not database_name.endswith("_test"):
        pytest.fail("WEAVE_TEST_DATABASE_URL database name must end in _test")

    engine = create_engine(url)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    try:
        command.upgrade(config, "head")
        yield engine
    finally:
        engine.dispose()
        cleanup_engine = create_engine(url)
        try:
            with cleanup_engine.begin() as connection:
                connection.execute(text("DROP SCHEMA public CASCADE"))
                connection.execute(text("CREATE SCHEMA public"))
        finally:
            cleanup_engine.dispose()
