"""401(k) Peer Benchmark — internal administrator tool.

Compares featured employer 401(k) plans against a market universe built from
DOL Form 5500 filings (plan year 2024). Private use only.
"""

import altair as alt
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

BAR_COLOR = "#0e544c"
BAR_SIZE = 36

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
    feat_df = pd.DataFrame(
        {short: [(str(featured[tag][col_key]) == "1") for col_key, _ in FEATURE_LABELS]
         for tag, short, _ in PLAN_ORDER},
        index=[label for _, label in FEATURE_LABELS],
    )

    def _feat_cell(v):
        if v:
            return ("background-color: #d7efe6; color: #0e544c; "
                    "font-weight: 700; text-align: center;")
        return ("background-color: #f3efe6; color: #b3aa99; text-align: center;")

    st.dataframe(
        feat_df.style.map(_feat_cell).format(lambda v: "✓" if v else "—"),
        use_container_width=True,
    )
    st.caption("Green = feature reported on the 2024 Form 5500; grey = not reported.")

    st.subheader("Employer generosity vs market")
    er = universe["er_per_active"].dropna()
    sh = universe["er_share"].dropna()
    ABBR = {"Toyota Motor North America": "TMNA", "Toyota Research Institute": "TRI",
            "Toyota Connected North America": "TCNA", "Woven by Toyota, U.S.": "Woven"}
    plans = [ABBR[short] for _, short, _ in PLAN_ORDER]

    def _layered_chart(bar_values, bench_values, y_title, pct):
        bar_df = pd.DataFrame({"Plan": plans, "value": bar_values})
        line_df = pd.DataFrame(
            {
                "Benchmark": ["Market p50", "Market p75", "Market p90"],
                "value": bench_values,
                "Plan": plans[0],
            }
        )
        bar_df["bar_label"] = bar_df["value"].map(
            lambda v: f"{v:.1f}%" if pct else f"${v:,.0f}")
        line_df["line_label"] = line_df["value"].map(
            lambda v: f"{v:.1f}%" if pct else f"${v:,.0f}")
        vmax = float(bar_df["value"].max())
        y_scale = alt.Scale(domain=[0, vmax * 1.15]) if vmax > 0 else alt.Scale()
        x_enc = alt.X("Plan:N", sort=None, title=None,
                      scale=alt.Scale(paddingOuter=0.6))
        bars = (
            alt.Chart(bar_df)
            .mark_bar(color=BAR_COLOR, size=BAR_SIZE)
            .encode(
                x=x_enc,
                y=alt.Y("value:Q", title=y_title, scale=y_scale),
                tooltip=[alt.Tooltip("Plan:N"),
                         alt.Tooltip("bar_label:N", title=y_title)],
            )
        )
        bar_labels = (
            alt.Chart(bar_df)
            .mark_text(dy=-8, color="#2b2620", fontWeight=600, fontSize=12)
            .encode(
                x=x_enc,
                y=alt.Y("value:Q", scale=y_scale),
                text=alt.Text("bar_label:N"),
            )
        )
        rules = (
            alt.Chart(line_df)
            .mark_rule(strokeDash=[6, 4], size=2)
            .encode(
                y=alt.Y("value:Q", scale=y_scale),
                color=alt.Color("Benchmark:N",
                                scale=alt.Scale(range=["#b3aa99", "#6b6259", "#2b2620"]),
                                legend=alt.Legend(title="Market benchmark")),
                tooltip=[alt.Tooltip("Benchmark:N"),
                         alt.Tooltip("line_label:N", title="Benchmark")],
            )
        )
        line_labels = (
            alt.Chart(line_df)
            .mark_text(align="right", dx=-26, dy=-6, color="#6b6259", fontSize=11)
            .encode(
                x=x_enc,
                y=alt.Y("value:Q", scale=y_scale),
                text=alt.Text("line_label:N"),
            )
        )
        return (bars + rules + bar_labels + line_labels).properties(height=300)

    gen_chart = _layered_chart(
        [float(featured[tag]["er_per_active"]) for tag, _, _ in PLAN_ORDER],
        [float(er.quantile(q)) for q in (0.50, 0.75, 0.90)],
        "USD per active participant",
        pct=False,
    )
    share_chart = _layered_chart(
        [float(featured[tag]["er_share"]) for tag, _, _ in PLAN_ORDER],
        [float(sh.quantile(q)) for q in (0.50, 0.75, 0.90)],
        "Employer % of total contributions",
        pct=True,
    )

    c1, cdiv, c2 = st.columns([10, 1, 10])
    with c1:
        st.markdown("**Employer $ per active participant (2024)**")
        st.altair_chart(gen_chart, use_container_width=True)
    with cdiv:
        st.markdown(
            '<div style="border-left:2px solid #e5e1d8;height:330px;margin:56px 0 0 40%"></div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown("**Employer share of total contributions (2024)**")
        st.altair_chart(share_chart, use_container_width=True)
    st.caption(
        "TMNA is outside the 200–2,000 participant comparison band; its bar is shown for reference only."
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
        hist_chart = (
            alt.Chart(pd.DataFrame({"value": s}))
            .mark_bar(color=BAR_COLOR)
            .encode(
                x=alt.X("value:Q", bin=alt.Bin(maxbins=30), title=title),
                y=alt.Y("count()", title="Number of plans"),
            )
            .properties(height=260)
        )
        st.altair_chart(hist_chart, use_container_width=True)

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
