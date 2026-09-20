import os

import pytest

from coldchain.infrastructure.database import Database


@pytest.mark.integration
async def test_postgres_connectivity() -> None:
    url = os.getenv("COLDCHAIN_TEST_DATABASE_URL")
    if not url:
        pytest.skip("COLDCHAIN_TEST_DATABASE_URL is not configured")
    database = Database(url)
    try:
        await database.ping()
    finally:
        await database.dispose()
