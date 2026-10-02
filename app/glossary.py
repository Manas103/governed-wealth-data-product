"""The business glossary: one ColumnDef per column, across 6 simulated
retail-investment extracts, each with a named domain steward as owner.

This glossary is deliberately imperfect, the same way a real firm's glossary
is imperfect: three columns that behave like enumerations in practice
(``account_type``, ``asset_class``, ``enrollment_channel``) have never been
declared with ``allowed_values`` by any source, which is exactly the kind
of gap the profiler in ``app/profiler.py`` is built to surface. Everything
else here is enforced by the publish gate in ``app/gate.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ColumnDef:
    name: str
    dtype: str  # "text", "int", "float", "date", "bool"
    nullable: bool
    owner: str
    description: str
    allowed_values: tuple | None = None
    min_value: float | None = None
    max_value: float | None = None
    is_natural_key: bool = False
    fk: tuple | None = None  # (source, column)


ACCOUNTS_STEWARD = "Accounts Domain Steward (R. Alvarez)"
POSITIONS_STEWARD = "Positions Domain Steward (M. Chen)"
CASH_STEWARD = "Cash Activity Domain Steward (D. Okafor)"
ADVICE_STEWARD = "Advice Domain Steward (S. Patel)"
PARTY_STEWARD = "Party/KYC Domain Steward (L. Fitzgerald)"
FEE_STEWARD = "Pricing & Fees Domain Steward (J. Kowalski)"


ACCOUNTS: tuple[ColumnDef, ...] = (
    ColumnDef("account_id", "text", False, ACCOUNTS_STEWARD,
              "Firm-wide unique account identifier.", is_natural_key=True),
    ColumnDef("account_type", "text", False, ACCOUNTS_STEWARD,
              "Product the account was opened under. No source has ever "
              "declared the closed set of values this column actually "
              "takes; see the profiler's implicit-enumeration finding."),
    ColumnDef("account_status", "text", False, ACCOUNTS_STEWARD,
              "Current lifecycle state of the account.",
              allowed_values=("Open", "Closed", "Restricted", "Pending")),
    ColumnDef("account_open_date", "date", False, ACCOUNTS_STEWARD,
              "Date the account was opened.",
              min_value="2000-01-01"),
    ColumnDef("account_close_date", "date", True, ACCOUNTS_STEWARD,
              "Date the account was closed, if it has been."),
    ColumnDef("registered_rep_id", "text", True, ACCOUNTS_STEWARD,
              "Assigned registered representative, if any."),
    ColumnDef("household_id", "text", True, ACCOUNTS_STEWARD,
              "Household grouping identifier, if the account is linked."),
    ColumnDef("tax_status", "text", False, ACCOUNTS_STEWARD,
              "Tax treatment of the account.",
              allowed_values=("Taxable", "TaxDeferred", "TaxExempt")),
    ColumnDef("base_currency", "text", False, ACCOUNTS_STEWARD,
              "Currency the account is denominated in.",
              allowed_values=("USD",)),
    ColumnDef("risk_tolerance_score", "int", False, ACCOUNTS_STEWARD,
              "Self-reported risk tolerance, 1 (conservative) to 10 "
              "(aggressive).", min_value=1, max_value=10),
    ColumnDef("is_retirement_account", "bool", False, ACCOUNTS_STEWARD,
              "Whether the account carries retirement tax treatment."),
    ColumnDef("advisory_fee_bps", "int", True, ACCOUNTS_STEWARD,
              "Advisory fee in basis points, if advisory.",
              min_value=0, max_value=150),
    ColumnDef("custodian_code", "text", False, ACCOUNTS_STEWARD,
              "Custodian of record for the account.",
              allowed_values=("VBS", "NFS", "PERSHING")),
    ColumnDef("account_title", "text", True, ACCOUNTS_STEWARD,
              "Registration title printed on statements."),
    ColumnDef("branch_code", "text", False, ACCOUNTS_STEWARD,
              "Servicing branch code."),
    ColumnDef("state_of_residence", "text", False, ACCOUNTS_STEWARD,
              "Two-letter state of the account owner's residence."),
    ColumnDef("account_source_system", "text", False, ACCOUNTS_STEWARD,
              "System the account record was onboarded through.",
              allowed_values=("WEALTH360", "LEGACY_ONBOARD", "ADVISOR_PORTAL")),
    ColumnDef("last_statement_date", "date", True, ACCOUNTS_STEWARD,
              "Date of the most recently generated statement."),
    ColumnDef("account_minimum_met", "bool", False, ACCOUNTS_STEWARD,
              "Whether the account satisfies its product's minimum balance."),
    ColumnDef("kyc_refresh_due_date", "date", True, ACCOUNTS_STEWARD,
              "Date the next KYC refresh is due, if scheduled."),
)

POSITIONS: tuple[ColumnDef, ...] = (
    ColumnDef("position_id", "text", False, POSITIONS_STEWARD,
              "Unique identifier for one account/security/as-of-date position row.",
              is_natural_key=True),
    ColumnDef("account_id", "text", False, POSITIONS_STEWARD,
              "Account the position belongs to.", fk=("accounts", "account_id")),
    ColumnDef("as_of_date", "date", False, POSITIONS_STEWARD,
              "Valuation date of the position."),
    ColumnDef("security_id", "text", False, POSITIONS_STEWARD,
              "Security identifier (internal symbol)."),
    ColumnDef("asset_class", "text", False, POSITIONS_STEWARD,
              "Broad asset class of the security. Never declared as a "
              "closed set by any source; see the profiler's finding."),
    ColumnDef("quantity", "float", False, POSITIONS_STEWARD,
              "Shares or units held.", min_value=0),
    ColumnDef("unit_price", "float", False, POSITIONS_STEWARD,
              "Price per share or unit on the as-of date.", min_value=0),
    ColumnDef("market_value", "float", False, POSITIONS_STEWARD,
              "Quantity times unit price.", min_value=0),
    ColumnDef("cost_basis", "float", True, POSITIONS_STEWARD,
              "Cost basis, if tracked for this security type."),
    ColumnDef("unrealized_gain_loss", "float", True, POSITIONS_STEWARD,
              "Market value minus cost basis, if cost basis is known."),
    ColumnDef("lot_id", "text", True, POSITIONS_STEWARD,
              "Tax lot identifier, if the position is lot-tracked."),
    ColumnDef("sleeve_code", "text", False, POSITIONS_STEWARD,
              "Portfolio sleeve the position is managed under.",
              allowed_values=("CORE", "SATELLITE", "CASH_RESERVE")),
    ColumnDef("security_type", "text", False, POSITIONS_STEWARD,
              "Instrument type of the security.",
              allowed_values=("EQUITY", "FIXED_INCOME", "MUTUAL_FUND", "ETF", "CASH")),
    ColumnDef("sector", "text", True, POSITIONS_STEWARD,
              "GICS-style sector, if applicable to the security type."),
    ColumnDef("country_of_risk", "text", False, POSITIONS_STEWARD,
              "Two-letter country of economic risk."),
    ColumnDef("is_restricted", "bool", False, POSITIONS_STEWARD,
              "Whether trading in this position is currently restricted."),
    ColumnDef("position_source_system", "text", False, POSITIONS_STEWARD,
              "System the position row was fed from.",
              allowed_values=("CUSTODY_FEED", "ADVISORY_BOOK")),
    ColumnDef("pricing_source", "text", False, POSITIONS_STEWARD,
              "Source of the unit price used to value the position.",
              allowed_values=("VENDOR_A", "VENDOR_B", "MANUAL")),
    ColumnDef("accrued_interest", "float", True, POSITIONS_STEWARD,
              "Accrued interest, if the security type carries it.", min_value=0),
    ColumnDef("settlement_date", "date", True, POSITIONS_STEWARD,
              "Settlement date of the most recent trade in this lot."),
    ColumnDef("holding_period_days", "int", True, POSITIONS_STEWARD,
              "Days held as of the valuation date.", min_value=0),
    ColumnDef("last_trade_date", "date", True, POSITIONS_STEWARD,
              "Date of the most recent trade affecting this position."),
)

CASH_ACTIVITY: tuple[ColumnDef, ...] = (
    ColumnDef("activity_id", "text", False, CASH_STEWARD,
              "Unique identifier for one cash activity line.", is_natural_key=True),
    ColumnDef("account_id", "text", False, CASH_STEWARD,
              "Account the activity posted to.", fk=("accounts", "account_id")),
    ColumnDef("activity_date", "date", False, CASH_STEWARD,
              "Date the activity was posted."),
    ColumnDef("activity_type", "text", False, CASH_STEWARD,
              "Nature of the cash movement.",
              allowed_values=("DEPOSIT", "WITHDRAWAL", "DIVIDEND", "INTEREST", "FEE", "TRANSFER")),
    ColumnDef("amount", "float", False, CASH_STEWARD,
              "Dollar amount of the activity, in whole dollars and cents.",
              min_value=-100000, max_value=100000),
    ColumnDef("currency", "text", False, CASH_STEWARD,
              "Currency of the amount.", allowed_values=("USD",)),
    ColumnDef("settlement_status", "text", False, CASH_STEWARD,
              "Settlement state of the activity.",
              allowed_values=("PENDING", "SETTLED", "REJECTED")),
    ColumnDef("source_batch_id", "text", False, CASH_STEWARD,
              "Batch the activity line arrived in."),
    ColumnDef("description", "text", True, CASH_STEWARD,
              "Free-text description printed on the statement line."),
    ColumnDef("counterparty", "text", True, CASH_STEWARD,
              "Counterparty name, for wires and transfers."),
    ColumnDef("is_recurring", "bool", False, CASH_STEWARD,
              "Whether this activity is part of a standing instruction."),
    ColumnDef("sweep_account_flag", "bool", False, CASH_STEWARD,
              "Whether the activity touched the cash sweep vehicle."),
    ColumnDef("reversal_flag", "bool", False, CASH_STEWARD,
              "Whether this line reverses an earlier activity."),
    ColumnDef("original_activity_id", "text", True, CASH_STEWARD,
              "The activity_id being reversed, if reversal_flag is true."),
    ColumnDef("posted_timestamp", "date", False, CASH_STEWARD,
              "Date-time the activity was posted to the ledger."),
    ColumnDef("channel", "text", False, CASH_STEWARD,
              "Payment channel used.",
              allowed_values=("ACH", "WIRE", "CHECK", "INTERNAL")),
    ColumnDef("tax_reportable", "bool", False, CASH_STEWARD,
              "Whether the activity is reportable on a tax form."),
    ColumnDef("activity_source_system", "text", False, CASH_STEWARD,
              "System the activity line was fed from.",
              allowed_values=("CUSTODY_FEED", "PAYMENTS_HUB")),
)

ADVICE_ENROLLMENTS: tuple[ColumnDef, ...] = (
    ColumnDef("enrollment_id", "text", False, ADVICE_STEWARD,
              "Unique identifier for one advice enrollment record.", is_natural_key=True),
    ColumnDef("account_id", "text", False, ADVICE_STEWARD,
              "Account enrolled in advice.", fk=("accounts", "account_id")),
    ColumnDef("enrollment_date", "date", False, ADVICE_STEWARD,
              "Date the account enrolled in the advice program."),
    ColumnDef("advice_program", "text", False, ADVICE_STEWARD,
              "Advice program the account is enrolled in.",
              allowed_values=("DIGITAL_ADVISOR", "HYBRID_ADVISOR", "FULL_SERVICE")),
    ColumnDef("enrollment_channel", "text", False, ADVICE_STEWARD,
              "Channel the enrollment was completed through. Never "
              "declared as a closed set by any source; see the profiler's "
              "finding."),
    ColumnDef("risk_profile_version", "text", False, ADVICE_STEWARD,
              "Version of the risk questionnaire used."),
    ColumnDef("advice_fee_bps", "int", False, ADVICE_STEWARD,
              "Advice fee in basis points.", min_value=0, max_value=100),
    ColumnDef("opted_in_tax_loss_harvesting", "bool", False, ADVICE_STEWARD,
              "Whether tax-loss harvesting is enabled."),
    ColumnDef("target_allocation_equity_pct", "int", False, ADVICE_STEWARD,
              "Target equity allocation percentage.", min_value=0, max_value=100),
    ColumnDef("target_allocation_fixed_income_pct", "int", False, ADVICE_STEWARD,
              "Target fixed income allocation percentage.", min_value=0, max_value=100),
    ColumnDef("rebalance_frequency", "text", False, ADVICE_STEWARD,
              "How often the account is checked for rebalancing.",
              allowed_values=("MONTHLY", "QUARTERLY", "THRESHOLD")),
    ColumnDef("last_review_date", "date", True, ADVICE_STEWARD,
              "Date of the most recent advice review."),
    ColumnDef("disengagement_date", "date", True, ADVICE_STEWARD,
              "Date the account left the advice program, if it has."),
    ColumnDef("advisor_assigned_id", "text", True, ADVICE_STEWARD,
              "Assigned advisor, for hybrid and full-service programs."),
    ColumnDef("enrollment_status", "text", False, ADVICE_STEWARD,
              "Current status of the enrollment.",
              allowed_values=("ACTIVE", "PAUSED", "TERMINATED")),
    ColumnDef("consent_document_version", "text", False, ADVICE_STEWARD,
              "Version of the advice consent document the client signed."),
)

PARTIES: tuple[ColumnDef, ...] = (
    ColumnDef("party_id", "text", False, PARTY_STEWARD,
              "Unique identifier for one party record.", is_natural_key=True),
    ColumnDef("account_id", "text", False, PARTY_STEWARD,
              "Account this party is related to.", fk=("accounts", "account_id")),
    ColumnDef("relationship_type", "text", False, PARTY_STEWARD,
              "This party's relationship to the account.",
              allowed_values=("PRIMARY", "JOINT", "BENEFICIARY", "TRUSTEE")),
    ColumnDef("first_name", "text", False, PARTY_STEWARD, "Party's first name."),
    ColumnDef("last_name", "text", False, PARTY_STEWARD, "Party's last name."),
    ColumnDef("date_of_birth", "date", False, PARTY_STEWARD, "Party's date of birth."),
    ColumnDef("tax_id_type", "text", False, PARTY_STEWARD,
              "Type of tax identifier on file.",
              allowed_values=("SSN", "ITIN", "EIN")),
    ColumnDef("tax_id_last4", "text", False, PARTY_STEWARD,
              "Last 4 digits of the tax identifier."),
    ColumnDef("citizenship_country", "text", False, PARTY_STEWARD,
              "Two-letter country of citizenship."),
    ColumnDef("residency_country", "text", False, PARTY_STEWARD,
              "Two-letter country of tax residency."),
    ColumnDef("employment_status", "text", False, PARTY_STEWARD,
              "Current employment status.",
              allowed_values=("EMPLOYED", "SELF_EMPLOYED", "RETIRED", "STUDENT", "UNEMPLOYED")),
    ColumnDef("accredited_investor_flag", "bool", False, PARTY_STEWARD,
              "Whether the party has attested to accredited investor status."),
    ColumnDef("pep_flag", "bool", False, PARTY_STEWARD,
              "Whether the party is flagged as a politically exposed person."),
    ColumnDef("kyc_status", "text", False, PARTY_STEWARD,
              "Current KYC verification status.",
              allowed_values=("VERIFIED", "PENDING", "EXPIRED")),
    ColumnDef("kyc_last_verified_date", "date", True, PARTY_STEWARD,
              "Date KYC was last verified, if ever."),
    ColumnDef("email", "text", True, PARTY_STEWARD, "Party's email address."),
    ColumnDef("phone", "text", True, PARTY_STEWARD, "Party's phone number."),
    ColumnDef("mailing_state", "text", False, PARTY_STEWARD,
              "Two-letter state of the party's mailing address."),
    ColumnDef("preferred_language", "text", False, PARTY_STEWARD,
              "Party's preferred communication language.",
              allowed_values=("EN", "ES", "ZH", "JA")),
    ColumnDef("electronic_delivery_consent", "bool", False, PARTY_STEWARD,
              "Whether the party consented to electronic delivery."),
    ColumnDef("beneficiary_percentage", "int", True, PARTY_STEWARD,
              "Percentage share, for beneficiary relationship rows.",
              min_value=0, max_value=100),
    ColumnDef("party_source_system", "text", False, PARTY_STEWARD,
              "System the party record was fed from.",
              allowed_values=("CRM", "ONBOARDING_PORTAL")),
)

FEE_SCHEDULES: tuple[ColumnDef, ...] = (
    ColumnDef("fee_schedule_id", "text", False, FEE_STEWARD,
              "Unique identifier for one fee schedule row.", is_natural_key=True),
    ColumnDef("account_id", "text", False, FEE_STEWARD,
              "Account the fee schedule applies to.", fk=("accounts", "account_id")),
    ColumnDef("fee_type", "text", False, FEE_STEWARD,
              "Category of fee.",
              allowed_values=("ADVISORY", "CUSTODY", "TRANSACTION", "FUND_EXPENSE")),
    ColumnDef("annual_fee_amount", "float", False, FEE_STEWARD,
              "Annualized fee amount, in whole dollars and cents.",
              min_value=0, max_value=50000),
    ColumnDef("billing_frequency", "text", False, FEE_STEWARD,
              "How often the fee is billed.",
              allowed_values=("MONTHLY", "QUARTERLY", "ANNUAL")),
    ColumnDef("effective_date", "date", False, FEE_STEWARD,
              "Date the fee schedule took effect."),
    ColumnDef("expiration_date", "date", True, FEE_STEWARD,
              "Date the fee schedule expires, if not open-ended."),
    ColumnDef("fee_tier", "text", False, FEE_STEWARD,
              "Pricing tier the account falls into.",
              allowed_values=("TIER1", "TIER2", "TIER3", "TIER4")),
    ColumnDef("fee_basis", "text", False, FEE_STEWARD,
              "How the fee is computed.",
              allowed_values=("BPS", "FLAT", "HYBRID")),
    ColumnDef("fee_bps_rate", "int", True, FEE_STEWARD,
              "Basis-point rate, if fee_basis uses bps.",
              min_value=0, max_value=300),
    ColumnDef("minimum_fee_amount", "float", True, FEE_STEWARD,
              "Minimum fee floor, if any.", min_value=0),
    ColumnDef("maximum_fee_amount", "float", True, FEE_STEWARD,
              "Maximum fee cap, if any.", min_value=0),
    ColumnDef("waived_flag", "bool", False, FEE_STEWARD,
              "Whether the fee is currently waived."),
    ColumnDef("waiver_reason", "text", True, FEE_STEWARD,
              "Reason for the waiver, if waived_flag is true."),
    ColumnDef("last_billed_date", "date", True, FEE_STEWARD,
              "Date the fee was last billed."),
    ColumnDef("next_bill_date", "date", True, FEE_STEWARD,
              "Date the fee will next be billed."),
    ColumnDef("fee_source_system", "text", False, FEE_STEWARD,
              "System the fee schedule row was fed from.",
              allowed_values=("BILLING_ENGINE", "LEGACY_BILLING")),
    ColumnDef("gl_account_code", "text", False, FEE_STEWARD,
              "General ledger account code the fee posts to."),
    ColumnDef("approved_by", "text", True, FEE_STEWARD,
              "Approver of record, for negotiated fee schedules."),
    ColumnDef("approval_date", "date", True, FEE_STEWARD,
              "Date the fee schedule was approved, if negotiated."),
)

GLOSSARY: dict[str, tuple[ColumnDef, ...]] = {
    "accounts": ACCOUNTS,
    "positions": POSITIONS,
    "cash_activity": CASH_ACTIVITY,
    "advice_enrollments": ADVICE_ENROLLMENTS,
    "parties": PARTIES,
    "fee_schedules": FEE_SCHEDULES,
}


def total_columns() -> int:
    return sum(len(cols) for cols in GLOSSARY.values())


def natural_key(source: str) -> str:
    for col in GLOSSARY[source]:
        if col.is_natural_key:
            return col.name
    raise ValueError(f"no natural key declared for {source}")


def columns_by_name(source: str) -> dict[str, ColumnDef]:
    return {col.name: col for col in GLOSSARY[source]}
