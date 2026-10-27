"""
app.py — Entry point for FinOps Intelligence Dashboard.

Run with:
    streamlit run app.py
"""

import sys
import os
import logging
from pathlib import Path

# Make src/ importable
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

# ---------------------------------------------------------------------------
# Page configuration — must be first Streamlit call
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="FinOps Intelligence",
    page_icon="💹",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": "FinOps Intelligence — Cloud & AI Cost Analytics Platform. "
                 "Portfolio project using synthetic data. Not a production billing tool.",
    },
)

# ---------------------------------------------------------------------------
# Global CSS
# ---------------------------------------------------------------------------

st.markdown("""
<style>
/* ── Global typography and background ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

.main .block-container {
    padding: 1.5rem 2rem 2rem 2rem;
    max-width: 1400px;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0F172A 0%, #1E293B 100%) !important;
    min-width: 240px !important;
}
[data-testid="stSidebar"] * {
    color: #CBD5E1 !important;
}
[data-testid="stSidebar"] .stRadio label {
    color: #94A3B8 !important;
    font-size: 0.875rem;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    color: #64748B !important;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}

/* ── Metric cards ── */
[data-testid="metric-container"] {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 1rem 1.25rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
[data-testid="metric-container"] label {
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    color: #64748B !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 1.6rem !important;
    font-weight: 700 !important;
    color: #0F172A !important;
}

/* ── Page headings ── */
h1 { font-size: 1.75rem !important; font-weight: 700 !important; color: #0F172A !important; }
h2 { font-size: 1.3rem !important;  font-weight: 600 !important; color: #1E293B !important; }
h3 { font-size: 1.05rem !important; font-weight: 600 !important; color: #334155 !important; }

/* ── Cards / panels ── */
.finops-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

/* ── Status badges ── */
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 9999px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.04em;
}
.badge-healthy    { background: #DCFCE7; color: #15803D; }
.badge-attention  { background: #FEF9C3; color: #854D0E; }
.badge-near       { background: #FEE2E2; color: #B91C1C; }
.badge-over       { background: #EDE9FE; color: #5B21B6; }
.badge-critical   { background: #EDE9FE; color: #5B21B6; }
.badge-high       { background: #FEE2E2; color: #B91C1C; }
.badge-medium     { background: #FEF9C3; color: #854D0E; }
.badge-low        { background: #DCFCE7; color: #15803D; }
.badge-new        { background: #DBEAFE; color: #1D4ED8; }
.badge-resolved   { background: #DCFCE7; color: #15803D; }
.badge-fp         { background: #F1F5F9; color: #475569; }

/* ── Dividers ── */
hr { border-color: #E2E8F0 !important; margin: 1rem 0 !important; }

/* ── Insight boxes ── */
.insight-box {
    background: #F0F9FF;
    border-left: 3px solid #2563EB;
    border-radius: 0 8px 8px 0;
    padding: 0.6rem 1rem;
    margin: 0.4rem 0;
    font-size: 0.875rem;
    color: #1E40AF;
}

/* ── Alerts ── */
.alert-over  { background: #FEE2E2; border-left: 4px solid #EF4444; padding: 0.75rem 1rem; border-radius: 0 8px 8px 0; margin: 0.4rem 0; }
.alert-near  { background: #FEF9C3; border-left: 4px solid #F59E0B; padding: 0.75rem 1rem; border-radius: 0 8px 8px 0; margin: 0.4rem 0; }

/* ── Disclaimer ── */
.disclaimer {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 0.6rem 1rem;
    font-size: 0.75rem;
    color: #64748B;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Initialise database on first run
# ---------------------------------------------------------------------------

from src.database import init_db, get_table_counts

@st.cache_resource(show_spinner=False)
def _init_database():
    init_db()
    return True

_init_database()

# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------

PAGES = {
    "📊 Overview":                      "pages/overview.py",
    "☁️ Cloud Cost Explorer":          "pages/cloud_cost_explorer.py",
    "💰 Budget Monitoring":             "pages/budget_monitoring.py",
    "🚨 Cost Anomaly Detection":        "pages/anomaly_detection.py",
    "🤖 AI Cost Analytics":             "pages/ai_cost_analytics.py",
    "💡 Optimization Recommendations":  "pages/optimization.py",
    "📁 Data Management":               "pages/data_management.py",
    "ℹ️ About Project":                 "pages/about.py",
}

with st.sidebar:
    st.markdown("""
    <div style="padding: 1rem 0 0.5rem 0;">
        <div style="font-size:1.5rem; font-weight:700; color:#F8FAFC; letter-spacing:-0.02em;">
            💹 FinOps Intelligence
        </div>
        <div style="font-size:0.72rem; color:#64748B; margin-top:2px; text-transform:uppercase; letter-spacing:0.08em;">
            Cloud & AI Cost Intelligence
        </div>
    </div>
    <hr style="border-color:#334155; margin: 0.75rem 0 1rem 0;"/>
    """, unsafe_allow_html=True)

    st.markdown("**NAVIGATION**")
    page_label = st.radio(
        "Navigate",
        list(PAGES.keys()),
        label_visibility="collapsed",
    )

    st.markdown("<hr style='border-color:#334155; margin: 1.5rem 0 0.75rem 0;'/>", unsafe_allow_html=True)

    # Quick stats
    try:
        counts = get_table_counts()
        billing_n = counts.get("cloud_billing", 0)
        ai_n      = counts.get("ai_usage", 0)
        anomaly_n = counts.get("anomaly_events", 0)
        st.markdown(f"""
        <div style='font-size:0.65rem; color:#475569; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:0.4rem;'>DATABASE STATUS</div>
        <div style='font-size:0.78rem; color:#94A3B8;'>
            Billing records: <b style='color:#CBD5E1;'>{billing_n:,}</b><br>
            AI records: <b style='color:#CBD5E1;'>{ai_n:,}</b><br>
            Anomalies: <b style='color:#CBD5E1;'>{anomaly_n:,}</b>
        </div>
        """, unsafe_allow_html=True)
    except Exception:
        pass

    st.markdown("""
    <div style='margin-top:1.5rem; font-size:0.65rem; color:#475569; line-height:1.5;'>
        ⚠️ Default dataset is synthetic. Not connected to any cloud billing provider.
        Portfolio project for internship demonstration purposes.
    </div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Load and run the selected page
# ---------------------------------------------------------------------------

page_path = PAGES[page_label]

try:
    with open(page_path, "r") as f:
        code = f.read()
    exec(compile(code, page_path, "exec"), {"__name__": "__main__"})
except FileNotFoundError:
    st.error(f"Page file not found: `{page_path}`")
    st.info("Use **Data Management** to load sample data, then navigate to other pages.")
except Exception as exc:
    import traceback
    st.error(f"An error occurred loading this page.")
    with st.expander("Error details (for debugging)"):
        st.code(traceback.format_exc())
    logging.exception("Page error: %s", page_path)
