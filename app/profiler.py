"""Column profiling and undeclared-defect discovery over the raw extracts.

Profiling is deliberately independent of the glossary's declared rules
(``app/gate.py`` is where declared rules get enforced). Everything below
is the kind of thing a profiler finds by looking at the data itself: a
column that behaves like an enumeration even though nothing declared it
as one, a numeric column whose magnitude jumps by a clean 100x for one
slice of records, a date column with two formats mixed together, a
"unique" key that is not, a foreign key with nothing on the other end,
and a date nobody sanity-checked against a plausible window.
"""

from __future__ import annotations

import re
from datetime import date

from app import glossary as g

ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
US_DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")

EARLIEST_PLAUSIBLE = date(2000, 1, 1)
TODAY = date(2026, 10, 1)

ENUM_MIN_DISTINCT = 2
ENUM_MAX_DISTINCT = 6
SCALE_RATIO_LOW = 50.0
SCALE_RATIO_HIGH = 200.0
SCALE_MIN_GROUP_SUPPORT = 10
GROUPING_MAX_DISTINCT = 10


def profile_columns(conn) -> list[dict]:
    """Per-(source, column) counts. One row per glossary column: 118 total."""
    profiles = []
    with conn.cursor() as cur:
        for source, cols in g.GLOSSARY.items():
            for col in cols:
                cur.execute(
                    f'SELECT COUNT(*), COUNT("{col.name}"), '
                    f'COUNT(DISTINCT "{col.name}") FROM raw_{source};'
                )
                total, non_null, distinct = cur.fetchone()
                profiles.append({
                    "source": source,
                    "column": col.name,
                    "declared_type": col.dtype,
                    "owner": col.owner,
                    "total_rows": total,
                    "null_count": total - non_null,
                    "distinct_count": distinct,
                })
    return profiles


def detect_implicit_enumerations(conn) -> list[dict]:
    findings = []
    with conn.cursor() as cur:
        for source, cols in g.GLOSSARY.items():
            for col in cols:
                if col.dtype != "text" or col.is_natural_key or col.fk or col.allowed_values:
                    continue
                cur.execute(
                    f'SELECT "{col.name}", COUNT(*) FROM raw_{source} '
                    f'WHERE "{col.name}" IS NOT NULL GROUP BY "{col.name}";'
                )
                rows = cur.fetchall()
                distinct = len(rows)
                if ENUM_MIN_DISTINCT <= distinct <= ENUM_MAX_DISTINCT:
                    values = sorted(v for v, _ in rows)
                    findings.append({
                        "type": "implicit_enumeration",
                        "source": source,
                        "column": col.name,
                        "detail": (
                            f'"{col.name}" in {source} takes only {distinct} distinct '
                            f"values ({', '.join(values)}) but no source has ever "
                            "declared it as a closed set in the glossary."
                        ),
                        "affected_count": sum(n for _, n in rows),
                    })
    return findings


