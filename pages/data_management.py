"""
pages/data_management.py — Dataset Lifecycle & CSV Ingestion for FinOps Intelligence.

Manages synthetic data generation, CSV schema validation, safe batch insertion,
and full dataset exports with zero arbitrary SQL execution.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import datetime
import io
import streamlit as st
import pandas as pd

from src import database as db
from src.data_generator import generate_billing_data, generate_ai_usage_data, RANDOM_SEED
from src.data_validation import validate_billing_csv, validate_ai_csv

st.markdown("# 📁 Data Management")
st.markdown(
    "<p style='color:#64748B; margin-top:-0.5rem; font-size:0.9rem;'>"
    "Generate synthetic benchmark datasets, upload and validate custom billing CSVs, "
    "and export processed records."
    "</p>",
    unsafe_allow_html=True,
)

# ── Summary of current database ───────────────────────────────────────────────
counts = db.get_table_counts()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Billing Records", f"{counts.get('cloud_billing', 0):,}")
c2.metric("AI Usage Records", f"{counts.get('ai_usage', 0):,}")
c3.metric("Configured Budgets", f"{counts.get('budgets', 0):,}")
c4.metric("Logged Anomalies", f"{counts.get('anomaly_events', 0):,}")

st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs([
    "🔄 Synthetic Benchmark Generator",
    "📤 Upload Billing Data (CSV)",
    "🤖 Upload AI Usage Data (CSV)",
    "📥 Export & Reset"
])

# ── Tab 1: Synthetic Generator ────────────────────────────────────────────────
with tab1:
    st.markdown("### Generate Deterministic Benchmark Data")
    st.markdown(
        "Generates realistic multi-cloud billing records spanning 180+ days across AWS, Azure, and GCP, "
        "including known injected cost spikes, organic growth curves, and AI token interactions."
    )

    col_g1, col_g2, col_g3 = st.columns(3)
    with col_g1:
        gen_days = st.number_input("Days of History", min_value=30, max_value=365, value=185, step=15)
    with col_g2:
        gen_seed = st.number_input("Random Seed (Reproducibility)", min_value=1, max_value=99999, value=RANDOM_SEED)
    with col_g3:
        preserve_uploads = st.checkbox("Preserve User Uploads", value=True)

    if st.button("🚀 Generate & Load Benchmark Data"):
        with st.spinner("Generating billing and AI usage datasets..."):
            # Clear synthetic records
            if preserve_uploads:
                db.clear_billing_data()
                db.clear_ai_data()
            else:
                db.clear_all_billing_data()
                db.clear_all_ai_data()

            db.clear_anomalies()
            db.clear_recommendations()

            billing_df = generate_billing_data(days=gen_days, seed=gen_seed)
            ai_df = generate_ai_usage_data(days=gen_days, seed=gen_seed + 1)

            db.insert_billing_records(billing_df)
            db.insert_ai_records(ai_df)

            # Seed default budgets for all represented months
            billing_df["billing_date"] = pd.to_datetime(billing_df["billing_date"])
            periods = billing_df["billing_date"].dt.to_period("M").unique()
            for p in periods:
                db.seed_default_budgets(p.year, p.month)

            # Seed default pricing
            db.seed_default_pricing()

            st.success(
                f"Successfully loaded {len(billing_df):,} billing records and "
                f"{len(ai_df):,} AI usage records across {gen_days} days!"
            )
            st.rerun()

# ── Tab 2: Upload Cloud Billing CSV ───────────────────────────────────────────
with tab2:
    st.markdown("### Ingest Cloud Billing CSV")
    st.markdown("""
    **Required Columns:** `billing_date`, `cloud_provider`, `service_name`, `total_cost`  
    **Optional Columns:** `service_category`, `account_id`, `region`, `project`, `department`, `environment`, `resource_id`, `usage_quantity`, `usage_unit`, `unit_price`, `currency`
    """)

    uploaded_billing_file = st.file_uploader("Choose Billing CSV File", type=["csv"], key="billing_upload")

    if uploaded_billing_file is not None:
        try:
            raw_billing_df = pd.read_csv(uploaded_billing_file)
            st.markdown(f"**Preview ({len(raw_billing_df)} rows loaded):**")
            st.dataframe(raw_billing_df.head(5), use_container_width=True)

            val_res = validate_billing_csv(raw_billing_df)

            if not val_res.is_valid:
                st.error("Validation failed with critical errors:")
                for err in val_res.errors:
                    st.write(f"- ❌ {err}")
            else:
                st.success(f"Validation Passed: {val_res.valid_count} valid rows identified.")
                if val_res.warnings:
                    with st.expander(f"⚠️ Validation Warnings ({len(val_res.warnings)})"):
                        for warn in val_res.warnings:
                            st.write(f"- {warn}")

                if val_res.invalid_count > 0:
                    st.warning(f"{val_res.invalid_count} row(s) failed validation checks.")
                    st.dataframe(val_res.invalid_rows.head(5), use_container_width=True)
                    import_mode = st.radio(
                        "Import Choice",
                        ["Import valid rows only (skip invalid)", "Reject entire file"],
                        index=0
                    )
                else:
                    import_mode = "Import valid rows only (skip invalid)"

                if import_mode == "Import valid rows only (skip invalid)":
                    if st.button("📥 Commit Valid Records to SQLite"):
                        inserted = db.insert_billing_records(val_res.valid_df)
                        st.success(f"Successfully inserted {inserted:,} records into database!")
                        st.rerun()
        except Exception as e:
            st.error(f"Error parsing CSV: {str(e)}")

# ── Tab 3: Upload AI Usage CSV ────────────────────────────────────────────────
with tab3:
    st.markdown("### Ingest AI / LLM Usage CSV")
    st.markdown("""
    **Required Columns:** `request_timestamp`, `provider`, `model_name`, `estimated_total_cost`  
    **Optional Columns:** `model_category`, `project`, `application`, `input_tokens`, `output_tokens`, `request_count`, `estimated_input_cost`, `estimated_output_cost`, `currency`, `status`
    """)

    uploaded_ai_file = st.file_uploader("Choose AI Usage CSV File", type=["csv"], key="ai_upload")

    if uploaded_ai_file is not None:
        try:
            raw_ai_df = pd.read_csv(uploaded_ai_file)
            st.markdown(f"**Preview ({len(raw_ai_df)} rows loaded):**")
            st.dataframe(raw_ai_df.head(5), use_container_width=True)

            val_ai_res = validate_ai_csv(raw_ai_df)

            if not val_ai_res.is_valid:
                st.error("Validation failed with critical errors:")
                for err in val_ai_res.errors:
                    st.write(f"- ❌ {err}")
            else:
                st.success(f"Validation Passed: {val_ai_res.valid_count} valid records identified.")
                if val_ai_res.warnings:
                    with st.expander(f"⚠️ Validation Warnings ({len(val_ai_res.warnings)})"):
                        for warn in val_ai_res.warnings:
                            st.write(f"- {warn}")

                if val_ai_res.invalid_count > 0:
                    st.warning(f"{val_ai_res.invalid_count} row(s) failed validation checks.")
                    ai_import_mode = st.radio(
                        "Import Mode",
                        ["Import valid rows only", "Cancel upload"],
                        index=0
                    )
                else:
                    ai_import_mode = "Import valid rows only"

                if ai_import_mode == "Import valid rows only":
                    if st.button("📥 Commit Valid AI Records to SQLite"):
                        inserted_ai = db.insert_ai_records(val_ai_res.valid_df)
                        st.success(f"Successfully inserted {inserted_ai:,} AI usage records!")
                        st.rerun()
        except Exception as e:
            st.error(f"Error parsing AI CSV: {str(e)}")

# ── Tab 4: Export & Database Maintenance ──────────────────────────────────────
with tab4:
    st.markdown("### 📥 Dataset Export")
    col_ex1, col_ex2 = st.columns(2)
    with col_ex1:
        all_billing = db.get_billing_df()
        if not all_billing.empty:
            csv_bill = all_billing.to_csv(index=False).encode('utf-8')
            st.download_button(
                "⬇️ Export Entire Cloud Billing Dataset (CSV)",
                data=csv_bill,
                file_name="finops_all_cloud_billing.csv",
                mime="text/csv"
            )
        else:
            st.write("No billing data to export.")

    with col_ex2:
        all_ai = db.get_ai_df()
        if not all_ai.empty:
            csv_ai = all_ai.to_csv(index=False).encode('utf-8')
            st.download_button(
                "⬇️ Export Entire AI Usage Dataset (CSV)",
                data=csv_ai,
                file_name="finops_all_ai_usage.csv",
                mime="text/csv"
            )
        else:
            st.write("No AI usage data to export.")

    st.markdown("---")
    st.markdown("### ⚠️ Database Reset")
    st.markdown("Permanently erase all active billing, AI usage, budgets, and anomaly records.")

    confirm_reset = st.checkbox("I confirm that I want to wipe the SQLite database.")
    if st.button("🗑️ Reset All Database Tables", disabled=not confirm_reset):
        db.clear_all_billing_data()
        db.clear_all_ai_data()
        db.clear_anomalies()
        db.clear_recommendations()
        st.success("Database has been completely reset to an empty state.")
        st.rerun()
