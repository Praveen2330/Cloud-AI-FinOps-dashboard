"""
pages/anomaly_detection.py — Statistical Cost Anomaly Detection for FinOps Intelligence.

Detects spending deviations using rolling z-score and IQR methods.
Allows investigating and persisting anomaly statuses directly to SQLite.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import datetime
import streamlit as st
import pandas as pd

from src import database as db
from src.anomaly_detector import (
    run_anomaly_detection, anomaly_summary,
    DEFAULT_WINDOW, DEFAULT_SENSITIVITY, DEFAULT_MIN_HISTORY,
    DEFAULT_MIN_COST_INCREASE, DEFAULT_MIN_PCT_INCREASE
)
from src.cloud_analytics import daily_spend_series
from src.visualization import (
    anomaly_timeline, anomaly_severity_bar
)

def _inr(v: float) -> str:
    if v >= 1_00_000:
        return f"₹{v/1_00_000:.2f}L"
    return f"₹{v:,.0f}"

st.markdown("# 🚨 Cost Anomaly Detection")
st.markdown(
    "<p style='color:#64748B; margin-top:-0.5rem; font-size:0.9rem;'>"
    "Statistical anomaly detection engine for identifying unexpected cloud cost spikes. "
    "Flagged events represent detected spending deviations that require human investigation."
    "</p>",
    unsafe_allow_html=True,
)

billing_df = db.get_billing_df()
if billing_df.empty:
    st.warning("No billing data found. Go to **📁 Data Management** to load sample data.")
    st.stop()

billing_df["billing_date"] = pd.to_datetime(billing_df["billing_date"])

# ── Sidebar Controls ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("---")
    st.markdown("**DETECTION PARAMETERS**")
    window = st.slider("Lookback Window (Days)", min_value=7, max_value=60, value=DEFAULT_WINDOW, step=1)
    sensitivity = st.slider("Sensitivity (Std Devs)", min_value=1.5, max_value=4.0, value=DEFAULT_SENSITIVITY, step=0.1)
    min_history = st.slider("Min History Required (Days)", min_value=7, max_value=30, value=DEFAULT_MIN_HISTORY, step=1)
    min_cost_inc = st.number_input("Min Absolute Cost Spike (₹)", min_value=0.0, value=DEFAULT_MIN_COST_INCREASE, step=1000.0)
    min_pct_inc = st.number_input("Min % Increase", min_value=0.0, value=DEFAULT_MIN_PCT_INCREASE, step=10.0)
    
    use_iqr = st.checkbox("Include IQR Robust Threshold", value=True)

    st.markdown("---")
    st.markdown("**SERVICE FILTER**")
    all_services = sorted(billing_df["service_name"].dropna().unique().tolist())
    selected_services = st.multiselect("Filter Specific Services", all_services, default=[])

    st.markdown("---")
    if st.button("🔄 Run Anomaly Scan & Sync"):
        with st.spinner("Analyzing cost trends..."):
            detected = run_anomaly_detection(
                billing_df,
                window=window,
                sensitivity=sensitivity,
                min_history=min_history,
                min_cost_increase=min_cost_inc,
                min_pct_increase=min_pct_inc,
                services_filter=selected_services if selected_services else None,
                use_iqr_secondary=use_iqr,
            )
            # Fetch existing recorded events to preserve statuses
            existing_anomalies = db.get_anomalies()
            existing_keys = set()
            if not existing_anomalies.empty:
                existing_keys = set(zip(
                    existing_anomalies["detection_date"].astype(str),
                    existing_anomalies["cloud_provider"].astype(str),
                    existing_anomalies["service_name"].astype(str)
                ))

            new_count = 0
            if not detected.empty:
                for _, row in detected.iterrows():
                    key = (str(row["detection_date"]), str(row["cloud_provider"]), str(row["service_name"]))
                    if key not in existing_keys:
                        db.insert_anomaly(row.to_dict())
                        new_count += 1
            st.success(f"Scan complete. Found {len(detected)} deviations ({new_count} new recorded).")
            st.rerun()

# ── Load Stored Anomalies ────────────────────────────────────────────────────
anomalies_df = db.get_anomalies()

# If empty, run detection once automatically to populate
if anomalies_df.empty:
    with st.spinner("Running initial statistical anomaly baseline detection..."):
        detected = run_anomaly_detection(
            billing_df,
            window=window,
            sensitivity=sensitivity,
            min_history=min_history,
            min_cost_increase=min_cost_inc,
            min_pct_increase=min_pct_inc,
            services_filter=selected_services if selected_services else None,
            use_iqr_secondary=use_iqr,
        )
        if not detected.empty:
            for _, row in detected.iterrows():
                db.insert_anomaly(row.to_dict())
        anomalies_df = db.get_anomalies()

# ── KPI Cards ─────────────────────────────────────────────────────────────────
summary = anomaly_summary(anomalies_df)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Anomalies", str(summary["total"]))
c2.metric("Critical / High", f"{summary['critical']} / {summary['high']}")
c3.metric("Medium / Low", f"{summary['medium']} / {summary['low']}")
c4.metric("Est. Excess Spend", _inr(summary["estimated_excess"]))
c5.metric("Services Affected", str(summary["services_affected"]))

st.markdown("---")

# ── Filters on Anomalies View ─────────────────────────────────────────────────
col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    filter_status = st.selectbox("Filter Status", ["All", "New", "Investigating", "Resolved", "False Positive"])
with col_f2:
    filter_severity = st.selectbox("Filter Severity", ["All", "Critical", "High", "Medium", "Low"])
with col_f3:
    filter_provider = st.selectbox("Filter Provider", ["All", "AWS", "Azure", "GCP"])

view_df = anomalies_df.copy()
if not view_df.empty:
    if filter_status != "All":
        view_df = view_df[view_df["status"] == filter_status]
    if filter_severity != "All":
        view_df = view_df[view_df["severity"] == filter_severity]
    if filter_provider != "All":
        view_df = view_df[view_df["cloud_provider"] == filter_provider]

# ── Timeline & Charts ────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📈 Timeline & Distributions", "📋 Anomaly Records & Triage", "ℹ️ How It Works"])

with tab1:
    col_t1, col_t2 = st.columns([2, 1])
    with col_t1:
        daily_spend = daily_spend_series(billing_df)
        st.plotly_chart(
            anomaly_timeline(daily_spend, view_df, title="Cloud Spend with Detected Anomaly Deviations"),
            width="stretch",
        )
    with col_t2:
        st.plotly_chart(anomaly_severity_bar(view_df), width="stretch")

    if not view_df.empty:
        st.markdown("### Top Anomalous Services by Excess Cost")
        top_anom = view_df.groupby("service_name")["absolute_increase"].sum().reset_index()
        top_anom = top_anom.sort_values("absolute_increase", ascending=False).head(10)
        top_anom["absolute_increase"] = top_anom["absolute_increase"].map(lambda x: f"₹{x:,.2f}")
        st.dataframe(top_anom, width="stretch", hide_index=True)

with tab2:
    st.markdown("### 🔍 Anomaly Triage & Investigation")
    if view_df.empty:
        st.info("No anomalies match the current filters.")
    else:
        st.caption("Select an anomaly below to review context, update investigation status, and add notes:")
        
        display_table = view_df[[
            "id", "detection_date", "cloud_provider", "service_name", "project",
            "actual_cost", "expected_cost", "absolute_increase", "pct_increase",
            "severity", "status"
        ]].copy()
        
        display_table["actual_cost"] = display_table["actual_cost"].map(lambda x: f"₹{x:,.2f}")
        display_table["expected_cost"] = display_table["expected_cost"].map(lambda x: f"₹{x:,.2f}")
        display_table["absolute_increase"] = display_table["absolute_increase"].map(lambda x: f"₹{x:,.2f}")
        display_table["pct_increase"] = display_table["pct_increase"].map(lambda x: f"{x:.1f}%")

        st.dataframe(display_table, width="stretch", hide_index=True)

        st.markdown("#### Update Anomaly Status")
        selected_id = st.selectbox("Select Anomaly ID to Manage", view_df["id"].tolist())
        selected_record = view_df[view_df["id"] == selected_id].iloc[0]

        st.markdown(f"""
        <div class="finops-card">
            <b>Date:</b> {selected_record['detection_date']} &nbsp;|&nbsp; 
            <b>Service:</b> {selected_record['service_name']} ({selected_record['cloud_provider']}) &nbsp;|&nbsp; 
            <b>Project:</b> {selected_record['project'] or 'N/A'}<br>
            <b>Actual Spend:</b> ₹{selected_record['actual_cost']:,.2f} &nbsp;|&nbsp; 
            <b>Baseline Expected:</b> ₹{selected_record['expected_cost']:,.2f} &nbsp;|&nbsp; 
            <b>Deviation:</b> +₹{selected_record['absolute_increase']:,.2f} (+{selected_record['pct_increase']:.1f}%)<br>
            <b>Preliminary Context:</b> {selected_record.get('notes') or f"Spending for {selected_record['service_name']} spiked significantly above rolling baseline. Review workload shifts and deployment logs."}
        </div>
        """, unsafe_allow_html=True)

        col_u1, col_u2, col_u3 = st.columns([1, 2, 1])
        with col_u1:
            new_status = st.selectbox(
                "Investigation Status",
                ["New", "Investigating", "Resolved", "False Positive"],
                index=["New", "Investigating", "Resolved", "False Positive"].index(selected_record["status"])
                if selected_record["status"] in ["New", "Investigating", "Resolved", "False Positive"] else 0
            )
        with col_u2:
            new_notes = st.text_input(
                "Investigation Notes / Resolution",
                value=selected_record.get("notes") or ""
            )
        with col_u3:
            st.write("")
            st.write("")
            if st.button("💾 Update Status"):
                db.update_anomaly_status(selected_id, new_status, new_notes)
                st.success(f"Anomaly #{selected_id} updated to '{new_status}'!")
                st.rerun()

with tab3:
    st.markdown("""
    ### 🔬 Cost Anomaly Detection Methodology

    #### 1. Rolling Baseline (Z-Score)
    - **Grouping:** Expenditures are aggregated daily by cloud provider and service name.
    - **Lookback Window:** Historical data over the preceding $N$ days (configurable, default 21 days) forms the reference window.
    - **Mean and Variance:** Rolling mean $\\mu$ and standard deviation $\\sigma$ are computed excluding the current day:
      $$\\mu_t = \\frac{1}{W} \\sum_{i=1}^{W} x_{t-i}, \\quad \\sigma_t = \\sqrt{\\frac{1}{W} \\sum_{i=1}^{W} (x_{t-i} - \\mu_t)^2}$$
    - **Deviation Score:**
      $$Z_t = \\frac{x_t - \\mu_t}{\\sigma_t}$$
    - If $Z_t > k$ (default $k=2.5$) and absolute increase $\\ge \\Delta_{min}$, the day is flagged as a potential deviation.

    #### 2. Robust Statistical Threshold (Interquartile Range)
    - For non-normal distributions or data with previous outliers, an IQR threshold acts as secondary validation:
      $$IQR = Q_3 - Q_1$$
      $$\\text{Upper Cutoff} = Q_3 + 2.5 \\times IQR$$

    #### 3. Reliability & Safeguards
    - **Minimum History:** Requires a minimum history (default 14 days) before detection begins.
    - **Zero Variance Protection:** Handles constant-cost services without division by zero.
    - **Missing Date Gap Filling:** Normalizes daily date sequences to prevent timeline distortions.
    - **Human Triage:** Detected deviations are flagged for human review, distinguishing calculated mathematical deviations from root causes.
    """)
