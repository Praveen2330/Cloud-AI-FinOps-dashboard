"""
cloud_analytics.py — Cloud cost aggregation and analysis functions.

All functions operate on DataFrames retrieved from the database layer,
keeping analytics logic decoupled from database access.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Period comparison helpers
# ---------------------------------------------------------------------------

def split_periods(df: pd.DataFrame, date_col: str = "billing_date") -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split a DataFrame into the most-recent half and the preceding half
    for period-over-period comparisons.
    """
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    if df.empty:
        return df, df
    mid = df[date_col].min() + (df[date_col].max() - df[date_col].min()) / 2
    current = df[df[date_col] > mid]
    previous= df[df[date_col] <= mid]
    return current, previous


def pct_change(current: float, previous: float) -> Optional[float]:
    """Return percentage change, None when previous is zero."""
    if previous == 0:
        return None
    return (current - previous) / previous * 100


# ---------------------------------------------------------------------------
# High-level KPI aggregations
# ---------------------------------------------------------------------------

def total_spend(df: pd.DataFrame, cost_col: str = "total_cost") -> float:
    if df.empty or cost_col not in df.columns:
        return 0.0
    return float(df[cost_col].sum())


def spend_by_period(df: pd.DataFrame, date_col: str = "billing_date") -> dict:
    """
    Return current, previous, and percentage change for a billing DataFrame.
    """
    curr_df, prev_df = split_periods(df, date_col)
    curr  = total_spend(curr_df)
    prev  = total_spend(prev_df)
    delta = pct_change(curr, prev)
    return {"current": curr, "previous": prev, "pct_change": delta}


def get_kpi_summary(billing_df: pd.DataFrame, ai_df: pd.DataFrame) -> dict:
    """
    Calculate executive KPI values from the active billing and AI DataFrames.
    """
    cloud_total = total_spend(billing_df)
    ai_total    = total_spend(ai_df, "estimated_total_cost") if not ai_df.empty else 0.0

    curr, prev = split_periods(billing_df)
    cloud_pct  = pct_change(total_spend(curr), total_spend(prev))

    curr_ai, prev_ai = split_periods(ai_df, "request_timestamp") if not ai_df.empty else (pd.DataFrame(), pd.DataFrame())
    ai_pct = pct_change(
        total_spend(curr_ai, "estimated_total_cost"),
        total_spend(prev_ai, "estimated_total_cost"),
    )

    return {
        "cloud_total":  cloud_total,
        "ai_total":     ai_total,
        "cloud_pct":    cloud_pct,
        "ai_pct":       ai_pct,
    }


# ---------------------------------------------------------------------------
# Aggregation utilities
# ---------------------------------------------------------------------------

def aggregate_by(df: pd.DataFrame, group_col: str, cost_col: str = "total_cost") -> pd.DataFrame:
    """Group-by a single column and sum cost."""
    if df.empty:
        return pd.DataFrame(columns=[group_col, cost_col])
    result = (
        df.groupby(group_col, as_index=False)[cost_col]
        .sum()
        .sort_values(cost_col, ascending=False)
        .reset_index(drop=True)
    )
    result["pct_of_total"] = (result[cost_col] / result[cost_col].sum() * 100).round(2)
    return result


def daily_spend_series(df: pd.DataFrame, date_col: str = "billing_date",
                        cost_col: str = "total_cost") -> pd.DataFrame:
    """Return a daily time series of spending."""
    if df.empty:
        return pd.DataFrame(columns=[date_col, cost_col])
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    result = (
        df.groupby(date_col, as_index=False)[cost_col]
        .sum()
        .sort_values(date_col)
        .reset_index(drop=True)
    )
    return result


def monthly_spend_series(df: pd.DataFrame, date_col: str = "billing_date",
                          cost_col: str = "total_cost") -> pd.DataFrame:
    """Return a monthly time series with year-month label."""
    if df.empty:
        return pd.DataFrame(columns=["year_month", cost_col])
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df["year_month"] = df[date_col].dt.to_period("M").astype(str)
    result = (
        df.groupby("year_month", as_index=False)[cost_col]
        .sum()
        .sort_values("year_month")
        .reset_index(drop=True)
    )
    return result


