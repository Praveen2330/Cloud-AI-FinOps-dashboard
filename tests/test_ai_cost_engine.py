"""
test_ai_cost_engine.py — Tests for AI token cost modeling, calculations, and aggregations.
"""

import pytest
import pandas as pd
from src.ai_cost_engine import (
    calculate_token_cost, recalculate_costs,
    daily_ai_spend, spend_by_model, ai_kpi_summary
)

def test_calculate_token_cost():
    # 1,000,000 input tokens at 1000 INR/M = 1000 INR
    # 500,000 output tokens at 4000 INR/M = 2000 INR
    # Total = 3000 INR
    in_cost, out_cost, total_cost = calculate_token_cost(
        input_tokens=1_000_000,
        output_tokens=500_000,
        input_price_per_million=1000.0,
        output_price_per_million=4000.0,
    )
    assert in_cost == 1000.0
    assert out_cost == 2000.0
    assert total_cost == 3000.0

def test_zero_tokens():
    in_cost, out_cost, total_cost = calculate_token_cost(
        input_tokens=0,
        output_tokens=0,
        input_price_per_million=2000.0,
        output_price_per_million=5000.0,
    )
    assert in_cost == 0.0
    assert out_cost == 0.0
    assert total_cost == 0.0

def test_recalculate_costs():
    ai_df = pd.DataFrame([{
        "provider": "Azure OpenAI",
        "model_name": "GPT-4o",
        "input_tokens": 500_000,
        "output_tokens": 100_000,
        "estimated_input_cost": 0.0,
        "estimated_output_cost": 0.0,
        "estimated_total_cost": 0.0,
    }])

    pricing_df = pd.DataFrame([{
        "provider": "Azure OpenAI",
        "model_name": "GPT-4o",
        "input_price_per_million": 4000.0,
        "output_price_per_million": 12000.0,
    }])

    updated = recalculate_costs(ai_df, pricing_df)
    assert updated.iloc[0]["estimated_input_cost"] == 2000.0
    assert updated.iloc[0]["estimated_output_cost"] == 1200.0
    assert updated.iloc[0]["estimated_total_cost"] == 3200.0

def test_ai_kpi_summary_empty():
    res = ai_kpi_summary(pd.DataFrame())
    assert res["total_cost"] == 0.0
    assert res["total_requests"] == 0
    assert res["avg_cost_per_request"] is None
