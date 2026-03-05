"""
tests/test_init_db.py
=====================

Integration tests for the database & cache initialisation script
(``scripts/init_db.sh``).

These tests verify:
    1. PostgreSQL is reachable and ``SELECT 1`` succeeds.
    2. The ``ai_crm`` database exists.
    3. The ``uuid-ossp`` and ``vector`` (pgvector) extensions are loaded.
    4. All core tables defined in ``contracts/db-schema.sql`` exist.
    5. Key indexes are present.
    6. The ``update_updated_at`` trigger function is installed.
    7. Redis responds to ``PING``.

Prerequisites
-------------
* PostgreSQL 16 and Redis 7 must be running locally (the init script
  should have been executed at least once).
* The ``psycopg2-binary`` and ``redis`` Python packages must be
  installed (see ``requirements.txt``).

Environment variables (optional overrides):
    PGUSER, PGHOST, PGPORT, DB_NAME, REDIS_HOST, REDIS_PORT
"""

from __future__ import annotations

import os
import subprocess

import pytest

# ---------------------------------------------------------------------------
# Configuration from environment (with sensible defaults)
# ---------------------------------------------------------------------------
PGUSER: str = os.getenv("PGUSER", os.getenv("USER", "postgres"))
PGHOST: str = os.getenv("PGHOST", "localhost")
PGPORT: int = int(os.getenv("PGPORT", "5432"))
DB_NAME: str = os.getenv("DB_NAME", "ai_crm")

REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))

# ---------------------------------------------------------------------------
# Expected schema artefacts (derived from contracts/db-schema.sql)
# ---------------------------------------------------------------------------
EXPECTED_TABLES: list[str] = [
    "users",
    "leads",
    "customers",
    "contacts",
    "opportunities",
    "activities",
    "audit_log",
    "agent_log",
]

EXPECTED_INDEXES: list[str] = [
    "idx_leads_company",
    "idx_leads_status",
    "idx_leads_owner",
    "idx_leads_created",
    "idx_customers_company",
    "idx_customers_level",
    "idx_customers_owner",
    "idx_contacts_customer",
    "idx_opp_customer",
    "idx_opp_stage",
    "idx_opp_owner",
    "idx_activities_customer",
    "idx_activities_opp",
    "idx_activities_created",
    "idx_audit_entity",
    "idx_audit_user",
    "idx_agent_log_session",
    "idx_agent_log_created",
]

