"""
test_budgets.py — Tests for budget monitoring, calculations, and projections.
"""

import pytest
import pandas as pd
from src.budget_engine import (
    budget_utilisation, remaining_budget, project_month_end,
    budget_status, build_budget_summary, DEFAULT_THRESHOLDS
)

def test_budget_utilisation():
    # Normal case: spend 500 on 1000 budget = 50%
    assert budget_utilisation(500.0, 1000.0) == 50.0
    # Over budget: spend 1200 on 1000 budget = 120%
    assert budget_utilisation(1200.0, 1000.0) == 120.0
    # Division by zero protection
    assert budget_utilisation(500.0, 0.0) is None
    assert budget_utilisation(500.0, -100.0) is None

def test_remaining_budget():
    assert remaining_budget(400.0, 1000.0) == 600.0
    # Negative when over budget
    assert remaining_budget(1200.0, 1000.0) == -200.0

def test_project_month_end():
    # Spent 300 across 3 days in a 30-day month -> avg 100/day -> 3000 projected
    assert project_month_end(300.0, current_day=3, days_in_month=30) == 3000.0
    # Guard against insufficient history (< 3 days)
    assert project_month_end(100.0, current_day=1, days_in_month=30) is None
    assert project_month_end(200.0, current_day=2, days_in_month=30) is None
    # Zero spend
    assert project_month_end(0.0, current_day=5, days_in_month=30) is None

def test_budget_status_thresholds():
    assert budget_status(50.0) == "Healthy"
    assert budget_status(75.0) == "Attention"
    assert budget_status(95.0) == "Near Limit"
    assert budget_status(105.0) == "Over Budget"
    
    # Custom thresholds
    custom_thr = {"healthy": 60.0, "attention": 80.0, "near_limit": 100.0}
    assert budget_status(65.0, custom_thr) == "Attention"

def test_build_budget_summary_empty():
    empty_budgets = pd.DataFrame()
    empty_billing = pd.DataFrame()
    empty_ai = pd.DataFrame()
    summary = build_budget_summary(empty_budgets, empty_billing, empty_ai, 2026, 1)
    assert summary.empty
