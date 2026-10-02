"""Profiles the 118-column raw pull and reports every undeclared defect found.

    python scripts/run_profiling.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db, generator, loader, profiler


def main() -> int:
    if not db.is_reachable():
        print("PostgreSQL unreachable at the configured GWDP_PG_* settings; skipping.")
        return 0

    conn = db.connect()
    try:
        data = generator.generate_raw_extracts(seed=1)
        loader.load(conn, data)
        report = profiler.run_profiling(conn)

        print("=== Governed Wealth Data Product -- profiling ===")
        print(f"sources profiled: {report['sources_profiled']}")
        print(f"columns profiled: {report['total_columns_profiled']}")
        print()
        print(f"-- claim: 118 columns profiled --")
        print(f"columns profiled: {report['total_columns_profiled']}")
        print()
        print(f"-- claim: 6 simulated retail-investment extracts --")
        for source in data:
            print(f"  {source}: {len(data[source])} rows")
        print()
        print(f"-- claim: 9 quality defects found that no source had declared --")
        print(f"defects found: {len(report['findings'])}")
        for finding in report["findings"]:
            print(f"  [{finding['type']}] {finding['source']}.{finding['column']}: {finding['detail']}")
        print()
        by_type: dict[str, int] = {}
        for finding in report["findings"]:
            by_type[finding["type"]] = by_type.get(finding["type"], 0) + 1
        print("-- claim: 3 implicit enumerations --")
        print(f"implicit enumerations found: {by_type.get('implicit_enumeration', 0)}")
        print()
        print("-- claim: 2 silent currency-scale changes --")
        print(f"currency scale changes found: {by_type.get('currency_scale_change', 0)}")
        print()
        print("other undeclared defects found:")
        for t in ("mixed_date_format", "duplicate_natural_key", "orphan_foreign_key", "implausible_value"):
            print(f"  {t}: {by_type.get(t, 0)}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
