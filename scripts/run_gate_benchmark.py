"""Runs the publish gate against 24 seeded violations and 20 clean loads.

    python scripts/run_gate_benchmark.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db, gate, generator, loader, violations


def main() -> int:
    if not db.is_reachable():
        print("PostgreSQL unreachable at the configured GWDP_PG_* settings; skipping.")
        return 0

    conn = db.connect()
    try:
        print("=== Governed Wealth Data Product -- publish gate benchmark ===")

        clean = generator.generate_clean_load(seed=100)
        mutated, expected = violations.inject_seeded_violations(clean, seed=555)
        loader.load(conn, mutated)
        holds = gate.validate(conn)
        hold_keys = {h.key(): h.reason for h in holds}

        caught = 0
        for source, column, record_id, reason in expected:
            got_reason = hold_keys.get((source, column, record_id))
            if got_reason == reason:
                caught += 1
            else:
                print(f"  MISSED: {source}.{column} record={record_id} expected={reason!r} got={got_reason!r}")

        unexpected = [h for h in holds if h.key() not in {(s, c, r) for s, c, r, _ in expected}]

        print()
        print("-- claim: 24 of 24 seeded violations caught by column and source record --")
        print(f"seeded violations caught: {caught} / {len(expected)}")
        print(f"unexpected holds on the seeded-violation load: {len(unexpected)}")
        for h in unexpected:
            print(f"  UNEXPECTED: {h.source}.{h.column} record={h.record_id} reason={h.reason!r}")

        false_holds_total = 0
        for i in range(20):
            clean_i = generator.generate_clean_load(seed=1000 + i)
            loader.load(conn, clean_i)
            holds_i = gate.validate(conn)
            false_holds_total += len(holds_i)
            if holds_i:
                print(f"  clean load seed={1000 + i} produced {len(holds_i)} false hold(s):")
                for h in holds_i:
                    print(f"    {h.source}.{h.column} record={h.record_id} reason={h.reason!r}")

        print()
        print("-- claim: 0 of 20 clean loads falsely held --")
        print(f"false holds across 20 independent clean loads: {false_holds_total}")

        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
