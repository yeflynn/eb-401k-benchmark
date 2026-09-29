"""401(k) Peer Benchmark — internal administrator tool.

Compares featured employer 401(k) plans against a market universe built from
DOL Form 5500 filings (plan year 2024). Private use only.
"""

import pandas as pd
import streamlit as st

DATA_PATH = "data/peer_401k_2024.csv"

FEATURE_LABELS = [
    ("feat_has_401k", "401(k) feature"),
    ("feat_profit_sharing", "Profit-sharing"),
    ("feat_match_or_aftertax_401m", "Match / after-tax (401(m))"),
    ("feat_auto_enrollment", "Auto-enrollment"),
    ("feat_qdias_default_investment", "QDIA default investment"),
    ("feat_self_directed_brokerage", "Self-directed brokerage"),
    ("feat_erisa_404c", "ERISA 404(c)"),
    ("feat_total_participant_directed", "Total participant-directed"),
    ("feat_age_weighted_allocation", "Age-weighted allocation"),
    ("feat_preapproved_plan", "Pre-approved plan"),
    ("feat_controlled_group", "Controlled group"),
]

PLAN_ORDER = [
    ("tmna", "Toyota Motor North America", "Retirement Savings Plan"),
    ("tri", "Toyota Research Institute", "401(k) Plan"),
    ("tcna", "Toyota Connected North America", "401(k) Plan"),
    ("woven", "Woven by Toyota, U.S.", "401(k) Plan"),
]

CAVEATS = """**Data & caveats**
- Source: U.S. Department of Labor Form 5500 filings, plan year 2024 (filed in 2025). Filings typically lag ~2 years.
- Market universe: 401(k) plans with 200–2,000 active participants. Toyota Motor North America (52,368 participants) is shown for reference but sits outside the comparison band.
- Schedule H administrative expenses **exclude revenue-shared fees** (netted from investment returns). Small-plan figures understate true cost — a like-for-like fee comparison requires Schedule C provider compensation.
- Form 5500 does **not** disclose: match formulas, vesting schedules, fund lineup / expense ratios, Roth availability, or auto-enrollment default rates.
"""


@st.cache_data
def load_data():
    df = pd.read_csv(DATA_PATH)
    df["featured"] = df["featured"].fillna("")
    df["er_per_active"] = df["employer_contrib"] / df["active_participants"].replace(0, pd.NA)
    df["admin_per_head"] = df["admin_expenses"] / df["total_participants"].replace(0, pd.NA)
    total_contrib = df["employer_contrib"] + df["participant_contrib"]
    df["er_share"] = (df["employer_contrib"] / total_contrib.replace(0, pd.NA) * 100)
    return df


def pct_rank(universe: pd.Series, value: float) -> float:
    s = universe.dropna()
    if len(s) == 0 or pd.isna(value):
        return float("nan")
    return float((s < value).mean() * 100)


def money(x):
    if pd.isna(x):
        return "—"
    return f"${x:,.0f}"


def pct1(x):
    if pd.isna(x):
        return "—"
    return f"{x:.1f}%"


def caveats():
    with st.expander("Data & caveats"):
        st.markdown(CAVEATS)


st.set_page_config(page_title="401(k) Peer Benchmark", layout="wide")
st.title("401(k) Peer Benchmark")
st.caption("Internal administrator tool · DOL Form 5500, plan year 2024")

df = load_data()
universe = df[df["featured"] == ""].copy()
featured = {tag: df[df["featured"] == tag].iloc[0] for tag, _, _ in PLAN_ORDER}

tab_peer, tab_market, tab_lookup = st.tabs(["Peer group", "Market benchmark", "Company lookup"])

