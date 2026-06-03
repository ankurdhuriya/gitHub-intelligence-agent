"""LangGraph Postgres checkpointer for Neon (or any Postgres)."""

import os

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

_pool: AsyncConnectionPool | None = None
_checkpointer: AsyncPostgresSaver | None = None


def get_database_url() -> str:
    """Return Neon/Postgres connection URL from DATABASE_URL."""
    url = os.getenv("DATABASE_URL")
    if not url:
        raise ValueError(
            "Missing DATABASE_URL: set your Neon connection string in .env "
            "(Dashboard → Connection details → connection string)."
        )
    return url


async def create_checkpointer() -> AsyncPostgresSaver:
    """Open a connection pool, migrate checkpoint tables, return the checkpointer."""
    global _pool, _checkpointer

    if _checkpointer is not None:
        return _checkpointer

    _pool = AsyncConnectionPool(
        conninfo=get_database_url(),
        max_size=10,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        },
    )
    await _pool.open()

    _checkpointer = AsyncPostgresSaver(_pool)
    await _checkpointer.setup()
    return _checkpointer


async def close_checkpointer() -> None:
    """Close the pool and reset module state (e.g. on Streamlit session reset)."""
    global _pool, _checkpointer

    _checkpointer = None
    if _pool is not None:
        await _pool.close()
        _pool = None