def detect_currency_scale_changes(conn) -> list[dict]:
    findings = []
    with conn.cursor() as cur:
        for source, cols in g.GLOSSARY.items():
            float_cols = [c for c in cols if c.dtype == "float"]
            grouping_cols = [c for c in cols if c.dtype == "text" and not c.is_natural_key]
            for fcol in float_cols:
                for gcol in grouping_cols:
                    cur.execute(
                        f'SELECT "{gcol.name}", "{fcol.name}" FROM raw_{source} '
                        f'WHERE "{fcol.name}" IS NOT NULL AND "{gcol.name}" IS NOT NULL;'
                    )
                    rows = cur.fetchall()
                    by_group: dict[str, list[float]] = {}
                    for group_val, raw_val in rows:
                        try:
                            v = abs(float(raw_val))
                        except ValueError:
                            continue
                        if v == 0:
                            continue
                        by_group.setdefault(group_val, []).append(v)
                    if len(by_group) > GROUPING_MAX_DISTINCT or len(by_group) < 2:
                        continue
                    medians = {}
                    for gval, vals in by_group.items():
                        if len(vals) < SCALE_MIN_GROUP_SUPPORT:
                            continue
                        vals.sort()
                        medians[gval] = vals[len(vals) // 2]
                    if len(medians) < 2:
                        continue
                    lo_group = min(medians, key=lambda k: medians[k])
                    hi_group = max(medians, key=lambda k: medians[k])
                    if lo_group == hi_group or medians[lo_group] == 0:
                        continue
                    ratio = medians[hi_group] / medians[lo_group]
                    if SCALE_RATIO_LOW <= ratio <= SCALE_RATIO_HIGH:
                        findings.append({
                            "type": "currency_scale_change",
                            "source": source,
                            "column": fcol.name,
                            "detail": (
                                f'"{fcol.name}" in {source} has a median magnitude of '
                                f'{medians[hi_group]:,.2f} for {gcol.name}={hi_group!r} '
                                f'vs {medians[lo_group]:,.2f} for {gcol.name}={lo_group!r}, '
                                f"a {ratio:.1f}x gap consistent with a silent unit-scale change, "
                                "not natural variation."
                            ),
                            "affected_count": len(by_group[hi_group]),
                        })
    return findings


def detect_mixed_date_formats(conn) -> list[dict]:
    findings = []
    with conn.cursor() as cur:
        for source, cols in g.GLOSSARY.items():
            for col in cols:
                if col.dtype != "date":
                    continue
                cur.execute(f'SELECT "{col.name}" FROM raw_{source} WHERE "{col.name}" IS NOT NULL;')
                values = [r[0] for r in cur.fetchall()]
                iso_count = sum(1 for v in values if ISO_DATE_RE.match(v))
                us_count = sum(1 for v in values if US_DATE_RE.match(v))
                if iso_count > 0 and us_count > 0:
                    findings.append({
                        "type": "mixed_date_format",
                        "source": source,
                        "column": col.name,
                        "detail": (
                            f'"{col.name}" in {source} mixes {iso_count} ISO-format '
                            f"(YYYY-MM-DD) dates with {us_count} US-format (MM/DD/YYYY) "
                            "dates in the same column, with no flag distinguishing them."
                        ),
                        "affected_count": us_count,
                    })
    return findings


def detect_duplicate_natural_keys(conn) -> list[dict]:
    findings = []
    with conn.cursor() as cur:
        for source, cols in g.GLOSSARY.items():
            key_col = g.natural_key(source)
            cur.execute(
                f'SELECT "{key_col}", COUNT(*) FROM raw_{source} '
                f'GROUP BY "{key_col}" HAVING COUNT(*) > 1;'
            )
            rows = cur.fetchall()
            if rows:
                findings.append({
                    "type": "duplicate_natural_key",
                    "source": source,
                    "column": key_col,
                    "detail": (
                        f'"{key_col}" is declared as the natural key of {source} but '
                        f"{len(rows)} value(s) appear on more than one row "
                        f"({sum(n for _, n in rows)} rows total)."
                    ),
                    "affected_count": sum(n for _, n in rows),
                })
    return findings


def detect_orphan_foreign_keys(conn) -> list[dict]:
    findings = []
    with conn.cursor() as cur:
        for source, cols in g.GLOSSARY.items():
            for col in cols:
                if not col.fk:
                    continue
                ref_source, ref_col = col.fk
                cur.execute(
                    f'SELECT COUNT(*) FROM raw_{source} s '
                    f'LEFT JOIN raw_{ref_source} r ON s."{col.name}" = r."{ref_col}" '
                    f'WHERE s."{col.name}" IS NOT NULL AND r."{ref_col}" IS NULL;'
                )
                (orphan_count,) = cur.fetchone()
                if orphan_count > 0:
                    findings.append({
                        "type": "orphan_foreign_key",
                        "source": source,
                        "column": col.name,
                        "detail": (
                            f'{orphan_count} row(s) in {source}."{col.name}" reference a '
                            f"{ref_source}.{ref_col} value that does not exist in this pull."
                        ),
                        "affected_count": orphan_count,
                    })
    return findings


def detect_implausible_values(conn) -> list[dict]:
    findings = []
    with conn.cursor() as cur:
        cur.execute(
            'SELECT account_id, account_open_date FROM raw_accounts '
            'WHERE account_open_date IS NOT NULL;'
        )
        bad = []
        for account_id, raw in cur.fetchall():
            try:
                d = date.fromisoformat(raw)
            except ValueError:
                bad.append((account_id, raw))
                continue
            if d < EARLIEST_PLAUSIBLE or d > TODAY:
                bad.append((account_id, raw))
        if bad:
            findings.append({
                "type": "implausible_value",
                "source": "accounts",
                "column": "account_open_date",
                "detail": (
                    f"{len(bad)} account(s) have account_open_date outside the "
                    f"plausible {EARLIEST_PLAUSIBLE.isoformat()} to {TODAY.isoformat()} "
                    "window (the firm's systems window), with no source rejecting them: "
                    + ", ".join(f"{aid}={raw}" for aid, raw in bad)
                ),
                "affected_count": len(bad),
            })
    return findings


def run_profiling(conn) -> dict:
    column_profiles = profile_columns(conn)
    findings = (
        detect_implicit_enumerations(conn)
        + detect_currency_scale_changes(conn)
        + detect_mixed_date_formats(conn)
        + detect_duplicate_natural_keys(conn)
        + detect_orphan_foreign_keys(conn)
        + detect_implausible_values(conn)
    )
    return {
        "total_columns_profiled": len(column_profiles),
        "sources_profiled": len(g.GLOSSARY),
        "column_profiles": column_profiles,
        "findings": findings,
    }
