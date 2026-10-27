"""
pages/overview.py — Executive Dashboard Overview for FinOps Intelligence.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd

from src import database as db
from src.cloud_analytics import (
    get_kpi_summary, daily_spend_series, aggregate_by,
    top_services, top_departments, top_projects, generate_insights,
    monthly_spend_series,
)
from src.ai_cost_engine import ai_kpi_summary
from src.budget_engine import build_budget_summary
from src.visualization import (
    daily_spend_line, spend_by_service_bar, spend_donut,
    budget_vs_actual_chart, cloud_vs_ai_chart, provider_pie,
    monthly_trend_by_provider,
)

# ── helpers ──────────────────────────────────────────────────────────────────

def _inr(v: float) -> str:
    if v >= 1_00_00_000:
        return f"₹{v/1_00_00_000:.2f} Cr"
    if v >= 1_00_000:
        return f"₹{v/1_00_000:.2f} L"
    return f"₹{v:,.0f}"


def _delta_str(pct: float | None) -> str:
    if pct is None:
        return ""
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}% vs prev period"


# ── page ─────────────────────────────────────────────────────────────────────

st.markdown("# 📊 Executive Overview")
st.markdown(
    "<p style='color:#64748B; margin-top:-0.5rem; font-size:0.9rem;'>"
    "All metrics are calculated from the active dataset in the local SQLite database."
    "</p>",
    unsafe_allow_html=True,
)

# Load data
billing_df = db.get_billing_df()
ai_df      = db.get_ai_df()

if billing_df.empty:
    st.warning(
        "No billing data found. Go to **📁 Data Management** and click **Load Sample Data** to get started."
    )
    st.stop()

billing_df["billing_date"] = pd.to_datetime(billing_df["billing_date"])
if not ai_df.empty:
    ai_df["request_timestamp"] = pd.to_datetime(ai_df["request_timestamp"])

# ── Date range filter ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("---")
    st.markdown("**FILTERS**")
    min_date = billing_df["billing_date"].min().date()
    max_date = billing_df["billing_date"].max().date()

    date_range = st.date_input(
        "Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start_d, end_d = date_range
else:
    start_d, end_d = min_date, max_date

filtered_billing = billing_df[
    (billing_df["billing_date"].dt.date >= start_d) &
    (billing_df["billing_date"].dt.date <= end_d)
].copy()

filtered_ai = ai_df.copy()
if not filtered_ai.empty:
    filtered_ai = filtered_ai[
        (filtered_ai["request_timestamp"].dt.date >= start_d) &
        (filtered_ai["request_timestamp"].dt.date <= end_d)
    ]

# ── KPI summary ──────────────────────────────────────────────────────────────
kpi = get_kpi_summary(filtered_billing, filtered_ai)
ai_kpi = ai_kpi_summary(filtered_ai)

# Budget for current month
import datetime
today  = datetime.date.today()
budgets_df = db.get_budgets(today.year, today.month)
budget_summary = build_budget_summary(budgets_df, filtered_billing, filtered_ai, today.year, today.month) \
    if not budgets_df.empty else pd.DataFrame()

overall_budget = 0.0
overall_util   = None
if not budget_summary.empty:
    ov = budget_summary[budget_summary["budget_type"] == "overall"]
    if not ov.empty:
        overall_budget = float(ov.iloc[0]["monthly_budget"])
        overall_util   = ov.iloc[0].get("utilisation_pct")

# Anomaly count
anomaly_df = db.get_anomalies()
anomaly_count = len(anomaly_df[anomaly_df["status"] != "False Positive"]) if not anomaly_df.empty else 0

st.markdown("## Key Performance Indicators")
col1, col2, col3, col4, col5, col6 = st.columns(6)

with col1:
    st.metric(
        "Total Cloud Spend",
        _inr(kpi["cloud_total"]),
        _delta_str(kpi["cloud_pct"]),
        delta_color="inverse",
    )
with col2:
    st.metric(
        "AI / LLM Spend",
        _inr(kpi["ai_total"]),
        _delta_str(kpi["ai_pct"]),
        delta_color="inverse",
    )
with col3:
    st.metric(
        "Monthly Budget",
        _inr(overall_budget) if overall_budget else "Not set",
    )
with col4:
    st.metric(
        "Budget Utilisation",
        f"{overall_util:.1f}%" if overall_util is not None else "N/A",
    )
with col5:
    st.metric("Detected Anomalies", str(anomaly_count))
with col6:
    st.metric(
        "Potential Savings",
        "See Recommendations",
    )

st.markdown("---")

# ── Row 1: Daily spend + Provider breakdown ───────────────────────────────
col_left, col_right = st.columns([2, 1])

with col_left:
    daily = daily_spend_series(filtered_billing)
    st.plotly_chart(
        daily_spend_line(daily, title="Daily Cloud Spending"),
        use_container_width=True,
    )

with col_right:
    prov_df = filtered_billing.groupby("cloud_provider")["total_cost"].sum().reset_index()
    st.plotly_chart(provider_pie(prov_df), use_container_width=True)

# ── Row 2: Top services + Department ──────────────────────────────────────
col_left2, col_right2 = st.columns([1, 1])

with col_left2:
    svc_df = top_services(filtered_billing)
    st.plotly_chart(spend_by_service_bar(svc_df), use_container_width=True)

with col_right2:
    dept_df = filtered_billing.groupby("department")["total_cost"].sum().reset_index()
    st.plotly_chart(
        spend_donut(dept_df, "department", title="Spend by Department"),
        use_container_width=True,
    )

# ── Row 3: Monthly trend + Cloud vs AI ───────────────────────────────────
col_left3, col_right3 = st.columns([2, 1])

with col_left3:
    st.plotly_chart(monthly_trend_by_provider(filtered_billing), use_container_width=True)

with col_right3:
    st.plotly_chart(
        cloud_vs_ai_chart(kpi["cloud_total"], kpi["ai_total"]),
        use_container_width=True,
    )

# ── Row 4: Budget vs Actual ───────────────────────────────────────────────
if not budget_summary.empty:
    st.markdown("## Budget vs Actual (Current Month)")
    top_budgets = budget_summary.nlargest(8, "monthly_budget")
    st.plotly_chart(budget_vs_actual_chart(top_budgets), use_container_width=True)

# ── Auto-generated insights ───────────────────────────────────────────────
st.markdown("## 💡 Auto-Generated Insights")
insights = generate_insights(filtered_billing, filtered_ai, budgets_df if not budgets_df.empty else None)

for insight in insights:
    st.markdown(f"<div class='insight-box'>📌 {insight}</div>", unsafe_allow_html=True)

st.markdown("""
<div class='disclaimer' style='margin-top:1rem;'>
    ℹ️ All data shown is synthetic. Metrics are calculated from the local SQLite database.
    Percentage changes compare the most recent half of the selected date range with the preceding half.
</div>
""", unsafe_allow_html=True)
