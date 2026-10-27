"""
pages/budget_monitoring.py — Budget monitoring and utilisation for FinOps Intelligence.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import datetime
import calendar
import streamlit as st
import pandas as pd

from src import database as db
from src.budget_engine import (
    build_budget_summary, get_over_budget_alerts,
    DEFAULT_THRESHOLDS, budget_status,
)
from src.visualization import budget_vs_actual_chart, budget_utilisation_bars

# ── helpers ──────────────────────────────────────────────────────────────────

def _inr(v) -> str:
    if v is None:
        return "N/A"
    v = float(v)
    if v >= 1_00_000:
        return f"₹{v/1_00_000:.2f}L"
    return f"₹{v:,.0f}"


def _badge(status: str) -> str:
    cls_map = {
        "Healthy":    "badge badge-healthy",
        "Attention":  "badge badge-attention",
        "Near Limit": "badge badge-near",
        "Over Budget":"badge badge-over",
    }
    return f"<span class='{cls_map.get(status, 'badge')}'>{status}</span>"


# ── page ─────────────────────────────────────────────────────────────────────

st.markdown("# 💰 Budget Monitoring")
st.markdown(
    "<p style='color:#64748B; margin-top:-0.5rem; font-size:0.9rem;'>"
    "Configure budgets and track utilisation against actual spending."
    "</p>",
    unsafe_allow_html=True,
)

today = datetime.date.today()
billing_df = db.get_billing_df()
ai_df      = db.get_ai_df()

if billing_df.empty:
    st.warning("No billing data found. Go to **📁 Data Management** to load sample data.")
    st.stop()

billing_df["billing_date"] = pd.to_datetime(billing_df["billing_date"])
if not ai_df.empty:
    ai_df["request_timestamp"] = pd.to_datetime(ai_df["request_timestamp"])

# ── Sidebar: Period + Threshold config ───────────────────────────────────────
with st.sidebar:
    st.markdown("---")
    st.markdown("**PERIOD**")
    all_months = (
        billing_df["billing_date"]
        .dt.to_period("M")
        .unique()
        .sort_values(ascending=False)
    )
    month_labels = [str(m) for m in all_months]
    sel_month_str = st.selectbox("Budget Month", month_labels)
    sel_period = pd.Period(sel_month_str)
    sel_year   = sel_period.year
    sel_month  = sel_period.month

    st.markdown("**ALERT THRESHOLDS (%)**")
    thr_healthy   = st.slider("Healthy threshold", 50, 85, 70)
    thr_attention = st.slider("Attention threshold", thr_healthy+1, 98, 90)
    thresholds    = {"healthy": thr_healthy, "attention": thr_attention, "near_limit": 100.0}

# Ensure default budgets exist
budgets_df = db.get_budgets(sel_year, sel_month)
if budgets_df.empty:
    db.seed_default_budgets(sel_year, sel_month)
    budgets_df = db.get_budgets(sel_year, sel_month)

# Build summary
budget_summary = build_budget_summary(
    budgets_df, billing_df, ai_df, sel_year, sel_month, thresholds
)

# ── Alerts ───────────────────────────────────────────────────────────────────
alerts = get_over_budget_alerts(budget_summary)
if not alerts.empty:
    for _, row in alerts.iterrows():
        cls = "alert-over" if row["status"] == "Over Budget" else "alert-near"
        icon = "🔴" if row["status"] == "Over Budget" else "🟡"
        st.markdown(
            f"<div class='{cls}'>{icon} <b>{row['name']}</b> ({row['budget_type']}) — "
            f"{row['status']} at {row['utilisation_pct']:.1f}% utilisation. "
            f"Remaining: {_inr(row['remaining'])}</div>",
            unsafe_allow_html=True,
        )

# ── KPIs ─────────────────────────────────────────────────────────────────────
if not budget_summary.empty:
    ov  = budget_summary[budget_summary["budget_type"] == "overall"]
    ai_ = budget_summary[budget_summary["budget_type"] == "ai"]

    total_budgeted = float(budgets_df["monthly_budget"].sum())
    total_actual   = float(budget_summary["actual_spend"].sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Budgeted",   _inr(total_budgeted))
    c2.metric("Total Actual",     _inr(total_actual))
    c3.metric("Overall Remaining",_inr(float(ov["remaining"].iloc[0])) if not ov.empty else "N/A")
    c4.metric("Over-budget Items",str(int((budget_summary["status"] == "Over Budget").sum())))

    st.markdown("---")

# ── Budget configuration editor ───────────────────────────────────────────────
with st.expander("⚙️ Configure Budgets", expanded=False):
    st.markdown(f"Editing budgets for **{sel_month_str}**")

    budget_types = ["overall", "provider", "department", "project", "ai"]
    edit_type    = st.selectbox("Budget Type", budget_types)

    if edit_type == "overall":
        name_options = ["Cloud Total"]
    elif edit_type == "provider":
        name_options = ["AWS", "Azure", "GCP"]
    elif edit_type == "department":
        name_options = sorted(billing_df["department"].dropna().unique().tolist())
    elif edit_type == "project":
        name_options = sorted(billing_df["project"].dropna().unique().tolist())
    else:
        name_options = ["AI/LLM Total"]

    edit_name   = st.selectbox("Budget Name", name_options)
    existing    = budgets_df[
        (budgets_df["budget_type"] == edit_type) & (budgets_df["name"] == edit_name)
    ]
    default_val = float(existing["monthly_budget"].iloc[0]) if not existing.empty else 100000.0
    new_budget  = st.number_input(f"Monthly Budget (₹) for {edit_name}", min_value=1.0, value=default_val, step=1000.0)

    if st.button("💾 Save Budget"):
        db.upsert_budget(edit_type, edit_name, new_budget, sel_year, sel_month)
        st.success(f"Budget for {edit_name} saved: ₹{new_budget:,.0f}")
        st.rerun()

# ── Charts ───────────────────────────────────────────────────────────────────
if not budget_summary.empty:
    tab1, tab2 = st.tabs(["📊 Charts", "📋 Table"])

    with tab1:
        # Overall view
        st.plotly_chart(budget_vs_actual_chart(budget_summary), use_container_width=True)
        st.plotly_chart(budget_utilisation_bars(budget_summary), use_container_width=True)

        # By type breakdown
        for btype in ["provider", "department", "project"]:
            sub = budget_summary[budget_summary["budget_type"] == btype]
            if sub.empty:
                continue
            st.markdown(f"**Budget by {btype.capitalize()}**")
            col_l, col_r = st.columns(2)
            with col_l:
                st.plotly_chart(budget_vs_actual_chart(sub, title=f"Budget vs Actual by {btype.capitalize()}"), use_container_width=True)
            with col_r:
                st.plotly_chart(budget_utilisation_bars(sub, height=250), use_container_width=True)

    with tab2:
        # Detailed table
        days_in_month = calendar.monthrange(sel_year, sel_month)[1]
        current_day   = today.day if (today.year == sel_year and today.month == sel_month) else days_in_month

        display_df = budget_summary.copy()
        display_df["monthly_budget"]  = display_df["monthly_budget"].map(_inr)
        display_df["actual_spend"]    = display_df["actual_spend"].map(_inr)
        display_df["remaining"]       = display_df["remaining"].map(_inr)
        display_df["utilisation_pct"] = display_df["utilisation_pct"].map(
            lambda x: f"{x:.1f}%" if x is not None else "N/A"
        )
        display_df["projected_eom"]   = display_df["projected_eom"].map(
            lambda x: _inr(x) if x is not None else "N/A"
        )

        st.dataframe(
            display_df[["budget_type","name","monthly_budget","actual_spend",
                         "remaining","utilisation_pct","projected_eom","status"]],
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("""
        <div class='disclaimer'>
            <b>Projection methodology:</b> Month-end projection = Average daily spend × Days in month.
            Requires at least 3 days of data. Assumes uniform daily spending — actual spending may vary.
            Projection is not available if fewer than 3 days of data exist in the selected month.
        </div>
        """, unsafe_allow_html=True)
