"""
database.py - Database access layer for FinOps Intelligence Dashboard.

Provides SQLite-backed storage with a modular interface designed so the
backend can be migrated to PostgreSQL by swapping the connection factory.
"""

import sqlite3
import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Default database path; can be overridden via environment variable.
_DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "finops.db"
DB_PATH: Path = Path(os.environ.get("FINOPS_DB_PATH", str(_DEFAULT_DB_PATH)))

# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

@contextmanager
def get_connection(db_path: Optional[Path] = None):
    """Yield a SQLite connection and close it automatically."""
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS cloud_billing (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    billing_date     DATE    NOT NULL,
    cloud_provider   TEXT    NOT NULL,
    service_name     TEXT    NOT NULL,
    service_category TEXT,
    account_id       TEXT,
    account_alias    TEXT,
    region           TEXT,
    project          TEXT,
    department       TEXT,
    environment      TEXT,
    resource_id      TEXT,
    usage_quantity   REAL,
    usage_unit       TEXT,
    unit_price       REAL,
    total_cost       REAL    NOT NULL CHECK(total_cost >= 0),
    currency         TEXT    NOT NULL DEFAULT 'INR',
    data_source      TEXT    DEFAULT 'synthetic'
);

CREATE INDEX IF NOT EXISTS idx_cb_date     ON cloud_billing(billing_date);
CREATE INDEX IF NOT EXISTS idx_cb_provider ON cloud_billing(cloud_provider);
CREATE INDEX IF NOT EXISTS idx_cb_project  ON cloud_billing(project);
CREATE INDEX IF NOT EXISTS idx_cb_dept     ON cloud_billing(department);

CREATE TABLE IF NOT EXISTS ai_usage (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    request_timestamp     DATETIME NOT NULL,
    provider              TEXT     NOT NULL,
    model_name            TEXT     NOT NULL,
    model_category        TEXT,
    project               TEXT,
    application           TEXT,
    input_tokens          INTEGER  DEFAULT 0,
    output_tokens         INTEGER  DEFAULT 0,
    request_count         INTEGER  DEFAULT 1,
    estimated_input_cost  REAL     DEFAULT 0.0,
    estimated_output_cost REAL     DEFAULT 0.0,
    estimated_total_cost  REAL     DEFAULT 0.0,
    currency              TEXT     NOT NULL DEFAULT 'INR',
    status                TEXT     DEFAULT 'success',
    data_source           TEXT     DEFAULT 'synthetic'
);

CREATE INDEX IF NOT EXISTS idx_ai_ts      ON ai_usage(request_timestamp);
CREATE INDEX IF NOT EXISTS idx_ai_project ON ai_usage(project);
CREATE INDEX IF NOT EXISTS idx_ai_model   ON ai_usage(model_name);

CREATE TABLE IF NOT EXISTS budgets (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    budget_type  TEXT    NOT NULL,   -- 'overall', 'provider', 'department', 'project', 'ai'
    name         TEXT    NOT NULL,
    monthly_budget REAL  NOT NULL CHECK(monthly_budget > 0),
    currency     TEXT    NOT NULL DEFAULT 'INR',
    period_year  INTEGER NOT NULL,
    period_month INTEGER NOT NULL,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(budget_type, name, period_year, period_month)
);

CREATE TABLE IF NOT EXISTS anomaly_events (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    detection_date   DATE    NOT NULL,
    cloud_provider   TEXT,
    service_name     TEXT,
    project          TEXT,
    actual_cost      REAL    NOT NULL,
    expected_cost    REAL    NOT NULL,
    absolute_increase REAL   NOT NULL,
    pct_increase     REAL    NOT NULL,
    detection_method TEXT    NOT NULL,
    severity         TEXT    NOT NULL,   -- 'Low', 'Medium', 'High', 'Critical'
    status           TEXT    NOT NULL DEFAULT 'New',  -- 'New','Investigating','Resolved','False Positive'
    notes            TEXT,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pricing_assumptions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    provider       TEXT    NOT NULL,
    model_name     TEXT    NOT NULL,
    input_price_per_million  REAL NOT NULL,
    output_price_per_million REAL NOT NULL,
    currency       TEXT    NOT NULL DEFAULT 'INR',
    effective_date DATE,
    notes          TEXT,
    UNIQUE(provider, model_name)
);