EXPECTED_EXTENSIONS: list[str] = [
    "uuid-ossp",
    "vector",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def pg_conn():
    """Return a live ``psycopg2`` connection to the *ai_crm* database.

    The fixture is module-scoped so a single connection is reused across
    all PostgreSQL tests in this file.
    """
    psycopg2 = pytest.importorskip(
        "psycopg2",
        reason="psycopg2-binary is required for DB tests",
    )
    try:
        conn = psycopg2.connect(
            host=PGHOST,
            port=PGPORT,
            user=PGUSER,
            dbname=DB_NAME,
        )
    except psycopg2.OperationalError as exc:
        pytest.skip(f"Cannot connect to PostgreSQL: {exc}")
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def redis_client():
    """Return a live ``redis.Redis`` client.

    The fixture is module-scoped so a single connection is reused across
    all Redis tests in this file.
    """
    redis_mod = pytest.importorskip(
        "redis",
        reason="redis package is required for cache tests",
    )
    client = redis_mod.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
    try:
        client.ping()
    except redis_mod.ConnectionError as exc:
        pytest.skip(f"Cannot connect to Redis: {exc}")
    yield client
    client.close()


# ---------------------------------------------------------------------------
# PostgreSQL tests
# ---------------------------------------------------------------------------
class TestPostgreSQL:
    """Verify PostgreSQL connectivity and schema."""

    def test_select_one(self, pg_conn) -> None:
        """``SELECT 1`` must return 1 — basic connectivity proof."""
        with pg_conn.cursor() as cur:
            cur.execute("SELECT 1;")
            result = cur.fetchone()
        assert result is not None
        assert result[0] == 1

    def test_database_exists(self, pg_conn) -> None:
        """The target database must appear in ``pg_database``."""
        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s;",
                (DB_NAME,),
            )
            result = cur.fetchone()
        assert result is not None, f"Database '{DB_NAME}' does not exist"

    @pytest.mark.parametrize("ext", EXPECTED_EXTENSIONS)
    def test_extension_loaded(self, pg_conn, ext: str) -> None:
        """Required PG extensions must be installed."""
        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_extension WHERE extname = %s;",
                (ext,),
            )
            result = cur.fetchone()
        assert result is not None, f"Extension '{ext}' is not loaded"

    @pytest.mark.parametrize("table", EXPECTED_TABLES)
    def test_table_exists(self, pg_conn, table: str) -> None:
        """All core tables from the schema must exist."""
        with pg_conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                  FROM information_schema.tables
                 WHERE table_schema = 'public'
                   AND table_name = %s;
                """,
                (table,),
            )
            result = cur.fetchone()
        assert result is not None, f"Table '{table}' is missing"

    @pytest.mark.parametrize("index", EXPECTED_INDEXES)
    def test_index_exists(self, pg_conn, index: str) -> None:
        """Key indexes defined in the schema must be present."""
        with pg_conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                  FROM pg_indexes
                 WHERE schemaname = 'public'
                   AND indexname = %s;
                """,
                (index,),
            )
            result = cur.fetchone()
        assert result is not None, f"Index '{index}' is missing"

    def test_trigger_function_exists(self, pg_conn) -> None:
        """The ``update_updated_at()`` trigger function must be defined."""
        with pg_conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                  FROM pg_proc
                 WHERE proname = 'update_updated_at';
                """,
            )
            result = cur.fetchone()
        assert result is not None, "Trigger function 'update_updated_at' is missing"

    def test_leads_trigger_attached(self, pg_conn) -> None:
        """The ``trg_leads_updated`` trigger must be attached to *leads*."""
        with pg_conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                  FROM information_schema.triggers
                 WHERE trigger_name = 'trg_leads_updated'
                   AND event_object_table = 'leads';
                """,
            )
            result = cur.fetchone()
        assert result is not None, "Trigger 'trg_leads_updated' is not attached to 'leads'"

    def test_vector_column_on_customers(self, pg_conn) -> None:
        """The ``ai_embedding`` column on *customers* must be of type ``vector``."""
        with pg_conn.cursor() as cur:
            cur.execute(
                """
                SELECT data_type
                  FROM information_schema.columns
                 WHERE table_schema = 'public'
                   AND table_name = 'customers'
                   AND column_name = 'ai_embedding';
                """,
            )
            result = cur.fetchone()
        assert result is not None, "Column 'ai_embedding' not found on 'customers'"
        # pgvector registers as 'USER-DEFINED'
        assert result[0].upper() == "USER-DEFINED", (
            f"Expected USER-DEFINED (vector) type, got '{result[0]}'"
        )

    def test_audit_log_is_partitioned(self, pg_conn) -> None:
        """``audit_log`` should be a partitioned table."""
        with pg_conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.relkind
                  FROM pg_class c
                  JOIN pg_namespace n ON n.oid = c.relnamespace
                 WHERE n.nspname = 'public'
                   AND c.relname = 'audit_log';
                """,
            )
            result = cur.fetchone()
        assert result is not None, "audit_log not found in pg_class"
        # 'p' = partitioned table
        assert result[0] == "p", (
            f"Expected audit_log relkind='p' (partitioned), got '{result[0]}'"
        )


# ---------------------------------------------------------------------------
# Redis tests
# ---------------------------------------------------------------------------
class TestRedis:
    """Verify Redis connectivity."""

    def test_ping(self, redis_client) -> None:
        """``PING`` must return ``True`` (pong)."""
        assert redis_client.ping() is True

    def test_set_get(self, redis_client) -> None:
        """Basic SET / GET round-trip."""
        key = "__sirus_crm_test__"
        redis_client.set(key, "ok", ex=10)
        value = redis_client.get(key)
        assert value == b"ok"
        redis_client.delete(key)

    def test_redis_version(self, redis_client) -> None:
        """Redis server version should be 7.x."""
        info = redis_client.info("server")
        version: str = info.get("redis_version", "")
        assert version.startswith("7"), (
            f"Expected Redis 7.x, got '{version}'"
        )


# ---------------------------------------------------------------------------
# CLI smoke tests (subprocess)
# ---------------------------------------------------------------------------
class TestCLISmoke:
    """Run the acceptance-criteria commands via subprocess."""

    def test_psql_select_one(self) -> None:
        """``psql -c 'SELECT 1'`` must succeed."""
        result = subprocess.run(
            [
                "psql",
                "-h", PGHOST,
                "-p", str(PGPORT),
                "-U", PGUSER,
                "-d", DB_NAME,
                "-tAc", "SELECT 1;",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"psql failed: {result.stderr}"
        assert result.stdout.strip() == "1"

    def test_redis_cli_ping(self) -> None:
        """``redis-cli ping`` must return PONG."""
        result = subprocess.run(
            ["redis-cli", "-h", REDIS_HOST, "-p", str(REDIS_PORT), "ping"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"redis-cli failed: {result.stderr}"
        assert result.stdout.strip() == "PONG"
