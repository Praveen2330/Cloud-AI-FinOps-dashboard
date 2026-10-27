"""
data_validation.py — CSV upload validation for FinOps Intelligence Dashboard.

Validates billing and AI usage CSVs before importing into SQLite.
Returns structured validation results so the UI can present clear messages.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Required / optional column definitions
# ---------------------------------------------------------------------------

BILLING_REQUIRED = {
    "billing_date", "cloud_provider", "service_name", "total_cost",
}
BILLING_OPTIONAL = {
    "service_category", "account_id", "account_alias", "region",
    "project", "department", "environment", "resource_id",
    "usage_quantity", "usage_unit", "unit_price", "currency",
}
BILLING_ALL = BILLING_REQUIRED | BILLING_OPTIONAL

AI_REQUIRED = {
    "request_timestamp", "provider", "model_name", "estimated_total_cost",
}
AI_OPTIONAL = {
    "model_category", "project", "application", "input_tokens", "output_tokens",
    "request_count", "estimated_input_cost", "estimated_output_cost",
    "currency", "status",
}
AI_ALL = AI_REQUIRED | AI_OPTIONAL

VALID_CURRENCIES = {"INR", "USD", "EUR", "GBP", "AUD", "SGD"}
VALID_PROVIDERS  = {"AWS", "Azure", "GCP", "AWS Bedrock", "Azure OpenAI", "Google Vertex"}


# ---------------------------------------------------------------------------
# Validation result structure
# ---------------------------------------------------------------------------

class ValidationResult:
    def __init__(self):
        self.errors:   list[str] = []
        self.warnings: list[str] = []
        self.valid_df: Optional[pd.DataFrame] = None
        self.invalid_rows: Optional[pd.DataFrame] = None
        self.total_rows   = 0
        self.valid_count  = 0
        self.invalid_count= 0

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        lines = [
            f"Total rows  : {self.total_rows}",
            f"Valid rows  : {self.valid_count}",
            f"Invalid rows: {self.invalid_count}",
        ]
        if self.errors:
            lines.append("Errors:")
            lines.extend(f"  - {e}" for e in self.errors)
        if self.warnings:
            lines.append("Warnings:")
            lines.extend(f"  - {w}" for w in self.warnings)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def _missing_columns(df: pd.DataFrame, required: set[str]) -> list[str]:
    return [c for c in required if c not in df.columns]


def _coerce_numeric(df: pd.DataFrame, col: str, result: ValidationResult) -> pd.Series:
    coerced = pd.to_numeric(df[col], errors="coerce")
    n_bad   = coerced.isna().sum() - df[col].isna().sum()
    if n_bad > 0:
        result.warnings.append(f"Column '{col}': {n_bad} non-numeric value(s) coerced to NaN.")
    return coerced


def _coerce_dates(df: pd.DataFrame, col: str, result: ValidationResult) -> pd.Series:
    coerced = pd.to_datetime(df[col], errors="coerce")
    n_bad   = coerced.isna().sum() - df[col].isna().sum()
    if n_bad > 0:
        result.warnings.append(f"Column '{col}': {n_bad} unparseable date(s) set to NaT.")
    return coerced


# ---------------------------------------------------------------------------
# Billing validation
# ---------------------------------------------------------------------------

def validate_billing_csv(df: pd.DataFrame) -> ValidationResult:
    """
    Validate an uploaded billing DataFrame.

    Checks for required columns, data types, negative costs, invalid dates, etc.
    Returns a ValidationResult with valid_df and invalid_rows separated.
    """
    result = ValidationResult()
    result.total_rows = len(df)

    # 1. Required columns
    missing = _missing_columns(df, BILLING_REQUIRED)
    if missing:
        result.errors.append(f"Missing required columns: {missing}")
        return result

    # 2. Warn about unknown columns
    unknown = [c for c in df.columns if c not in BILLING_ALL]
    if unknown:
        result.warnings.append(f"Unknown columns will be ignored: {unknown}")

    df = df.copy()

    # 3. Parse dates
    df["billing_date"] = _coerce_dates(df, "billing_date", result)

    # 4. Parse numeric cost
    df["total_cost"] = _coerce_numeric(df, "total_cost", result)

    # 5. Parse optional numerics
    for col in ("usage_quantity", "unit_price"):
        if col in df.columns:
            df[col] = _coerce_numeric(df, col, result)

    # 6. Currency normalisation
    if "currency" not in df.columns:
        df["currency"] = "INR"
        result.warnings.append("Column 'currency' not found; defaulting all rows to INR.")
    else:
        df["currency"] = df["currency"].str.upper().str.strip()
        bad_curr = ~df["currency"].isin(VALID_CURRENCIES) & df["currency"].notna()
        if bad_curr.any():
            result.warnings.append(
                f"{bad_curr.sum()} row(s) have unsupported currency values and will keep original value."
            )

    # 7. Cloud provider normalisation
    df["cloud_provider"] = df["cloud_provider"].str.strip()

    # 8. Build invalid mask
    invalid_mask = (
        df["billing_date"].isna() |
        df["total_cost"].isna() |
        (df["total_cost"] < 0) |
        df["cloud_provider"].isna() |
        df["service_name"].isna()
    )

    # Additional check: future dates
    today = pd.Timestamp.today().normalize()
    future_mask = df["billing_date"] > today
    if future_mask.sum() > 0:
        result.warnings.append(f"{future_mask.sum()} row(s) have future billing dates.")

    n_negative = ((df["total_cost"] < 0) & df["total_cost"].notna()).sum()
    if n_negative > 0:
        result.warnings.append(f"{n_negative} row(s) have negative total_cost and will be excluded.")

    result.valid_df      = df[~invalid_mask].reset_index(drop=True)
    result.invalid_rows  = df[invalid_mask].reset_index(drop=True)
    result.valid_count   = len(result.valid_df)
    result.invalid_count = len(result.invalid_rows)

    if result.valid_count == 0:
        result.errors.append("No valid rows remain after validation.")

    # Tag data source
    result.valid_df["data_source"] = "user_upload"

    logger.info(
        "Billing validation: %d total, %d valid, %d invalid",
        result.total_rows, result.valid_count, result.invalid_count,
    )
    return result


# ---------------------------------------------------------------------------
# AI usage validation
# ---------------------------------------------------------------------------

def validate_ai_csv(df: pd.DataFrame) -> ValidationResult:
    """
    Validate an uploaded AI usage DataFrame.
    """
    result = ValidationResult()
    result.total_rows = len(df)

    missing = _missing_columns(df, AI_REQUIRED)
    if missing:
        result.errors.append(f"Missing required columns: {missing}")
        return result

    unknown = [c for c in df.columns if c not in AI_ALL]
    if unknown:
        result.warnings.append(f"Unknown columns will be ignored: {unknown}")

    df = df.copy()

    # Parse timestamps
    df["request_timestamp"] = _coerce_dates(df, "request_timestamp", result)

    # Parse numerics
    for col in ("estimated_total_cost", "estimated_input_cost", "estimated_output_cost"):
        if col in df.columns:
            df[col] = _coerce_numeric(df, col, result)
    for col in ("input_tokens", "output_tokens", "request_count"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    if "currency" not in df.columns:
        df["currency"] = "INR"
    else:
        df["currency"] = df["currency"].str.upper().str.strip()

    if "status" not in df.columns:
        df["status"] = "success"

    invalid_mask = (
        df["request_timestamp"].isna() |
        df["estimated_total_cost"].isna() |
        (df["estimated_total_cost"] < 0) |
        df["provider"].isna() |
        df["model_name"].isna()
    )

    result.valid_df      = df[~invalid_mask].reset_index(drop=True)
    result.invalid_rows  = df[invalid_mask].reset_index(drop=True)
    result.valid_count   = len(result.valid_df)
    result.invalid_count = len(result.invalid_rows)

    if result.valid_count == 0:
        result.errors.append("No valid rows remain after validation.")

    result.valid_df["data_source"] = "user_upload"

    logger.info(
        "AI usage validation: %d total, %d valid, %d invalid",
        result.total_rows, result.valid_count, result.invalid_count,
    )
    return result
