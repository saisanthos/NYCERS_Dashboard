import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nycers.clean import MOODYS_SCALE, RENAME, SP_SCALE, clean, normalize_rating  # noqa: E402
from nycers import metrics as m  # noqa: E402


@pytest.mark.parametrize("raw,expected", [
    ("BB-", "BB-"), ("A-p", "A-"), ("- 0", None), ("0", None), ("NR", None), (None, None)])
def test_sp_ratings(raw, expected):
    assert normalize_rating(raw, SP_SCALE) == expected


@pytest.mark.parametrize("raw,expected", [
    ("Ba1u", "BA1"), ("(P)B3", "B3"), ("BAA3", "BAA3"), ("Aaa", "AAA"), ("WR", None)])
def test_moodys_ratings(raw, expected):
    assert normalize_rating(raw, MOODYS_SCALE) == expected


def _row(**kw):
    base = {c: 0 for c in RENAME}
    base.update({"Local Currency Code": "USD", "Trade Country Name": "UNITED STATES OF AMERICA (THE)",
                 "Security Name": "X CORP", "Security Description": "", "Maturity Date": None,
                 "Period End Date": "06/30/2024", "Asset Class": "FIXED INCOME",
                 "Investment Type Name": "CORPORATE BONDS", "Major Industry Name": "CORPORATE",
                 "Minor Industry Name": "INDUSTRIAL", "Moody's Quality Rating": "Ba1",
                 "S and P Quality Rating": "BBB-", "Direct/Group Trust Holding": "Groupt Trust",
                 "Data As Of": "03/03/2025", "Base Market Value": 100.0, "Base Total Cost": 90.0,
                 "Base Unrealized Gain/Loss": 10.0})
    base.update(kw)
    return base


def test_clean_rules():
    raw = pd.DataFrame([
        _row(),
        _row(),                                   # exact duplicate
        _row(**{"Period End Date": "12/31/1899"}),  # placeholder
        _row(**{"Period End Date": "06/30/2015"}),  # orphan year
        _row(**{"Security Name": "Y", "Major Industry Name": "VENTURE CAPITAL", "Asset Class": "EQUITY"}),
    ])
    df, log = clean(raw)
    assert len(df) == 2
    assert log["dropped_exact_duplicates"] == 1
    assert log["dropped_placeholder_1899_rows"] == 1
    assert log["dropped_orphan_2015_rows"] == 1
    bond = df[df.security_name == "X CORP"].iloc[0]
    assert bond.country == "UNITED STATES"
    assert bond.holding_vehicle == "Group Trust"
    # BBB- (IG) vs Ba1 (HY): the worse rating wins
    assert bond.credit_bucket == "High yield"
    assert bond.fiscal_year == 2024
    assert df[df.security_name == "Y"].iloc[0].segment == "Private markets"


@pytest.mark.skipif(not m.CLEAN_PATH.exists(), reason="processed data not built")
def test_processed_data_invariants():
    df = m.load()
    assert sorted(df.fiscal_year.unique()) == [2017, 2019, 2020, 2021, 2022, 2023, 2024]
    assert not df.duplicated().any()
    mix = m.segment_mix(df)
    assert mix.groupby("fiscal_year")["share"].sum().round(6).eq(1).all()
    tot = m.totals_by_year(df).set_index("fiscal_year")["market_value"]
    assert 85e9 < tot[2024] < 88e9
