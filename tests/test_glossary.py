from app import glossary as g


def test_total_columns_is_118():
    assert g.total_columns() == 118


def test_six_sources():
    assert set(g.GLOSSARY) == {
        "accounts", "positions", "cash_activity",
        "advice_enrollments", "parties", "fee_schedules",
    }


def test_every_source_has_exactly_one_natural_key():
    for source, cols in g.GLOSSARY.items():
        keys = [c for c in cols if c.is_natural_key]
        assert len(keys) == 1, f"{source} has {len(keys)} natural keys"


def test_every_column_has_a_named_owner():
    for source, cols in g.GLOSSARY.items():
        for col in cols:
            assert col.owner, f"{source}.{col.name} has no owner"


def test_fk_columns_reference_declared_sources_and_columns():
    for source, cols in g.GLOSSARY.items():
        for col in cols:
            if col.fk:
                ref_source, ref_col = col.fk
                assert ref_source in g.GLOSSARY
                assert ref_col in g.columns_by_name(ref_source)
