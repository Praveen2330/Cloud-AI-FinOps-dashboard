# 💹 FinOps Intelligence: Cloud & AI Cost Analytics Platform

> **Cloud and AI FinOps Analytics Dashboard with Statistical Cost Anomaly Detection**  
> *A full-stack, enterprise-grade cloud economics and LLM token cost intelligence platform designed for Cloud FinOps Engineers and AI Infrastructure Analysts.*

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.45%2B-red.svg)](https://streamlit.io/)
[![Plotly](https://img.shields.io/badge/Plotly-5.20%2B-purple.svg)](https://plotly.com/)
[![SQLite](https://img.shields.io/badge/Database-SQLite-lightgrey.svg)](https://www.sqlite.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📌 Disclaimer
> **Portfolio Project Notice:**  
> The default dataset is synthetic and deterministically generated. This application is an educational and technical portfolio demonstration for Cloud and AI FinOps internships and is **not** connected to live enterprise AWS, Azure, or GCP production billing APIs. No real customer credentials, proprietary telemetry, or account identifiers are used.

---

## 📖 Executive Summary & Business Problem

As enterprises scale generative AI workloads alongside traditional cloud infrastructure, cloud bills frequently suffer from:
1. **Unpredictable AI Inference Cost Spikes:** Lack of token-level visibility across applications and models.
2. **Delayed Anomaly Triage:** Traditional billing dashboards deliver monthly retrospective reports rather than daily deviation detection.
3. **Budget Blind Spots:** Static spreadsheets fail to project dynamic month-end exhaustion trajectories.
4. **Unsubstantiated Optimization Recommendations:** Generic cost-cutting advice without verifiable mathematical evidence.

**FinOps Intelligence** bridges these gaps by combining SQL-driven relational billing stores, rolling statistical time-series anomaly detection ($Z$-Score and IQR), transparent AI token pricing economics, and actionable engineering recommendations.

---

## 🌟 Key Features

### 1. 📊 Executive Overview
* **KPI Metrics:** Total Cloud Spend, AI/LLM Spend, Monthly Budget, Budget Utilization, Detected Anomalies, and Estimated Optimization Opportunities.
* **Period-over-Period Delta:** Mathematical % shifts comparing current and previous observation windows.
* **Auto-Generated Insights:** Plain-English dynamic observations generated directly from live SQL queries.
* **Multi-Cloud Mix:** Interactive breakdown across AWS, Microsoft Azure, and Google Cloud Platform.

### 2. ☁️ Cloud Cost Explorer
* **Granular Dimensional Filtering:** Filter by cloud provider, service name, service category, department, project, region, environment, and free-text resource search.
* **Parameterized SQL Aggregations:** Groupings by service, department, project, region, and environment with zero SQL-injection vulnerability.
* **Period Comparison Engine:** Compare expenditure between custom date ranges.
* **Data Export:** Filtered records downloadable as CSV on demand.

### 3. 💰 Budget Monitoring & Month-End Projections
* **Hierarchical Budgeting:** Configure monthly budgets for overall cloud, per provider, per department, per project, and for AI workloads.
* **Configurable Alert Thresholds:** Healthy ($<70\%$), Attention ($70\%\text{--}90\%$), Near Limit ($90\%\text{--}100\%$), and Over Budget ($>100\%$).
* **Safe Linear Month-End Projections:**
  $$\text{Projected Month-End Spend} = \left(\frac{\text{Actual Spend to Date}}{\text{Current Day}}\right) \times \text{Days in Month}$$
  *Requires $\ge 3$ days of historical data to avoid single-day extrapolation distortion.*

### 4. 🚨 Statistical Cost Anomaly Detection
* **Primary Detector (Rolling Z-Score):**
  $$\mu_t = \frac{1}{W} \sum_{i=1}^{W} x_{t-i}, \quad \sigma_t = \sqrt{\frac{1}{W} \sum_{i=1}^{W} (x_{t-i} - \mu_t)^2}, \quad Z_t = \frac{x_t - \mu_t}{\sigma_t}$$
* **Secondary Detector (Interquartile Range - IQR):**
  $$\text{Upper Threshold} = Q_3 + 2.5 \times (Q_3 - Q_1)$$
* **Triage & Status Persistence:** Mark deviations as *New*, *Investigating*, *Resolved*, or *False Positive* with persistent notes stored directly in SQLite.
* **Zero Variance & Gap Safeguards:** Prevents division by zero on flat-spend services and handles calendar day gaps without window warping.

### 5. 🤖 AI and LLM Cost Analytics
* **Transparent Token Cost Modeling:**
  $$\text{Cost} = \left(\frac{\text{Input Tokens}}{1,000,000} \times P_{\text{in}}\right) + \left(\frac{\text{Output Tokens}}{1,000,000} \times P_{\text{out}}\right)$$
* **Model & Application Breakdown:** Analyzes Claude, GPT-4o, and Gemini workloads across enterprise applications (ChatAssistant, CodeReview, DataPipeline, etc.).
* **Configurable Pricing Assumptions:** Modify INR/USD rates per million tokens and recalculate historical records on demand.
* **Token Efficiency Metrics:** Cost per 1,000 tokens and average cost per request.

### 6. 💡 Evidence-Based Cost Optimization
* **FinOps Truth in Savings:** Distinguishes *observed spending increases* and *potential optimization opportunities* from *realized savings*.
* **Rule Categories:**
  * Spending Growth spikes ($>50\%$ growth and $>₹5,000$ increase)
  * Budget exhaustion risks
  * Storage lifecycle opportunities (when storage $>20\%$ total bill)
  * AI token efficiency & model-routing disparities
* Every recommendation includes **Title, Affected Resource, Evidence, Action, Estimated Impact, Confidence, and Priority**.

### 7. 📁 Dataset Lifecycle & CSV Ingestion
* **Reproducible Benchmark Generator:** Generates 180+ days of deterministic multi-cloud data with seeded anomaly spikes.
* **Strict CSV Schema Validation:** Verifies required headers, data types, negative values, and date parsing with options to reject or import valid rows.
* **Full Data Export & Reset:** Export current databases or wipe tables with confirmation safeguards.

---

## 🏛️ System Architecture

```
                    +-------------------------------------+
                    |       Streamlit Web Dashboard       |
                    | (app.py + 8 Multi-Page Modules)     |
                    +-------------------+-----------------+
                                        |
               +------------------------+------------------------+
               |                                                 |
+--------------v---------------+                 +---------------v---------------+
|    Analytical Engine Layer    |                 |   Visualization Layer (Plotly) |
| - cloud_analytics.py         |                 | - visualization.py            |
| - budget_engine.py           |                 | - Consistent design tokens    |
| - anomaly_detector.py        |                 | - Responsive cards & badges   |
| - ai_cost_engine.py          |                 +-------------------------------+
| - recommendation_engine.py   |
+--------------+---------------+
               |
+--------------v---------------+
|   Data Access & Validation   |
| - database.py (SQLite / WAL) |
| - data_validation.py         |
| - data_generator.py          |
+--------------+---------------+
               |
+--------------v---------------+
|     Local SQLite Store       |
| (data/finops.db + WAL Log)   |
+------------------------------+
```

---

## 🗄️ Database Schema

The SQLite schema is modular and indexed for fast analytical aggregation:

1. **`cloud_billing`**: `id`, `billing_date`, `cloud_provider`, `service_name`, `service_category`, `account_id`, `account_alias`, `region`, `project`, `department`, `environment`, `resource_id`, `usage_quantity`, `usage_unit`, `unit_price`, `total_cost`, `currency`, `data_source`
2. **`ai_usage`**: `id`, `request_timestamp`, `provider`, `model_name`, `model_category`, `project`, `application`, `input_tokens`, `output_tokens`, `request_count`, `estimated_input_cost`, `estimated_output_cost`, `estimated_total_cost`, `currency`, `status`, `data_source`
3. **`budgets`**: `id`, `budget_type`, `name`, `monthly_budget`, `currency`, `period_year`, `period_month`, `created_at`, `updated_at`
4. **`anomaly_events`**: `id`, `detection_date`, `cloud_provider`, `service_name`, `project`, `actual_cost`, `expected_cost`, `absolute_increase`, `pct_increase`, `detection_method`, `severity`, `status`, `notes`, `created_at`, `updated_at`
5. **`pricing_assumptions`**: `id`, `provider`, `model_name`, `input_price_per_million`, `output_price_per_million`, `currency`, `effective_date`, `notes`
6. **`optimization_recommendations`**: `id`, `category`, `title`, `affected_resource`, `evidence`, `recommended_action`, `estimated_impact`, `impact_currency`, `confidence_level`, `priority`, `status`, `created_at`

---

## 🚀 Installation & Quickstart

### Prerequisites
* Python 3.12 or newer
* Git

### Step 1: Clone Repository
```bash
git clone https://github.com/your-username/finops-dashboard.git
cd finops-dashboard
```

### Step 2: Create and Activate Virtual Environment
```bash
# macOS/Linux
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Seed Database with Initial 185-Day Benchmark Data
```bash
python seed_db.py
```

### Step 5: Launch the Application
```bash
streamlit run app.py
```
The application will open in your browser at `http://localhost:8501`.

---

## 🧪 Automated Testing

The suite includes 25 comprehensive automated tests verifying statistical anomaly detection, budget calculations, zero division safety, CSV validation, and database persistence.

### Run with Built-in Runner:
```bash
python run_tests.py
```

### Run with pytest:
```bash
pytest -v
```

### Verified Test Cases:
* ✅ Cloud spending aggregation & period-over-period delta
* ✅ SQL filtering across providers and departments
* ✅ Empty dataset and zero cost edge cases
* ✅ Budget utilization, remaining budget, and status threshold triggers
* ✅ Month-end projection with $<3$ day history safeguards
* ✅ Statistical anomaly detection on steady normal data (no false alerts)
* ✅ Detection of deliberately injected 10x cost spikes
* ✅ Safe handling of zero historical variance ($\sigma = 0$)
* ✅ Anomaly status persistence and note updating in SQLite
* ✅ AI token cost formula calculation & bulk price recalculations
* ✅ CSV schema validation (required fields, negative values, malformed dates)

---

## 💼 Internship Interview Demonstration Guide

When presenting this project to engineering recruiters and FinOps managers:

1. **Start on Executive Overview (`pages/overview.py`):**
   * Highlight total cloud expenditure, AI spend proportion, and dynamic period-over-period trends.
   * Point out the **Auto-Generated Insights** section and explain that every statement is calculated live from the dataset using SQL aggregations.
2. **Demonstrate Cloud Cost Explorer (`pages/cloud_cost_explorer.py`):**
   * Filter by provider (e.g., `AWS`) and service (e.g., `EC2`).
   * Show the period-over-period comparison tab to identify growth drivers.
   * Export the filtered data to CSV to demonstrate analyst workflow support.
3. **Walk through Cost Anomaly Detection (`pages/anomaly_detection.py`):**
   * Explain the mathematics: Rolling Z-Score with 21-day window + IQR robust bounds.
   * Show how an injected spike (e.g., SageMaker or BigQuery) is flagged.
   * Open the triage drawer, change status from `New` to `Investigating`, add an engineering investigation note, and show that the state persists upon page refresh.
4. **Showcase AI Cost Economics (`pages/ai_cost_analytics.py`):**
   * Explain the token economics formula: input vs output token cost asymmetry.
   * Navigate to the **Pricing Assumptions** tab, adjust a model's rate, and demonstrate live recalculation of the historical dataset.
5. **Explain FinOps Principles in Optimization (`pages/optimization.py`):**
   * Articulate why the dashboard refuses to label potential opportunities as realized savings.
   * Show how recommendations cite exact empirical evidence before proposing action.

---

## ⚠️ Known Limitations & Future Enhancements

### Current Limitations:
* **Linear Month-End Projection:** Extrapolates based on average daily spend. It does not account for intra-month seasonality (e.g. batch jobs run on the final day).
* **Simulated Telemetry:** CPU/RAM utilization metrics are simulated; live rightsizing requires continuous agent telemetry.
* **Currency Support:** Standardized on INR with USD token equivalents; multi-currency live conversions require an external FX API.

### Future Roadmap:
* [ ] Support PostgreSQL connection strings via `.env` configuration.
* [ ] Native FOCUS (FinOps Open Cost and Usage Specification) 1.0 schema alignment.
* [ ] Holt-Winters exponential smoothing and Prophet time-series models for seasonal anomaly detection.
* [ ] Webhook alerts for Slack and Microsoft Teams on Critical anomaly detection.

---

## 📄 License
This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
