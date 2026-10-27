"""
pages/optimization.py — Cost Optimization Recommendations for FinOps Intelligence.

Generates actionable recommendations based on actual calculations from the active dataset.
Distinguishes between observed spending increases, potential optimization opportunities,
and simulated examples without fabricating savings.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import datetime
import streamlit as st
import pandas as pd

from src import database as db
from src.recommendation_engine import generate_recommendations
from src.budget_engine import build_budget_summary

def _inr(v: float | None) -> str:
    if v is None:
        return "N/A"
    if v >= 1_00_000:
        return f"₹{v/1_00_000:.2f}L"
    return f"₹{v:,.0f}"

def _badge_priority(p: str) -> str:
    cls = {
        "Critical": "badge badge-critical",
        "High":     "badge badge-high",
        "Medium":   "badge badge-medium",
        "Low":      "badge badge-low",
    }.get(p, "badge")
    return f"<span class='{cls}'>{p}</span>"

def _badge_confidence(c: str) -> str:
    cls = {
        "High":   "badge badge-healthy",
        "Medium": "badge badge-attention",
        "Low":    "badge badge-near",
    }.get(c, "badge")
    return f"<span class='{cls}'>{c} Confidence</span>"

st.markdown("# 💡 Cost Optimization Recommendations")
st.markdown(
    "<p style='color:#64748B; margin-top:-0.5rem; font-size:0.9rem;'>"
    "Data-driven recommendations generated from expenditure anomalies, budget utilization, "
    "storage allocation patterns, and AI token economics."
    "</p>",
    unsafe_allow_html=True,
)

billing_df = db.get_billing_df()
ai_df = db.get_ai_df()

if billing_df.empty:
    st.warning("No billing data found. Go to **📁 Data Management** to load sample data.")
    st.stop()

# Budget summary for current period
today = datetime.date.today()
budgets_df = db.get_budgets(today.year, today.month)
b_summary = build_budget_summary(budgets_df, billing_df, ai_df, today.year, today.month) if not budgets_df.empty else None

# Generate recommendations
recs_df = generate_recommendations(billing_df, ai_df, b_summary)

# ── Sidebar Filter ────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("---")
    st.markdown("**RECOMMENDATION FILTERS**")
    cats = ["All"] + sorted(recs_df["category"].unique().tolist()) if not recs_df.empty else ["All"]
    sel_cat = st.selectbox("Category", cats)

    priorities = ["All", "Critical", "High", "Medium", "Low"]
    sel_prio = st.selectbox("Priority", priorities)

filtered_recs = recs_df.copy()
if not filtered_recs.empty:
    if sel_cat != "All":
        filtered_recs = filtered_recs[filtered_recs["category"] == sel_cat]
    if sel_prio != "All":
        filtered_recs = filtered_recs[filtered_recs["priority"] == sel_prio]

# ── Summary Metrics ───────────────────────────────────────────────────────────
total_recs = len(filtered_recs)
potential_impact = filtered_recs["estimated_impact"].dropna().sum() if not filtered_recs.empty else 0.0
crit_count = int((filtered_recs["priority"] == "Critical").sum()) if not filtered_recs.empty else 0
high_count = int((filtered_recs["priority"] == "High").sum()) if not filtered_recs.empty else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Active Recommendations", str(total_recs))
c2.metric("Critical / High Actions", f"{crit_count} / {high_count}")
c3.metric("Est. Potential Impact", _inr(potential_impact) if potential_impact > 0 else "Calculable per item")
c4.metric("Savings Type", "Simulated / Potential")

st.markdown("""
<div class='disclaimer' style='margin: 1rem 0;'>
    ⚠️ <b>FinOps Verification Principle:</b>
    All figures presented reflect <i>potential opportunities</i> or <i>observed cost growth</i>,
    never claimed as <i>realized savings</i> until engineering validation and deployment occur.
    In synthetic environments, recommendations serve as illustrative optimization scenarios.
</div>
""", unsafe_allow_html=True)

# ── Recommendations List ──────────────────────────────────────────────────────
if filtered_recs.empty:
    st.info("No recommendations found for the selected filter.")
else:
    for idx, row in filtered_recs.iterrows():
        impact_str = f"Estimated Impact: **{_inr(row['estimated_impact'])}**" if pd.notna(row['estimated_impact']) else "Impact: Subject to workload investigation"
        st.markdown(f"""
        <div class="finops-card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-size:1.1rem; font-weight:600; color:#0F172A;">{row['title']}</span>
                <div>
                    {_badge_priority(row['priority'])} &nbsp; {_badge_confidence(row['confidence_level'])}
                </div>
            </div>
            <div style="font-size:0.85rem; color:#64748B; margin-top:0.3rem;">
                <b>Category:</b> {row['category']} &nbsp;|&nbsp; <b>Affected Resource/Scope:</b> {row['affected_resource']}
            </div>
            <div style="margin-top:0.75rem; background:#F8FAFC; padding:0.75rem 1rem; border-radius:8px; border:1px solid #E2E8F0; font-size:0.875rem;">
                <b>📊 Evidence Observed:</b><br>{row['evidence']}
            </div>
            <div style="margin-top:0.75rem; font-size:0.9rem; color:#1E293B;">
                <b>🛠️ Recommended Engineering Action:</b><br>{row['recommended_action']}
            </div>
            <div style="margin-top:0.75rem; font-size:0.85rem; color:#2563EB;">
                💰 {impact_str}
            </div>
        </div>
        """, unsafe_allow_html=True)

# ── Methodology Note ─────────────────────────────────────────────────────────
with st.expander("ℹ️ FinOps Optimization Engine Rules & Standards"):
    st.markdown("""
    ### FinOps Recommendation Standards
    To avoid misleading optimization claims:
    1. **Observed Cost Increases:** Identified by comparing the second half of the time window against the first half. Growth $>50\\%$ and absolute increase $>₹5,000$ triggers a review recommendation.
    2. **Budget Thresholds:** Projects or services running at $\\ge 90\\%$ or $>100\\%$ of budget trigger preventative realignment or capacity adjustments.
    3. **Storage Tiering:** Storage spend exceeding $20\\%$ of total cloud bill flags lifecycle policy reviews. Potential savings are conservatively estimated at 15% with a low-confidence tag (since actual object access frequency telemetry is absent).
    4. **AI Efficiency:** Model-routing disparities ($>5\\times$ price differences between models) and application cost outliers trigger token efficiency optimization.
    5. **Rightsizing & Idle Telemetry:** CPU/RAM utilization metrics are required before recommending machine down-sizing, adhering strictly to FinOps Foundation best practices.
    """)
