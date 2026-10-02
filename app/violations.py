"""Injects exactly 24 seeded violations into a copy of a clean load.

Four per source, cycling through the gate's rule families (a required
value gone missing, a value outside its declared allowed set, a value
outside its declared numeric range or a value that does not even parse
as its declared type, and either a dangling foreign key or a duplicated
natural key), so ``scripts/run_gate_benchmark.py`` exercises every family
the gate enforces, with an exactly known expected catch for each.

Duplicate-key violations are injected by *appending* a cloned row rather
than overwriting an existing one, specifically so that nothing else in
the load (a foreign key pointing at the row that would otherwise have
been overwritten) is disturbed as a side effect.
"""

from __future__ import annotations

import copy
import random

NONEXISTENT_ACCOUNT_ID = "ACCT-999999"


def _clone(data: dict[str, list[dict]]) -> dict[str, list[dict]]:
    return {source: [dict(row) for row in rows] for source, rows in data.items()}


def inject_seeded_violations(data: dict[str, list[dict]], seed: int = 555):
    """Returns (mutated_data, expected) where expected is a list of
    (source, column, record_id, reason) tuples, one per seeded violation."""
    rng = random.Random(seed)
    mutated = _clone(data)
    expected: list[tuple[str, str, str, str]] = []

    def pick(source: str, n: int) -> list[int]:
        return rng.sample(range(len(mutated[source])), n)

    # accounts: no foreign key of its own, so null / enum / range / duplicate.
    i_null, i_enum, i_range, i_dup = pick("accounts", 4)
    mutated["accounts"][i_null]["account_status"] = None
    expected.append(("accounts", "account_status", mutated["accounts"][i_null]["account_id"], "required value missing"))

    mutated["accounts"][i_enum]["tax_status"] = "RothIRA"
    expected.append(("accounts", "tax_status", mutated["accounts"][i_enum]["account_id"], "value outside declared allowed values"))

    mutated["accounts"][i_range]["risk_tolerance_score"] = "15"
    expected.append(("accounts", "risk_tolerance_score", mutated["accounts"][i_range]["account_id"], "value outside declared range"))

    dup_clone = dict(mutated["accounts"][i_dup])  # same account_id on purpose
    mutated["accounts"].append(dup_clone)
    expected.append(("accounts", "account_id", dup_clone["account_id"], "natural key not unique"))

    # positions: null / enum / range / orphan foreign key.
    i_null, i_enum, i_range, i_fk = pick("positions", 4)
    mutated["positions"][i_null]["quantity"] = None
    expected.append(("positions", "quantity", mutated["positions"][i_null]["position_id"], "required value missing"))

    mutated["positions"][i_enum]["security_type"] = "OPTION"
    expected.append(("positions", "security_type", mutated["positions"][i_enum]["position_id"], "value outside declared allowed values"))

    mutated["positions"][i_range]["quantity"] = "-5"
    expected.append(("positions", "quantity", mutated["positions"][i_range]["position_id"], "value outside declared range"))

    mutated["positions"][i_fk]["account_id"] = NONEXISTENT_ACCOUNT_ID
    expected.append(("positions", "account_id", mutated["positions"][i_fk]["position_id"], "foreign key does not reference an existing record"))

    # cash_activity: null / enum / unparseable value / orphan foreign key.
    i_null, i_enum, i_badtype, i_fk = pick("cash_activity", 4)
    mutated["cash_activity"][i_null]["activity_type"] = None
    expected.append(("cash_activity", "activity_type", mutated["cash_activity"][i_null]["activity_id"], "required value missing"))

    mutated["cash_activity"][i_enum]["channel"] = "CRYPTO"
    expected.append(("cash_activity", "channel", mutated["cash_activity"][i_enum]["activity_id"], "value outside declared allowed values"))

    mutated["cash_activity"][i_badtype]["amount"] = "N/A"
    expected.append(("cash_activity", "amount", mutated["cash_activity"][i_badtype]["activity_id"], "value does not parse as declared type"))

    mutated["cash_activity"][i_fk]["account_id"] = NONEXISTENT_ACCOUNT_ID
    expected.append(("cash_activity", "account_id", mutated["cash_activity"][i_fk]["activity_id"], "foreign key does not reference an existing record"))

    # advice_enrollments: null / enum / range / orphan foreign key.
    i_null, i_enum, i_range, i_fk = pick("advice_enrollments", 4)
    mutated["advice_enrollments"][i_null]["advice_program"] = None
    expected.append(("advice_enrollments", "advice_program", mutated["advice_enrollments"][i_null]["enrollment_id"], "required value missing"))

    mutated["advice_enrollments"][i_enum]["enrollment_status"] = "CANCELLED"
    expected.append(("advice_enrollments", "enrollment_status", mutated["advice_enrollments"][i_enum]["enrollment_id"], "value outside declared allowed values"))

    mutated["advice_enrollments"][i_range]["advice_fee_bps"] = "500"
    expected.append(("advice_enrollments", "advice_fee_bps", mutated["advice_enrollments"][i_range]["enrollment_id"], "value outside declared range"))

    mutated["advice_enrollments"][i_fk]["account_id"] = NONEXISTENT_ACCOUNT_ID
    expected.append(("advice_enrollments", "account_id", mutated["advice_enrollments"][i_fk]["enrollment_id"], "foreign key does not reference an existing record"))

    # parties: null / enum / duplicate / orphan foreign key.
    i_null, i_enum, i_dup, i_fk = pick("parties", 4)
    mutated["parties"][i_null]["relationship_type"] = None
    expected.append(("parties", "relationship_type", mutated["parties"][i_null]["party_id"], "required value missing"))

    mutated["parties"][i_enum]["kyc_status"] = "UNKNOWN"
    expected.append(("parties", "kyc_status", mutated["parties"][i_enum]["party_id"], "value outside declared allowed values"))

    dup_clone = dict(mutated["parties"][i_dup])
    mutated["parties"].append(dup_clone)
    expected.append(("parties", "party_id", dup_clone["party_id"], "natural key not unique"))

    mutated["parties"][i_fk]["account_id"] = NONEXISTENT_ACCOUNT_ID
    expected.append(("parties", "account_id", mutated["parties"][i_fk]["party_id"], "foreign key does not reference an existing record"))

    # fee_schedules: null / enum / range / orphan foreign key.
    i_null, i_enum, i_range, i_fk = pick("fee_schedules", 4)
    mutated["fee_schedules"][i_null]["fee_type"] = None
    expected.append(("fee_schedules", "fee_type", mutated["fee_schedules"][i_null]["fee_schedule_id"], "required value missing"))

    mutated["fee_schedules"][i_enum]["billing_frequency"] = "WEEKLY"
    expected.append(("fee_schedules", "billing_frequency", mutated["fee_schedules"][i_enum]["fee_schedule_id"], "value outside declared allowed values"))

    mutated["fee_schedules"][i_range]["annual_fee_amount"] = "-500.00"
    expected.append(("fee_schedules", "annual_fee_amount", mutated["fee_schedules"][i_range]["fee_schedule_id"], "value outside declared range"))

    mutated["fee_schedules"][i_fk]["account_id"] = NONEXISTENT_ACCOUNT_ID
    expected.append(("fee_schedules", "account_id", mutated["fee_schedules"][i_fk]["fee_schedule_id"], "foreign key does not reference an existing record"))

    assert len(expected) == 24, f"expected exactly 24 seeded violations, built {len(expected)}"
    return mutated, expected
