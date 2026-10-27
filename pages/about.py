"""
pages/about.py — About FinOps Intelligence Platform & Engineering Architecture.
"""

import streamlit as st

st.markdown("# ℹ️ About FinOps Intelligence")
st.markdown(
    "<p style='color:#64748B; margin-top:-0.5rem; font-size:0.9rem;'>"
    "Cloud & AI Cost Intelligence Platform — Architecture, Engineering Design & Principles."
    "</p>",
    unsafe_allow_html=True,
)

st.markdown("""
<div class="finops-card">
    <div style="font-size:1.15rem; font-weight:700; color:#0F172A; margin-bottom:0.5rem;">
        🎯 Project Objective & Role Context
    </div>
    <div style="font-size:0.9rem; line-height:1.6; color:#334155;">
        <b>FinOps Intelligence</b> is designed as an enterprise-grade cloud cost observability and AI infrastructure economics platform.
        Developed for technical demonstration in <b>Cloud and AI FinOps Engineering</b> roles, the application integrates
        principles from data analytics, statistical anomaly detection, cloud billing schemas, and LLM token pricing models.
        <br><br>
        Rather than presenting static mockups, the platform executes live analytical SQL queries, rolling statistical models,
        strict data validation pipelines, and persistent investigation state across multi-cloud environments.
    </div>
</div>
""", unsafe_allow_html=True)

col_a1, col_a2 = st.columns(2)

with col_a1:
    st.markdown("""
    ### 🏗️ Technical Architecture
    - **Frontend:** Streamlit with custom design tokens, responsive CSS metric containers, and custom typography.
    - **Visualization:** Plotly interactive charts with standardized cross-page color palettes and zero layout shifts.
    - **Data Layer:** Normalized SQLite database with parameterized SQL queries, indexing on dates/providers/projects, and clean separation between access logic and UI.
    - **Backend Analytics:**
      - Time-series rolling Z-score and Interquartile Range (IQR) detection.
      - Dynamic period-over-period variance calculation.
      - Configurable linear month-end budget projections.
      - Explicit token price modeling for frontier LLMs.
    """)

with col_a2:
    st.markdown("""
    ### 🛡️ FinOps Verification & Integrity
    - **Observed vs. Claimed Savings:** Never confuses observed spending increases with realized savings.
    - **Safe Month-End Projections:** Requires $\\ge 3$ days of historical data to extrapolate monthly trends, preventing single-day distortion.
    - **Zero Division Safety:** Handles zero variance, missing calendar dates, and newly provisioned services gracefully.
    - **Persistence:** Investigation states (<i>New, Investigating, Resolved, False Positive</i>) persist directly to SQLite.
    """)

st.markdown("---")

st.markdown("""
### 🧠 Core Mathematical Formulations

#### 1. Statistical Cost Anomaly Detection
$$\\mu_t = \\frac{1}{W} \\sum_{i=1}^{W} x_{t-i}, \\quad \\sigma_t = \\sqrt{\\frac{1}{W} \\sum_{i=1}^{W} (x_{t-i} - \\mu_t)^2}$$
$$Z_t = \\frac{x_t - \\mu_t}{\\sigma_t}$$
Observations where $Z_t > k$ and $\\Delta x_t \\ge \\Delta_{min}$ trigger deviation alerts.

#### 2. Budget Utilisation & Projections
$$\\text{Utilisation (\\%)} = \\frac{\\text{Actual Spend}}{\\text{Configured Budget}} \\times 100$$
$$\\text{Remaining Budget} = \\text{Configured Budget} - \\text{Actual Spend}$$
$$\\text{Projected Month-End Spend} = \\left( \\frac{\\text{Actual Spend to Date}}{\\text{Current Day}} \\right) \\times \\text{Days in Month}$$

#### 3. LLM Token Economics
$$\\text{Estimated Request Cost} = \\left( \\frac{\\text{Input Tokens}}{10^6} \\times P_{in} \\right) + \\left( \\frac{\\text{Output Tokens}}{10^6} \\times P_{out} \\right)$$

---
<div class='disclaimer'>
    ⚠️ <b>Disclaimer:</b><br>
    This application is a portfolio and engineering demonstration project. The default dataset is synthetic and deterministically generated.
    The system is not affiliated with or directly connected to AWS Cost Explorer, Azure Cost Management, or Google Cloud Billing APIs.
</div>
""", unsafe_allow_html=True)
