"""
Local Law 174 spend filter (NYC Comptroller, Annual Report on M/WBE Procurement).

Applies Local Law 174 inclusion and exclusion rules to FMS payment records,
assigns each payment an industry, and totals spend by agency, ownership group,
M/WBE category, and industry for three agency groups:

    LL174              mayoral agencies (subject to Local Law 174)
    All Rated          mayoral agencies plus DOE and the Comptroller
    Elected Officials  All Rated agencies plus elected officials' offices

Rules follow the FY23 report's documented methodology: the Local Law 174
inclusion/exclusion rules and the MTG Industry Mapping Rules.

The script runs once per fiscal year extract. Each agency group produces a
totals CSV in ./output and a reconciliation of rows and dollars kept vs. excluded.

Usage:
    python ll174_spend_filter.py                  # uses sample_spend.csv
    python ll174_spend_filter.py FY2023_Extract.csv
"""

import sys
from pathlib import Path

import pandas as pd

GREATER_THAN_1M = "Greater than $1 Million"

EXCLUDED_AWARD_METHOD_CODES = {
    5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17,
    18, 24, 25, 26, 28, 29, 40, 41, 42, 43, 44, 45,
    51, 61, 62, 68, 78, 79, 99, 100, 101, 102, 103,
    104, 105, 106, 107, 251, 511,
}

EXCLUDED_CONTRACT_TYPE_CODES = {
    15, 17, 18, 20, 25, 26, 29, 30, 35, 36, 39, 40, 41,
    42, 43, 44, 46, 65, 68, 70, 72, 78, 79, 83, 85, 88,
}

EXCLUDED_VENDORS = {
    "NYC Economic Development Corporation",
    "New York City Housing Authority",
}

LL174_AGENCY_CODES = {
    2, 17, 25, 30, 32, 54, 56, 57, 68, 69,
    71, 72, 96, 125, 126, 136, 156, 226, 260, 781,
    801, 806, 810, 816, 820, 826, 827, 829, 836, 841,
    846, 850, 856, 857, 858, 860, 866,
}

ALL_RATED_AGENCY_CODES = {
    2, 17, 15, 25, 30, 32, 40, 54, 56, 57, 68, 69,
    71, 72, 96, 125, 126, 136, 156, 226, 260, 781,
    801, 806, 810, 816, 820, 826, 827, 829, 836, 841,
    846, 850, 856, 857, 858, 860, 866,
}

ELECTED_OFFICIALS_AGENCY_CODES = {
    2, 10, 11, 12, 13, 14, 15, 17, 25,
    30, 32, 40, 54, 56, 57, 68, 69, 71, 72,
    96, 101, 102, 103, 125, 126, 136, 156,
    226, 260, 781, 801, 806, 810, 816, 820,
    826, 827, 829, 836, 841, 846, 850, 856,
    857, 858, 860, 866, 901, 902, 903, 904, 905,
}

AGENCY_GROUPS = {
    "LL174": LL174_AGENCY_CODES,
    "All Rated": ALL_RATED_AGENCY_CODES,
    "Elected Officials": ELECTED_OFFICIALS_AGENCY_CODES,
}

# (label, woman-owned, minority-owned)
OWNERSHIP_GROUPS = [
    ("WBEs", True, True),         # woman- and minority-owned
    ("Caucasian", True, False),   # woman-owned, not minority-owned
    ("MBEs", False, True),        # minority-owned, not woman-owned
    ("Other", False, False),      # neither
]

CONSTRUCTION_EXPENSES = {
    "CONSTRUCTION-BUILDINGS", "DEMOLITION", "IOTB CONSTRUCTION",
    "LEASEHOLD IMP CONSTRUCTION", "MAINT & OPER OF INFRASTRUCTURE",
    "POLLUTION REMEDIATION OBLIGATIONS",
}

GOODS_EXPENSES = {
    "AUTOMOTIVE SUPPLIES & MATERIAL", "BOOKS-OTHER", "CAPITAL PURCHASED EQUIPMENT",
    "CLEANING SUPPLIES", "COST SNACKS BREAKFAST-LUNCH PG", "DATA PROCESSING SUPPLIES",
    "EQUIPMENT GENERAL", "FOOD & FORAGE SUPPLIES", "FUEL OIL",
    "INSTRUCTIONL EQUIPMNT-BOE ONLY", "LEASING OF MISC EQUIP", "LIBRARY BOOKS",
    "MAINTENANCE SUPPLIES", "MEDICAL,SURGICAL & LAB EQUIP", "MEDICAL,SURGICAL & LAB SUPPLY",
    "MOTOR VEHICLE EQUIPMENT", "MOTOR VEHICLE FUEL", "MOTOR VEHICLES", "OFFICE EQUIPMENT",
    "OFFICE FURITURE", "PRINTING SUPPLIES", "PURCH DATA PROCESSING EQUIPT",
    "RENTAL-DATA PROCESSING EQUIP", "SECURITY EQUIPMENT", "SUPPLIES + MATERIALS - GENERAL",
    "TELECOMMUNICATIONS EQUIPMENT",
}

