"""
anomaly_detector.py — Statistical cost anomaly detection for FinOps Intelligence.

Primary method  : Rolling z-score (mean ± k × std over a configurable window).
Secondary method: Interquartile Range (IQR) robust threshold.

These are spending deviation detectors, not proof of an anomalous event.
Every detected deviation requires human investigation to determine root cause.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------

DEFAULT_WINDOW       = 21    # Rolling window in days
DEFAULT_SENSITIVITY  = 2.5   # Number of standard deviations for z-score
DEFAULT_MIN_HISTORY  = 14    # Minimum past observations before detection is enabled
DEFAULT_MIN_COST_INCREASE = 5000.0  # Minimum absolute cost increase (INR) to flag
DEFAULT_MIN_PCT_INCREASE  = 50.0   # Minimum % increase to flag


# ---------------------------------------------------------------------------
# Severity mapping
# ---------------------------------------------------------------------------

def _severity(absolute_increase: float, pct_increase: float) -> str:
    """
    Map cost deviation metrics to a severity label.
    Rules use both absolute and relative thresholds so small-cost,
    high-percentage spikes are not over-classified.
    """
    if absolute_increase >= 100_000 or pct_increase >= 400:
        return "Critical"
    if absolute_increase >= 30_000 or pct_increase >= 200:
        return "High"
    if absolute_increase >= 10_000 or pct_increase >= 100:
        return "Medium"
    return "Low"


# ---------------------------------------------------------------------------
# Rolling z-score detection
# ---------------------------------------------------------------------------

def detect_zscore(
    series: pd.Series,
    window: int   = DEFAULT_WINDOW,
    sensitivity: float = DEFAULT_SENSITIVITY,
    min_history: int   = DEFAULT_MIN_HISTORY,
) -> pd.DataFrame:
    """
    Detect cost spikes using a rolling z-score on a time series.

    Parameters
    ----------
    series      : Daily cost series indexed by date (DatetimeIndex or date strings).
    window      : Rolling lookback window (days).
    sensitivity : Detection threshold in standard deviations.
    min_history : Minimum observations required before flagging.

    Returns
    -------
    DataFrame with columns: date, actual, expected, std_dev, z_score, is_anomaly.
    """
    if series.empty:
        return pd.DataFrame()

    s = series.copy()
    if not isinstance(s.index, pd.DatetimeIndex):
        s.index = pd.to_datetime(s.index)

    # Fill missing dates with 0 to avoid gaps distorting the rolling window
    full_idx = pd.date_range(s.index.min(), s.index.max(), freq="D")
    s = s.reindex(full_idx, fill_value=0.0)

    rolling_mean = s.shift(1).rolling(window=window, min_periods=min_history).mean()
    rolling_std  = s.shift(1).rolling(window=window, min_periods=min_history).std()

    # Handle zero variance safely:
    # If historical variance was zero, any increase above mean has infinite deviation
    diff = s - rolling_mean
    with np.errstate(divide='ignore', invalid='ignore'):
        z_score = np.where(
            rolling_std.isna(),
            np.nan,
            np.where(
                rolling_std == 0.0,
                np.where(diff > 0, np.inf, 0.0),
                diff / rolling_std
            )
        )

    result = pd.DataFrame({
        "date":      s.index,
        "actual":    s.values,
        "expected":  rolling_mean.values,
        "std_dev":   rolling_std.values,
        "z_score":   z_score,
    })

    # Anomaly if z_score > sensitivity AND sufficient history
    has_history = rolling_mean.notna().values
    result["is_anomaly"] = (result["z_score"] > sensitivity) & has_history
    result["is_anomaly"] = result["is_anomaly"].fillna(False)

    return result.reset_index(drop=True)


# ---------------------------------------------------------------------------
# IQR-based detection (secondary / validation method)
# ---------------------------------------------------------------------------

def detect_iqr(
    series: pd.Series,
    window: int  = DEFAULT_WINDOW,
    multiplier: float = 2.5,
    min_history: int  = DEFAULT_MIN_HISTORY,
) -> pd.DataFrame:
    """
    Detect cost spikes using an interquartile range (IQR) rolling threshold.

    Upper threshold = Q3 + multiplier × IQR
    """
    if series.empty:
        return pd.DataFrame()

    s = series.copy()
    if not isinstance(s.index, pd.DatetimeIndex):
        s.index = pd.to_datetime(s.index)

    full_idx = pd.date_range(s.index.min(), s.index.max(), freq="D")
    s = s.reindex(full_idx, fill_value=0.0)

    def iqr_threshold(window_vals):
        q1, q3 = np.percentile(window_vals, [25, 75])
        iqr    = q3 - q1
        return q3 + multiplier * iqr

    def window_median(window_vals):
        return np.median(window_vals)

    # Use expanding approach: for each row, look at the previous `window` rows
    n = len(s)
    thresholds = np.full(n, np.nan)
    medians    = np.full(n, np.nan)

    for i in range(min_history, n):
        hist = s.iloc[max(0, i - window):i].values
        if len(hist) >= min_history:
            thresholds[i] = iqr_threshold(hist)
            medians[i]    = window_median(hist)

    result = pd.DataFrame({
        "date":      s.index,
        "actual":    s.values,
        "expected":  medians,
        "threshold": thresholds,
    })
    result["is_anomaly"] = result["actual"] > result["threshold"]
    result["is_anomaly"] = result["is_anomaly"].fillna(False)
    return result.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Full anomaly detection pipeline
# ---------------------------------------------------------------------------

def run_anomaly_detection(
    billing_df: pd.DataFrame,
    window: int           = DEFAULT_WINDOW,
    sensitivity: float    = DEFAULT_SENSITIVITY,
    min_history: int      = DEFAULT_MIN_HISTORY,
    min_cost_increase: float = DEFAULT_MIN_COST_INCREASE,
    min_pct_increase: float  = DEFAULT_MIN_PCT_INCREASE,
    services_filter: Optional[list] = None,
    use_iqr_secondary: bool = True,
) -> pd.DataFrame:
    """
    Run anomaly detection across all service–provider combinations.

    Returns
    -------
    DataFrame of detected anomalies with severity and preliminary context.
    """
    if billing_df.empty:
        logger.warning("Anomaly detection called with empty DataFrame.")
        return pd.DataFrame()

    df = billing_df.copy()
    df["billing_date"] = pd.to_datetime(df["billing_date"])

    groups = df.groupby(["cloud_provider", "service_name"])

    anomalies = []

    for (provider, service), grp in groups:
        if services_filter and service not in services_filter:
            continue

        daily = grp.groupby("billing_date")["total_cost"].sum().sort_index()

        if len(daily) < min_history:
            logger.debug(
                "Skipping %s / %s — only %d days of history (min: %d)",
                provider, service, len(daily), min_history,
            )
            continue

        # Primary: z-score
        zdf = detect_zscore(daily, window, sensitivity, min_history)
        flagged_z = zdf[zdf["is_anomaly"]].copy()
        flagged_z["detection_method"] = "Z-Score"

        # Secondary: IQR
        if use_iqr_secondary:
            idf = detect_iqr(daily, window, min_history=min_history)
            flagged_i = idf[idf["is_anomaly"]].copy()
            flagged_i["detection_method"] = "IQR"
        else:
            flagged_i = pd.DataFrame()

        # Union — same date flagged by both → Z-Score takes priority label
        zdf_dates = set(flagged_z["date"].astype(str)) if not flagged_z.empty else set()
        if not flagged_i.empty:
            flagged_i = flagged_i[~flagged_i["date"].astype(str).isin(zdf_dates)]

        flagged = pd.concat([flagged_z, flagged_i], ignore_index=True)

        for _, row in flagged.iterrows():
            actual   = float(row["actual"])
            expected = float(row["expected"]) if pd.notna(row["expected"]) else 0.0
            abs_inc  = actual - expected
            pct_inc  = (abs_inc / expected * 100) if expected > 0 else float("inf")

            # Apply minimum thresholds to reduce noise
            if abs_inc < min_cost_increase or pct_inc < min_pct_increase:
                continue

            sev = _severity(abs_inc, pct_inc)

            # Preliminary context (based on data, not assumed root cause)
            context = (
                f"{service} spending on {row['date'].date()} was "
                f"₹{actual:,.0f} against an expected baseline of ₹{expected:,.0f} "
                f"({pct_inc:.0f}% above baseline). "
                f"Detected via {row['detection_method']}. "
                "Review recent deployments, workload changes, or configuration updates for this service."
            )

            # Dominant project for this service / date
            day_str  = str(row["date"].date())
            day_grp  = grp[grp["billing_date"].dt.strftime("%Y-%m-%d") == day_str]
            top_proj = (
                day_grp.groupby("project")["total_cost"].sum().idxmax()
                if not day_grp.empty and "project" in day_grp.columns
                else None
            )

            anomalies.append({
                "detection_date":    str(row["date"].date()),
                "cloud_provider":    provider,
                "service_name":      service,
                "project":           top_proj,
                "actual_cost":       round(actual, 2),
                "expected_cost":     round(expected, 2),
                "absolute_increase": round(abs_inc, 2),
                "pct_increase":      round(pct_inc, 2),
                "detection_method":  row["detection_method"],
                "severity":          sev,
                "status":            "New",
                "context":           context,
            })

    result = pd.DataFrame(anomalies)
    if not result.empty:
        result = result.sort_values("detection_date", ascending=False).reset_index(drop=True)

    logger.info(
        "Anomaly detection complete — %d deviation(s) detected across %d service groups.",
        len(result), groups.ngroups,
    )
    return result


# ---------------------------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------------------------

def anomaly_summary(anomaly_df: pd.DataFrame) -> dict:
    """Return high-level summary statistics for detected anomalies."""
    if anomaly_df.empty:
        return {
            "total": 0, "critical": 0, "high": 0, "medium": 0, "low": 0,
            "estimated_excess": 0.0, "services_affected": 0,
        }
    return {
        "total":             len(anomaly_df),
        "critical":          int((anomaly_df["severity"] == "Critical").sum()),
        "high":              int((anomaly_df["severity"] == "High").sum()),
        "medium":            int((anomaly_df["severity"] == "Medium").sum()),
        "low":               int((anomaly_df["severity"] == "Low").sum()),
        "estimated_excess":  float(anomaly_df["absolute_increase"].sum()),
        "services_affected": int(anomaly_df["service_name"].nunique()),
    }
