"""
pages/ai_cost_analytics.py — AI & LLM Cost Analytics for FinOps Intelligence.

Tracks simulated AI / LLM workload expenditure across models and applications.
Supports transparent pricing configurations and recalculations.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd

from src import database as db
from src.ai_cost_engine import (
    calculate_token_cost, recalculate_costs,
    daily_ai_spend, spend_by_model, spend_by_application,
    spend_by_project, cost_per_request, token_efficiency,
    detect_ai_spend_increase, ai_kpi_summary
)
from src.visualization import (
    ai_daily_line, token_usage_bar
)

def _inr(v: float | None) -> str:
    if v is None:
        return "N/A"
    if v >= 1_00_000:
        return f"₹{v/1_00_000:.2f}L"
    return f"₹{v:,.2f}"

st.markdown("# 🤖 AI and LLM Cost Analytics")
st.markdown(
    "<p style='color:#64748B; margin-top:-0.5rem; font-size:0.9rem;'>"
    "Monitor token consumption, analyze LLM usage economics, and manage pricing models. "
    "All figures are computed from explicit token counts and pricing rules."
    "</p>",
    unsafe_allow_html=True,
)

ai_df = db.get_ai_df()
pricing_df = db.get_pricing()

if pricing_df.empty:
    db.seed_default_pricing()
    pricing_df = db.get_pricing()

if ai_df.empty:
    st.warning("No AI usage records found. Go to **📁 Data Management** to generate sample AI usage data.")
    st.stop()

ai_df["request_timestamp"] = pd.to_datetime(ai_df["request_timestamp"])

# ── Sidebar Filter ────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("---")
    st.markdown("**AI ANALYTICS FILTERS**")
    
    prov_opts = ["All"] + sorted(ai_df["provider"].dropna().unique().tolist())
    sel_prov = st.selectbox("Model Provider", prov_opts)

    model_opts = ["All"] + sorted(ai_df["model_name"].dropna().unique().tolist())
    sel_model = st.selectbox("Model", model_opts)

    app_opts = ["All"] + sorted(ai_df["application"].dropna().unique().tolist())
    sel_app = st.selectbox("Application", app_opts)

    proj_opts = ["All"] + sorted(ai_df["project"].dropna().unique().tolist())
    sel_proj = st.selectbox("Project", proj_opts)

    min_d = ai_df["request_timestamp"].min().date()
    max_d = ai_df["request_timestamp"].max().date()
    d_range = st.date_input("Date Range", value=(min_d, max_d), min_value=min_d, max_value=max_d)

f_ai = ai_df.copy()
if isinstance(d_range, (list, tuple)) and len(d_range) == 2:
    f_ai = f_ai[
        (f_ai["request_timestamp"].dt.date >= d_range[0]) &
        (f_ai["request_timestamp"].dt.date <= d_range[1])
    ]

if sel_prov != "All":
    f_ai = f_ai[f_ai["provider"] == sel_prov]
if sel_model != "All":
    f_ai = f_ai[f_ai["model_name"] == sel_model]
if sel_app != "All":
    f_ai = f_ai[f_ai["application"] == sel_app]
if sel_proj != "All":
    f_ai = f_ai[f_ai["project"] == sel_proj]

if f_ai.empty:
    st.warning("No AI usage records found matching the active filters.")
    st.stop()

# ── KPI Cards ─────────────────────────────────────────────────────────────────
kpi = ai_kpi_summary(f_ai)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total AI Spend", _inr(kpi["total_cost"]))
c2.metric("Input Tokens Spend", _inr(kpi["input_cost"]))
c3.metric("Output Tokens Spend", _inr(kpi["output_cost"]))
c4.metric("Total Requests", f"{kpi['total_requests']:,}")
c5.metric("Avg Cost / Request", f"₹{kpi['avg_cost_per_request']:.4f}" if kpi['avg_cost_per_request'] else "N/A")

# Alert on sudden spike
spike_info = detect_ai_spend_increase(f_ai)
if spike_info and spike_info.get("is_elevated"):
    st.markdown(
        f"<div class='alert-near'>⚠️ <b>Elevated AI Spending Detected:</b> "
        f"Recent daily spend is ₹{spike_info['recent_daily_spend']:,.2f}, which is "
        f"<b>{spike_info['pct_increase']:.1f}%</b> higher than the recent 7-day baseline of "
        f"₹{spike_info['rolling_avg']:,.2f}.</div>",
        unsafe_allow_html=True
    )

st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Spending & Trends",
    "🤖 Models & Efficiency",
    "📱 Application Breakdown",
    "⚙️ Pricing Assumptions"
])

with tab1:
    col1, col2 = st.columns([2, 1])
    with col1:
        daily_ai = daily_ai_spend(f_ai)
        st.plotly_chart(ai_daily_line(daily_ai), width="stretch")
    with col2:
        model_sum = spend_by_model(f_ai)
        st.plotly_chart(token_usage_bar(model_sum), width="stretch")

    st.markdown("### Daily Token Consumption & Expense Log")
    if not daily_ai.empty:
        display_daily = daily_ai.copy()
        display_daily["total_cost"] = display_daily["total_cost"].map(lambda x: f"₹{x:,.2f}")
        display_daily["input_tokens"] = display_daily["input_tokens"].map(lambda x: f"{x:,}")
        display_daily["output_tokens"] = display_daily["output_tokens"].map(lambda x: f"{x:,}")
        display_daily["request_count"] = display_daily["request_count"].map(lambda x: f"{x:,}")
        st.dataframe(display_daily, width="stretch", hide_index=True)

with tab2:
    st.markdown("### Model-Level Cost & Efficiency Analysis")
    eff_df = token_efficiency(f_ai)
    if not eff_df.empty:
        eff_display = eff_df[[
            "model_name", "provider", "total_cost", "input_cost", "output_cost",
            "request_count", "total_tokens", "cost_per_1k_tokens"
        ]].copy()
        eff_display["total_cost"] = eff_display["total_cost"].map(lambda x: f"₹{x:,.2f}")
        eff_display["input_cost"] = eff_display["input_cost"].map(lambda x: f"₹{x:,.2f}")
        eff_display["output_cost"] = eff_display["output_cost"].map(lambda x: f"₹{x:,.2f}")
        eff_display["request_count"] = eff_display["request_count"].map(lambda x: f"{x:,}")
        eff_display["total_tokens"] = eff_display["total_tokens"].map(lambda x: f"{x:,}")
        eff_display["cost_per_1k_tokens"] = eff_display["cost_per_1k_tokens"].map(
            lambda x: f"₹{x:.4f}" if x is not None else "N/A"
        )
        st.dataframe(eff_display, width="stretch", hide_index=True)

    st.markdown("""
    <div class='disclaimer'>
        <b>Pricing Formula Note:</b><br>
        <code>Estimated Request Cost = (Input Tokens / 1,000,000 × Input Price) + (Output Tokens / 1,000,000 × Output Price)</code><br>
        Output tokens are typically 3x to 4x more expensive per unit than input tokens across modern frontier LLMs.
    </div>
    """, unsafe_allow_html=True)

with tab3:
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("### Spend by Application")
        app_df = spend_by_application(f_ai)
        if not app_df.empty:
            app_df_disp = app_df.copy()
            app_df_disp["total_cost"] = app_df_disp["total_cost"].map(lambda x: f"₹{x:,.2f}")
            app_df_disp["request_count"] = app_df_disp["request_count"].map(lambda x: f"{x:,}")
            st.dataframe(app_df_disp, width="stretch", hide_index=True)

    with col_b:
        st.markdown("### Spend by Project")
        proj_df = spend_by_project(f_ai)
        if not proj_df.empty:
            proj_df_disp = proj_df.copy()
            proj_df_disp["total_cost"] = proj_df_disp["total_cost"].map(lambda x: f"₹{x:,.2f}")
            proj_df_disp["request_count"] = proj_df_disp["request_count"].map(lambda x: f"{x:,}")
            st.dataframe(proj_df_disp, width="stretch", hide_index=True)

with tab4:
    st.markdown("### ⚙️ Configurable Token Pricing Assumptions")
    st.markdown("""
    Prices per 1 Million Tokens are stored separately in the database and can be edited.
    *Note: Prices are illustrative estimates calibrated for comparative FinOps analysis.*
    """)

    pricing_data = db.get_pricing()
    if not pricing_data.empty:
        p_disp = pricing_data[["provider", "model_name", "input_price_per_million", "output_price_per_million", "currency"]].copy()
        p_disp["input_price_per_million"] = p_disp["input_price_per_million"].map(lambda x: f"₹{x:,.2f}")
        p_disp["output_price_per_million"] = p_disp["output_price_per_million"].map(lambda x: f"₹{x:,.2f}")
        st.dataframe(p_disp, width="stretch", hide_index=True)

    st.markdown("#### Update Pricing Rate")
    with st.form("edit_pricing_form"):
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            p_prov = st.selectbox("Provider", pricing_data["provider"].unique().tolist())
            p_models = pricing_data[pricing_data["provider"] == p_prov]["model_name"].tolist()
            p_model = st.selectbox("Model Name", p_models)
        with col_p2:
            p_curr = pricing_data[(pricing_data["provider"] == p_prov) & (pricing_data["model_name"] == p_model)].iloc[0]
            new_inp = st.number_input("Input Price / 1M Tokens (₹)", value=float(p_curr["input_price_per_million"]), step=10.0)
            new_out = st.number_input("Output Price / 1M Tokens (₹)", value=float(p_curr["output_price_per_million"]), step=50.0)

        submitted = st.form_submit_button("Update Rate & Recalculate Stored Costs")
        if submitted:
            db.upsert_pricing(p_prov, p_model, new_inp, new_out, "INR")
            # Recalculate all AI records in database
            all_ai = db.get_ai_df()
            all_pricing = db.get_pricing()
            updated_ai = recalculate_costs(all_ai, all_pricing)
            
            # Save updated back to DB
            db.clear_all_ai_data()
            db.insert_ai_records(updated_ai)
            st.success(f"Pricing updated for {p_model}. All historical records recalculated.")
            st.rerun()