HUMAN_SERVICES_EXPENSES = {
    "AID TO DEPENDENT CHILDREN", "AIDS SERVICES", "CHILD WELFARE SERVICES",
    "CHILDRENS CHARITABLE INSTITUTN", "COMMUNITY CONSULTANT CONTRACTS", "DAY CARE OF CHILDREN",
    "DIRECT FOSTER CARE OF CHLD-MEDICAL PAYMT", "DIRECT FOSTER CARE OF CHLD-NOT REPORTBLE",
    "DIRECT FOSTER CARE OF CHLD-OTHER PAYMTS", "DONAT PAT INMATE & DISCHG PRIS",
    "EDUCATION & REC FOR YOUTH PRGM", "EMPLOYMENT SERVICES", "HEAD START", "HOME CARE SERVICES",
    "HOME CARE SERVICES-REIMBURSABLE", "HOMELESS FAM SVCS-MEDICAL SVCS", "HOMELESS FAMILY SERVICES",
    "HOMELESS IND SVCS-MEDICAL SVCS", "HOMEMAKING SERVICES", "HOSPITALS CONTRACTS",
    "MENTAL HYGIENE SERVICES", "PAYMENTS TO DELEGATE AGENCIES", "PROTECTIVE SERVICES FOR ADULTS",
    "SOCIAL SERVICES - GENERAL", "SOCIAL SERVICES GENERAL", "SOCIAL SERVICES-GENERAL-REIMBURSABLE",
    "SPEC ED FACIL INST FOST CARE", "SPECIAL CLINICAL SERVICES", "SUBSIDIZED ADOPTION",
}

PROFESSIONAL_SERVICES_EXPENSES = {
    "ARCH/ENGINEERING FEES", "DESIGN-CONSULTANT-BUILDINGS", "DESIGN-CONSULTANT-IOTB",
    "DESIGN-CONSULTANT-LAND", "PROF SERV ACCTING & AUDITING", "PROF SERV COMPUTER SERVICES",
    "PROF SERV CURRIC & PROF DEVEL", "PROF SERV DIRECT EDUC SERV", "PROF SERV ENGINEER & ARCHITECT",
    "PROF SERV LEGAL SERVICES", "PROF SERV OTHER",
}

STANDARD_SERVICES_EXPENSES = {
    "ADVERTISING", "CLEANING SERVICES", "CONTRACTUAL SERVICES GENERAL",
    "DATA PROCESSING EQUIPMENT MAINTENANCE", "DATA PROCESSING SERVICES", "IN REM MAINTENANCE COSTS",
    "MAINT & REP GENERAL", "MAINT & REP MOTOR VEH EQUIP", "MAINT & REP OF MOTOR VEH EQUIP",
    "MAINTENANCE REPAIRS - GENERAL", "RENTALS OF MISC.EQUIP", "LEASING OF DATA PROC EQUIP",
    "MUNICIPAL WASTE EXPORT", "OFFICE EQUIPMENT MAINTENANCE", "PAY FOR SURETY BOND/INSUR PREM",
    "POSTAGE", "PRINTING CONTRACTS", "SECURITY SERVICES", "SNOW REMOVAL SERVICES",
    "TELECOMMUNICATIONS MAINT", "TELEPHONE & OTHER COMMUNICATNS", "TEMPORARY SERVICES",
    "TRAINING CITY EMPLOYEES", "TRAINING PRGM CITY EMPLOYEES",
}


PROFESSIONAL_SERVICES_AWARD_CATEGORIES = {1, 2, 3, 4, 5, 23, 200, 888}
STANDARD_SERVICES_AWARD_CATEGORIES = set(range(10, 23)) | set(range(24, 30)) | {35, 53}
HUMAN_SERVICES_AWARD_CATEGORIES = {30, 40, 41, 42, 43} | set(range(50, 69)) | set(range(100, 104))


def extended_industry_category(row):
    """Assign an industry using the MTG Industry Mapping Rules, in order; the
    first match wins, so contract type and award category codes take precedence
    over expense category."""
    award_category = row["Award Category Code"]
    contract_type = row["Prime CT Code"]
    expense = row["Expense Category"]

    # Rules 1-6: contract type, alone or with award category
    if award_category == 23 and contract_type in (51, 70):
        return "Professional Services"
    if contract_type == 53:  # design-build
        return "Construction"
    if award_category in (30, 40) and contract_type == 70:
        return "Standard Services"
    if contract_type == 70:
        return "Human Services"
    if contract_type in (5, 48, 52):
        return "Construction"
    if contract_type in (46, 51, 81, 82):
        return "Goods"
    # Rules 7-10: award category
    if award_category == 300:
        return "Goods"
    if award_category in PROFESSIONAL_SERVICES_AWARD_CATEGORIES:
        return "Professional Services"
    if award_category in STANDARD_SERVICES_AWARD_CATEGORIES:
        return "Standard Services"
    if award_category in HUMAN_SERVICES_AWARD_CATEGORIES:
        return "Human Services"
    # Rules 11-15: expense category
    if expense in CONSTRUCTION_EXPENSES:
        return "Construction"
    if expense in GOODS_EXPENSES:
        return "Goods"
    if expense in HUMAN_SERVICES_EXPENSES:
        return "Human Services"
    if expense in PROFESSIONAL_SERVICES_EXPENSES:
        return "Professional Services"
    if expense in STANDARD_SERVICES_EXPENSES:
        return "Standard Services"
    return "Unclassified"


