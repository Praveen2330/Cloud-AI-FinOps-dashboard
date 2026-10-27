"""
data_generator.py — Reproducible synthetic cloud and AI billing data for FinOps Intelligence.

Generates 180+ days of daily billing records across multiple cloud providers,
services, projects, and departments with:
- Realistic daily variation and growth trends
- Deliberately injected cost spikes for anomaly detection testing
- AI/LLM usage records with token counts
- Monthly budgets at varying utilisation levels

All data is fictional. No real credentials, account IDs, or customer data.
"""

import logging
from datetime import date, timedelta, datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Fixed seed for reproducibility
RANDOM_SEED = 42

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROVIDERS = ["AWS", "Azure", "GCP"]

AWS_SERVICES = [
    ("EC2",             "Compute",  "ap-south-1",   180.0),
    ("S3",              "Storage",  "ap-south-1",    60.0),
    ("RDS",             "Database", "ap-south-1",   120.0),
    ("Lambda",          "Compute",  "us-east-1",     20.0),
    ("CloudFront",      "Network",  "us-east-1",     15.0),
    ("EMR",             "Analytics","ap-south-1",    90.0),
    ("Redshift",        "Database", "ap-south-1",   110.0),
    ("DynamoDB",        "Database", "us-east-1",     35.0),
    ("SageMaker",       "AI/ML",    "ap-south-1",   200.0),
    ("EKS",             "Compute",  "ap-south-1",   130.0),
]

AZURE_SERVICES = [
    ("Virtual Machines","Compute",  "centralindia",  160.0),
    ("Blob Storage",    "Storage",  "centralindia",   50.0),
    ("SQL Database",    "Database", "centralindia",  100.0),
    ("Azure Functions", "Compute",  "eastus",         18.0),
    ("Azure CDN",       "Network",  "eastus",         12.0),
    ("Azure Synapse",   "Analytics","centralindia",   85.0),
    ("AKS",             "Compute",  "centralindia",  120.0),
    ("Cosmos DB",       "Database", "centralindia",   45.0),
    ("Azure ML",        "AI/ML",    "centralindia",  180.0),
]

GCP_SERVICES = [
    ("Compute Engine",  "Compute",  "asia-south1",   140.0),
    ("Cloud Storage",   "Storage",  "asia-south1",    45.0),
    ("Cloud SQL",       "Database", "asia-south1",    90.0),
    ("Cloud Functions", "Compute",  "us-central1",    16.0),
    ("BigQuery",        "Analytics","asia-south1",    95.0),
    ("GKE",             "Compute",  "asia-south1",   110.0),
    ("Firestore",       "Database", "asia-south1",    30.0),
    ("Vertex AI",       "AI/ML",    "asia-south1",   190.0),
]

PROJECTS = [
    ("Project-Alpha",   "Engineering"),
    ("Project-Beta",    "Data Science"),
    ("Project-Gamma",   "DevOps"),
    ("Project-Delta",   "Analytics"),
    ("Project-Epsilon", "Finance"),
]

ENVIRONMENTS = ["Production", "Staging", "Development", "Testing"]
ENV_WEIGHTS  = [0.55, 0.20, 0.15, 0.10]

AI_PROVIDERS = ["AWS Bedrock", "Azure OpenAI", "Google Vertex"]

AI_MODELS = {
    "AWS Bedrock": [
        ("Claude-3-Haiku",    "Text Generation", 1260.0,  4200.0),
        ("Claude-3-Sonnet",   "Text Generation", 2520.0, 12600.0),
        ("Titan-Text-Express","Text Generation",  672.0,   672.0),
    ],
    "Azure OpenAI": [
        ("GPT-4o",              "Text Generation", 4200.0, 12600.0),
        ("GPT-4o-mini",         "Text Generation",  126.0,   504.0),
        ("text-embedding-3-small","Embeddings",      16.8,    16.8),
    ],
    "Google Vertex": [
        ("Gemini-1.5-Pro",      "Text Generation", 5880.0, 17640.0),
        ("Gemini-1.5-Flash",    "Text Generation",  252.0,   756.0),
        ("textembedding-gecko", "Embeddings",        33.6,    33.6),
    ],
}

