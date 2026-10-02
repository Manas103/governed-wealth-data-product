import pytest

from app import db, generator, loader, profiler

pytestmark = pytest.mark.skipif(not db.is_reachable(), reason="PostgreSQL not reachable")


@pytest.fixture(scope="module")
def conn():
    connection = db.connect()
    yield connection
    connection.close()


def test_profiles_all_118_columns(conn):
    data = generator.generate_raw_extracts(seed=1)
    loader.load(conn, data)
    report = profiler.run_profiling(conn)
    assert report["total_columns_profiled"] == 118
    assert report["sources_profiled"] == 6


def test_finds_exactly_9_undeclared_defects(conn):
    data = generator.generate_raw_extracts(seed=1)
    loader.load(conn, data)
    report = profiler.run_profiling(conn)
    findings = report["findings"]
    assert len(findings) == 9

    by_type: dict[str, int] = {}
    for f in findings:
        by_type[f["type"]] = by_type.get(f["type"], 0) + 1

    assert by_type.get("implicit_enumeration", 0) == 3
    assert by_type.get("currency_scale_change", 0) == 2
    assert by_type.get("mixed_date_format", 0) == 1
    assert by_type.get("duplicate_natural_key", 0) == 1
    assert by_type.get("orphan_foreign_key", 0) == 1
    assert by_type.get("implausible_value", 0) == 1


def test_implicit_enumerations_are_the_three_undeclared_columns(conn):
    data = generator.generate_raw_extracts(seed=1)
    loader.load(conn, data)
    report = profiler.run_profiling(conn)
    enum_cols = {
        (f["source"], f["column"])
        for f in report["findings"] if f["type"] == "implicit_enumeration"
    }
    assert enum_cols == {
        ("accounts", "account_type"),
        ("positions", "asset_class"),
        ("advice_enrollments", "enrollment_channel"),
    }


def test_does_not_flag_declared_enum_columns(conn):
    data = generator.generate_raw_extracts(seed=1)
    loader.load(conn, data)
    findings = profiler.detect_implicit_enumerations(conn)
    flagged = {(f["source"], f["column"]) for f in findings}
    assert ("accounts", "account_status") not in flagged
