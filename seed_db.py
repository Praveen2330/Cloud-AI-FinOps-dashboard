"""
seed_db.py — Pre-populates the SQLite database with 185 days of benchmark synthetic data.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
from src import database as db
from src.data_generator import generate_billing_data, generate_ai_usage_data, RANDOM_SEED

def seed():
    print("Initializing SQLite schema at finops.db...")
    db.init_db()

    print("Generating 185 days of synthetic cloud billing records...")
    billing_df = generate_billing_data(days=185, seed=RANDOM_SEED)
    db.insert_billing_records(billing_df)
    print(f"  Inserted {len(billing_df):,} billing records.")

    print("Generating AI/LLM token usage records...")
    ai_df = generate_ai_usage_data(days=185, seed=RANDOM_SEED + 1)
    db.insert_ai_records(ai_df)
    print(f"  Inserted {len(ai_df):,} AI usage records.")

    print("Seeding monthly budgets...")
    billing_df["billing_date"] = pd.to_datetime(billing_df["billing_date"])
    periods = billing_df["billing_date"].dt.to_period("M").unique()
    for p in periods:
        db.seed_default_budgets(p.year, p.month)

    print("Seeding pricing assumptions...")
    db.seed_default_pricing()

    print("Database seeding complete!")

if __name__ == "__main__":
    seed()
