# Governed Wealth Data Product: Profiling, Definitions and Publish Gates

Profiles 118 columns across 6 simulated retail-investment extracts
(accounts, positions, cash activity, advice enrollments, parties,
fee schedules), finds 9 data-quality defects that no source had ever
declared, then enforces a business glossary of named-owner definitions
as a publish gate that holds a load at the exact column and record that
broke its definition, not the whole source. Every number below was
measured on this machine, not targeted: the gate caught 24 of 24 seeded
violations with 0 unexpected holds, and 0 of 20 independently generated
clean loads were falsely held.

## Why this exists

Governance usually starts after something has already gone wrong: a
number a business partner disputes, a report that silently changed
scale. This project is a small version of doing it the other way around,
discovery first. A profiler looks at six extracts with no prior
assumptions and finds the defects no source declared (an undeclared
enumeration, a unit that silently changed scale, a key that is not
unique). Only after that does a glossary, with a named owner per column,
become something a publish gate can actually enforce, at the precision
of one column on one record, not an all-or-nothing hold on the whole
load.

## Honest framing, up front

- **This is simulated retail-investment data, not a connection to any
  real custodian, account, or client.** `app/generator.py` generates
  every record below from a fixed seed; nothing here is a real account
  number, balance, or person.
- **The 9 profiling defects are organic, not seeded for the gate.** They
  are baked into `generate_raw_extracts()` by construction (a legacy
  feed that writes amounts at 100x scale, a party id two source systems
  both assigned, a handful of implausible dates) and are discovered by
  `app/profiler.py`'s own heuristics, independent of the glossary. The
  24 seeded violations used to measure the gate are a separate,
  deliberately corrupted copy of a clean load (`app/violations.py`);
  the two mechanisms never see each other's data.
- **PostgreSQL is not a managed service on this machine.** The local
  stand-up used for every number below is a PostgreSQL 14 instance
  inside WSL2 Ubuntu 22.04, reachable from native Windows Python through
  WSL2's localhost port forwarding, database `governed_wealth` owned by
  role `mvuser`. Every script and test below checks reachability first
  and skips cleanly if that instance is not running.
- **Every column is loaded as `TEXT`.** These are extracts exactly as
  they would arrive, before any type is enforced; the glossary's
  declared types, ranges, and allowed values are applied by
  `app/gate.py` and `app/profiler.py` reading that text, not by the
  table schema.
- **Machine and toolchain.** 8 physical / 16 logical cores (AMD Ryzen 7
  7800X3D), Windows 11 Home, Python 3.12.10 (native Windows), PostgreSQL
  14.24 (WSL2 Ubuntu 22.04), psycopg2-binary 2.9.13, pytest 9.1.1.

## Architecture

```
app/
  glossary.py     the business glossary: one ColumnDef per column (118 total)
                  across 6 sources, each with dtype, nullability, a named
                  domain steward, and (where declared) allowed values or a
                  numeric/date range. 3 columns are deliberately left
                  undeclared as enumerations; see Findings.
  generator.py    deterministic synthetic data. generate_raw_extracts()
                  bakes in 9 organic defects; generate_clean_load() conforms
                  exactly to the glossary and is the gate benchmark's baseline.
  loader.py       loads a dict of extracts into PostgreSQL as TEXT columns
                  (DROP/CREATE then bulk insert via execute_values).
  profiler.py     column profiling (count, null rate, distinct count via SQL)
                  plus 6 detector functions covering the 9 defect types.
  violations.py   injects exactly 24 seeded violations into a clean load copy,
                  4 per source, cycling null / invalid-enum / range-or-type /
                  foreign-key-or-duplicate, each with a known expected catch.
  gate.py         the publish gate: for every glossary rule, a SQL query
                  naming the exact (source, column, record) that breaks it.
  db.py           connection helper; is_reachable() lets every script and
                  test skip cleanly if PostgreSQL is not running.
scripts/
  run_profiling.py        profiles the raw pull, prints all 9 findings
  run_gate_benchmark.py   24-seeded-violation catch rate plus 20 clean loads
tests/            30 pytest tests (glossary, generator, violations: no DB
                  needed; profiler and gate: skip cleanly if PostgreSQL is
                  not reachable)
```

### Why profiling and the gate never see each other's data

`generate_raw_extracts()` and `generate_clean_load()` share the same
per-source generator functions but diverge on a single `flawed` flag.
The 9 organic defects are properties of what a real pull would already
contain (an enumeration nobody declared, a legacy feed's silent 100x
scale) and would make a poor test of the gate, because the gate is
supposed to hold on things the glossary actually declares, and none of
these 9 defects are declared anywhere. Keeping them in a dataset the
gate never sees is what makes "9 found by profiling" and "24 of 24
caught by the gate" independent, non-overlapping claims rather than the
same discovery counted twice.

### Why the currency-scale detector groups by source system instead of thresholding the raw numbers

