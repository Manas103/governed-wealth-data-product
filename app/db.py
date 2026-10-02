"""Connection helper for the local PostgreSQL instance used by this project.

PostgreSQL is not a managed service on this machine (see BUILDER.md section
3). This project's local stand-up, used for every number in the README, is
a PostgreSQL 14 instance inside WSL2 Ubuntu 22.04, reachable from native
Windows Python through WSL2's localhost port forwarding, database
``governed_wealth`` owned by role ``mvuser``. Override with the
``GWDP_PG_*`` environment variables if that instance is not reachable;
``connect()`` raises ``psycopg2.OperationalError`` in that case, which
every script and test below catches to skip cleanly rather than fail.
"""

from __future__ import annotations

import os

import psycopg2

DEFAULTS = {
    "host": "localhost",
    "port": "5432",
    "dbname": "governed_wealth",
    "user": "mvuser",
    "password": "mvpass",
}


def connect():
    kwargs = {
        "host": os.environ.get("GWDP_PG_HOST", DEFAULTS["host"]),
        "port": os.environ.get("GWDP_PG_PORT", DEFAULTS["port"]),
        "dbname": os.environ.get("GWDP_PG_DB", DEFAULTS["dbname"]),
        "user": os.environ.get("GWDP_PG_USER", DEFAULTS["user"]),
        "password": os.environ.get("GWDP_PG_PASSWORD", DEFAULTS["password"]),
    }
    return psycopg2.connect(**kwargs)


def is_reachable() -> bool:
    try:
        conn = connect()
    except psycopg2.OperationalError:
        return False
    conn.close()
    return True