def top_services(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Return the top N services by cost."""
    return aggregate_by(df, "service_name").head(n)


def top_projects(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    return aggregate_by(df, "project").head(n)


def top_departments(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    return aggregate_by(df, "department").head(n)


def top_regions(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    return aggregate_by(df, "region").head(n)


# ---------------------------------------------------------------------------
# Period-over-period comparison
# ---------------------------------------------------------------------------

def compare_periods(
    df: pd.DataFrame,
    current_start: str,
    current_end: str,
    previous_start: str,
    previous_end: str,
    group_col: str = "service_name",
) -> pd.DataFrame:
    """
    Compare two periods for a given grouping column.
    Returns a DataFrame with current_cost, previous_cost, change, and pct_change.
    """
    df = df.copy()
    df["billing_date"] = pd.to_datetime(df["billing_date"])

    curr = df[(df["billing_date"] >= pd.Timestamp(current_start)) &
              (df["billing_date"] <= pd.Timestamp(current_end))]
    prev = df[(df["billing_date"] >= pd.Timestamp(previous_start)) &
              (df["billing_date"] <= pd.Timestamp(previous_end))]

    curr_agg = curr.groupby(group_col)["total_cost"].sum().rename("current_cost")
    prev_agg = prev.groupby(group_col)["total_cost"].sum().rename("previous_cost")

    combined = pd.concat([curr_agg, prev_agg], axis=1).fillna(0).reset_index()
    combined["change"]     = combined["current_cost"] - combined["previous_cost"]
    combined["pct_change"] = combined.apply(
        lambda r: pct_change(r["current_cost"], r["previous_cost"]), axis=1
    )
    return combined.sort_values("current_cost", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Auto-generated insights
# ---------------------------------------------------------------------------

def generate_insights(billing_df: pd.DataFrame, ai_df: pd.DataFrame,
                       budget_df: Optional[pd.DataFrame] = None) -> list[str]:
    """
    Generate plain-English insights from the active dataset.
    All figures are computed dynamically — nothing is hardcoded.
    """
    insights = []
    if billing_df.empty:
        return ["No billing data available to generate insights."]

    billing_df = billing_df.copy()
    billing_df["billing_date"] = pd.to_datetime(billing_df["billing_date"])

    # 1. Top service by cost
    svc_agg = aggregate_by(billing_df, "service_name")
    if not svc_agg.empty:
        top_svc  = svc_agg.iloc[0]["service_name"]
        top_pct  = svc_agg.iloc[0]["pct_of_total"]
        insights.append(
            f"{top_svc} is the highest-spend cloud service, accounting for "
            f"{top_pct:.1f}% of total cloud expenditure."
        )

    # 2. Biggest spending increase (service)
    curr_df, prev_df = split_periods(billing_df)
    if not curr_df.empty and not prev_df.empty:
        curr_svc = curr_df.groupby("service_name")["total_cost"].sum()
        prev_svc = prev_df.groupby("service_name")["total_cost"].sum()
        comp     = pd.DataFrame({"curr": curr_svc, "prev": prev_svc}).fillna(0)
        comp["pct"] = comp.apply(lambda r: pct_change(r["curr"], r["prev"]), axis=1)
        comp = comp[comp["prev"] > 0].dropna(subset=["pct"])
        if not comp.empty:
            biggest = comp["pct"].idxmax()
            biggest_pct = comp.loc[biggest, "pct"]
            insights.append(
                f"{biggest} expenditure increased by {biggest_pct:.1f}% "
                f"compared with the previous period."
            )

    # 3. Department with highest spend
    dept_agg = aggregate_by(billing_df, "department")
    if not dept_agg.empty:
        top_dept = dept_agg.iloc[0]["department"]
        top_dept_pct = dept_agg.iloc[0]["pct_of_total"]
        insights.append(
            f"The {top_dept} department drives {top_dept_pct:.1f}% of total cloud spend."
        )

    # 4. Budget alert (most utilised project)
    if budget_df is not None and not budget_df.empty:
        proj_spend = billing_df.groupby("project")["total_cost"].sum()
        proj_budgets = budget_df[budget_df["budget_type"] == "project"].set_index("name")["monthly_budget"]
        combined = pd.DataFrame({"spend": proj_spend, "budget": proj_budgets}).dropna()
        if not combined.empty:
            combined["util"] = combined["spend"] / combined["budget"] * 100
            top_util = combined["util"].idxmax()
            util_pct = combined.loc[top_util, "util"]
            insights.append(
                f"The {top_util} project has used {util_pct:.1f}% of its monthly budget."
            )

    # 5. AI spend as % of total
    if not ai_df.empty:
        ai_total    = float(ai_df["estimated_total_cost"].sum())
        cloud_total = float(billing_df["total_cost"].sum())
        if cloud_total > 0:
            ai_pct = ai_total / cloud_total * 100
            insights.append(
                f"AI/LLM expenditure represents {ai_pct:.1f}% of total cloud infrastructure spend."
            )

    # 6. Weekend vs weekday
    billing_df["is_weekend"] = billing_df["billing_date"].dt.weekday >= 5
    wkday_avg = billing_df[~billing_df["is_weekend"]].groupby("billing_date")["total_cost"].sum().mean()
    wkend_avg = billing_df[billing_df["is_weekend"]].groupby("billing_date")["total_cost"].sum().mean()
    if pd.notna(wkday_avg) and pd.notna(wkend_avg) and wkday_avg > 0:
        diff = (wkday_avg - wkend_avg) / wkday_avg * 100
        insights.append(
            f"Average daily spend on weekdays is {diff:.1f}% higher than on weekends, "
            f"suggesting workload-driven cost patterns."
        )

    return insights