def ll174_status(row, agency_codes):
    """Return ('Yes'|'No', reason) for whether a payment is included for the agency group."""
    over_1m = row["Prime Contract Classification"] == GREATER_THAN_1M

    if row["Contracting Agency Code"] not in agency_codes:
        return "No", "agency not in group"
    if row["Prime AM Code"] in EXCLUDED_AWARD_METHOD_CODES:
        return "No", "excluded award method"
    if row["Prime CT Code"] in EXCLUDED_CONTRACT_TYPE_CODES:
        return "No", "excluded contract type"
    if row["Industry"] == "Human Services":
        return "No", "human services"
    if row["Industry"] == "Goods" and over_1m:
        return "No", "goods over $1M"
    if row["Payee Name"] in EXCLUDED_VENDORS:
        return "No", "excluded vendor"
    return "Yes", "included"


def prepare(df):
    """Add industry and ownership flags; drop 'Individuals & Others' payments
    that have no prime contract number."""
    df = df.copy()
    df["Industry"] = df.apply(extended_industry_category, axis=1)
    df["Minority Owned Business"] = df["Minority Owned Business"].eq("Y")
    df["Woman Owned Business"] = df["Woman Owned Business"].eq("Y")

    no_contract = (df["M/WBE Category"] == "Individuals & Others") & df["Prime Contract Number"].isna()
    print(f"Individuals & Others without a contract number dropped: {no_contract.sum():,} rows, "
          f"${df.loc[no_contract, 'Check Amount'].sum():,.0f}")
    return df[~no_contract]


def totals_by_ownership(included):
    """Total check amount by agency, ownership group, M/WBE category, and industry."""
    frames = []
    for label, woman_owned, minority_owned in OWNERSHIP_GROUPS:
        group = included[
            (included["Woman Owned Business"] == woman_owned)
            & (included["Minority Owned Business"] == minority_owned)
        ]
        totals = (group.groupby(["Contracting Agency Name", "M/WBE Category", "Industry"])["Check Amount"]
                  .sum()
                  .reset_index())
        totals["Ownership Group"] = label
        frames.append(totals)

    result = pd.concat(frames, ignore_index=True).rename(columns={"Contracting Agency Name": "Agency"})
    return result[["Agency", "Ownership Group", "M/WBE Category", "Industry", "Check Amount"]].sort_values(
        ["Agency", "Ownership Group", "M/WBE Category", "Industry"])


def reconcile(name, flagged, totals):
    """Print rows and dollars by status/reason and confirm nothing was lost."""
    summary = (flagged.groupby(["status", "reason"])["Check Amount"]
               .agg(rows="size", dollars="sum")
               .reset_index())
    print(f"\n=== {name} ===")
    print(summary.to_string(index=False, formatters={"dollars": "${:,.0f}".format}))

    kept = flagged[flagged["status"] == "Yes"]
    assert summary["rows"].sum() == len(flagged), "row counts do not reconcile"
    assert abs(summary["dollars"].sum() - flagged["Check Amount"].sum()) < 0.01, "dollars do not reconcile"
    assert abs(totals["Check Amount"].sum() - kept["Check Amount"].sum()) < 0.01, "output total != kept total"
    print(f"Kept {len(kept):,} of {len(flagged):,} rows; ${kept['Check Amount'].sum():,.0f} "
          f"of ${flagged['Check Amount'].sum():,.0f}. Output total matches.")


def main():
    base = Path(__file__).resolve().parent
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else base / "sample_spend.csv"
    output_dir = base / "output"
    output_dir.mkdir(exist_ok=True)

    raw = pd.read_csv(input_path, low_memory=False)
    print(f"Loaded {len(raw):,} rows, ${raw['Check Amount'].sum():,.0f} from {input_path.name}")
    df = prepare(raw)

    for name, agency_codes in AGENCY_GROUPS.items():
        flagged = df.copy()
        flagged[["status", "reason"]] = flagged.apply(
            ll174_status, axis=1, result_type="expand", agency_codes=agency_codes)
        totals = totals_by_ownership(flagged[flagged["status"] == "Yes"])
        reconcile(name, flagged, totals)

        out_file = output_dir / f"{name.lower().replace(' ', '_')}_totals.csv"
        totals.to_csv(out_file, index=False)
        print(f"Wrote {out_file.relative_to(base)}")


if __name__ == "__main__":
    main()