CREATE TABLE IF NOT EXISTS optimization_recommendations (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    category         TEXT    NOT NULL,
    title            TEXT    NOT NULL,
    affected_resource TEXT,
    evidence         TEXT,
    recommended_action TEXT,
    estimated_impact REAL,
    impact_currency  TEXT    DEFAULT 'INR',
    confidence_level TEXT,   -- 'High', 'Medium', 'Low'
    priority         TEXT,   -- 'Critical', 'High', 'Medium', 'Low'
    status           TEXT    DEFAULT 'Open',
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""


def init_db(db_path: Optional[Path] = None) -> None:
    """Create all tables and indexes if they do not exist."""
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
    logger.info("Database initialised at %s", db_path or DB_PATH)


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def query_df(sql: str, params: tuple = (), db_path: Optional[Path] = None) -> pd.DataFrame:
    """Run a SELECT query and return a DataFrame."""
    with get_connection(db_path) as conn:
        return pd.read_sql_query(sql, conn, params=params)


def execute(sql: str, params: tuple = (), db_path: Optional[Path] = None) -> int:
    """Run a non-SELECT statement and return the lastrowid."""
    with get_connection(db_path) as conn:
        cur = conn.execute(sql, params)
        return cur.lastrowid


def executemany(sql: str, params_list, db_path: Optional[Path] = None) -> int:
    """Bulk-insert rows and return the row count."""
    with get_connection(db_path) as conn:
        cur = conn.executemany(sql, params_list)
        return cur.rowcount


# ---------------------------------------------------------------------------
# Cloud billing queries
# ---------------------------------------------------------------------------

def insert_billing_records(df: pd.DataFrame, db_path: Optional[Path] = None) -> int:
    cols = [
        "billing_date", "cloud_provider", "service_name", "service_category",
        "account_id", "account_alias", "region", "project", "department",
        "environment", "resource_id", "usage_quantity", "usage_unit",
        "unit_price", "total_cost", "currency", "data_source",
    ]
    df = df[[c for c in cols if c in df.columns]].copy()
    df["billing_date"] = pd.to_datetime(df["billing_date"]).dt.strftime("%Y-%m-%d")
    records = [tuple(row) for _, row in df.iterrows()]
    placeholders = ", ".join(["?" for _ in df.columns])
    col_names = ", ".join(df.columns)
    sql = f"INSERT INTO cloud_billing ({col_names}) VALUES ({placeholders})"
    return executemany(sql, records, db_path)


def get_billing_df(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    providers: Optional[list] = None,
    departments: Optional[list] = None,
    projects: Optional[list] = None,
    environments: Optional[list] = None,
    regions: Optional[list] = None,
    db_path: Optional[Path] = None,
) -> pd.DataFrame:
    """Retrieve billing records with optional filters."""
    conditions = ["1=1"]
    params: list = []
    if start_date:
        conditions.append("billing_date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("billing_date <= ?")
        params.append(end_date)
    if providers:
        placeholders = ",".join("?" for _ in providers)
        conditions.append(f"cloud_provider IN ({placeholders})")
        params.extend(providers)
    if departments:
        placeholders = ",".join("?" for _ in departments)
        conditions.append(f"department IN ({placeholders})")
        params.extend(departments)
    if projects:
        placeholders = ",".join("?" for _ in projects)
        conditions.append(f"project IN ({placeholders})")
        params.extend(projects)
    if environments:
        placeholders = ",".join("?" for _ in environments)
        conditions.append(f"environment IN ({placeholders})")
        params.extend(environments)
    if regions:
        placeholders = ",".join("?" for _ in regions)
        conditions.append(f"region IN ({placeholders})")
        params.extend(regions)
    where = " AND ".join(conditions)
    sql = f"SELECT * FROM cloud_billing WHERE {where} ORDER BY billing_date DESC"
    return query_df(sql, tuple(params), db_path)


def get_daily_spend(db_path: Optional[Path] = None) -> pd.DataFrame:
    sql = """
        SELECT billing_date, SUM(total_cost) AS total_cost
        FROM cloud_billing
        GROUP BY billing_date
        ORDER BY billing_date
    """
    return query_df(sql, db_path=db_path)


def get_spend_by_service(db_path: Optional[Path] = None) -> pd.DataFrame:
    sql = """
        SELECT service_name, cloud_provider, SUM(total_cost) AS total_cost
        FROM cloud_billing
        GROUP BY service_name, cloud_provider
        ORDER BY total_cost DESC
    """
    return query_df(sql, db_path=db_path)


def get_spend_by_provider(db_path: Optional[Path] = None) -> pd.DataFrame:
    sql = """
        SELECT cloud_provider, SUM(total_cost) AS total_cost
        FROM cloud_billing
        GROUP BY cloud_provider
        ORDER BY total_cost DESC
    """
    return query_df(sql, db_path=db_path)


def get_spend_by_department(db_path: Optional[Path] = None) -> pd.DataFrame:
    sql = """
        SELECT department, SUM(total_cost) AS total_cost
        FROM cloud_billing
        GROUP BY department
        ORDER BY total_cost DESC
    """
    return query_df(sql, db_path=db_path)


def get_spend_by_project(db_path: Optional[Path] = None) -> pd.DataFrame:
    sql = """
        SELECT project, department, SUM(total_cost) AS total_cost
        FROM cloud_billing
        GROUP BY project, department
        ORDER BY total_cost DESC
    """
    return query_df(sql, db_path=db_path)


def get_spend_by_region(db_path: Optional[Path] = None) -> pd.DataFrame:
    sql = """
        SELECT region, SUM(total_cost) AS total_cost
        FROM cloud_billing
        GROUP BY region
        ORDER BY total_cost DESC
    """
    return query_df(sql, db_path=db_path)


def get_spend_by_environment(db_path: Optional[Path] = None) -> pd.DataFrame:
    sql = """
        SELECT environment, SUM(total_cost) AS total_cost
        FROM cloud_billing
        GROUP BY environment
        ORDER BY total_cost DESC
    """
    return query_df(sql, db_path=db_path)


def get_monthly_spend(db_path: Optional[Path] = None) -> pd.DataFrame:
    sql = """
        SELECT
            strftime('%Y', billing_date) AS year,
            strftime('%m', billing_date) AS month,
            cloud_provider,
            service_name,
            SUM(total_cost) AS total_cost
        FROM cloud_billing
        GROUP BY year, month, cloud_provider, service_name
        ORDER BY year, month
    """
    return query_df(sql, db_path=db_path)


def get_daily_spend_by_service(db_path: Optional[Path] = None) -> pd.DataFrame:
    sql = """
        SELECT billing_date, service_name, cloud_provider, SUM(total_cost) AS total_cost
        FROM cloud_billing
        GROUP BY billing_date, service_name, cloud_provider
        ORDER BY billing_date
    """
    return query_df(sql, db_path=db_path)


def clear_billing_data(db_path: Optional[Path] = None) -> None:
    execute("DELETE FROM cloud_billing WHERE data_source = 'synthetic'", db_path=db_path)


def clear_all_billing_data(db_path: Optional[Path] = None) -> None:
    execute("DELETE FROM cloud_billing", db_path=db_path)


# ---------------------------------------------------------------------------
# AI usage queries
# ---------------------------------------------------------------------------

def insert_ai_records(df: pd.DataFrame, db_path: Optional[Path] = None) -> int:
    cols = [
        "request_timestamp", "provider", "model_name", "model_category",
        "project", "application", "input_tokens", "output_tokens",
        "request_count", "estimated_input_cost", "estimated_output_cost",
        "estimated_total_cost", "currency", "status", "data_source",
    ]
    df = df[[c for c in cols if c in df.columns]].copy()
    df["request_timestamp"] = pd.to_datetime(df["request_timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    records = [tuple(row) for _, row in df.iterrows()]
    placeholders = ", ".join(["?" for _ in df.columns])
    col_names = ", ".join(df.columns)
    sql = f"INSERT INTO ai_usage ({col_names}) VALUES ({placeholders})"
    return executemany(sql, records, db_path)


def get_ai_df(db_path: Optional[Path] = None) -> pd.DataFrame:
    sql = "SELECT * FROM ai_usage ORDER BY request_timestamp DESC"
    return query_df(sql, db_path=db_path)


def get_ai_daily_spend(db_path: Optional[Path] = None) -> pd.DataFrame:
    sql = """
        SELECT
            DATE(request_timestamp) AS usage_date,
            SUM(estimated_total_cost) AS total_cost,
            SUM(input_tokens) AS input_tokens,
            SUM(output_tokens) AS output_tokens,
            SUM(request_count) AS request_count
        FROM ai_usage
        GROUP BY usage_date
        ORDER BY usage_date
    """
    return query_df(sql, db_path=db_path)


def get_ai_spend_by_model(db_path: Optional[Path] = None) -> pd.DataFrame:
    sql = """
        SELECT
            model_name, provider,
            SUM(estimated_total_cost) AS total_cost,
            SUM(estimated_input_cost)  AS input_cost,
            SUM(estimated_output_cost) AS output_cost,
            SUM(input_tokens)          AS input_tokens,
            SUM(output_tokens)         AS output_tokens,
            SUM(request_count)         AS request_count
        FROM ai_usage
        GROUP BY model_name, provider
        ORDER BY total_cost DESC
    """
    return query_df(sql, db_path=db_path)


def get_ai_spend_by_project(db_path: Optional[Path] = None) -> pd.DataFrame:
    sql = """
        SELECT
            project,
            SUM(estimated_total_cost) AS total_cost,
            SUM(input_tokens) AS input_tokens,
            SUM(output_tokens) AS output_tokens,
            SUM(request_count) AS request_count
        FROM ai_usage
        GROUP BY project
        ORDER BY total_cost DESC
    """
    return query_df(sql, db_path=db_path)


def clear_ai_data(db_path: Optional[Path] = None) -> None:
    execute("DELETE FROM ai_usage WHERE data_source = 'synthetic'", db_path=db_path)


def clear_all_ai_data(db_path: Optional[Path] = None) -> None:
    execute("DELETE FROM ai_usage", db_path=db_path)


# ---------------------------------------------------------------------------
# Budget queries
# ---------------------------------------------------------------------------

def upsert_budget(budget_type: str, name: str, monthly_budget: float,
                  year: int, month: int, currency: str = "INR",
                  db_path: Optional[Path] = None) -> None:
    sql = """
        INSERT INTO budgets (budget_type, name, monthly_budget, currency, period_year, period_month)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(budget_type, name, period_year, period_month)
        DO UPDATE SET monthly_budget = excluded.monthly_budget,
                      currency = excluded.currency,
                      updated_at = CURRENT_TIMESTAMP
    """
    execute(sql, (budget_type, name, monthly_budget, currency, year, month), db_path)


def get_budgets(year: int, month: int, db_path: Optional[Path] = None) -> pd.DataFrame:
    sql = """
        SELECT * FROM budgets
        WHERE period_year = ? AND period_month = ?
        ORDER BY budget_type, name
    """
    return query_df(sql, (year, month), db_path)


def get_all_budgets(db_path: Optional[Path] = None) -> pd.DataFrame:
    sql = "SELECT * FROM budgets ORDER BY period_year DESC, period_month DESC, budget_type, name"
    return query_df(sql, db_path=db_path)


def seed_default_budgets(year: int, month: int, db_path: Optional[Path] = None) -> None:
    """Insert sensible default budgets for the sample dataset."""
    defaults = [
        ("overall",    "Cloud Total",         500000.0),
        ("provider",   "AWS",                 200000.0),
        ("provider",   "Azure",               150000.0),
        ("provider",   "GCP",                 100000.0),
        ("department", "Engineering",         180000.0),
        ("department", "Data Science",        120000.0),
        ("department", "DevOps",               80000.0),
        ("department", "Analytics",            70000.0),
        ("department", "Finance",              30000.0),
        ("project",    "Project-Alpha",        90000.0),
        ("project",    "Project-Beta",         75000.0),
        ("project",    "Project-Gamma",        60000.0),
        ("project",    "Project-Delta",        50000.0),
        ("project",    "Project-Epsilon",      40000.0),
        ("ai",         "AI/LLM Total",        120000.0),
    ]
    for btype, name, budget in defaults:
        upsert_budget(btype, name, budget, year, month, "INR", db_path)


# ---------------------------------------------------------------------------
# Anomaly queries
# ---------------------------------------------------------------------------

def insert_anomaly(event: dict, db_path: Optional[Path] = None) -> int:
    sql = """
        INSERT INTO anomaly_events
            (detection_date, cloud_provider, service_name, project,
             actual_cost, expected_cost, absolute_increase, pct_increase,
             detection_method, severity, status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """
    return execute(sql, (
        event["detection_date"], event.get("cloud_provider"), event.get("service_name"),
        event.get("project"), event["actual_cost"], event["expected_cost"],
        event["absolute_increase"], event["pct_increase"],
        event["detection_method"], event["severity"], event.get("status", "New"),
    ), db_path)


def get_anomalies(db_path: Optional[Path] = None) -> pd.DataFrame:
    sql = "SELECT * FROM anomaly_events ORDER BY detection_date DESC"
    return query_df(sql, db_path=db_path)


def update_anomaly_status(anomaly_id: int, status: str, notes: str = "",
                          db_path: Optional[Path] = None) -> None:
    sql = """
        UPDATE anomaly_events
        SET status = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """
    execute(sql, (status, notes, anomaly_id), db_path)


def clear_anomalies(db_path: Optional[Path] = None) -> None:
    execute("DELETE FROM anomaly_events", db_path=db_path)


# ---------------------------------------------------------------------------
# Pricing assumptions
# ---------------------------------------------------------------------------

def upsert_pricing(provider: str, model_name: str,
                   input_price: float, output_price: float,
                   currency: str = "INR",
                   db_path: Optional[Path] = None) -> None:
    sql = """
        INSERT INTO pricing_assumptions
            (provider, model_name, input_price_per_million, output_price_per_million, currency)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(provider, model_name)
        DO UPDATE SET
            input_price_per_million  = excluded.input_price_per_million,
            output_price_per_million = excluded.output_price_per_million,
            currency = excluded.currency
    """
    execute(sql, (provider, model_name, input_price, output_price, currency), db_path)


def get_pricing(db_path: Optional[Path] = None) -> pd.DataFrame:
    sql = "SELECT * FROM pricing_assumptions ORDER BY provider, model_name"
    return query_df(sql, db_path=db_path)


def seed_default_pricing(db_path: Optional[Path] = None) -> None:
    """Insert illustrative pricing assumptions (INR-denominated, not official)."""
    # INR prices = approximate USD × 84 conversion — clearly labeled as illustrative
    defaults = [
        ("AWS Bedrock",     "Claude-3-Haiku",    1260.0,  4200.0),
        ("AWS Bedrock",     "Claude-3-Sonnet",   2520.0,  12600.0),
        ("AWS Bedrock",     "Titan-Text-Express", 672.0,   672.0),
        ("Azure OpenAI",    "GPT-4o",            4200.0,  12600.0),
        ("Azure OpenAI",    "GPT-4o-mini",        126.0,   504.0),
        ("Azure OpenAI",    "text-embedding-3-small", 16.8, 16.8),
        ("Google Vertex",   "Gemini-1.5-Pro",    5880.0,  17640.0),
        ("Google Vertex",   "Gemini-1.5-Flash",   252.0,   756.0),
        ("Google Vertex",   "textembedding-gecko", 33.6,   33.6),
    ]
    for provider, model, inp, out in defaults:
        upsert_pricing(provider, model, inp, out, "INR", db_path)


# ---------------------------------------------------------------------------
# Optimisation recommendations
# ---------------------------------------------------------------------------

def insert_recommendation(rec: dict, db_path: Optional[Path] = None) -> int:
    sql = """
        INSERT INTO optimization_recommendations
            (category, title, affected_resource, evidence, recommended_action,
             estimated_impact, impact_currency, confidence_level, priority, status)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """
    return execute(sql, (
        rec["category"], rec["title"], rec.get("affected_resource"),
        rec.get("evidence"), rec.get("recommended_action"),
        rec.get("estimated_impact"), rec.get("impact_currency", "INR"),
        rec.get("confidence_level"), rec.get("priority"), rec.get("status", "Open"),
    ), db_path)


def get_recommendations(db_path: Optional[Path] = None) -> pd.DataFrame:
    sql = "SELECT * FROM optimization_recommendations ORDER BY created_at DESC"
    return query_df(sql, db_path=db_path)


def clear_recommendations(db_path: Optional[Path] = None) -> None:
    execute("DELETE FROM optimization_recommendations", db_path=db_path)


# ---------------------------------------------------------------------------
# Database statistics
# ---------------------------------------------------------------------------

def get_table_counts(db_path: Optional[Path] = None) -> dict:
    tables = ["cloud_billing", "ai_usage", "budgets", "anomaly_events",
              "pricing_assumptions", "optimization_recommendations"]
    counts = {}
    for t in tables:
        try:
            df = query_df(f"SELECT COUNT(*) AS cnt FROM {t}", db_path=db_path)
            counts[t] = int(df["cnt"].iloc[0]) if not df.empty else 0
        except Exception:
            counts[t] = 0
    return counts
