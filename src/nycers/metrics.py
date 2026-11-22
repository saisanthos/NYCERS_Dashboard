"""Portfolio-level aggregations shared by the notebook and the dashboard.

All functions take the cleaned holdings table (one row per position per
fiscal-year snapshot) and return tidy DataFrames. Values are in USD.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CLEAN_PATH = ROOT / "data" / "processed" / "holdings_clean.parquet"
SEGMENT_ORDER = ["Public equity", "Private markets", "Fixed income", "Cash"]


def load(path: Path | str = CLEAN_PATH) -> pd.DataFrame:
    return pd.read_parquet(path)


def _share(df: pd.DataFrame, by: str, value: str = "market_value") -> pd.DataFrame:
    out = df.groupby(["fiscal_year", by], observed=True)[value].sum().reset_index()
    out["share"] = out[value] / out.groupby("fiscal_year")[value].transform("sum")
    return out


def totals_by_year(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("fiscal_year").agg(
        market_value=("market_value", "sum"),
        total_cost=("total_cost", "sum"),
        unrealized_gl=("unrealized_gl", "sum"),
        positions=("market_value", "size"),
        securities=("security_name", "nunique"),
    )
    g["unrealized_pct_of_cost"] = g["unrealized_gl"] / g["total_cost"]
    return g.reset_index()


def segment_mix(df: pd.DataFrame) -> pd.DataFrame:
    out = _share(df, "segment")
    out["segment"] = pd.Categorical(out["segment"], SEGMENT_ORDER, ordered=True)
    return out.sort_values(["fiscal_year", "segment"])


def sector_mix(df: pd.DataFrame, segment: str = "Public equity") -> pd.DataFrame:
    return _share(df[df["segment"] == segment], "major_industry")


def us_share(df: pd.DataFrame, segment: str = "Public equity") -> pd.DataFrame:
    sub = df[df["segment"] == segment]
    g = sub.groupby(["fiscal_year", "is_us"])["market_value"].sum().unstack(fill_value=0)
    return pd.DataFrame({"fiscal_year": g.index, "us_share": (g[True] / g.sum(axis=1)).values})


def country_mix(df: pd.DataFrame, segment: str = "Public equity", exclude_us: bool = True) -> pd.DataFrame:
    sub = df[df["segment"] == segment]
    if exclude_us:
        sub = sub[~sub["is_us"]]
    return _share(sub, "country")


def top_holdings(df: pd.DataFrame, year: int, n: int = 10, segment: str | None = "Public equity") -> pd.DataFrame:
    sub = df[df["fiscal_year"] == year]
    if segment:
        sub = sub[sub["segment"] == segment]
    g = sub.groupby("security_name", observed=True)["market_value"].sum().sort_values(ascending=False)
    total = sub["market_value"].sum()
    out = g.head(n).rename("market_value").reset_index()
    out["share_of_segment"] = out["market_value"] / total
    return out


def concentration(df: pd.DataFrame, segment: str = "Public equity") -> pd.DataFrame:
    """Top-10 share and Herfindahl-Hirschman index of issuer weights, by year."""
    rows = []
    for year, sub in df[df["segment"] == segment].groupby("fiscal_year"):
        w = sub.groupby("security_name", observed=True)["market_value"].sum()
        w = w[w > 0]
        w = w / w.sum()
        rows.append({"fiscal_year": year, "top10_share": w.nlargest(10).sum(),
                     "hhi": float((w ** 2).sum()),
                     "effective_n": float(1 / (w ** 2).sum()), "issuers": len(w)})
    return pd.DataFrame(rows)


def credit_mix(df: pd.DataFrame) -> pd.DataFrame:
    fi = df[df["segment"] == "Fixed income"].copy()
    fi["credit_bucket"] = fi["credit_bucket"].astype("string").fillna("Not rated")
    return _share(fi, "credit_bucket")


def fixed_income_profile(df: pd.DataFrame) -> pd.DataFrame:
    """Value-weighted coupon, maturity and rating for the bond book."""
    all_fi = df[df["segment"] == "Fixed income"]
    fi = all_fi[all_fi["market_value"] > 0]  # weights must be positive

    def wavg(s: pd.DataFrame, col: str) -> float:
        m = s[col].notna()
        return float(np.average(s.loc[m, col], weights=s.loc[m, "market_value"])) if m.any() else np.nan

    rows = []
    for year, s in fi.groupby("fiscal_year"):
        rows.append({"fiscal_year": year,
                     "wavg_coupon": wavg(s, "coupon_rate"),
                     "wavg_years_to_maturity": wavg(s[s["years_to_maturity"] > 0], "years_to_maturity"),
                     "wavg_rating_notch": wavg(s, "rating_notch"),
                     "unrealized_gl": all_fi.loc[all_fi["fiscal_year"] == year, "unrealized_gl"].sum(),
                     "unrealized_pct_of_cost": (all_fi.loc[all_fi["fiscal_year"] == year, "unrealized_gl"].sum()
                                                / all_fi.loc[all_fi["fiscal_year"] == year, "total_cost"].sum())})
    return pd.DataFrame(rows)


def maturity_ladder(df: pd.DataFrame, year: int) -> pd.DataFrame:
    fi = df[(df["segment"] == "Fixed income") & (df["fiscal_year"] == year)]
    bins = [0, 1, 3, 5, 10, 20, 100]
    labels = ["<1y", "1-3y", "3-5y", "5-10y", "10-20y", "20y+"]
    b = pd.cut(fi["years_to_maturity"], bins=bins, labels=labels)
    out = fi.groupby(b, observed=False)["market_value"].sum().rename("market_value").reset_index()
    out.columns = ["maturity_bucket", "market_value"]
    out["share"] = out["market_value"] / out["market_value"].sum()
    return out


def unrealized_by_segment(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(["fiscal_year", "segment"], observed=True)[["unrealized_gl", "total_cost"]].sum().reset_index()
    g["unrealized_pct_of_cost"] = g["unrealized_gl"] / g["total_cost"]
    return g


def currency_mix(df: pd.DataFrame) -> pd.DataFrame:
    return _share(df, "currency")
