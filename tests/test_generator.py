from datetime import date

from app import generator as gen
from app import glossary as g


def test_raw_extracts_deterministic():
    a = gen.generate_raw_extracts(seed=7)
    b = gen.generate_raw_extracts(seed=7)
    assert a == b


def test_clean_load_deterministic():
    a = gen.generate_clean_load(seed=7)
    b = gen.generate_clean_load(seed=7)
    assert a == b


def test_different_seeds_differ():
    a = gen.generate_clean_load(seed=1)
    b = gen.generate_clean_load(seed=2)
    assert a != b


def test_all_six_sources_present_and_nonempty():
    data = gen.generate_clean_load(seed=1)
    assert set(data) == set(g.GLOSSARY)
    for source, rows in data.items():
        assert len(rows) > 0, source


def test_every_row_has_every_glossary_column():
    data = gen.generate_clean_load(seed=1)
    for source, rows in data.items():
        col_names = {c.name for c in g.GLOSSARY[source]}
        for row in rows:
            assert set(row) == col_names


def test_clean_load_respects_required_allowed_values_and_ranges():
    data = gen.generate_clean_load(seed=3)
    for source, rows in data.items():
        for col in g.GLOSSARY[source]:
            for row in rows:
                value = row[col.name]
                if not col.nullable:
                    assert value is not None, f"{source}.{col.name} is required but null"
                if value is None:
                    continue
                if col.allowed_values:
                    assert value in col.allowed_values, f"{source}.{col.name}={value!r} not allowed"
                if col.dtype in ("int", "float"):
                    numeric = float(value)
                    if col.min_value is not None:
                        assert numeric >= col.min_value
                    if col.max_value is not None:
                        assert numeric <= col.max_value
                if col.dtype == "date":
                    d = date.fromisoformat(value)
                    if col.min_value is not None:
                        assert d >= date.fromisoformat(col.min_value)
                if col.dtype == "bool":
                    assert value in ("true", "false")


def test_clean_load_foreign_keys_resolve():
    data = gen.generate_clean_load(seed=4)
    account_ids = {row["account_id"] for row in data["accounts"]}
    for source, rows in data.items():
        for col in g.GLOSSARY[source]:
            if col.fk == ("accounts", "account_id"):
                for row in rows:
                    assert row[col.name] in account_ids


def test_clean_load_natural_keys_are_unique():
    data = gen.generate_clean_load(seed=5)
    for source, rows in data.items():
        key_col = g.natural_key(source)
        values = [row[key_col] for row in rows]
        assert len(values) == len(set(values)), f"{source}.{key_col} has duplicates"


def test_raw_extracts_contain_the_organic_defects():
    data = gen.generate_raw_extracts(seed=1)

    account_ids = {row["account_id"] for row in data["accounts"]}
    orphan_positions = [r for r in data["positions"] if r["account_id"] not in account_ids]
    assert len(orphan_positions) > 0

    party_ids = [row["party_id"] for row in data["parties"]]
    assert len(party_ids) != len(set(party_ids))

    us_format_dates = [
        r["enrollment_date"] for r in data["advice_enrollments"]
        if "/" in r["enrollment_date"]
    ]
    assert len(us_format_dates) > 0
