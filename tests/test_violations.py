from app import generator as gen
from app import violations as v


def test_exactly_24_seeded_violations():
    clean = gen.generate_clean_load(seed=100)
    mutated, expected = v.inject_seeded_violations(clean, seed=1)
    assert len(expected) == 24


def test_seeded_violation_keys_are_distinct():
    clean = gen.generate_clean_load(seed=100)
    mutated, expected = v.inject_seeded_violations(clean, seed=1)
    keys = [(s, c, r) for s, c, r, _ in expected]
    assert len(keys) == len(set(keys))


def test_deterministic_given_same_seed():
    clean = gen.generate_clean_load(seed=100)
    m1, e1 = v.inject_seeded_violations(clean, seed=42)
    m2, e2 = v.inject_seeded_violations(clean, seed=42)
    assert e1 == e2
    assert m1 == m2


def test_mutation_does_not_touch_the_original():
    clean = gen.generate_clean_load(seed=100)
    original_accounts_len = len(clean["accounts"])
    v.inject_seeded_violations(clean, seed=1)
    assert len(clean["accounts"]) == original_accounts_len


def test_every_source_contributes_four():
    clean = gen.generate_clean_load(seed=100)
    _, expected = v.inject_seeded_violations(clean, seed=1)
    counts: dict[str, int] = {}
    for source, _, _, _ in expected:
        counts[source] = counts.get(source, 0) + 1
    assert counts == {
        "accounts": 4, "positions": 4, "cash_activity": 4,
        "advice_enrollments": 4, "parties": 4, "fee_schedules": 4,
    }
