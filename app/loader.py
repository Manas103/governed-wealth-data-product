"""Loads generated extracts into PostgreSQL as an untyped text landing zone.

Every column is loaded as ``TEXT``, deliberately: these are extracts as
they actually arrive, before any type is enforced. ``app/profiler.py`` and
``app/gate.py`` are what apply the glossary's declared types, not the
table schema.
"""

from __future__ import annotations

from psycopg2.extras import execute_values

from app import glossary as g


def reset_schema(conn) -> None:
    with conn.cursor() as cur:
        for source, cols in g.GLOSSARY.items():
            cur.execute(f"DROP TABLE IF EXISTS raw_{source};")
            col_defs = ", ".join(f'"{c.name}" TEXT' for c in cols)
            cur.execute(f"CREATE TABLE raw_{source} ({col_defs});")
    conn.commit()


def load(conn, data: dict[str, list[dict]]) -> None:
    reset_schema(conn)
    with conn.cursor() as cur:
        for source, rows in data.items():
            if not rows:
                continue
            col_names = [c.name for c in g.GLOSSARY[source]]
            values = [[row.get(name) for name in col_names] for row in rows]
            col_list = ", ".join(f'"{c}"' for c in col_names)
            execute_values(
                cur,
                f'INSERT INTO raw_{source} ({col_list}) VALUES %s',
                values,
            )
    conn.commit()
