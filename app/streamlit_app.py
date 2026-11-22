"""NYCERS Holdings Explorer: interactive companion to notebooks/nycers_analysis.ipynb.

Run locally:  streamlit run app/streamlit_app.py
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nycers import metrics as m  # noqa: E402
from nycers.style import (ACCENT, CREDIT_COLORS, GAIN, LOSS, NEUTRAL,  # noqa: E402
                          SEGMENT_COLORS)

st.set_page_config(page_title="NYCERS Holdings Explorer", page_icon="📊", layout="wide")


@st.cache_data(show_spinner="Loading holdings…")
def load() -> pd.DataFrame:
    return m.load(ROOT / "data" / "processed" / "holdings_clean.parquet")


def fmt_bn(x: float) -> str:
    return f"${x / 1e9:,.1f}B"


def style(fig: go.Figure, height: int = 380, legend: bool = True) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=40, b=10), hovermode="closest",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="top", y=-0.22, x=0, title=None) if legend else None,
        showlegend=legend, font=dict(size=13),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.18)", zeroline=False)
    return fig


df = load()
YEARS = sorted(df["fiscal_year"].unique())

# ---------------- Sidebar ----------------
st.sidebar.title("NYCERS Holdings Explorer")
year = st.sidebar.select_slider("Fiscal year (ends June 30)", options=YEARS, value=YEARS[-1])
st.sidebar.caption(
    "Source: NYC Office of the Comptroller, NYCERS Holdings Data (NYC Open Data). "
    "FY2018 was not published. Values are market value in USD at June 30.")
st.sidebar.markdown("Code, cleaning rules and full analysis: see the project README on GitHub.")

snap = df[df["fiscal_year"] == year]
prev_years = [y for y in YEARS if y < year]
prev = df[df["fiscal_year"] == prev_years[-1]] if prev_years else None

st.title(f"Where NYCERS's money was on June 30, {year}")

# ---------------- KPI row ----------------
tot = snap["market_value"].sum()
seg = snap.groupby("segment", observed=True)["market_value"].sum()
c1, c2, c3, c4 = st.columns(4)
delta = f"{tot / prev['market_value'].sum() - 1:+.1%} vs FY{prev_years[-1]}" if prev is not None else None
c1.metric("Total holdings", fmt_bn(tot), delta)
c2.metric("Private markets share", f"{seg.get('Private markets', 0) / tot:.1%}")
c3.metric("Positions", f"{len(snap):,}")
fi_snap = snap[snap["segment"] == "Fixed income"]
c4.metric("Bond book vs cost", f"{fi_snap['unrealized_gl'].sum() / fi_snap['total_cost'].sum():+.1%}",
          help="Unrealized gain/loss as % of cost. Not an annual return.")

tab_overview, tab_equity, tab_fi, tab_explore, tab_about = st.tabs(
    ["Overview", "Public equity", "Fixed income", "Holdings explorer", "About the data"])

# ---------------- Overview ----------------
with tab_overview:
    mix = m.segment_mix(df)
    mix["segment"] = mix["segment"].astype(str)
    left, right = st.columns(2)
    with left:
        mix["fy"] = mix["fiscal_year"].astype(str)
        mix["value_bn"] = mix["market_value"] / 1e9
        fig = px.bar(mix, x="fy", y="value_bn", color="segment",
                     color_discrete_map=SEGMENT_COLORS, category_orders={"segment": m.SEGMENT_ORDER},
                     labels={"fy": "Fiscal year", "value_bn": "Market value", "segment": "Segment"},
                     title="Total holdings by segment")
        fig.update_xaxes(type="category")
        fig.update_traces(marker_line_color="white", marker_line_width=1.5,
                          hovertemplate="%{fullData.name}<br>FY%{x}: $%{y:,.1f}B<extra></extra>")
        fig.update_yaxes(tickprefix="$", ticksuffix="B")
        st.plotly_chart(style(fig), width="stretch")
    with right:
        fig = px.line(mix, x="fiscal_year", y="share", color="segment", markers=True,
                      color_discrete_map=SEGMENT_COLORS, category_orders={"segment": m.SEGMENT_ORDER},
                      labels={"fiscal_year": "Fiscal year", "share": "Share of total", "segment": "Segment"},
                      title="Asset mix: the shift into private markets")
        fig.update_traces(hovertemplate="%{fullData.name}<br>FY%{x}: %{y:.1%}<extra></extra>", line_width=2.5)
        fig.update_yaxes(tickformat=".0%", rangemode="tozero")
        fig.update_xaxes(tickvals=YEARS)
        fig.add_vline(x=year, line_dash="dot", line_color=NEUTRAL)
        st.plotly_chart(style(fig), width="stretch")
    st.markdown(
        "Private markets (private equity, private credit and real estate fund interests) grew from "
        "about **11% to 24%** of the fund between FY2017 and FY2024. Public equity fell from 58% to 42%.")

# ---------------- Public equity ----------------
with tab_equity:
    eq = snap[snap["segment"] == "Public equity"]
    left, right = st.columns([3, 2])
    with left:
        n = st.slider("Number of holdings", 5, 30, 15)
        top = m.top_holdings(df, year, n=n)
        top["value_m"] = top["market_value"] / 1e6
        fig = px.bar(top.iloc[::-1], x="value_m", y="security_name", orientation="h",
                     custom_data=["share_of_segment"], title=f"Largest public-equity holdings, FY{year}",
                     labels={"value_m": "Market value ($M)", "security_name": ""})
        fig.update_traces(marker_color=ACCENT,
                          hovertemplate="%{y}<br>$%{x:,.0f}M (%{customdata[0]:.2%} of public equity)<extra></extra>")
        fig.update_xaxes(tickprefix="$", ticksuffix="M", showgrid=True, gridcolor="rgba(128,128,128,0.18)")
        st.plotly_chart(style(fig, height=max(380, 24 * n), legend=False), width="stretch")
    with right:
        conc = m.concentration(df)
        fig = px.line(conc, x="fiscal_year", y="top10_share", markers=True, title="Top-10 share of public equity",
                      labels={"fiscal_year": "Fiscal year", "top10_share": "Top-10 share"})
        fig.update_traces(line_color=ACCENT, line_width=2.5, hovertemplate="FY%{x}: %{y:.1%}<extra></extra>")
        fig.update_yaxes(tickformat=".0%", rangemode="tozero"); fig.update_xaxes(tickvals=YEARS)
        st.plotly_chart(style(fig, height=300, legend=False), width="stretch")
        r = conc[conc["fiscal_year"] == year].iloc[0]
        st.caption(f"FY{year}: {int(r.issuers):,} issuers, but an *effective* number of only "
                   f"**{r.effective_n:,.0f}** equal-weight holdings (1 / HHI).")

    left, right = st.columns(2)
    with left:
        sec = (eq.groupby("major_industry", observed=True)["market_value"].sum()
               .sort_values().rename("market_value").reset_index())
        sec = sec[sec["market_value"] / sec["market_value"].sum() > 0.005]
        sec["share"] = sec["market_value"] / eq["market_value"].sum()
        fig = px.bar(sec, x="share", y=sec["major_industry"].str.title(), orientation="h",
                     title=f"Sector weights, FY{year}", labels={"share": "Share of public equity", "y": ""})
        fig.update_traces(marker_color=ACCENT, hovertemplate="%{y}: %{x:.1%}<extra></extra>")
        fig.update_xaxes(tickformat=".0%")
        st.plotly_chart(style(fig, height=420, legend=False), width="stretch")
    with right:
        geo = eq.groupby("country", observed=True)["market_value"].sum().reset_index()
        geo = geo[geo["market_value"] > 0]
        geo["share"] = geo["market_value"] / geo["market_value"].sum()
        geo["label"] = geo["country"].astype(str).str.replace(r" \(.*\)", "", regex=True).str.title()
        exclude_us = st.toggle("Exclude the United States", value=True)
        g = geo[geo["country"] != "UNITED STATES"] if exclude_us else geo
        g = g.nlargest(12, "market_value").iloc[::-1]
        g = g.assign(value_m=g["market_value"] / 1e6)
        fig = px.bar(g, x="value_m", y="label", orientation="h", custom_data=["share"],
                     title="Largest country exposures", labels={"value_m": "Market value ($M)", "label": ""})
        fig.update_traces(marker_color=ACCENT,
                          hovertemplate="%{y}<br>$%{x:,.0f}M (%{customdata[0]:.1%} of public equity)<extra></extra>")
        fig.update_xaxes(tickprefix="$", ticksuffix="M")
        st.plotly_chart(style(fig, height=380, legend=False), width="stretch")

# ---------------- Fixed income ----------------
with tab_fi:
    fip = m.fixed_income_profile(df)
    left, right = st.columns(2)
    with left:
        fig = go.Figure(go.Bar(
            x=fip["fiscal_year"].astype(str), y=fip["unrealized_pct_of_cost"],
            marker_color=[GAIN if v >= 0 else LOSS for v in fip["unrealized_pct_of_cost"]],
            customdata=fip["unrealized_gl"] / 1e9,
            hovertemplate="FY%{x}: %{y:+.1%} of cost<br>(%{customdata:+,.2f} $B)<extra></extra>"))
        fig.update_layout(title="Bond book: unrealized gain/loss vs cost")
        fig.update_xaxes(type="category", title="Fiscal year")
        fig.update_yaxes(tickformat=".0%")
        st.plotly_chart(style(fig, legend=False), width="stretch")
    with right:
        cr = m.credit_mix(df)
        fig = px.line(cr, x="fiscal_year", y="share", color="credit_bucket", markers=True,
                      color_discrete_map=CREDIT_COLORS, category_orders={"credit_bucket": list(CREDIT_COLORS)},
                      title="Credit quality mix", labels={"fiscal_year": "Fiscal year", "share": "Share of fixed income",
                                                          "credit_bucket": "Rating"})
        fig.update_traces(hovertemplate="%{fullData.name}<br>FY%{x}: %{y:.1%}<extra></extra>", line_width=2.5)
        fig.update_yaxes(tickformat=".0%", rangemode="tozero"); fig.update_xaxes(tickvals=YEARS)
        st.plotly_chart(style(fig), width="stretch")

    left, right = st.columns(2)
    with left:
        lad = m.maturity_ladder(df, year)
        lad = lad.assign(bucket=lad["maturity_bucket"].astype(str), value_bn=lad["market_value"] / 1e9)
        fig = px.bar(lad, x="bucket", y="value_bn", custom_data=["share"],
                     title=f"Maturity ladder, FY{year}", labels={"bucket": "Years to maturity", "value_bn": "Market value"})
        fig.update_traces(marker_color=ACCENT, hovertemplate="%{x}: $%{y:,.2f}B (%{customdata[0]:.0%})<extra></extra>")
        fig.update_yaxes(tickprefix="$", ticksuffix="B")
        st.plotly_chart(style(fig, legend=False), width="stretch")
    with right:
        fig = px.line(fip, x="fiscal_year", y="wavg_coupon", markers=True, title="Value-weighted coupon",
                      labels={"fiscal_year": "Fiscal year", "wavg_coupon": "Coupon"})
        fig.update_traces(line_color=ACCENT, line_width=2.5, hovertemplate="FY%{x}: %{y:.2f}%<extra></extra>")
        fig.update_xaxes(tickvals=YEARS)
        fig.update_yaxes(ticksuffix="%", range=[2, 4.5])
        st.plotly_chart(style(fig, legend=False), width="stretch")
    st.markdown(
        "When rates rose in 2022, bond prices fell: the book went from **+5.0%** above cost (FY2020) to "
        "**-10.4%** (FY2022). Bonds bought since then pay more, so the average coupon climbed to **3.9%** by FY2024.")

# ---------------- Explorer ----------------
with tab_explore:
    c1, c2, c3 = st.columns([1, 1, 2])
    segs = c1.multiselect("Segment", m.SEGMENT_ORDER, default=m.SEGMENT_ORDER)
    countries = sorted(snap["country"].dropna().astype(str).unique())
    ctry = c2.multiselect("Country", countries)
    q = c3.text_input("Search security name", placeholder="e.g. APPLE, TREASURY, KKR")
    view = snap[snap["segment"].isin(segs)]
    if ctry:
        view = view[view["country"].isin(ctry)]
    if q:
        view = view[view["security_name"].str.contains(q, case=False, na=False)]
    cols = ["security_name", "segment", "investment_type", "major_industry", "country", "currency",
            "market_value", "total_cost", "unrealized_gl", "unrealized_pct_of_cost", "coupon_rate",
            "maturity_date", "sp_rating", "moodys_rating"]
    view = view[cols].sort_values("market_value", ascending=False)
    st.caption(f"{len(view):,} positions · {fmt_bn(view['market_value'].sum())}")
    st.dataframe(
        view.head(5000), width="stretch", hide_index=True, height=520,
        column_config={
            "market_value": st.column_config.NumberColumn("Market value", format="$%.0f"),
            "total_cost": st.column_config.NumberColumn("Cost", format="$%.0f"),
            "unrealized_gl": st.column_config.NumberColumn("Unrealized G/L", format="$%.0f"),
            "unrealized_pct_of_cost": st.column_config.NumberColumn("G/L % of cost", format="percent"),
            "maturity_date": st.column_config.DateColumn("Maturity"),
        })
    st.download_button("Download filtered rows as CSV", view.to_csv(index=False).encode(),
                       file_name=f"nycers_fy{year}_filtered.csv", mime="text/csv")

# ---------------- About ----------------
with tab_about:
    st.markdown("""
**What this is.** Seven annual snapshots (June 30, FY2017 and FY2019 to FY2024) of every position held by the
New York City Employees' Retirement System, published by the NYC Comptroller.

**Cleaning.** 299,944 raw rows become 244,361 after removing 48,350 placeholder rows (dated 1899, all zeros),
119 blank rows, 7,113 exact duplicates and 1 stray FY2015 row. Ratings are normalised to the standard S&P and
Moody's scales, using the lower of the two when both exist. Full rules: `src/nycers/clean.py`.

**Read with care.**
* *Unrealized gain/loss* is measured against purchase cost. It is not an annual return; the data has no cash flows.
* *Private markets* are LP interests the source labels "Venture Capital". Their values are lagged appraisals.
* Security names are not unique IDs (no CUSIP/ISIN), so one company can appear under several names.
""")
