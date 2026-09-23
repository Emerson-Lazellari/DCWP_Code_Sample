Local Law 174 Spend Filter
==========================

What it does
------------
Code I wrote for the NYC Comptroller's FY23 Annual Report on M/WBE Procurement.
It applies Local Law 174's inclusion and exclusion rules to City payment records
(Checkbook spend) and totals spend by agency, ownership group, M/WBE category,
and industry. The filtered spend is the base for the report's agency
comparisons, including the z-score and cohort rankings in my writing sample.

Public report:
https://comptroller.nyc.gov/reports/annual-report-on-m-wbe-procurement-fy23-findings-and-recommendations/

Rules
-----
The rules follow the FY23 report's documented methodology: the Local Law 174
inclusion/exclusion rules and the MTG Industry Mapping Rules (the Checkbook NYC
industry mapping).

Agency groups
  LL174              mayoral agencies only
  All Rated          mayoral agencies plus DOE (040) and the Comptroller (015)
  Elected Officials  All Rated plus elected officials' offices
                     (010-014, 101-103, 901-905)

Industry (MTG Industry Mapping Rules; applied in order, first match wins)
   1. Award category 023 and contract type 51 or 70      Professional Services
   2. Contract type 53 (design-build)                    Construction
   3. Award category 030 or 040 and contract type 70     Standard Services
   4. Contract type 70                                   Human Services
   5. Contract type 05, 48, or 52                        Construction
   6. Contract type 46, 51, 81, or 82                    Goods
   7. Award category 300                                 Goods
   8. Award category 001-005, 023, 200, 888              Professional Services
   9. Award category 010-022, 024-029, 035, 053          Standard Services
  10. Award category 030, 040-043, 050-068, 100-103      Human Services
  11-15. Expense category lists (see code)               Construction, Goods,
                                                         Human Services,
                                                         Professional Services,
                                                         Standard Services
  No match                                               Unclassified

  Code-based rules come first because contract type and award category describe
  the procurement itself; expense category is a fallback.

Exclusions (a payment is excluded at the first rule it meets)
  - Agency not in the agency group
  - Award method not subject to participation goals (e.g., sole source,
    emergency, government-to-government)
  - Contract type excluded by program design
  - Industry: human services, or goods over $1 million
  - Vendor: NYC Economic Development Corporation, NYC Housing Authority
  - "Individuals & Others" payments with no prime contract number (removed
    before the rules run; they can't be tied to a covered procurement)

  Award method, contract type, and contract value come from the prime contract,
  so payments under master agreements carry their parent contract's
  characteristics.

Steps
-----
1. Assign an industry to every payment.
2. Drop "Individuals & Others" payments with no prime contract number.
3. For each agency group, flag every payment Yes/No with the exclusion reason.
4. Reconcile: rows and dollars by reason must add back to the input, and the
   output totals must equal the included spend. The script stops if they don't.
5. Write totals by agency, ownership group, M/WBE category, and industry.

In production the script ran once per fiscal year on the full Checkbook extract.

Data
----
sample_spend.csv is synthetic (30 rows; fictional vendors and amounts) with the
same columns as the production extract. Rows are chosen to trigger each rule
and exclusion at least once. No real City data is included.

How to run
----------
  pip install -r requirements.txt
  python ll174_spend_filter.py                  (uses sample_spend.csv)
  python ll174_spend_filter.py <extract.csv>    (any file with the same columns)

The code file is also provided as ll174_spend_filter.txt; rename it to .py to run.

Output
------
Console: reconciliation table for each agency group.
./output/ll174_totals.csv
./output/all_rated_totals.csv
./output/elected_officials_totals.csv

Notes
-----
The original was an exploratory Jupyter notebook. For sharing I consolidated the
three duplicated agency-group filters into one function, added exclusion reasons
and the reconciliation checks, replaced local file paths, and aligned the rules
with the documented FY23 methodology.
