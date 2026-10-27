"""
recommendation_engine.py — Cost optimisation recommendations for FinOps Intelligence.

Recommendations are generated from observable patterns in billing and AI usage data.
Every recommendation includes the evidence it is based on and an honest confidence level.

Labels:
  - "Observed spending increase"    : Factual, based on data.
  - "Potential optimisation"        : Suggested, requires investigation.
  - "Simulated example"             : Generated from synthetic data.
"""

import logging
from typing import Optional

import pandas as pd
import numpy as np

from .cloud_analytics import pct_change, aggregate_by

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Recommendation builders
# ---------------------------------------------------------------------------

def _rec(category: str, title: str, affected: str, evidence: str,
         action: str, impact: Optional[float] = None,
         confidence: str = "Medium", priority: str = "Medium") -> dict:
    return {
        "category":           category,
        "title":              title,
        "affected_resource":  affected,
        "evidence":           evidence,
        "recommended_action": action,
        "estimated_impact":   impact,
        "impact_currency":    "INR",
        "confidence_level":   confidence,
        "priority":           priority,
        "status":             "Open",
    }


# ---------------------------------------------------------------------------
# A. Spending increases
# ---------------------------------------------------------------------------

def _check_spending_increases(billing_df: pd.DataFrame) -> list[dict]:
    recs = []
    if billing_df.empty:
        return recs

    df = billing_df.copy()
    df["billing_date"] = pd.to_datetime(df["billing_date"])
    mid = df["billing_date"].min() + (df["billing_date"].max() - df["billing_date"].min()) / 2

    curr = df[df["billing_date"] > mid].groupby("service_name")["total_cost"].sum()
    prev = df[df["billing_date"] <= mid].groupby("service_name")["total_cost"].sum()

    for svc in curr.index:
        c = float(curr.get(svc, 0.0))
        p = float(prev.get(svc, 0.0))
        if p <= 0:
            continue
        pct = (c - p) / p * 100
        abs_inc = c - p
        if pct >= 50 and abs_inc >= 5000:
            priority = "High" if pct >= 100 else "Medium"
            recs.append(_rec(
                category="Spending Increase",
                title=f"Significant cost growth in {svc}",
                affected=svc,
                evidence=(
                    f"Current-period spend: ₹{c:,.0f}. "
                    f"Previous-period spend: ₹{p:,.0f}. "
                    f"Increase: {pct:.1f}% (₹{abs_inc:,.0f}). "
                    "This is an observed spending increase — root cause requires investigation."
                ),
                action=(
                    "Review resource usage, recent deployments, and workload changes for this service. "
                    "Check for unused resources or over-provisioning."
                ),
                impact=abs_inc,
                confidence="High",
                priority=priority,
            ))

    return recs[:5]  # limit to top 5


# ---------------------------------------------------------------------------
# B. Budget utilisation
# ---------------------------------------------------------------------------

def _check_budget_utilisation(summary_df: pd.DataFrame) -> list[dict]:
    recs = []
    if summary_df is None or summary_df.empty:
        return recs

    over = summary_df[summary_df["status"].isin(["Over Budget", "Near Limit"])]
    for _, row in over.iterrows():
        util = row.get("utilisation_pct", 0) or 0
        name = row["name"]
        btype= row["budget_type"]
        remain = float(row.get("remaining", 0) or 0)
        priority = "Critical" if row["status"] == "Over Budget" else "High"

        recs.append(_rec(
            category="Budget Optimisation",
            title=f"{btype.capitalize()} budget alert: {name}",
            affected=name,
            evidence=(
                f"{name} ({btype}) is at {util:.1f}% of its monthly budget. "
                f"Remaining: ₹{abs(remain):,.0f} {'over budget' if remain < 0 else 'remaining'}."
            ),
            action=(
                "Review recent spending for this budget category. "
                "Consider increasing the budget allocation if the spending is intentional, "
                "or identify services that can be scaled down."
            ),
            impact=abs(remain) if remain < 0 else None,
            confidence="High",
            priority=priority,
        ))

    return recs


# ---------------------------------------------------------------------------
# C. Storage optimisation opportunities
# ---------------------------------------------------------------------------

def _check_storage(billing_df: pd.DataFrame) -> list[dict]:
    recs = []
    if billing_df.empty:
        return recs

    df = billing_df.copy()
    storage = df[df["service_category"] == "Storage"]
    if storage.empty:
        return recs

    storage_total = float(storage["total_cost"].sum())
    total         = float(df["total_cost"].sum())
    if total <= 0:
        return recs

    storage_pct = storage_total / total * 100

    if storage_pct >= 20:
        by_service = storage.groupby("service_name")["total_cost"].sum().sort_values(ascending=False)
        top_svc    = by_service.index[0]
        top_cost   = float(by_service.iloc[0])

        recs.append(_rec(
            category="Storage Optimisation",
            title=f"Storage accounts for {storage_pct:.1f}% of total spend",
            affected=top_svc,
            evidence=(
                f"Storage services total ₹{storage_total:,.0f} ({storage_pct:.1f}% of cloud spend). "
                f"{top_svc} is the highest storage cost at ₹{top_cost:,.0f}. "
                "This recommendation is based on observed spend proportion only; "
                "actual storage lifecycle or utilisation data is not available."
            ),
            action=(
                "Review object lifecycle policies, data retention rules, and storage tiers. "
                "Identify infrequently accessed data that can be moved to cheaper storage classes."
            ),
            impact=storage_total * 0.15,  # potential, not verified
            confidence="Low",
            priority="Medium",
        ))

    return recs


