"""Clean the raw NYCERS holdings export into one tidy, analysis-ready table.

Usage:
    python -m nycers.clean --raw data/raw/<file>.csv --out data/processed/holdings_clean.parquet

Every rule below is logged, so the data-quality report can be regenerated
from scratch rather than written by hand.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

RENAME = {
    "Local Currency Code": "currency",
    "Trade Country Name": "country",
    "Security Name": "security_name",
    "Security Description": "security_description",
    "Maturity Date": "maturity_date",
    "Interest Rate": "coupon_rate",
    "Original Face": "original_face",
    "Shares/Par Value": "shares_par",
    "Base Market Value": "market_value",
    "Base Total Cost": "total_cost",
    "Base Unrealized Gain/Loss": "unrealized_gl",
    "Base Accrued Interest": "accrued_interest",
    "Local Market Value": "local_market_value",
    "Local Total Cost Amount": "local_total_cost",
    "Local Unrealized Gain/Loss": "local_unrealized_gl",
    "Local Accrued Interest": "local_accrued_interest",
    "Period End Date": "period_end",
    "Asset Class": "asset_class",
    "Investment Type Name": "investment_type",
    "Major Industry Name": "major_industry",
    "Minor Industry Name": "minor_industry",
    "Moody's Quality Rating": "moodys_rating",
    "S and P Quality Rating": "sp_rating",
    "Direct/Group Trust Holding": "holding_vehicle",
    "Data As Of": "data_as_of",
}

# The source uses two spellings for the US; everything else is left as published.
COUNTRY_FIX = {"UNITED STATES OF AMERICA (THE)": "UNITED STATES"}

# Standard S&P / Moody's ladders, best to worst. Index = numeric notch (1 = AAA).
SP_SCALE = ["AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-",
            "BB+", "BB", "BB-", "B+", "B", "B-", "CCC+", "CCC", "CCC-", "CC", "C", "D"]
MOODYS_SCALE = ["AAA", "AA1", "AA2", "AA3", "A1", "A2", "A3", "BAA1", "BAA2", "BAA3",
                "BA1", "BA2", "BA3", "B1", "B2", "B3", "CAA1", "CAA2", "CAA3", "CA", "C"]
INVESTMENT_GRADE_MAX_NOTCH = 10  # BBB- / Baa3

PRIVATE_MARKETS_LABEL = "VENTURE CAPITAL"  # source label for LP interests


def normalize_rating(value, scale: list[str]) -> str | None:
    """Map messy rating strings ('Ba1u', '(P)B3', 'A-p', 'BAA3', '- 0') onto a scale."""
    if pd.isna(value):
        return None
    s = str(value).strip().upper()
    s = re.sub(r"^\(P\)", "", s)          # provisional prefix
    s = re.sub(r"(?<=[A-Z0-9+\-])[UP]$", "", s)  # 'u' unsolicited / 'p' provisional suffix
    return s if s in scale else None      # '0', '- 0', 'NR', 'WR' -> not rated


def notch(rating: str | None, scale: list[str]) -> float:
    return float(scale.index(rating) + 1) if rating in scale else np.nan


def clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    log: dict[str, int | float] = {"raw_rows": len(raw)}
    df = raw.rename(columns=RENAME).copy()

    # 1. Placeholder rows: dated 12/31/1899 with every field zeroed.
    placeholder = df["period_end"].eq("12/31/1899")
    log["dropped_placeholder_1899_rows"] = int(placeholder.sum())
    df = df[~placeholder]

    # 2. Fully blank rows (no security, no values).
    blank = df["security_name"].isna() & df["market_value"].isna()
    log["dropped_blank_rows"] = int(blank.sum())
    df = df[~blank]

    # 3. Exact duplicate rows. Their combined value is immaterial (logged below).
    dup = df.duplicated(keep="first")
    log["dropped_exact_duplicates"] = int(dup.sum())
    log["duplicate_market_value_usd"] = float(df.loc[dup, "market_value"].sum())
    df = df[~dup]

    # 4. A single stray row dated 2015 (no other 2015 data exists).
    df["period_end"] = pd.to_datetime(df["period_end"], format="%m/%d/%Y")
    orphan = df["period_end"].dt.year.eq(2015)
    log["dropped_orphan_2015_rows"] = int(orphan.sum())
    df = df[~orphan]

    # Dates. NYC's fiscal year ends June 30, so 06/30/2024 = FY2024.
    df["fiscal_year"] = df["period_end"].dt.year.astype("int16")
    df["maturity_date"] = pd.to_datetime(df["maturity_date"], format="%m/%d/%Y", errors="coerce")
    df["data_as_of"] = pd.to_datetime(df["data_as_of"], format="%m/%d/%Y", errors="coerce")
    df["years_to_maturity"] = (df["maturity_date"] - df["period_end"]).dt.days / 365.25

    # Text normalisation.
    for col in ["country", "asset_class", "investment_type", "major_industry",
                "minor_industry", "currency", "security_name"]:
        df[col] = df[col].astype("string").str.strip()
    df["country"] = df["country"].replace(COUNTRY_FIX)
    df["holding_vehicle"] = (df["holding_vehicle"].astype("string").str.strip()
                             .replace({"Groupt Trust": "Group Trust"}))
    log["fixed_groupt_trust_typo"] = int(raw["Direct/Group Trust Holding"].eq("Groupt Trust").sum())

    # Ratings: harmonise, then a single 'best available' notch for analysis.
    df["sp_rating"] = df["sp_rating"].map(lambda v: normalize_rating(v, SP_SCALE))
    df["moodys_rating"] = df["moodys_rating"].map(lambda v: normalize_rating(v, MOODYS_SCALE))
    sp_n = df["sp_rating"].map(lambda r: notch(r, SP_SCALE))
    md_n = df["moodys_rating"].map(lambda r: notch(r, MOODYS_SCALE))
    # Conservative convention: use the lower (worse) of the two ratings when both exist.
    df["rating_notch"] = np.fmax(sp_n, md_n)
    df["credit_bucket"] = np.select(
        [df["rating_notch"].le(INVESTMENT_GRADE_MAX_NOTCH), df["rating_notch"].gt(INVESTMENT_GRADE_MAX_NOTCH)],
        ["Investment grade", "High yield"], default="Not rated")
    df.loc[df["asset_class"].ne("FIXED INCOME"), "credit_bucket"] = pd.NA

    # Readable portfolio segment used throughout the analysis and dashboard.
    df["segment"] = np.select(
        [df["major_industry"].eq(PRIVATE_MARKETS_LABEL),
         df["asset_class"].eq("EQUITY"),
         df["asset_class"].eq("FIXED INCOME")],
        ["Private markets", "Public equity", "Fixed income"],
        default="Cash")
    df["is_us"] = df["country"].eq("UNITED STATES")

    # Derived value metric. NOTE: this is unrealised gain since purchase,
    # not an annual return; cost basis differs by purchase date.
    cost = df["total_cost"].where(df["total_cost"].abs() > 0)
    df["unrealized_pct_of_cost"] = df["unrealized_gl"] / cost

    keep = ["fiscal_year", "period_end", "data_as_of", "segment", "asset_class",
            "investment_type", "major_industry", "minor_industry", "security_name",
            "security_description", "country", "is_us", "currency", "holding_vehicle",
            "shares_par", "market_value", "total_cost", "unrealized_gl",
            "unrealized_pct_of_cost", "accrued_interest", "coupon_rate", "maturity_date",
            "years_to_maturity", "sp_rating", "moodys_rating", "rating_notch", "credit_bucket"]
    df = df[keep].reset_index(drop=True)
    for col in ["segment", "asset_class", "investment_type", "major_industry",
                "minor_industry", "country", "currency", "holding_vehicle",
                "sp_rating", "moodys_rating", "credit_bucket"]:
        df[col] = df[col].astype("category")
    log["clean_rows"] = len(df)
    log["fiscal_years"] = sorted(int(y) for y in df["fiscal_year"].unique())
    return df, log


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw", required=True, type=Path)
    ap.add_argument("--out", default=Path("data/processed/holdings_clean.parquet"), type=Path)
    args = ap.parse_args()
    raw = pd.read_csv(args.raw, low_memory=False)
    df, log = clean(raw)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.out, index=False, compression="zstd")
    (args.out.parent / "cleaning_log.json").write_text(json.dumps(log, indent=2))
    print(json.dumps(log, indent=2))


if __name__ == "__main__":
    main()
