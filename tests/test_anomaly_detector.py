"""
test_anomaly_detector.py — Tests for statistical anomaly detection and spike identification.
"""

import pytest
import pandas as pd
import numpy as np
from src.anomaly_detector import detect_zscore, detect_iqr, run_anomaly_detection
from src import database as db

def test_anomaly_detection_on_normal_data():
    # 30 days of flat steady spend: 100 with small noise +/- 2
    dates = pd.date_range("2026-01-01", periods=30, freq="D")
    rng = np.random.default_rng(42)
    costs = 100.0 + rng.normal(0, 1.0, size=30)
    series = pd.Series(costs, index=dates)

    res = detect_zscore(series, window=14, sensitivity=2.5, min_history=10)
    # Steady normal data should not trigger anomalies
    assert res["is_anomaly"].sum() == 0

def test_detection_of_injected_cost_spike():
    dates = pd.date_range("2026-01-01", periods=30, freq="D")
    costs = np.full(30, 100.0)
    # Inject a 10x spike on day 25
    costs[25] = 1000.0
    series = pd.Series(costs, index=dates)

    res = detect_zscore(series, window=14, sensitivity=2.5, min_history=10)
    # Spike on day 25 must be detected
    spike_row = res.iloc[25]
    assert spike_row["is_anomaly"] == True
    assert spike_row["actual"] == 1000.0

def test_handling_insufficient_history():
    # Only 5 days of history when min_history=14
    dates = pd.date_range("2026-01-01", periods=5, freq="D")
    costs = [100.0, 100.0, 100.0, 100.0, 5000.0]
    series = pd.Series(costs, index=dates)

    res = detect_zscore(series, window=14, sensitivity=2.0, min_history=14)
    # Must not flag because min_history requirement is not met
    assert res["is_anomaly"].sum() == 0

def test_zero_variance_safety():
    # Exactly identical costs every day -> std dev = 0
    dates = pd.date_range("2026-01-01", periods=20, freq="D")
    costs = np.full(20, 50.0)
    series = pd.Series(costs, index=dates)

    res = detect_zscore(series, window=10, sensitivity=2.5, min_history=7)
    # Must not throw DivisionByZero or flag false anomalies
    assert res["is_anomaly"].sum() == 0

def test_run_anomaly_detection_with_spikes():
    # Generate billing records with 30 days of data and 1 known spike
    dates = pd.date_range("2026-01-01", periods=30, freq="D")
    records = []
    for d in dates:
        records.append({
            "billing_date": d.strftime("%Y-%m-%d"),
            "cloud_provider": "AWS",
            "service_name": "EC2",
            "project": "Alpha",
            "total_cost": 500.0,
            "currency": "INR",
            "data_source": "test"
        })
    # Inject spike on day 20: 50,000 INR
    records[20]["total_cost"] = 50000.0
    df = pd.DataFrame(records)

    detected = run_anomaly_detection(
        df,
        window=14,
        sensitivity=2.5,
        min_history=10,
        min_cost_increase=1000.0,
        min_pct_increase=50.0,
    )

    assert len(detected) == 1
    assert detected.iloc[0]["service_name"] == "EC2"
    assert detected.iloc[0]["actual_cost"] == 50000.0

def test_anomaly_status_persistence(tmp_path):
    test_db = tmp_path / "anomaly_test.db"
    db.init_db(test_db)

    event = {
        "detection_date": "2026-01-20",
        "cloud_provider": "AWS",
        "service_name": "SageMaker",
        "project": "Alpha",
        "actual_cost": 45000.0,
        "expected_cost": 5000.0,
        "absolute_increase": 40000.0,
        "pct_increase": 800.0,
        "detection_method": "Z-Score",
        "severity": "Critical",
        "status": "New"
    }
    anom_id = db.insert_anomaly(event, db_path=test_db)
    assert anom_id > 0

    # Verify initial status
    stored = db.get_anomalies(db_path=test_db)
    assert stored.iloc[0]["status"] == "New"

    # Update status to Investigating
    db.update_anomaly_status(anom_id, "Investigating", "Checking cluster autoscaling logs", db_path=test_db)

    # Verify status changed and persisted
    updated = db.get_anomalies(db_path=test_db)
    assert updated.iloc[0]["status"] == "Investigating"
    assert updated.iloc[0]["notes"] == "Checking cluster autoscaling logs"