# ---------------------------------------------------------------------------
# D. AI token efficiency
# ---------------------------------------------------------------------------

def _check_ai_efficiency(ai_df: pd.DataFrame) -> list[dict]:
    recs = []
    if ai_df.empty:
        return recs

    df = ai_df.copy()
    df["request_timestamp"] = pd.to_datetime(df["request_timestamp"])
    df["usage_date"] = df["request_timestamp"].dt.date

    # Applications with rising cost per request
    app_stats = (
        df.groupby("application")
        .agg(total_cost=("estimated_total_cost", "sum"),
             request_count=("request_count", "sum"),
             total_tokens=("input_tokens", lambda x: x.sum() + df.loc[x.index, "output_tokens"].sum()))
        .reset_index()
    )
    app_stats["cost_per_request"] = app_stats.apply(
        lambda r: r["total_cost"] / r["request_count"] if r["request_count"] > 0 else 0, axis=1
    )

    mean_cpr = app_stats["cost_per_request"].mean()
    if mean_cpr > 0:
        high_cost_apps = app_stats[app_stats["cost_per_request"] > mean_cpr * 2]
        for _, row in high_cost_apps.iterrows():
            recs.append(_rec(
                category="AI Token Efficiency",
                title=f"High cost-per-request in application: {row['application']}",
                affected=row["application"],
                evidence=(
                    f"Average cost per request: ₹{row['cost_per_request']:.4f}. "
                    f"Overall average: ₹{mean_cpr:.4f}. "
                    f"Total requests: {int(row['request_count']):,}."
                ),
                action=(
                    "Review prompt design, model selection, and whether a smaller model "
                    "can satisfy the application's requirements. "
                    "Consider input/output token optimisation."
                ),
                confidence="Medium",
                priority="Medium",
            ))

    # Model cost comparison
    model_stats = df.groupby("model_name").agg(
        total_cost=("estimated_total_cost", "sum"),
        request_count=("request_count", "sum"),
    ).reset_index()
    model_stats["cost_per_request"] = model_stats.apply(
        lambda r: r["total_cost"] / r["request_count"] if r["request_count"] > 0 else 0, axis=1
    )

    if len(model_stats) > 1:
        most_expensive  = model_stats.loc[model_stats["cost_per_request"].idxmax()]
        least_expensive = model_stats.loc[model_stats["cost_per_request"].idmin()
                          if hasattr(model_stats["cost_per_request"], "idmin")
                          else model_stats["cost_per_request"].idxmin()]
        ratio = most_expensive["cost_per_request"] / least_expensive["cost_per_request"] \
            if least_expensive["cost_per_request"] > 0 else None
        if ratio and ratio >= 5:
            recs.append(_rec(
                category="AI Token Efficiency",
                title="Large cost-per-request gap between models",
                affected=most_expensive["model_name"],
                evidence=(
                    f"{most_expensive['model_name']}: ₹{most_expensive['cost_per_request']:.4f}/req. "
                    f"{least_expensive['model_name']}: ₹{least_expensive['cost_per_request']:.4f}/req. "
                    f"Ratio: {ratio:.1f}×. Confirm that the higher-cost model is required for each use case."
                ),
                action=(
                    "Evaluate whether tasks using the higher-cost model can be routed to a "
                    "more cost-efficient model without acceptable quality degradation."
                ),
                confidence="Medium",
                priority="Low",
            ))

    return recs[:5]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_recommendations(
    billing_df: pd.DataFrame,
    ai_df: pd.DataFrame,
    budget_summary_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Generate all recommendations and return as a DataFrame.
    """
    all_recs: list[dict] = []

    all_recs.extend(_check_spending_increases(billing_df))
    all_recs.extend(_check_storage(billing_df))

    if budget_summary_df is not None:
        all_recs.extend(_check_budget_utilisation(budget_summary_df))

    if not ai_df.empty:
        all_recs.extend(_check_ai_efficiency(ai_df))

    if not all_recs:
        return pd.DataFrame()

    df = pd.DataFrame(all_recs)
    # Priority sort order
    priority_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    df["_sort"] = df["priority"].map(priority_order).fillna(4)
    df = df.sort_values("_sort").drop(columns="_sort").reset_index(drop=True)
    return df
