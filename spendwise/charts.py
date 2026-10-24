from datetime import datetime

import plotly.graph_objects as go

from spendwise.ui import CURRENCY, EXPENSE, INCOME, PRIMARY

CATEGORY_COLORS = [
    "#4F46E5", "#10B981", "#F59E0B", "#EF4444", "#06B6D4",
    "#8B5CF6", "#EC4899", "#84CC16", "#64748B",
]
FONT = dict(family="Inter, Segoe UI, sans-serif", color="#0F172A")


def _style(fig, height):
    """Shared look for every chart: transparent background, tight margins."""
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=FONT,
    )
    return fig


def category_donut(rows):
    """rows: output of analytics.category_spending()."""
    total = sum(r["total"] for r in rows)
    fig = go.Figure(
        go.Pie(
            labels=[r["category"] for r in rows],
            values=[r["total"] for r in rows],
            hole=0.62,
            sort=False,
            textinfo="none",
            marker=dict(colors=CATEGORY_COLORS, line=dict(color="#FFFFFF", width=2)),
            hovertemplate=f"%{{label}}<br>{CURRENCY}%{{value:,.2f}} (%{{percent}})<extra></extra>",
        )
    )
    fig.add_annotation(
        text=f"<b>{CURRENCY}{total:,.0f}</b><br><span style='font-size:12px;color:#64748B'>spent</span>",
        showarrow=False,
        font=dict(size=22),
    )
    fig.update_layout(legend=dict(orientation="v", yanchor="middle", y=0.5, x=1.02))
    return _style(fig, 340)


def income_expense_bars(rows):
    """rows: output of analytics.monthly_totals()."""
    labels = [datetime.strptime(r["month"], "%Y-%m").strftime("%b %Y") for r in rows]
    fig = go.Figure()
    fig.add_bar(
        x=labels,
        y=[r["income"] for r in rows],
        name="Income",
        marker_color=INCOME,
        hovertemplate=f"Income<br>{CURRENCY}%{{y:,.2f}}<extra></extra>",
    )
    fig.add_bar(
        x=labels,
        y=[r["expenses"] for r in rows],
        name="Expenses",
        marker_color=EXPENSE,
        hovertemplate=f"Expenses<br>{CURRENCY}%{{y:,.2f}}<extra></extra>",
    )
    fig.update_layout(
        barmode="group",
        bargap=0.35,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#E2E8F0", tickprefix=CURRENCY, tickformat=",.0f", zeroline=False)
    return _style(fig, 340)

def spending_trend(current, previous, current_name, previous_name):
    """Cumulative spending by day: this month (solid) against last month (dashed).

    current / previous: output of analytics.cumulative_spending().
    """
    fig = go.Figure()
    fig.add_scatter(
        x=[p["day"] for p in previous],
        y=[p["total"] for p in previous],
        name=previous_name,
        mode="lines",
        line=dict(color="#94A3B8", width=2, dash="dash"),
        hovertemplate=f"{CURRENCY}%{{y:,.2f}}<extra>{previous_name}</extra>",
    )
    fig.add_scatter(
        x=[p["day"] for p in current],
        y=[p["total"] for p in current],
        name=current_name,
        mode="lines",
        line=dict(color=PRIMARY, width=3),
        fill="tozeroy",
        fillcolor="rgba(79, 70, 229, 0.08)",
        hovertemplate=f"{CURRENCY}%{{y:,.2f}}<extra>{current_name}</extra>",
    )
    fig.update_layout(
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(title="Day of month", showgrid=False)
    fig.update_yaxes(gridcolor="#E2E8F0", tickprefix=CURRENCY, tickformat=",.0f", zeroline=False)
    return _style(fig, 340)

def savings_trend(series):
    """Net savings per month as bars (green/red), savings rate as a line on the right axis.

    series: output of analytics.monthly_series().
    """
    labels = [datetime.strptime(r["month"], "%Y-%m").strftime("%b %Y") for r in series]
    fig = go.Figure()
    fig.add_bar(
        x=labels,
        y=[r["net"] for r in series],
        name="Net savings",
        marker_color=[INCOME if r["net"] >= 0 else EXPENSE for r in series],
        hovertemplate=f"Net savings<br>{CURRENCY}%{{y:,.2f}}<extra></extra>",
    )
    fig.add_scatter(
        x=labels,
        y=[r["savings_rate"] for r in series],
        name="Savings rate",
        mode="lines+markers",
        yaxis="y2",
        connectgaps=False,
        line=dict(color=PRIMARY, width=3),
        hovertemplate="Savings rate<br>%{y:.1f}%<extra></extra>",
    )
    fig.update_layout(
        bargap=0.4,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis2=dict(overlaying="y", side="right", ticksuffix="%", showgrid=False, zeroline=False),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_layout(
        yaxis=dict(gridcolor="#E2E8F0", tickprefix=CURRENCY, tickformat=",.0f", zeroline=False)
    )
    return _style(fig, 340)


def category_stacked(rows, months):
    """Stacked bars: spending per category for each month.

    rows: output of analytics.category_by_month(); months: the month list, oldest first.
    """
    labels = [datetime.strptime(m, "%Y-%m").strftime("%b %Y") for m in months]
    totals = {}
    for r in rows:
        totals[r["category"]] = totals.get(r["category"], 0) + r["total"]
    order = sorted(totals, key=totals.get, reverse=True)

    fig = go.Figure()
    for i, name in enumerate(order):
        values = [
            sum(r["total"] for r in rows if r["category"] == name and r["month"] == m) for m in months
        ]
        fig.add_bar(
            x=labels,
            y=values,
            name=name,
            marker_color=CATEGORY_COLORS[i % len(CATEGORY_COLORS)],
            hovertemplate=f"{name}<br>{CURRENCY}%{{y:,.2f}}<extra></extra>",
        )
    fig.update_layout(barmode="stack", bargap=0.35, legend=dict(orientation="h", y=-0.15))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#E2E8F0", tickprefix=CURRENCY, tickformat=",.0f", zeroline=False)
    return _style(fig, 380)


def top_categories_bar(rows):
    """Horizontal bars for the biggest categories. rows: output of analytics.top_categories()."""
    rows = list(reversed(rows[:8]))
    fig = go.Figure(
        go.Bar(
            x=[r["total"] for r in rows],
            y=[r["category"] for r in rows],
            orientation="h",
            marker_color=PRIMARY,
            text=[f"{r['share']:.0f}%" for r in rows],
            textposition="outside",
            cliponaxis=False,
            hovertemplate=f"%{{y}}<br>{CURRENCY}%{{x:,.2f}}<extra></extra>",
        )
    )
    fig.update_xaxes(gridcolor="#E2E8F0", tickprefix=CURRENCY, tickformat=",.0f", zeroline=False)
    fig.update_yaxes(showgrid=False)
    return _style(fig, 340)