# ---------------------------------------------------------------- Peer group
with tab_peer:
    st.subheader("Toyota peer group — 2024 filings")
    cols = st.columns(4)
    for (tag, short, plan), col in zip(PLAN_ORDER, cols):
        r = featured[tag]
        with col:
            st.markdown(f"**{short}**")
            st.caption(plan)
            st.metric("Active participants", f"{int(r['active_participants']):,}")
            st.metric("Plan assets", money(r["assets_eoy"]))
            st.metric("Employer contributions (2024)", money(r["employer_contrib"]))
            st.metric("Employee contributions (2024)", money(r["participant_contrib"]))
            st.metric("Employer share of contributions (2024)", pct1(r["er_share"]))
            st.metric("Employer $ / active participant", money(r["er_per_active"]))
            st.metric("Admin $ / participant", money(r["admin_per_head"]))

    st.subheader("Plan design features")
    feat_rows = []
    for col_key, label in FEATURE_LABELS:
        feat_rows.append(
            {"Feature": label, **{short: ("✓" if str(featured[tag][col_key]) == "1" else "—")
                                  for tag, short, _ in PLAN_ORDER}}
        )
    st.dataframe(pd.DataFrame(feat_rows).set_index("Feature"), use_container_width=True)

    st.subheader("Employer generosity vs market")
    er = universe["er_per_active"].dropna()
    bench = pd.DataFrame(
        {
            "Plan": ["Market p50", "Market p75", "Market p90"]
            + [short for _, short, _ in PLAN_ORDER],
            "Employer $ per active participant (2024)": [
                er.quantile(0.50), er.quantile(0.75), er.quantile(0.90),
                *(featured[tag]["er_per_active"] for tag, _, _ in PLAN_ORDER),
            ],
        }
    ).set_index("Plan")
    st.bar_chart(bench, use_container_width=True)

    st.subheader("Employer share of total contributions (2024)")
    sh = universe["er_share"].dropna()
    share_bench = pd.DataFrame(
        {
            "Plan": ["Market p50", "Market p75", "Market p90"]
            + [short for _, short, _ in PLAN_ORDER],
            "Employer % of total contributions": [
                sh.quantile(0.50), sh.quantile(0.75), sh.quantile(0.90),
                *(featured[tag]["er_share"] for tag, _, _ in PLAN_ORDER),
            ],
        }
    ).set_index("Plan")
    st.bar_chart(share_bench, use_container_width=True)
    st.caption(
        "TMNA is outside the 200–2,000 participant comparison band; its bars are shown for reference only."
    )
    caveats()

# ---------------------------------------------------------- Market benchmark
with tab_market:
    st.subheader("Market benchmark")
    st.caption(
        f"Universe: {len(universe):,} 401(k) plans with 200–2,000 active participants, plan year 2024."
    )

    for metric, title, fmt in [
        ("er_per_active", "Employer contributions per active participant (2024)", money),
        ("admin_per_head", "Administrative expense per participant (2024, Schedule H)", money),
    ]:
        st.markdown(f"**{title}**")
        s = universe[metric].dropna()
        if metric == "er_per_active":
            s = s[s <= s.quantile(0.99)]
        bins = pd.cut(s, bins=30)
        hist = s.groupby(bins, observed=True).size()
        hist.index = [f"{iv.left:,.0f}–{iv.right:,.0f}" for iv in hist.index]
        st.bar_chart(hist, use_container_width=True)

        ranks = []
        for tag, short, _ in PLAN_ORDER:
            if tag == "tmna":
                ranks.append({"Plan": short, "Value": money(featured[tag][metric]),
                              "Percentile vs market": "n/a (outside band)"})
            else:
                ranks.append({"Plan": short, "Value": money(featured[tag][metric]),
                              "Percentile vs market": f"{pct_rank(s, featured[tag][metric]):.0f}th"})
        st.dataframe(pd.DataFrame(ranks).set_index("Plan"), use_container_width=True)

    st.subheader("Percentile table — market universe")
    er = universe["er_per_active"].dropna()
    ad = universe["admin_per_head"].dropna()
    pct_df = pd.DataFrame(
        {
            "p10": [er.quantile(0.10), ad.quantile(0.10)],
            "p25": [er.quantile(0.25), ad.quantile(0.25)],
            "p50": [er.quantile(0.50), ad.quantile(0.50)],
            "p75": [er.quantile(0.75), ad.quantile(0.75)],
            "p90": [er.quantile(0.90), ad.quantile(0.90)],
        },
        index=["Employer $ / active participant (2024)", "Admin $ / participant (2024)"],
    ).map(lambda x: f"${x:,.0f}")
    st.dataframe(pct_df, use_container_width=True)
    caveats()

# ------------------------------------------------------------ Company lookup
with tab_lookup:
    st.subheader("Company lookup")
    q = st.text_input("Sponsor name contains", placeholder="e.g. toyota, netflix, …")
    if q:
        hits = universe[universe["sponsor_name"].str.contains(q, case=False, na=False)].copy()
        st.caption(f"{len(hits)} matching plan(s) in the comparison universe.")
        if len(hits):
            er = universe["er_per_active"].dropna()
            ad = universe["admin_per_head"].dropna()
            out = pd.DataFrame(
                {
                    "Sponsor": hits["sponsor_name"],
                    "Plan": hits["plan_name"],
                    "State": hits["state"],
                    "Active": hits["active_participants"],
                    "Assets": hits["assets_eoy"].map(money),
                    "Employer $/active (2024)": hits["er_per_active"].map(money),
                    "Employer share (2024)": hits["er_share"].map(pct1),
                    "ER percentile": hits["er_per_active"].map(
                        lambda v: f"{pct_rank(er, v):.0f}th" if pd.notna(v) else "—"),
                    "Admin $/head (2024)": hits["admin_per_head"].map(money),
                }
            )
            st.dataframe(out, use_container_width=True, hide_index=True)
    else:
        st.info("Type part of a sponsor name to search the 401(k) universe.")
    caveats()
