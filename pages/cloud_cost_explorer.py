"""
pages/cloud_cost_explorer.py — Detailed cloud cost analysis with filtering and export.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import io

from src import database as db
from src.cloud_analytics import (
    aggregate_by, daily_spend_series, compare_periods, pct_change,
)
from src.visualization import (
    daily_spend_line, spend_by_service_bar, spend_donut,
    provider_pie, monthly_trend_by_provider,
)

# ── helpers ──────────────────────────────────────────────────────────────────

def _inr(v: float) -> str:
    if v >= 1_00_000:
        return f"₹{v/1_00_000:.2f}L"
    return f"₹{v:,.0f}"


st.markdown("# ☁️ Cloud Cost Explorer")
st.markdown(
    "<p style='color:#64748B; margin-top:-0.5rem; font-size:0.9rem;'>"
    "Explore and analyse cloud billing records. All data is synthetic — not real cloud provider billing."
    "</p>",
    unsafe_allow_html=True,
)

# Load raw data
billing_df = db.get_billing_df()
if billing_df.empty:
    st.warning("No billing data found. Go to **📁 Data Management** to load sample data.")
    st.stop()

billing_df["billing_date"] = pd.to_datetime(billing_df["billing_date"])

# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("---")
    st.markdown("**FILTERS**")

    providers = ["All"] + sorted(billing_df["cloud_provider"].dropna().unique().tolist())
    sel_provider = st.selectbox("Cloud Provider", providers)

    categories = ["All"] + sorted(billing_df["service_category"].dropna().unique().tolist())
    sel_category = st.selectbox("Service Category", categories)

    departments = ["All"] + sorted(billing_df["department"].dropna().unique().tolist())
    sel_dept = st.selectbox("Department", departments)

    projects = ["All"] + sorted(billing_df["project"].dropna().unique().tolist())
    sel_project = st.selectbox("Project", projects)

    environments = ["All"] + sorted(billing_df["environment"].dropna().unique().tolist())
    sel_env = st.selectbox("Environment", environments)

    regions = ["All"] + sorted(billing_df["region"].dropna().unique().tolist())
    sel_region = st.selectbox("Region", regions)

    min_d = billing_df["billing_date"].min().date()
    max_d = billing_df["billing_date"].max().date()
    date_range = st.date_input("Date Range", value=(min_d, max_d), min_value=min_d, max_value=max_d)

    search_text = st.text_input("🔍 Search Service / Resource", "")

# Apply filters
fdf = billing_df.copy()

if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    fdf = fdf[(fdf["billing_date"].dt.date >= date_range[0]) &
              (fdf["billing_date"].dt.date <= date_range[1])]

if sel_provider != "All":
    fdf = fdf[fdf["cloud_provider"] == sel_provider]
if sel_category != "All":
    fdf = fdf[fdf["service_category"] == sel_category]
if sel_dept != "All":
    fdf = fdf[fdf["department"] == sel_dept]
if sel_project != "All":
    fdf = fdf[fdf["project"] == sel_project]
if sel_env != "All":
    fdf = fdf[fdf["environment"] == sel_env]
if sel_region != "All":
    fdf = fdf[fdf["region"] == sel_region]
if search_text:
    mask = (
        fdf["service_name"].str.contains(search_text, case=False, na=False) |
        fdf.get("resource_id", pd.Series(dtype=str)).str.contains(search_text, case=False, na=False)
    )
    fdf = fdf[mask]

if fdf.empty:
    st.warning("No records match the current filters. Try adjusting your selections.")
    st.stop()

# ── Summary metrics ──────────────────────────────────────────────────────────
total_cost  = float(fdf["total_cost"].sum())
num_records = len(fdf)
num_services= fdf["service_name"].nunique()
avg_daily   = fdf.groupby("billing_date")["total_cost"].sum().mean()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Spend",      _inr(total_cost))
c2.metric("Filtered Records", f"{num_records:,}")
c3.metric("Unique Services",  str(num_services))
c4.metric("Avg Daily Spend",  _inr(avg_daily))

st.markdown("---")

# ── Charts ───────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(
    ["📈 Daily Spend", "🏷️ By Service", "🗂️ By Dimension", "🔄 Period Comparison"]
)

with tab1:
    daily = daily_spend_series(fdf)
    st.plotly_chart(daily_spend_line(daily, title="Daily Cloud Spending (Filtered)"), use_container_width=True)

with tab2:
    col_a, col_b = st.columns(2)
    svc_agg = aggregate_by(fdf, "service_name")
    col_a.plotly_chart(spend_by_service_bar(svc_agg, n=10), use_container_width=True)

    prov_agg = fdf.groupby("cloud_provider")["total_cost"].sum().reset_index()
    col_b.plotly_chart(provider_pie(prov_agg), use_container_width=True)

with tab3:
    dim = st.selectbox("Group by", ["department", "project", "environment", "region", "service_category"])
    dim_agg = aggregate_by(fdf, dim)
    col_x, col_y = st.columns(2)
    col_x.plotly_chart(
        spend_donut(dim_agg, dim, title=f"Spend by {dim.capitalize()}"),
        use_container_width=True,
    )
    col_y.plotly_chart(
        spend_by_service_bar(dim_agg.rename(columns={dim: "service_name"}),
                             title=f"Spend by {dim.capitalize()}"),
        use_container_width=True,
    )

with tab4:
    st.markdown("### Period-over-Period Comparison")
    total_days = (fdf["billing_date"].max() - fdf["billing_date"].min()).days

    if total_days < 14:
        st.info("At least 14 days of data required for period comparison.")
    else:
        mid_date = fdf["billing_date"].min() + (fdf["billing_date"].max() - fdf["billing_date"].min()) / 2

        grp_col = st.selectbox("Compare by", ["service_name", "cloud_provider", "department", "project"])

        comp_df = compare_periods(
            fdf,
            current_start=str(mid_date.date()),
            current_end=str(fdf["billing_date"].max().date()),
            previous_start=str(fdf["billing_date"].min().date()),
            previous_end=str(mid_date.date()),
            group_col=grp_col,
        )

        comp_display = comp_df.head(20).copy()
        comp_display["current_cost"]  = comp_display["current_cost"].map(lambda x: f"₹{x:,.0f}")
        comp_display["previous_cost"] = comp_display["previous_cost"].map(lambda x: f"₹{x:,.0f}")
        comp_display["change"]        = comp_display["change"].map(lambda x: f"₹{x:+,.0f}")
        comp_display["pct_change"]    = comp_display["pct_change"].map(
            lambda x: f"{x:+.1f}%" if x is not None else "N/A"
        )
        st.dataframe(comp_display, use_container_width=True, hide_index=True)

# ── Detailed records table ────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 📋 Billing Records")

display_cols = [
    "billing_date", "cloud_provider", "service_name", "service_category",
    "region", "project", "department", "environment",
    "usage_quantity", "usage_unit", "unit_price", "total_cost", "currency",
]
display_cols = [c for c in display_cols if c in fdf.columns]

records_display = fdf[display_cols].copy()
records_display["billing_date"] = records_display["billing_date"].dt.strftime("%Y-%m-%d")
records_display["total_cost"]   = records_display["total_cost"].map(lambda x: f"₹{x:,.2f}")
records_display = records_display.sort_values("billing_date", ascending=False).reset_index(drop=True)

sort_col = st.selectbox("Sort records by", ["billing_date", "total_cost", "service_name", "cloud_provider"])
ascending = st.checkbox("Ascending order", value=False)
records_display = fdf[display_cols].copy()
records_display["billing_date"] = records_display["billing_date"].dt.strftime("%Y-%m-%d")
sort_col_actual = sort_col if sort_col in records_display.columns else "billing_date"
records_display = records_display.sort_values(sort_col_actual, ascending=ascending).reset_index(drop=True)

# Format for display
records_display["total_cost"]  = records_display["total_cost"].map(lambda x: f"₹{x:,.2f}")
if "unit_price" in records_display.columns:
    records_display["unit_price"] = records_display["unit_price"].map(lambda x: f"₹{x:.4f}")

st.dataframe(records_display.head(500), use_container_width=True, hide_index=True)
st.caption(f"Showing up to 500 of {num_records:,} filtered records.")

# ── Export ────────────────────────────────────────────────────────────────────
st.markdown("---")
col_exp1, col_exp2 = st.columns([1, 3])

with col_exp1:
    export_df = fdf[display_cols].copy()
    export_df["billing_date"] = pd.to_datetime(export_df["billing_date"]).dt.strftime("%Y-%m-%d")
    csv_bytes = export_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Export Filtered Records (CSV)",
        data=csv_bytes,
        file_name="finops_billing_export.csv",
        mime="text/csv",
    )

# ── SQL analytics summary ─────────────────────────────────────────────────────
with st.expander("📊 SQL Analytical Summaries"):
    query_type = st.selectbox("Analytical Query", [
        "Total by Service", "Total by Provider", "Total by Department",
        "Total by Project", "Total by Region", "Total by Environment",
        "Daily Spend", "Monthly Spend",
    ])

    q_map = {
        "Total by Service":     ("service_name",     fdf.groupby("service_name")["total_cost"].sum().reset_index()),
        "Total by Provider":    ("cloud_provider",   fdf.groupby("cloud_provider")["total_cost"].sum().reset_index()),
        "Total by Department":  ("department",       fdf.groupby("department")["total_cost"].sum().reset_index()),
        "Total by Project":     ("project",          fdf.groupby("project")["total_cost"].sum().reset_index()),
        "Total by Region":      ("region",           fdf.groupby("region")["total_cost"].sum().reset_index()),
        "Total by Environment": ("environment",      fdf.groupby("environment")["total_cost"].sum().reset_index()),
        "Daily Spend":          ("billing_date",     fdf.groupby(fdf["billing_date"].dt.date)["total_cost"].sum().reset_index()),
        "Monthly Spend":        ("billing_date",     None),
    }

    if query_type == "Monthly Spend":
        tmp = fdf.copy()
        tmp["month"] = tmp["billing_date"].dt.to_period("M").astype(str)
        result_df = tmp.groupby("month")["total_cost"].sum().reset_index()
    else:
        _, result_df = q_map[query_type]

    result_df = result_df.sort_values("total_cost", ascending=False)
    result_df["total_cost"] = result_df["total_cost"].map(lambda x: f"₹{x:,.2f}")
    st.dataframe(result_df, use_container_width=True, hide_index=True)