A naive detector ("flag anything over $10,000") would also flag a large
legitimate position or a wealthy household's fee, and would miss a scale
bug that happens to land in a plausible-looking range. `detect_currency_scale_changes`
instead computes the median magnitude of a numeric column separately for
each value of every other low-cardinality text column in the same
source, and flags a pair of groups whose medians differ by a 50x-200x
ratio. That is what a silently scaled subset actually looks like: not an
outlier, but an entire group's typical value shifted by a clean order of
magnitude. The first version of this detector grouped `cash_activity.amount`
by `activity_source_system` while only a random fraction of
`PAYMENTS_HUB` rows were scaled; the scaled minority didn't move that
group's median and the detector found nothing (see Findings).

### Why the gate holds by (source, column, record), not by source

`app/gate.py` runs one SQL query per declared rule (nullability, allowed
values, numeric or date range, natural-key uniqueness, foreign-key
existence) and returns a `Hold` naming the exact natural-key value of
the offending record. The alternative, holding the whole source when any
rule fails anywhere in it, would make "24 of 24 caught" a trivial claim
(a single failure holds all 300 accounts) and would be useless to a
data steward who needs to know which record to look at.

## Validation

### Profiling (118 columns, 9 undeclared defects)

```
$ python scripts/run_profiling.py
columns profiled: 118
sources profiled: 6

-- claim: 9 quality defects found that no source had declared --
defects found: 9
  [implicit_enumeration] accounts.account_type: 4 distinct values, never declared
  [implicit_enumeration] positions.asset_class: 5 distinct values, never declared
  [implicit_enumeration] advice_enrollments.enrollment_channel: 3 distinct values, never declared
  [currency_scale_change] cash_activity.amount: 96.0x median gap, PAYMENTS_HUB vs CUSTODY_FEED
  [currency_scale_change] fee_schedules.annual_fee_amount: 141.6x median gap, LEGACY_BILLING vs BILLING_ENGINE
  [mixed_date_format] advice_enrollments.enrollment_date: ISO and MM/DD/YYYY mixed
  [duplicate_natural_key] parties.party_id: 6 values appear on more than one row
  [orphan_foreign_key] positions.account_id: 5 rows reference a nonexistent account
  [implausible_value] accounts.account_open_date: 4 accounts outside the plausible window
```

Full output: `docs/profiling_output.txt`.

### Publish gate (24 seeded violations, 20 clean loads)

```
$ python scripts/run_gate_benchmark.py
-- claim: 24 of 24 seeded violations caught by column and source record --
seeded violations caught: 24 / 24
unexpected holds on the seeded-violation load: 0

-- claim: 0 of 20 clean loads falsely held --
false holds across 20 independent clean loads: 0
```

Full output: `docs/gate_benchmark_output.txt`.

### Tests

30 pytest tests: glossary structural invariants (118 columns, one
natural key per source, every column owned, every foreign key resolves
to a declared column), generator determinism and glossary conformance of
the clean load (checked directly in Python, independent of the gate, as
a second line of evidence for "0 false holds"), the 24-seeded-violation
set's shape, and (skipped cleanly if PostgreSQL is not reachable) the
profiler's 9-defect count and the gate's 24-of-24 catch rate plus 5
additional clean-load false-hold checks.

```
$ python -m pytest tests -q
..............................                                          [100%]
30 passed in 27.72s
```

Full transcript: `docs/test_output.txt`.

## Findings

### The first currency-scale detector found nothing, because it compared the wrong population

**Symptom.** The first run of `run_profiling.py` reported 8 defects, not
9: every implicit enumeration, the mixed date format, the duplicate key,
the orphan foreign key, and the implausible date all showed up, but
`currency_scale_change` found 0.

**Wrong hypothesis first.** The detector itself looked right: group a
float column by a low-cardinality text column, compare median
magnitudes, flag a 50x-200x gap. The first guess was a threshold
problem, that 50x-200x was too narrow a band.

**The measurement that discriminated.** Printing the actual per-group
medians for `cash_activity.amount` grouped by `activity_source_system`
showed `PAYMENTS_HUB` at roughly the same order of magnitude as
`CUSTODY_FEED`, not 100x apart. The scaled rows were there (a budgeted,
probabilistic subset of `PAYMENTS_HUB` rows), but they were a minority
inside that group, so the group's median, the statistic the detector
actually reads, was still set by the unscaled majority.

**Root cause.** The generator applied the scale bug to a random ~35% of
`PAYMENTS_HUB` rows (`legacy_budget` with a 0.35 draw), which is a
reasonable way to model "sometimes buggy," but it meant no single text
column's groups lined up with "scaled" versus "not scaled": within
`PAYMENTS_HUB`, scaled and unscaled rows were mixed together.

**Fix.** The organic defect was changed to apply to 100% of
`PAYMENTS_HUB` rows (and, in the same class of bug, 100% of
`LEGACY_BILLING` fee rows), which is also the more realistic version of
this bug: a legacy feed does not scale its amounts correctly some of the
time, it does it every time, consistently, which is exactly why nobody
catches it by eyeballing individual values. After the fix, both
currency-scale defects were found on the first run, at 96.0x and 141.6x
respectively.

