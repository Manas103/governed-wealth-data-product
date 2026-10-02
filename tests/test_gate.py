import pytest

from app import db, gate, generator, loader, violations

pytestmark = pytest.mark.skipif(not db.is_reachable(), reason="PostgreSQL not reachable")


@pytest.fixture(scope="module")
def conn():
    connection = db.connect()
    yield connection
    connection.close()


def test_catches_all_24_seeded_violations_by_column_and_record(conn):
    clean = generator.generate_clean_load(seed=100)
    mutated, expected = violations.inject_seeded_violations(clean, seed=555)
    loader.load(conn, mutated)
    holds = gate.validate(conn)
    hold_keys = {h.key(): h.reason for h in holds}

    for source, column, record_id, reason in expected:
        assert hold_keys.get((source, column, record_id)) == reason, (
            f"did not catch {source}.{column} record={record_id} as {reason!r}"
        )


def test_no_unexpected_holds_on_the_seeded_violation_load(conn):
    clean = generator.generate_clean_load(seed=100)
    mutated, expected = violations.inject_seeded_violations(clean, seed=555)
    loader.load(conn, mutated)
    holds = gate.validate(conn)
    expected_keys = {(s, c, r) for s, c, r, _ in expected}
    unexpected = [h for h in holds if h.key() not in expected_keys]
    assert unexpected == []


@pytest.mark.parametrize("seed", [2001, 2002, 2003, 2004, 2005])
def test_clean_loads_produce_zero_false_holds(conn, seed):
    clean = generator.generate_clean_load(seed=seed)
    loader.load(conn, clean)
    holds = gate.validate(conn)
    assert holds == []