AI_APPLICATIONS = [
    "ChatAssistant", "DocumentSearch", "CodeReview",
    "DataPipeline", "CustomerSupport", "AnalyticsBot",
]

# Deliberately injected anomaly spikes (day offset from start_date, provider, service_name, multiplier)
INJECTED_SPIKES = [
    (45,  "AWS",   "SageMaker",       6.5),
    (70,  "Azure", "Virtual Machines",5.0),
    (100, "GCP",   "BigQuery",        7.0),
    (130, "AWS",   "EC2",             4.5),
    (155, "Azure", "Azure ML",        5.5),
    (170, "GCP",   "Vertex AI",       6.0),
]


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_billing_data(
    days: int = 185,
    end_date: Optional[date] = None,
    seed: int = RANDOM_SEED,
) -> pd.DataFrame:
    """
    Generate synthetic cloud billing records for the given number of days.

    Returns a DataFrame ready to be inserted into cloud_billing.
    """
    rng = np.random.default_rng(seed)
    end_dt   = end_date or date.today()
    start_dt = end_dt - timedelta(days=days - 1)

    # Build date range
    dates = [start_dt + timedelta(days=d) for d in range(days)]

    # Combine all service definitions with provider
    all_services = (
        [("AWS", *s) for s in AWS_SERVICES] +
        [("Azure", *s) for s in AZURE_SERVICES] +
        [("GCP", *s) for s in GCP_SERVICES]
    )

    records = []

    for provider, service_name, category, region, base_daily in all_services:
        # Assign project / department
        proj_idx = rng.integers(0, len(PROJECTS))
        project, department = PROJECTS[proj_idx]

        # Account identifiers
        account_id    = f"ACC-{rng.integers(100000, 999999)}"
        account_alias = f"{provider.lower()}-{project.lower().replace(' ', '-')}"

        # Usage unit by category
        unit_map = {
            "Compute": ("vCPU-hours", 100, 500),
            "Storage": ("GB-months",   50, 300),
            "Database":("DB-hours",    80, 400),
            "Network": ("GB-transfer", 20, 200),
            "Analytics":("DPU-hours",  30, 200),
            "AI/ML":   ("GPU-hours",   10, 100),
        }
        usage_unit, usage_lo, usage_hi = unit_map.get(category, ("units", 10, 100))

        # Growth trend: some services grow 0.5–1.5 % per week
        weekly_growth = rng.uniform(0.001, 0.003)

        for d_idx, dt in enumerate(dates):
            day_cost = base_daily * 83.0  # scale to INR (illustrative)

            # Weekly pattern: Mon–Fri higher, weekends lower
            weekday_factor = 0.75 if dt.weekday() >= 5 else 1.0 + rng.uniform(0.0, 0.15)

            # Noise
            noise_factor = 1.0 + rng.normal(0, 0.08)

            # Growth trend
            growth = 1.0 + weekly_growth * (d_idx / 7)

            # Environment multiplier
            env = rng.choice(ENVIRONMENTS, p=ENV_WEIGHTS)
            env_factor = {"Production": 1.5, "Staging": 0.7, "Development": 0.4, "Testing": 0.3}[env]

            cost = max(day_cost * weekday_factor * noise_factor * growth * env_factor, 0.01)

            # Usage quantity and unit price
            usage_qty = rng.uniform(usage_lo, usage_hi)
            unit_price = cost / usage_qty

            records.append({
                "billing_date":     dt.strftime("%Y-%m-%d"),
                "cloud_provider":   provider,
                "service_name":     service_name,
                "service_category": category,
                "account_id":       account_id,
                "account_alias":    account_alias,
                "region":           region,
                "project":          project,
                "department":       department,
                "environment":      env,
                "resource_id":      f"res-{service_name.lower().replace(' ', '-')}-{rng.integers(1000,9999)}",
                "usage_quantity":   round(float(usage_qty), 3),
                "usage_unit":       usage_unit,
                "unit_price":       round(float(unit_price), 4),
                "total_cost":       round(float(cost), 2),
                "currency":         "INR",
                "data_source":      "synthetic",
            })

    df = pd.DataFrame(records)

    # Inject anomaly spikes
    for day_offset, prov, svc, multiplier in INJECTED_SPIKES:
        spike_date = (start_dt + timedelta(days=day_offset)).strftime("%Y-%m-%d")
        mask = (df["billing_date"] == spike_date) & (df["cloud_provider"] == prov) & (df["service_name"] == svc)
        df.loc[mask, "total_cost"] = (df.loc[mask, "total_cost"] * multiplier).round(2)
        df.loc[mask, "unit_price"] = (df.loc[mask, "unit_price"] * multiplier).round(4)

    logger.info(
        "Generated %d billing records covering %s to %s",
        len(df), start_dt, end_dt,
    )
    return df