**Why the method mattered.** The detector's logic was never wrong; the
synthetic data's shape was. A grouped-median comparison is only as good
as whether the grouping key actually separates the two populations, and
printing the per-group numbers rather than trusting the pass/fail
boolean is what showed that the groups were mixed rather than the ratio
threshold being wrong.

### Three incidental quasi-enumerations had to be designed out of the "free text" columns

**Symptom.** An early version of `detect_implicit_enumerations` reported
4 implicit enumerations, not 3: `parties.citizenship_country`, generated
from a 6-country pool, tripped the same distinct-count-between-2-and-6
threshold intended for the 3 designated undeclared columns.

**Fix.** `citizenship_country`'s value pool was widened to 8 distinct
countries, safely above the threshold; the same audit caught four other
columns at risk of the same accident (`account_title`, `sector`,
`description`, `risk_profile_version`, `consent_document_version`) and
widened each before this became a silent flake. The detector's threshold
itself did not change; the synthetic data's free-text columns needed
enough genuine variety to actually look like free text.

## Measured results

8 physical / 16 logical cores, Windows 11 Home, Python 3.12.10,
PostgreSQL 14.24 (WSL2).

| Metric | Measured | Claim |
|---|---|---|
| **Columns profiled** | **118** | 118 columns profiled |
| Extracts | 6 (accounts 300, positions 1,652, cash_activity 2,438, advice_enrollments 147, parties 374, fee_schedules 269 rows) | 6 simulated retail-investment extracts |
| **Undeclared defects found** | **9** | 9 quality defects found that no source had declared |
| Implicit enumerations | 3 (account_type, asset_class, enrollment_channel) | 3 implicit enumerations |
| Silent currency-scale changes | 2 (cash_activity.amount 96.0x, fee_schedules.annual_fee_amount 141.6x) | 2 silent currency-scale changes |
| **Seeded violations caught** | **24 / 24**, 0 unexpected holds | 24 of 24 seeded violations caught by column and source record |
| **False holds, 20 clean loads** | **0** | 0 of 20 clean loads falsely held |

Row counts vary run to run with the generator's internal randomness
(enrollment and fee-schedule eligibility, position and activity counts
per account); the column count, defect count, and catch/false-hold rates
above are exact and seed-independent across the runs in `docs/`.

## Building and running

```bash
# PostgreSQL stand-up used for this run (not a managed service on this
# machine): a local PostgreSQL 14 instance inside WSL2 Ubuntu 22.04,
# listening on 127.0.0.1:5432, database `governed_wealth` owned by role
# `mvuser` / password `mvpass` (override with GWDP_PG_* environment
# variables). Created with:
#   sudo -u postgres psql -c "CREATE DATABASE governed_wealth OWNER mvuser;"

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

python -m pytest tests -q                 # docs/test_output.txt
python scripts/run_profiling.py           # docs/profiling_output.txt
python scripts/run_gate_benchmark.py      # docs/gate_benchmark_output.txt
```

## Sibling comparison

[`investment-data-quality-lineage-gate`](https://github.com/Manas103/investment-data-quality-lineage-gate)
and [`entity-resolution-drift-quarantine`](https://github.com/Manas103/entity-resolution-drift-quarantine)
are this portfolio's other named-rule publish gates (45/45 and 30/30
seeded defects caught respectively, both with 0 false holds). Both
start from an engineer-authored validation spec; neither is built
around a business glossary with a named owner per column, and neither
project has a profiling phase whose job is to find what the rules don't
yet cover. This project's defining property is upstream of both: a
profiler that looks at ungoverned data first and finds 9 real gaps (3 of
them enumerations nobody had declared, which is exactly the kind of gap
a glossary-driven gate cannot catch until someone writes the rule down),
before any gate exists to enforce anything.

## Limitations

- **The 9 organic defects are a fixed, designed set, not a general
  anomaly detector.** `app/profiler.py` looks for exactly 6 kinds of
  undeclared problem; a defect that is not an implicit enumeration, a
  currency-scale clustering, a mixed date format, a duplicate key, an
  orphan foreign key, or an implausible date would not be found by this
  tool.
- **The implicit-enumeration threshold (2 to 6 distinct values) is a
  fixed heuristic.** A real free-text column that happens to have 5
  distinct values in a given pull would also be flagged; a human still
  decides whether to codify it as a glossary enumeration or leave it as
  free text.
- **The currency-scale detector needs a grouping column that actually
  separates the scaled population from the rest** (see Findings); a
  scale bug spread evenly across every value of every other column in
  its source would not produce the median gap this detector looks for.
- **The glossary's rule set (nullability, allowed values, numeric and
  date ranges, natural-key uniqueness, foreign-key existence) does not
  include cross-column business rules** (for example, that
  `target_allocation_equity_pct` plus `target_allocation_fixed_income_pct`
  should sum to 100); `business-rules-acceptance-criteria-pack` is where
  that class of rule is the entire subject.
- **No throughput claim.** Row counts here (a few hundred to a few
  thousand per extract) are sized for a credible profiling exercise on
  a shared development machine, not a production data-volume benchmark.
