"""Deterministic synthetic data for the 6 retail-investment extracts.

Two modes, both seeded and reproducible:

``generate_raw_extracts(seed)``
    A single realistic-looking pull with 9 organic data-quality defects
    baked in by construction, none of them declared by any source. This is
    what ``scripts/run_profiling.py`` profiles; it is never run through the
    publish gate.

``generate_clean_load(seed)``
    A load that conforms exactly to every rule in ``app/glossary.py``. This
    is the baseline for the gate benchmark: ``app/violations.py`` injects
    seeded violations into a copy of it, and 20 independently seeded clean
    loads are run through the gate unmodified to measure false holds.

Every row is represented as ``dict[str, str | None]``, mirroring how these
extracts actually arrive, as text, before any type is enforced.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

TODAY = date(2026, 10, 1)
EARLIEST_PLAUSIBLE = date(2000, 1, 1)

N_ACCOUNTS = 300

ACCOUNT_TYPES = ("Retail Brokerage", "Retail IRA", "Advisory Managed", "Education Savings")
ASSET_CLASSES = ("US Equity", "Intl Equity", "Fixed Income", "Cash & Equivalents", "Alternatives")
ENROLLMENT_CHANNELS = ("Web", "Mobile App", "Branch")

STATES = ("NC", "VA", "SC", "GA", "PA", "NY", "FL", "TX", "OH", "IL")

# Pools sized deliberately above the profiler's implicit-enumeration
# threshold (distinct count 2-6), so only the 3 designated columns above
# trip that detector; these free-text-shaped columns are not meant to.
ACCOUNT_TITLE_NAMES = ("Alvarez", "Nguyen", "Okafor", "Patel", "Chen", "Fitzgerald", "Kowalski", "Rossi", "Haddad", "Sato")
ACCOUNT_TITLE_SUFFIXES = ("Individual Account", "Joint Account", "Trust Account")
SECTORS = ("Technology", "Financials", "Healthcare", "Energy", "Industrials",
           "Consumer Discretionary", "Consumer Staples", "Utilities", "Materials", "Real Estate")
COUNTRIES_OF_RISK = ("US", "US", "US", "US", "CA", "GB", "JP", "DE", "FR", "AU", "CH")
CASH_DESCRIPTIONS = ("Dividend reinvestment", "Monthly advisory fee", "ACH transfer", "Scheduled withdrawal",
                     "Wire transfer in", "Wire transfer out", "Interest credit", "Check deposit",
                     "Account transfer", "Fee reversal")
RISK_PROFILE_VERSIONS = ("v3.0", "v3.1", "v4.0", "v4.1", "v4.2", "v5.0", "v5.1", "v5.2")
CONSENT_DOC_VERSIONS = ("2023.1", "2023.2", "2024.1", "2024.2", "2025.1", "2025.2", "2026.1")


def _fmt_date(d: date) -> str:
    return d.isoformat()


def _fmt_bool(b: bool) -> str:
    return "true" if b else "false"


def _fmt_money(x: float) -> str:
    return f"{x:.2f}"


def _random_date(rng: random.Random, start: date, end: date) -> date:
    span = (end - start).days
    return start + timedelta(days=rng.randint(0, max(span, 0)))


def _gen_accounts(rng: random.Random, flawed: bool) -> list[dict]:
    rows = []
    implausible_idx = set(rng.sample(range(N_ACCOUNTS), 4)) if flawed else set()
    for i in range(N_ACCOUNTS):
        account_id = f"ACCT-{i:06d}"
        open_date = _random_date(rng, EARLIEST_PLAUSIBLE, TODAY - timedelta(days=30))
        if i in implausible_idx:
            # Organic defect #9: implausible account_open_date, no source
            # ever validated this against a sane firm-history window.
            open_date = rng.choice([date(1955, 3, 1), date(1988, 11, 2), TODAY + timedelta(days=200)])
        is_closed = rng.random() < 0.1
        status = "Closed" if is_closed else rng.choice(["Open", "Open", "Open", "Restricted", "Pending"])
        close_date = _random_date(rng, open_date + timedelta(days=1), TODAY) if is_closed else None
        is_retirement = rng.random() < 0.3
        rows.append({
            "account_id": account_id,
            "account_type": rng.choice(ACCOUNT_TYPES),
            "account_status": status,
            "account_open_date": _fmt_date(open_date),
            "account_close_date": _fmt_date(close_date) if close_date else None,
            "registered_rep_id": f"REP-{rng.randint(1, 40):04d}" if rng.random() < 0.7 else None,
            "household_id": f"HH-{rng.randint(1, 180):05d}" if rng.random() < 0.6 else None,
            "tax_status": "TaxDeferred" if is_retirement else rng.choice(["Taxable", "TaxExempt"]),
            "base_currency": "USD",
            "risk_tolerance_score": str(rng.randint(1, 10)),
            "is_retirement_account": _fmt_bool(is_retirement),
            "advisory_fee_bps": str(rng.randint(25, 120)) if rng.random() < 0.5 else None,
            "custodian_code": rng.choice(["VBS", "VBS", "NFS", "PERSHING"]),
            "account_title": f"{rng.choice(ACCOUNT_TITLE_NAMES)} {rng.choice(ACCOUNT_TITLE_SUFFIXES)}" if rng.random() < 0.8 else None,
            "branch_code": f"BR-{rng.randint(1, 25):03d}",
            "state_of_residence": rng.choice(STATES),
            "account_source_system": rng.choice(["WEALTH360", "WEALTH360", "LEGACY_ONBOARD", "ADVISOR_PORTAL"]),
            "last_statement_date": _fmt_date(_random_date(rng, TODAY - timedelta(days=60), TODAY)) if rng.random() < 0.9 else None,
            "account_minimum_met": _fmt_bool(rng.random() < 0.85),
            "kyc_refresh_due_date": _fmt_date(_random_date(rng, TODAY, TODAY + timedelta(days=365))) if rng.random() < 0.6 else None,
        })
    return rows


def _gen_positions(rng: random.Random, accounts: list[dict], flawed: bool) -> list[dict]:
    rows = []
    account_ids = [a["account_id"] for a in accounts]
    idx = 0
    orphan_budget = 5 if flawed else 0
    for acc in accounts:
        n = rng.randint(2, 9)
        for _ in range(n):
            qty = round(rng.uniform(1, 5000), 4)
            price = round(rng.uniform(1, 450), 2)
            account_ref = acc["account_id"]
            if flawed and orphan_budget > 0 and rng.random() < 0.02:
                # Organic defect #8: a position referencing an account_id
                # that never made it into this pull's accounts extract.
                account_ref = f"ACCT-{900000 + idx:06d}"
                orphan_budget -= 1
            rows.append({
                "position_id": f"POS-{idx:07d}",
                "account_id": account_ref,
                "as_of_date": _fmt_date(TODAY),
                "security_id": f"SEC-{rng.randint(1, 600):05d}",
                "asset_class": rng.choice(ASSET_CLASSES),
                "quantity": str(qty),
                "unit_price": _fmt_money(price),
                "market_value": _fmt_money(round(qty * price, 2)),
                "cost_basis": _fmt_money(round(qty * price * rng.uniform(0.6, 1.1), 2)) if rng.random() < 0.8 else None,
                "unrealized_gain_loss": _fmt_money(round(qty * price * rng.uniform(-0.3, 0.3), 2)) if rng.random() < 0.7 else None,
                "lot_id": f"LOT-{idx:07d}" if rng.random() < 0.6 else None,
                "sleeve_code": rng.choice(["CORE", "CORE", "SATELLITE", "CASH_RESERVE"]),
                "security_type": rng.choice(["EQUITY", "FIXED_INCOME", "MUTUAL_FUND", "ETF", "CASH"]),
                "sector": rng.choice(SECTORS + (None, None)),
                "country_of_risk": rng.choice(COUNTRIES_OF_RISK),
                "is_restricted": _fmt_bool(rng.random() < 0.03),
                "position_source_system": rng.choice(["CUSTODY_FEED", "ADVISORY_BOOK"]),
                "pricing_source": rng.choice(["VENDOR_A", "VENDOR_B", "MANUAL"]),
                "accrued_interest": _fmt_money(round(rng.uniform(0, 40), 2)) if rng.random() < 0.3 else None,
                "settlement_date": _fmt_date(_random_date(rng, TODAY - timedelta(days=5), TODAY)) if rng.random() < 0.5 else None,
                "holding_period_days": str(rng.randint(0, 3000)) if rng.random() < 0.7 else None,
                "last_trade_date": _fmt_date(_random_date(rng, TODAY - timedelta(days=90), TODAY)) if rng.random() < 0.6 else None,
            })
            idx += 1
    return rows


def _gen_cash_activity(rng: random.Random, accounts: list[dict], flawed: bool) -> list[dict]:
    rows = []
    idx = 0
    for acc in accounts:
        n = rng.randint(4, 12)
        for _ in range(n):
            amount = round(rng.uniform(-8000, 8000), 2)
            batch = f"BATCH-{rng.randint(1, 60):04d}"
            source_system = rng.choice(["CUSTODY_FEED", "CUSTODY_FEED", "PAYMENTS_HUB"])
            amount_str = _fmt_money(amount)
            if flawed and source_system == "PAYMENTS_HUB":
                # Organic defect #4: the payments hub feed has, for its
                # entire history, silently written amounts scaled by 100
                # (dollars encoded as whole cents), with no unit marker
                # anywhere in the extract.
                amount_str = f"{int(round(amount * 100)):d}.00"
            rows.append({
                "activity_id": f"CASH-{idx:07d}",
                "account_id": acc["account_id"],
                "activity_date": _fmt_date(_random_date(rng, TODAY - timedelta(days=120), TODAY)),
                "activity_type": rng.choice(["DEPOSIT", "WITHDRAWAL", "DIVIDEND", "INTEREST", "FEE", "TRANSFER"]),
                "amount": amount_str,
                "currency": "USD",
                "settlement_status": rng.choice(["SETTLED", "SETTLED", "SETTLED", "PENDING", "REJECTED"]),
                "source_batch_id": batch,
                "description": rng.choice(CASH_DESCRIPTIONS + (None,)),
                "counterparty": f"EXT-BANK-{rng.randint(1, 20):03d}" if rng.random() < 0.3 else None,
                "is_recurring": _fmt_bool(rng.random() < 0.2),
                "sweep_account_flag": _fmt_bool(rng.random() < 0.15),
                "reversal_flag": _fmt_bool(False),
                "original_activity_id": None,
                "posted_timestamp": _fmt_date(_random_date(rng, TODAY - timedelta(days=120), TODAY)),
                "channel": rng.choice(["ACH", "WIRE", "CHECK", "INTERNAL"]),
                "tax_reportable": _fmt_bool(rng.random() < 0.4),
                "activity_source_system": source_system,
            })
            idx += 1
    return rows


def _gen_advice_enrollments(rng: random.Random, accounts: list[dict], flawed: bool) -> list[dict]:
    rows = []
    idx = 0
    legacy_date_budget = 30 if flawed else 0
    for acc in accounts:
        if rng.random() >= 0.5:
            continue
        is_terminated = rng.random() < 0.15
        enroll_date = _random_date(rng, EARLIEST_PLAUSIBLE + timedelta(days=1000), TODAY - timedelta(days=30))
        enroll_date_str = _fmt_date(enroll_date)
        if flawed and legacy_date_budget > 0 and rng.random() < 0.4:
            # Organic defect #6: a legacy enrollment cohort's dates arrived
            # as MM/DD/YYYY, never normalized, mixed in with ISO dates from
            # every other cohort in the same column.
            enroll_date_str = f"{enroll_date.month:02d}/{enroll_date.day:02d}/{enroll_date.year:04d}"
            legacy_date_budget -= 1
        rows.append({
            "enrollment_id": f"ADV-{idx:06d}",
            "account_id": acc["account_id"],
            "enrollment_date": enroll_date_str,
            "advice_program": rng.choice(["DIGITAL_ADVISOR", "HYBRID_ADVISOR", "FULL_SERVICE"]),
            "enrollment_channel": rng.choice(ENROLLMENT_CHANNELS),
            "risk_profile_version": rng.choice(RISK_PROFILE_VERSIONS),
            "advice_fee_bps": str(rng.randint(15, 85)),
            "opted_in_tax_loss_harvesting": _fmt_bool(rng.random() < 0.5),
            "target_allocation_equity_pct": str(rng.randint(20, 90)),
            "target_allocation_fixed_income_pct": str(rng.randint(10, 80)),
            "rebalance_frequency": rng.choice(["MONTHLY", "QUARTERLY", "THRESHOLD"]),
            "last_review_date": _fmt_date(_random_date(rng, enroll_date, TODAY)) if rng.random() < 0.7 else None,
            "disengagement_date": _fmt_date(_random_date(rng, enroll_date, TODAY)) if is_terminated else None,
            "advisor_assigned_id": f"ADVR-{rng.randint(1, 30):04d}" if rng.random() < 0.6 else None,
            "enrollment_status": "TERMINATED" if is_terminated else rng.choice(["ACTIVE", "ACTIVE", "PAUSED"]),
            "consent_document_version": rng.choice(CONSENT_DOC_VERSIONS),
        })
        idx += 1
    return rows


def _gen_parties(rng: random.Random, accounts: list[dict], flawed: bool) -> list[dict]:
    rows = []
    idx = 0
    seen_ids: list[str] = []
    dup_budget = 6 if flawed else 0
    for acc in accounts:
        n = rng.choice([1, 1, 1, 2])
        for p in range(n):
            party_id = f"PTY-{idx:06d}"
            if flawed and dup_budget > 0 and seen_ids and rng.random() < 0.08:
                # Organic defect #7: two source feeds (CRM and the onboarding
                # portal) independently assigned the same party_id to two
                # different people; nothing in either feed catches it.
                party_id = rng.choice(seen_ids)
                dup_budget -= 1
            else:
                seen_ids.append(party_id)
            rows.append({
                "party_id": party_id,
                "account_id": acc["account_id"],
                "relationship_type": "PRIMARY" if p == 0 else rng.choice(["JOINT", "BENEFICIARY", "TRUSTEE"]),
                "first_name": rng.choice(["James", "Maria", "Wei", "Fatima", "Noah", "Olivia", "Hiroshi", "Grace"]),
                "last_name": rng.choice(["Smith", "Garcia", "Chen", "Khan", "Johnson", "Kim", "Patel", "Nguyen"]),
                "date_of_birth": _fmt_date(_random_date(rng, date(1935, 1, 1), date(2007, 1, 1))),
                "tax_id_type": rng.choice(["SSN", "SSN", "SSN", "ITIN"]),
                "tax_id_last4": f"{rng.randint(0, 9999):04d}",
                "citizenship_country": rng.choice(COUNTRIES_OF_RISK),
                "residency_country": "US",
                "employment_status": rng.choice(["EMPLOYED", "SELF_EMPLOYED", "RETIRED", "STUDENT", "UNEMPLOYED"]),
                "accredited_investor_flag": _fmt_bool(rng.random() < 0.1),
                "pep_flag": _fmt_bool(rng.random() < 0.01),
                "kyc_status": rng.choice(["VERIFIED", "VERIFIED", "VERIFIED", "PENDING", "EXPIRED"]),
                "kyc_last_verified_date": _fmt_date(_random_date(rng, TODAY - timedelta(days=700), TODAY)) if rng.random() < 0.8 else None,
                "email": f"party{idx}@example-mail.test" if rng.random() < 0.85 else None,
                "phone": f"+1-{rng.randint(200,999)}-{rng.randint(200,999)}-{rng.randint(1000,9999)}" if rng.random() < 0.8 else None,
                "mailing_state": rng.choice(STATES),
                "preferred_language": rng.choice(["EN", "EN", "EN", "ES", "ZH", "JA"]),
                "electronic_delivery_consent": _fmt_bool(rng.random() < 0.65),
                "beneficiary_percentage": str(rng.choice([25, 50, 100])) if p > 0 and rng.random() < 0.7 else None,
                "party_source_system": rng.choice(["CRM", "ONBOARDING_PORTAL"]),
            })
            idx += 1
    return rows


def _gen_fee_schedules(rng: random.Random, accounts: list[dict], flawed: bool) -> list[dict]:
    rows = []
    idx = 0
    for acc in accounts:
        if rng.random() >= 0.9:
            continue
        fee_basis = rng.choice(["BPS", "FLAT", "HYBRID"])
        source_system = rng.choice(["BILLING_ENGINE", "BILLING_ENGINE", "LEGACY_BILLING"])
        annual_amount = round(rng.uniform(50, 4500), 2)
        amount_str = _fmt_money(annual_amount)
        if flawed and source_system == "LEGACY_BILLING":
            # Organic defect #5: the legacy billing engine's annual fee
            # amount is also silently scaled by 100, the same class of bug
            # as the payments hub feed but in a different source system.
            amount_str = f"{int(round(annual_amount * 100)):d}.00"
        effective = _random_date(rng, TODAY - timedelta(days=700), TODAY - timedelta(days=10))
        rows.append({
            "fee_schedule_id": f"FEE-{idx:06d}",
            "account_id": acc["account_id"],
            "fee_type": rng.choice(["ADVISORY", "CUSTODY", "TRANSACTION", "FUND_EXPENSE"]),
            "annual_fee_amount": amount_str,
            "billing_frequency": rng.choice(["MONTHLY", "QUARTERLY", "ANNUAL"]),
            "effective_date": _fmt_date(effective),
            "expiration_date": _fmt_date(effective + timedelta(days=365)) if rng.random() < 0.2 else None,
            "fee_tier": rng.choice(["TIER1", "TIER2", "TIER3", "TIER4"]),
            "fee_basis": fee_basis,
            "fee_bps_rate": str(rng.randint(10, 150)) if fee_basis in ("BPS", "HYBRID") else None,
            "minimum_fee_amount": _fmt_money(round(rng.uniform(10, 100), 2)) if rng.random() < 0.4 else None,
            "maximum_fee_amount": _fmt_money(round(rng.uniform(1000, 6000), 2)) if rng.random() < 0.3 else None,
            "waived_flag": _fmt_bool(rng.random() < 0.08),
            "waiver_reason": "Household relationship pricing" if rng.random() < 0.08 else None,
            "last_billed_date": _fmt_date(_random_date(rng, TODAY - timedelta(days=90), TODAY)) if rng.random() < 0.8 else None,
            "next_bill_date": _fmt_date(_random_date(rng, TODAY, TODAY + timedelta(days=90))) if rng.random() < 0.8 else None,
            "fee_source_system": source_system,
            "gl_account_code": f"GL-{rng.randint(1000, 1999)}",
            "approved_by": f"OFFICER-{rng.randint(1,15):03d}" if rng.random() < 0.3 else None,
            "approval_date": _fmt_date(_random_date(rng, effective - timedelta(days=30), effective)) if rng.random() < 0.3 else None,
        })
        idx += 1
    return rows


def _generate(seed: int, flawed: bool) -> dict[str, list[dict]]:
    rng = random.Random(seed)
    accounts = _gen_accounts(rng, flawed)
    positions = _gen_positions(rng, accounts, flawed)
    cash_activity = _gen_cash_activity(rng, accounts, flawed)
    advice_enrollments = _gen_advice_enrollments(rng, accounts, flawed)
    parties = _gen_parties(rng, accounts, flawed)
    fee_schedules = _gen_fee_schedules(rng, accounts, flawed)
    return {
        "accounts": accounts,
        "positions": positions,
        "cash_activity": cash_activity,
        "advice_enrollments": advice_enrollments,
        "parties": parties,
        "fee_schedules": fee_schedules,
    }


def generate_raw_extracts(seed: int = 1) -> dict[str, list[dict]]:
    """The organically flawed pull that ``run_profiling.py`` profiles."""
    return _generate(seed, flawed=True)


def generate_clean_load(seed: int = 100) -> dict[str, list[dict]]:
    """A load that conforms exactly to ``app/glossary.py``."""
    return _generate(seed, flawed=False)