# ---------------------------------------------------------------------------
# AI usage data generator
# ---------------------------------------------------------------------------

def generate_ai_usage_data(
    days: int = 185,
    end_date: Optional[date] = None,
    seed: int = RANDOM_SEED + 1,
) -> pd.DataFrame:
    """Generate synthetic AI/LLM usage records."""
    rng = np.random.default_rng(seed)
    end_dt   = end_date or date.today()
    start_dt = end_dt - timedelta(days=days - 1)

    records = []

    for d_idx in range(days):
        dt = start_dt + timedelta(days=d_idx)
        # Vary number of requests per day (weekday effect)
        is_weekday  = dt.weekday() < 5
        n_requests  = int(rng.integers(80, 250) if is_weekday else rng.integers(30, 100))

        for _ in range(n_requests):
            # Pick model
            ai_prov = str(rng.choice(AI_PROVIDERS))
            model_list = AI_MODELS[ai_prov]
            model_data = model_list[rng.integers(0, len(model_list))]
            model_name, model_category, input_price_pm, output_price_pm = model_data
            input_price_pm = float(input_price_pm)
            output_price_pm = float(output_price_pm)

            # Token usage — embeddings use fewer output tokens
            if model_category == "Embeddings":
                input_tokens  = int(rng.integers(50, 2000))
                output_tokens = 0
            else:
                input_tokens  = int(rng.integers(200, 8000))
                output_tokens = int(rng.integers(100, 4000))

            est_input_cost  = (input_tokens  / 1_000_000) * input_price_pm
            est_output_cost = (output_tokens / 1_000_000) * output_price_pm
            est_total       = est_input_cost + est_output_cost

            project, _ = PROJECTS[rng.integers(0, len(PROJECTS))]
            application = rng.choice(AI_APPLICATIONS)

            # Random hour within the day
            hour   = int(rng.integers(0, 24))
            minute = int(rng.integers(0, 60))
            ts     = datetime(dt.year, dt.month, dt.day, hour, minute)

            records.append({
                "request_timestamp":    ts.strftime("%Y-%m-%d %H:%M:%S"),
                "provider":             ai_prov,
                "model_name":           model_name,
                "model_category":       model_category,
                "project":              project,
                "application":          application,
                "input_tokens":         input_tokens,
                "output_tokens":        output_tokens,
                "request_count":        1,
                "estimated_input_cost": round(est_input_cost, 6),
                "estimated_output_cost":round(est_output_cost, 6),
                "estimated_total_cost": round(est_total, 6),
                "currency":             "INR",
                "status":               "success",
                "data_source":          "synthetic",
            })

    df = pd.DataFrame(records)
    logger.info(
        "Generated %d AI usage records covering %s to %s",
        len(df), start_dt, end_dt,
    )
    return df


# ---------------------------------------------------------------------------
# Entry point for quick testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    billing = generate_billing_data()
    ai      = generate_ai_usage_data()
    print(f"Billing rows  : {len(billing):,}")
    print(f"AI usage rows : {len(ai):,}")
    print(billing.head(3).to_string())
    print(ai.head(3).to_string())
