"""
test_data_validation.py — Tests for CSV schema validation, sanitization, and error reporting.
"""

import pytest
import pandas as pd
from src.data_validation import validate_billing_csv, validate_ai_csv

def test_validate_billing_csv_valid():
    df = pd.DataFrame([
        {
            "billing_date": "2026-01-15",
            "cloud_provider": "AWS",
            "service_name": "EC2",
            "total_cost": 250.75,
            "currency": "INR",
        }
    ])
    result = validate_billing_csv(df)
    assert result.is_valid is True
    assert result.valid_count == 1
    assert result.invalid_count == 0

def test_validate_billing_csv_missing_columns():
    # Missing 'total_cost'
    df = pd.DataFrame([
        {
            "billing_date": "2026-01-15",
            "cloud_provider": "AWS",
            "service_name": "EC2",
        }
    ])
    result = validate_billing_csv(df)
    assert result.is_valid is False
    assert any("Missing required columns" in e for e in result.errors)

def test_validate_billing_csv_negative_cost_handling():
    df = pd.DataFrame([
        {"billing_date": "2026-01-15", "cloud_provider": "AWS", "service_name": "EC2", "total_cost": 100.0},
        {"billing_date": "2026-01-16", "cloud_provider": "AWS", "service_name": "EC2", "total_cost": -50.0}, # Negative cost
    ])
    result = validate_billing_csv(df)
    assert result.valid_count == 1
    assert result.invalid_count == 1
    assert any("negative total_cost" in w for w in result.warnings)

def test_validate_billing_csv_invalid_date():
    df = pd.DataFrame([
        {"billing_date": "invalid-date-string", "cloud_provider": "AWS", "service_name": "EC2", "total_cost": 100.0},
    ])
    result = validate_billing_csv(df)
    # The row has invalid date so valid count should be 0, triggering error "No valid rows remain"
    assert result.valid_count == 0
    assert result.invalid_count == 1

def test_validate_ai_csv_valid():
    df = pd.DataFrame([
        {
            "request_timestamp": "2026-01-15 10:30:00",
            "provider": "Azure OpenAI",
            "model_name": "GPT-4o",
            "estimated_total_cost": 12.50,
        }
    ])
    result = validate_ai_csv(df)
    assert result.is_valid is True
    assert result.valid_count == 1
