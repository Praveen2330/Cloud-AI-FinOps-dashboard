"""
ai_cost_engine.py — AI/LLM cost calculation and analysis for FinOps Intelligence.

Costs are estimated using explicitly configured pricing assumptions.
All prices are illustrative; verify against current official provider pricing.

Formula:
    Estimated Request Cost =
        (Input Tokens  / 1,000,000 × Input Price per Million Tokens)
      + (Output Tokens / 1,000,000 × Output Price per Million Tokens)
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cost calculation
# ---------------------------------------------------------------------------

def calculate_token_cost(
    input_tokens: int,
    output_tokens: int,
    input_price_per_million: float,
    output_price_per_million: float,
) -> tuple[float, float, float]:
    """
    Calculate estimated token cost (input, output, total).

    Parameters
    ----------
    input_tokens              : Number of input tokens.
    output_tokens             : Number of output tokens.
    input_price_per_million   : Price per 1M input tokens (INR by convention).
    output_price_per_million  : Price per 1M output tokens (INR by convention).

    Returns
    -------
    (input_cost, output_cost, total_cost)
    """
    input_cost  = (input_tokens  / 1_000_000) * input_price_per_million
    output_cost = (output_tokens / 1_000_000) * output_price_per_million
    return input_cost, output_cost, input_cost + output_cost


def recalculate_costs(
    ai_df: pd.DataFrame,
    pricing_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Recalculate estimated costs for all AI usage records using the
    provided pricing_assumptions DataFrame.

    Rows without a matching pricing entry retain their existing cost values.
    """
    if ai_df.empty:
        return ai_df.copy()

    df = ai_df.copy()
    pricing_map = (
        pricing_df.set_index(["provider", "model_name"])
        [["input_price_per_million", "output_price_per_million"]]
        .to_dict("index")
    ) if not pricing_df.empty else {}

    def _recalc(row):
        key = (row.get("provider"), row.get("model_name"))
        if key in pricing_map:
            p = pricing_map[key]
            ic, oc, tc = calculate_token_cost(
                row.get("input_tokens", 0),
                row.get("output_tokens", 0),
                p["input_price_per_million"],
                p["output_price_per_million"],
            )
            return pd.Series({"estimated_input_cost": ic, "estimated_output_cost": oc, "estimated_total_cost": tc})
        return pd.Series({
            "estimated_input_cost":  row.get("estimated_input_cost", 0.0),
            "estimated_output_cost": row.get("estimated_output_cost", 0.0),
            "estimated_total_cost":  row.get("estimated_total_cost", 0.0),
        })

    costs = df.apply(_recalc, axis=1)
    df[["estimated_input_cost", "estimated_output_cost", "estimated_total_cost"]] = costs
    return df


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def daily_ai_spend(ai_df: pd.DataFrame) -> pd.DataFrame:
    """Daily aggregated AI spend with token counts."""
    if ai_df.empty:
        return pd.DataFrame()
    df = ai_df.copy()
    df["usage_date"] = pd.to_datetime(df["request_timestamp"]).dt.date
    return (
        df.groupby("usage_date")
        .agg(
            total_cost=("estimated_total_cost", "sum"),
            input_tokens=("input_tokens", "sum"),
            output_tokens=("output_tokens", "sum"),
            request_count=("request_count", "sum"),
        )
        .reset_index()
        .sort_values("usage_date")
    )


def spend_by_model(ai_df: pd.DataFrame) -> pd.DataFrame:
    if ai_df.empty:
        return pd.DataFrame()
    return (
        ai_df.groupby(["model_name", "provider"])
        .agg(
            total_cost=("estimated_total_cost", "sum"),
            input_cost=("estimated_input_cost", "sum"),
            output_cost=("estimated_output_cost", "sum"),
            input_tokens=("input_tokens", "sum"),
            output_tokens=("output_tokens", "sum"),
            request_count=("request_count", "sum"),
        )
        .reset_index()
        .sort_values("total_cost", ascending=False)
    )


def spend_by_application(ai_df: pd.DataFrame) -> pd.DataFrame:
    if ai_df.empty:
        return pd.DataFrame()
    return (
        ai_df.groupby("application")
        .agg(
            total_cost=("estimated_total_cost", "sum"),
            request_count=("request_count", "sum"),
            input_tokens=("input_tokens", "sum"),
            output_tokens=("output_tokens", "sum"),
        )
        .reset_index()
        .sort_values("total_cost", ascending=False)
    )


def spend_by_project(ai_df: pd.DataFrame) -> pd.DataFrame:
    if ai_df.empty:
        return pd.DataFrame()
    return (
        ai_df.groupby("project")
        .agg(
            total_cost=("estimated_total_cost", "sum"),
            request_count=("request_count", "sum"),
        )
        .reset_index()
        .sort_values("total_cost", ascending=False)
    )


def cost_per_request(spend_df: pd.DataFrame) -> pd.DataFrame:
    """Add cost-per-request column to a grouped DataFrame that has total_cost and request_count."""
    df = spend_df.copy()
    df["cost_per_request"] = df.apply(
        lambda r: r["total_cost"] / r["request_count"] if r.get("request_count", 0) > 0 else None,
        axis=1,
    )
    return df


def token_efficiency(ai_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate per-model token efficiency metrics.
    Identifies models with unusually high cost per token.
    """
    if ai_df.empty:
        return pd.DataFrame()

    model_df = spend_by_model(ai_df)
    model_df["total_tokens"] = model_df["input_tokens"] + model_df["output_tokens"]
    model_df["cost_per_1k_tokens"] = model_df.apply(
        lambda r: (r["total_cost"] / r["total_tokens"] * 1000)
        if r["total_tokens"] > 0 else None,
        axis=1,
    )
    return model_df


def detect_ai_spend_increase(ai_df: pd.DataFrame, window: int = 7) -> Optional[dict]:
    """
    Detect if recent AI spending is elevated compared to the rolling average.
    Returns a summary dict or None.
    """
    if ai_df.empty:
        return None

    daily = daily_ai_spend(ai_df)
    if len(daily) < window + 1:
        return None

    recent  = float(daily["total_cost"].iloc[-1])
    baseline= float(daily["total_cost"].iloc[-(window + 1):-1].mean())
    pct_inc = (recent - baseline) / baseline * 100 if baseline > 0 else None

    return {
        "recent_daily_spend": recent,
        "rolling_avg":        baseline,
        "pct_increase":       pct_inc,
        "is_elevated":        (pct_inc is not None and pct_inc > 50),
    }


# ---------------------------------------------------------------------------
# KPI summary
# ---------------------------------------------------------------------------

def ai_kpi_summary(ai_df: pd.DataFrame) -> dict:
    if ai_df.empty:
        return {
            "total_cost": 0.0, "input_cost": 0.0, "output_cost": 0.0,
            "total_requests": 0, "total_input_tokens": 0,
            "total_output_tokens": 0, "avg_cost_per_request": None,
        }
    tc  = float(ai_df["estimated_total_cost"].sum())
    ic  = float(ai_df["estimated_input_cost"].sum())
    oc  = float(ai_df["estimated_output_cost"].sum())
    req = int(ai_df["request_count"].sum())
    return {
        "total_cost":          tc,
        "input_cost":          ic,
        "output_cost":         oc,
        "total_requests":      req,
        "total_input_tokens":  int(ai_df["input_tokens"].sum()),
        "total_output_tokens": int(ai_df["output_tokens"].sum()),
        "avg_cost_per_request":tc / req if req > 0 else None,
    }
