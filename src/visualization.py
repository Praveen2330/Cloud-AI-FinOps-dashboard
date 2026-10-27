"""
visualization.py — Reusable Plotly chart builders for FinOps Intelligence Dashboard.

All functions return go.Figure objects; no Streamlit calls here.
Color palette, fonts, and layout are centralised so every page looks consistent.
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from typing import Optional

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------

BRAND_COLORS = {
    "primary":   "#2563EB",
    "secondary": "#7C3AED",
    "success":   "#22C55E",
    "warning":   "#F59E0B",
    "danger":    "#EF4444",
    "neutral":   "#64748B",
    "aws":       "#FF9900",
    "azure":     "#0078D4",
    "gcp":       "#4285F4",
}

PROVIDER_COLORS = {
    "AWS":   BRAND_COLORS["aws"],
    "Azure": BRAND_COLORS["azure"],
    "GCP":   BRAND_COLORS["gcp"],
}

STATUS_COLORS = {
    "Healthy":    BRAND_COLORS["success"],
    "Attention":  BRAND_COLORS["warning"],
    "Near Limit": BRAND_COLORS["danger"],
    "Over Budget":BRAND_COLORS["secondary"],
}

SEVERITY_COLORS = {
    "Critical": BRAND_COLORS["secondary"],
    "High":     BRAND_COLORS["danger"],
    "Medium":   BRAND_COLORS["warning"],
    "Low":      BRAND_COLORS["success"],
}

PALETTE_10 = px.colors.qualitative.Plotly
PLOTLY_TEMPLATE = "plotly_white"

BASE_LAYOUT = dict(
    template=PLOTLY_TEMPLATE,
    margin=dict(l=20, r=20, t=40, b=20),
    font=dict(family="Inter, sans-serif", size=13, color="#1E293B"),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)


def _apply_base(fig: go.Figure, title: str = "", height: int = 400) -> go.Figure:
    fig.update_layout(title=title, height=height, **BASE_LAYOUT)
    return fig


def _fmt_inr(v: float) -> str:
    if v >= 1_00_00_000:
        return f"₹{v/1_00_00_000:.2f}Cr"
    if v >= 1_00_000:
        return f"₹{v/1_00_000:.2f}L"
    if v >= 1000:
        return f"₹{v/1000:.1f}K"
    return f"₹{v:.0f}"


# ---------------------------------------------------------------------------
# 1. Daily spend line chart
# ---------------------------------------------------------------------------

def daily_spend_line(
    daily_df: pd.DataFrame,
    date_col: str = "billing_date",
    cost_col: str = "total_cost",
    compare_df: Optional[pd.DataFrame] = None,
    title: str = "Daily Cloud Spend",
    height: int = 350,
) -> go.Figure:
    fig = go.Figure()

    if not daily_df.empty:
        fig.add_trace(go.Scatter(
            x=daily_df[date_col],
            y=daily_df[cost_col],
            mode="lines",
            name="Current Period",
            line=dict(color=BRAND_COLORS["primary"], width=2),
            fill="tozeroy",
            fillcolor="rgba(37,99,235,0.08)",
            hovertemplate="%{x|%d %b %Y}<br>₹%{y:,.0f}<extra></extra>",
        ))

    if compare_df is not None and not compare_df.empty:
        fig.add_trace(go.Scatter(
            x=compare_df[date_col],
            y=compare_df[cost_col],
            mode="lines",
            name="Previous Period",
            line=dict(color=BRAND_COLORS["neutral"], width=1.5, dash="dot"),
            hovertemplate="%{x|%d %b %Y}<br>₹%{y:,.0f}<extra></extra>",
        ))

    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(tickprefix="₹", showgrid=True, gridcolor="#F1F5F9")
    return _apply_base(fig, title, height)


# ---------------------------------------------------------------------------
# 2. Spend by service bar chart
# ---------------------------------------------------------------------------

def spend_by_service_bar(
    df: pd.DataFrame,
    n: int = 12,
    title: str = "Cloud Spend by Service",
    height: int = 400,
) -> go.Figure:
    if df.empty:
        return go.Figure()

    df = df.nlargest(n, "total_cost")
    fig = go.Figure(go.Bar(
        x=df["total_cost"],
        y=df["service_name"],
        orientation="h",
        marker_color=BRAND_COLORS["primary"],
        text=[_fmt_inr(v) for v in df["total_cost"]],
        textposition="outside",
        hovertemplate="%{y}<br>₹%{x:,.0f}<extra></extra>",
    ))
    fig.update_layout(yaxis=dict(autorange="reversed"), xaxis=dict(showgrid=True, gridcolor="#F1F5F9"))
    return _apply_base(fig, title, height)


# ---------------------------------------------------------------------------
# 3. Spend by department / project donut
# ---------------------------------------------------------------------------

def spend_donut(
    df: pd.DataFrame,
    label_col: str,
    value_col: str = "total_cost",
    title: str = "Spend Distribution",
    height: int = 380,
) -> go.Figure:
    if df.empty:
        return go.Figure()

    fig = go.Figure(go.Pie(
        labels=df[label_col],
        values=df[value_col],
        hole=0.55,
        marker=dict(colors=PALETTE_10),
        textinfo="label+percent",
        hovertemplate="%{label}<br>₹%{value:,.0f} (%{percent})<extra></extra>",
    ))
    fig.update_layout(
        legend=dict(orientation="v", x=1.0, y=0.5),
        annotations=[dict(text=_fmt_inr(float(df[value_col].sum())),
                          x=0.5, y=0.5, font_size=16, showarrow=False)],
    )
    return _apply_base(fig, title, height)


# ---------------------------------------------------------------------------
# 4. Budget vs actual bar chart
# ---------------------------------------------------------------------------

def budget_vs_actual_chart(
    summary_df: pd.DataFrame,
    title: str = "Budget vs Actual Spend",
    height: int = 400,
) -> go.Figure:
    if summary_df.empty:
        return go.Figure()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Budget",
        x=summary_df["name"],
        y=summary_df["monthly_budget"],
        marker_color="#CBD5E1",
        hovertemplate="%{x}<br>Budget: ₹%{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="Actual Spend",
        x=summary_df["name"],
        y=summary_df["actual_spend"],
        marker_color=[
            STATUS_COLORS.get(s, BRAND_COLORS["primary"])
            for s in summary_df.get("status", [""] * len(summary_df))
        ],
        hovertemplate="%{x}<br>Actual: ₹%{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(barmode="group")
    fig.update_xaxes(tickangle=-30)
    fig.update_yaxes(tickprefix="₹", showgrid=True, gridcolor="#F1F5F9")
    return _apply_base(fig, title, height)


# ---------------------------------------------------------------------------
# 5. Cloud vs AI spend comparison
# ---------------------------------------------------------------------------

def cloud_vs_ai_chart(
    cloud_total: float,
    ai_total: float,
    height: int = 300,
) -> go.Figure:
    labels = ["Cloud Infrastructure", "AI / LLM"]
    values = [cloud_total, ai_total]
    colors = [BRAND_COLORS["primary"], BRAND_COLORS["secondary"]]

    fig = go.Figure(go.Bar(
        x=labels, y=values,
        marker_color=colors,
        text=[_fmt_inr(v) for v in values],
        textposition="outside",
        hovertemplate="%{x}<br>₹%{y:,.0f}<extra></extra>",
    ))
    fig.update_yaxes(tickprefix="₹", showgrid=True, gridcolor="#F1F5F9")
    return _apply_base(fig, "Cloud vs AI Spend", height)


# ---------------------------------------------------------------------------
# 6. Anomaly timeline scatter
# ---------------------------------------------------------------------------

def anomaly_timeline(
    daily_df: pd.DataFrame,
    anomaly_df: pd.DataFrame,
    date_col: str = "billing_date",
    cost_col: str = "total_cost",
    title: str = "Spend with Detected Anomalies",
    height: int = 400,
) -> go.Figure:
    fig = go.Figure()

    if not daily_df.empty:
        fig.add_trace(go.Scatter(
            x=daily_df[date_col],
            y=daily_df[cost_col],
            mode="lines",
            name="Daily Spend",
            line=dict(color=BRAND_COLORS["primary"], width=1.5),
            hovertemplate="%{x|%d %b %Y}<br>₹%{y:,.0f}<extra></extra>",
        ))

    if not anomaly_df.empty:
        for sev in ["Critical", "High", "Medium", "Low"]:
            sub = anomaly_df[anomaly_df["severity"] == sev]
            if sub.empty:
                continue
            fig.add_trace(go.Scatter(
                x=sub["detection_date"],
                y=sub["actual_cost"],
                mode="markers",
                name=f"Anomaly ({sev})",
                marker=dict(
                    color=SEVERITY_COLORS[sev],
                    size=12,
                    symbol="x",
                    line=dict(width=2),
                ),
                hovertemplate="<b>%{x}</b><br>Actual: ₹%{y:,.0f}<extra></extra>",
            ))

    return _apply_base(fig, title, height)


# ---------------------------------------------------------------------------
# 7. AI daily spend line
# ---------------------------------------------------------------------------

def ai_daily_line(
    daily_df: pd.DataFrame,
    title: str = "Daily AI/LLM Spend",
    height: int = 320,
) -> go.Figure:
    fig = go.Figure()
    if not daily_df.empty:
        fig.add_trace(go.Scatter(
            x=daily_df["usage_date"].astype(str),
            y=daily_df["total_cost"],
            mode="lines",
            name="AI Spend",
            line=dict(color=BRAND_COLORS["secondary"], width=2),
            fill="tozeroy",
            fillcolor="rgba(124,58,237,0.08)",
        ))
    fig.update_yaxes(tickprefix="₹")
    return _apply_base(fig, title, height)


# ---------------------------------------------------------------------------
# 8. Token usage stacked bar (input vs output)
# ---------------------------------------------------------------------------

def token_usage_bar(
    model_df: pd.DataFrame,
    title: str = "Token Usage by Model",
    height: int = 370,
) -> go.Figure:
    if model_df.empty:
        return go.Figure()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Input Tokens",
        x=model_df["model_name"],
        y=model_df["input_tokens"],
        marker_color=BRAND_COLORS["primary"],
    ))
    fig.add_trace(go.Bar(
        name="Output Tokens",
        x=model_df["model_name"],
        y=model_df["output_tokens"],
        marker_color=BRAND_COLORS["secondary"],
    ))
    fig.update_layout(barmode="stack")
    fig.update_xaxes(tickangle=-30)
    return _apply_base(fig, title, height)


# ---------------------------------------------------------------------------
# 9. Provider spend pie
# ---------------------------------------------------------------------------

def provider_pie(provider_df: pd.DataFrame, height: int = 340) -> go.Figure:
    if provider_df.empty:
        return go.Figure()
    colors = [PROVIDER_COLORS.get(p, BRAND_COLORS["neutral"]) for p in provider_df["cloud_provider"]]
    fig = go.Figure(go.Pie(
        labels=provider_df["cloud_provider"],
        values=provider_df["total_cost"],
        hole=0.5,
        marker=dict(colors=colors),
        textinfo="label+percent",
        hovertemplate="%{label}<br>₹%{value:,.0f}<extra></extra>",
    ))
    return _apply_base(fig, "Spend by Cloud Provider", height)


# ---------------------------------------------------------------------------
# 10. Monthly spend trend multi-line by provider
# ---------------------------------------------------------------------------

def monthly_trend_by_provider(billing_df: pd.DataFrame, height: int = 380) -> go.Figure:
    if billing_df.empty:
        return go.Figure()

    df = billing_df.copy()
    df["billing_date"] = pd.to_datetime(df["billing_date"])
    df["ym"] = df["billing_date"].dt.to_period("M").astype(str)
    monthly = df.groupby(["ym", "cloud_provider"])["total_cost"].sum().reset_index()

    fig = go.Figure()
    for prov in monthly["cloud_provider"].unique():
        sub = monthly[monthly["cloud_provider"] == prov].sort_values("ym")
        fig.add_trace(go.Scatter(
            x=sub["ym"], y=sub["total_cost"],
            mode="lines+markers",
            name=prov,
            line=dict(color=PROVIDER_COLORS.get(prov)),
            hovertemplate=f"<b>{prov}</b><br>%{{x}}<br>₹%{{y:,.0f}}<extra></extra>",
        ))

    fig.update_yaxes(tickprefix="₹")
    return _apply_base(fig, "Monthly Spend by Provider", height)


# ---------------------------------------------------------------------------
# 11. Anomaly severity distribution
# ---------------------------------------------------------------------------

def anomaly_severity_bar(anomaly_df: pd.DataFrame, height: int = 300) -> go.Figure:
    if anomaly_df.empty:
        return go.Figure()

    counts = anomaly_df["severity"].value_counts().reindex(
        ["Critical", "High", "Medium", "Low"], fill_value=0
    )
    fig = go.Figure(go.Bar(
        x=counts.index,
        y=counts.values,
        marker_color=[SEVERITY_COLORS[s] for s in counts.index],
        text=counts.values,
        textposition="outside",
    ))
    return _apply_base(fig, "Anomalies by Severity", height)


# ---------------------------------------------------------------------------
# 12. Budget utilisation progress (horizontal bar)
# ---------------------------------------------------------------------------

def budget_utilisation_bars(summary_df: pd.DataFrame, height: int = 400) -> go.Figure:
    if summary_df.empty:
        return go.Figure()

    df = summary_df.dropna(subset=["utilisation_pct"]).copy()
    df = df.sort_values("utilisation_pct", ascending=True)

    colors = [STATUS_COLORS.get(s, BRAND_COLORS["primary"]) for s in df["status"]]

    fig = go.Figure(go.Bar(
        x=df["utilisation_pct"].clip(upper=120),
        y=df["name"],
        orientation="h",
        marker_color=colors,
        text=[f"{v:.1f}%" for v in df["utilisation_pct"]],
        textposition="outside",
        hovertemplate="%{y}<br>Utilisation: %{x:.1f}%<extra></extra>",
    ))

    fig.add_vline(x=100, line_dash="dash", line_color="#94A3B8",
                  annotation_text="100% budget", annotation_position="top")

    fig.update_xaxes(range=[0, 130], ticksuffix="%")
    return _apply_base(fig, "Budget Utilisation", height)
