"""
budget_engine.py — Budget calculation and monitoring for FinOps Intelligence.

Implements budget utilisation, remaining budget, and month-end projections.
Threshold logic is configurable so the UI can expose it to users.
"""

import logging
from datetime import date
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default thresholds (configurable via UI)
# ---------------------------------------------------------------------------

DEFAULT_THRESHOLDS = {
    "healthy":    70.0,   # below this = Healthy
    "attention":  90.0,   # 70–90 = Attention
    "near_limit": 100.0,  # 90–100 = Near Limit
    # above 100 = Over Budget
}

STATUS_COLORS = {
    "Healthy":    "#22C55E",
    "Attention":  "#F59E0B",
    "Near Limit": "#EF4444",
    "Over Budget":"#7C3AED",
}


# ---------------------------------------------------------------------------
# Core formulae
# ---------------------------------------------------------------------------

def budget_utilisation(actual: float, budget: float) -> Optional[float]:
    """
    Budget Utilisation (%) = Actual Spend / Budget × 100

    Returns None when budget is zero (undefined).
    """
    if budget <= 0:
        return None
    return actual / budget * 100


def remaining_budget(actual: float, budget: float) -> float:
    """Remaining Budget = Budget − Actual Spend (can be negative when over budget)."""
    return budget - actual


def project_month_end(
    actual_so_far: float,
    current_day: int,
    days_in_month: int,
) -> Optional[float]:
    """
    Projected Month-End Spend = Average Daily Spend × Days in Month

    Assumptions:
    - Spending is uniform throughout the month (simple linear projection).
    - Requires at least 3 days of data (current_day >= 3) to avoid
      extrapolating from a single day.
    - Returns None when current_day < 3 or actual_so_far is zero.

    This is an approximation. Actual spending may be front- or back-loaded.
    """
    if current_day < 3 or actual_so_far <= 0:
        return None
    avg_daily = actual_so_far / current_day
    return avg_daily * days_in_month


def budget_status(utilisation_pct: float, thresholds: Optional[dict] = None) -> str:
    """Map a utilisation percentage to a status label."""
    t = thresholds or DEFAULT_THRESHOLDS
    if utilisation_pct < t["healthy"]:
        return "Healthy"
    if utilisation_pct < t["attention"]:
        return "Attention"
    if utilisation_pct <= t["near_limit"]:
        return "Near Limit"
    return "Over Budget"


# ---------------------------------------------------------------------------
# Budget monitoring aggregation
# ---------------------------------------------------------------------------

def build_budget_summary(
    budgets_df: pd.DataFrame,
    billing_df: pd.DataFrame,
    ai_df: pd.DataFrame,
    year: int,
    month: int,
    thresholds: Optional[dict] = None,
) -> pd.DataFrame:
    """
    Merge budget definitions with actual spend to produce a budget summary table.

    Handles:
    - overall, provider, department, project, ai budget types
    - Month-end projections (documented limitations inline)
    - Consistent currency (INR)
    """
    if budgets_df.empty:
        return pd.DataFrame()

    today      = date.today()
    current_day= today.day if (today.year == year and today.month == month) else 31
    import calendar
    days_in_month = calendar.monthrange(year, month)[1]

    # Month filter
    month_billing = billing_df.copy()
    if not month_billing.empty:
        month_billing["billing_date"] = pd.to_datetime(month_billing["billing_date"])
        month_billing = month_billing[
            (month_billing["billing_date"].dt.year  == year) &
            (month_billing["billing_date"].dt.month == month)
        ]

    month_ai = ai_df.copy()
    if not month_ai.empty:
        month_ai["request_timestamp"] = pd.to_datetime(month_ai["request_timestamp"])
        month_ai = month_ai[
            (month_ai["request_timestamp"].dt.year  == year) &
            (month_ai["request_timestamp"].dt.month == month)
        ]

    # Precompute spend groups
    cloud_total  = float(month_billing["total_cost"].sum()) if not month_billing.empty else 0.0
    ai_total     = float(month_ai["estimated_total_cost"].sum()) if not month_ai.empty else 0.0

    prov_spend   = month_billing.groupby("cloud_provider")["total_cost"].sum().to_dict() \
        if not month_billing.empty else {}
    dept_spend   = month_billing.groupby("department")["total_cost"].sum().to_dict() \
        if not month_billing.empty else {}
    proj_spend   = month_billing.groupby("project")["total_cost"].sum().to_dict() \
        if not month_billing.empty else {}

    rows = []
    for _, row in budgets_df.iterrows():
        btype  = row["budget_type"]
        name   = row["name"]
        budget = float(row["monthly_budget"])

        if btype == "overall":
            actual = cloud_total
        elif btype == "provider":
            actual = prov_spend.get(name, 0.0)
        elif btype == "department":
            actual = dept_spend.get(name, 0.0)
        elif btype == "project":
            actual = proj_spend.get(name, 0.0)
        elif btype == "ai":
            actual = ai_total
        else:
            actual = 0.0

        util    = budget_utilisation(actual, budget)
        remain  = remaining_budget(actual, budget)
        proj    = project_month_end(actual, current_day, days_in_month)
        status  = budget_status(util or 0.0, thresholds)

        rows.append({
            "budget_type":     btype,
            "name":            name,
            "monthly_budget":  budget,
            "actual_spend":    actual,
            "remaining":       remain,
            "utilisation_pct": util,
            "projected_eom":   proj,
            "status":          status,
            "currency":        row.get("currency", "INR"),
        })

    result = pd.DataFrame(rows)
    return result


# ---------------------------------------------------------------------------
# Alert detection
# ---------------------------------------------------------------------------

def get_over_budget_alerts(summary_df: pd.DataFrame) -> pd.DataFrame:
    """Return rows where status is 'Over Budget' or 'Near Limit'."""
    if summary_df.empty:
        return pd.DataFrame()
    return summary_df[summary_df["status"].isin(["Over Budget", "Near Limit"])].reset_index(drop=True)
