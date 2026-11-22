# Raw data

Put the raw export here as `nycers_holdings_20251008.csv`. It isn't committed because it is 57 MB.

**Source:** NYC Open Data, *Office of the Comptroller: NYC Employee Retirement System (NYCERS) Holdings Data*.
Search for the title on https://opendata.cityofnewyork.us and export it as CSV.
The file used here was exported on 2025-10-08 (299,944 rows, 25 columns).

Then rebuild the clean table:

```bash
PYTHONPATH=src python -m nycers.clean --raw data/raw/nycers_holdings_20251008.csv
```
