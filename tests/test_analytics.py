"""
test_analytics.py — Tests for cloud spending aggregation and query filters.
"""

import pytest
import pandas as pd
from pathlib import Path
from src.cloud_analytics import (
    total_spend, spend_by_period, aggregate_by,
    daily_spend_series, split_periods, pct_change, generate_insights
)
from src import database as db

@pytest.fixture
def sample_billing_df():
    data = [
        {"billing_date": "2026-01-01", "cloud_provider": "AWS", "service_name": "EC2", "department": "Engineering", "project": "Alpha", "total_cost": 100.0, "currency": "INR", "data_source": "test"},
        {"billing_date": "2026-01-02", "cloud_provider": "AWS", "service_name": "EC2", "department": "Engineering", "project": "Alpha", "total_cost": 150.0, "currency": "INR", "data_source": "test"},
        {"billing_date": "2026-01-03", "cloud_provider": "Azure", "service_name": "VM", "department": "Analytics", "project": "Beta", "total_cost": 200.0, "currency": "INR", "data_source": "test"},
        {"billing_date": "2026-01-04", "cloud_provider": "GCP", "service_name": "BigQuery", "department": "Data Science", "project": "Gamma", "total_cost": 300.0, "currency": "INR", "data_source": "test"},
    ]
    return pd.DataFrame(data)

def test_total_spend(sample_billing_df):
    assert total_spend(sample_billing_df) == 750.0

def test_empty_dataset_handling():
    empty_df = pd.DataFrame()
    assert total_spend(empty_df) == 0.0
    daily = daily_spend_series(empty_df)
    assert daily.empty
    agg = aggregate_by(empty_df, "service_name")
    assert agg.empty
    insights = generate_insights(empty_df, empty_df)
    assert len(insights) > 0
    assert "No billing data available" in insights[0]

def test_aggregate_by(sample_billing_df):
    agg = aggregate_by(sample_billing_df, "cloud_provider")
    assert len(agg) == 3
    aws_row = agg[agg["cloud_provider"] == "AWS"].iloc[0]
    assert aws_row["total_cost"] == 250.0
    assert round(aws_row["pct_of_total"], 2) == round(250.0 / 750.0 * 100, 2)

def test_period_comparison(sample_billing_df):
    curr, prev = split_periods(sample_billing_df)
    assert len(curr) > 0
    assert len(prev) > 0
    assert pct_change(100.0, 50.0) == 100.0
    assert pct_change(50.0, 100.0) == -50.0
    assert pct_change(100.0, 0.0) is None

def test_database_filtering(tmp_path):
    test_db = tmp_path / "test_finops.db"
    db.init_db(test_db)
    
    df = pd.DataFrame([
        {"billing_date": "2026-01-01", "cloud_provider": "AWS", "service_name": "EC2", "department": "Engineering", "project": "Alpha", "total_cost": 100.0, "currency": "INR", "data_source": "test"},
        {"billing_date": "2026-01-02", "cloud_provider": "Azure", "service_name": "VM", "department": "Analytics", "project": "Beta", "total_cost": 200.0, "currency": "INR", "data_source": "test"},
    ])
    db.insert_billing_records(df, db_path=test_db)
    
    # Query all
    res = db.get_billing_df(db_path=test_db)
    assert len(res) == 2
    
    # Query filtered by provider
    aws_res = db.get_billing_df(providers=["AWS"], db_path=test_db)
    assert len(aws_res) == 1
    assert aws_res.iloc[0]["service_name"] == "EC2"
