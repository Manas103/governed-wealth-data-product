"""The publish gate: enforces every declared rule in ``app/glossary.py``.

Operates on whatever has most recently been loaded into the ``raw_<source>``
text tables by ``app/loader.py``. A load is held at (source, column,
record) granularity, named by the source's own natural key, not as an
all-or-nothing per-source decision: a column breaking its glossary
definition holds only the records that actually break it.
"""

from __future__ import annotations

from dataclasses import dataclass

from app import glossary as g

NUMERIC_RE = r'^-?\d+(\.\d+)?$'
DATE_RE = r'^\d{4}-\d{2}-\d{2}$'
BOOL_RE = r'^(true|false)$'


@dataclass(frozen=True)
class Hold:
    source: str
    column: str
    record_id: str
    reason: str

    def key(self) -> tuple:
        return (self.source, self.column, self.record_id)


def _required_holds(cur, source: str, key_col: str, col) -> list[Hold]:
    if col.nullable:
        return []
    cur.execute(f'SELECT "{key_col}" FROM raw_{source} WHERE "{col.name}" IS NULL;')
    return [Hold(source, col.name, r[0], "required value missing") for r in cur.fetchall()]


def _allowed_value_holds(cur, source: str, key_col: str, col) -> list[Hold]:
    if not col.allowed_values:
        return []
    placeholders = ", ".join(["%s"] * len(col.allowed_values))
    cur.execute(
        f'SELECT "{key_col}" FROM raw_{source} '
        f'WHERE "{col.name}" IS NOT NULL AND "{col.name}" NOT IN ({placeholders});',
        col.allowed_values,
    )
    return [Hold(source, col.name, r[0], "value outside declared allowed values") for r in cur.fetchall()]


def _numeric_holds(cur, source: str, key_col: str, col) -> list[Hold]:
    holds = []
    cur.execute(
        f'SELECT "{key_col}" FROM raw_{source} '
        f'WHERE "{col.name}" IS NOT NULL AND "{col.name}" !~ %s;',
        (NUMERIC_RE,),
    )
    holds += [Hold(source, col.name, r[0], "value does not parse as declared type") for r in cur.fetchall()]
    if col.min_value is not None and col.max_value is not None:
        cur.execute(
            f'SELECT "{key_col}" FROM raw_{source} '
            f'WHERE "{col.name}" IS NOT NULL AND "{col.name}" ~ %s '
            f'AND ("{col.name}"::numeric < %s OR "{col.name}"::numeric > %s);',
            (NUMERIC_RE, col.min_value, col.max_value),
        )
        holds += [Hold(source, col.name, r[0], "value outside declared range") for r in cur.fetchall()]
    elif col.min_value is not None:
        cur.execute(
            f'SELECT "{key_col}" FROM raw_{source} '
            f'WHERE "{col.name}" IS NOT NULL AND "{col.name}" ~ %s AND "{col.name}"::numeric < %s;',
            (NUMERIC_RE, col.min_value),
        )
        holds += [Hold(source, col.name, r[0], "value outside declared range") for r in cur.fetchall()]
    elif col.max_value is not None:
        cur.execute(
            f'SELECT "{key_col}" FROM raw_{source} '
            f'WHERE "{col.name}" IS NOT NULL AND "{col.name}" ~ %s AND "{col.name}"::numeric > %s;',
            (NUMERIC_RE, col.max_value),
        )
        holds += [Hold(source, col.name, r[0], "value outside declared range") for r in cur.fetchall()]
    return holds


def _date_holds(cur, source: str, key_col: str, col) -> list[Hold]:
    holds = []
    cur.execute(
        f'SELECT "{key_col}" FROM raw_{source} '
        f'WHERE "{col.name}" IS NOT NULL AND "{col.name}" !~ %s;',
        (DATE_RE,),
    )
    holds += [Hold(source, col.name, r[0], "date does not parse in declared format") for r in cur.fetchall()]
    if col.min_value is not None:
        cur.execute(
            f'SELECT "{key_col}" FROM raw_{source} '
            f'WHERE "{col.name}" IS NOT NULL AND "{col.name}" ~ %s AND "{col.name}" < %s;',
            (DATE_RE, col.min_value),
        )
        holds += [Hold(source, col.name, r[0], "date outside declared range") for r in cur.fetchall()]
    return holds


def _bool_holds(cur, source: str, key_col: str, col) -> list[Hold]:
    cur.execute(
        f'SELECT "{key_col}" FROM raw_{source} '
        f'WHERE "{col.name}" IS NOT NULL AND "{col.name}" !~* %s;',
        (BOOL_RE,),
    )
    return [Hold(source, col.name, r[0], "value does not parse as declared type") for r in cur.fetchall()]


def _natural_key_holds(cur, source: str, key_col: str) -> list[Hold]:
    cur.execute(
        f'SELECT "{key_col}" FROM raw_{source} '
        f'GROUP BY "{key_col}" HAVING COUNT(*) > 1;'
    )
    return [Hold(source, key_col, r[0], "natural key not unique") for r in cur.fetchall()]


def _fk_holds(cur, source: str, key_col: str, col) -> list[Hold]:
    ref_source, ref_col = col.fk
    cur.execute(
        f'SELECT s."{key_col}" FROM raw_{source} s '
        f'LEFT JOIN raw_{ref_source} r ON s."{col.name}" = r."{ref_col}" '
        f'WHERE s."{col.name}" IS NOT NULL AND r."{ref_col}" IS NULL;'
    )
    return [Hold(source, col.name, r[0], "foreign key does not reference an existing record") for r in cur.fetchall()]


def validate(conn) -> list[Hold]:
    holds: list[Hold] = []
    with conn.cursor() as cur:
        for source, cols in g.GLOSSARY.items():
            key_col = g.natural_key(source)
            holds += _natural_key_holds(cur, source, key_col)
            for col in cols:
                holds += _required_holds(cur, source, key_col, col)
                holds += _allowed_value_holds(cur, source, key_col, col)
                if col.dtype in ("int", "float"):
                    holds += _numeric_holds(cur, source, key_col, col)
                elif col.dtype == "date":
                    holds += _date_holds(cur, source, key_col, col)
                elif col.dtype == "bool":
                    holds += _bool_holds(cur, source, key_col, col)
                if col.fk:
                    holds += _fk_holds(cur, source, key_col, col)
    return holds
