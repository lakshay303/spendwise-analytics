import html

import streamlit as st

CURRENCY = "₹"

# Brand colors, used by the CSS and later by the charts
PRIMARY = "#4F46E5"
INCOME = "#10B981"
EXPENSE = "#EF4444"
WARNING = "#F59E0B"
MUTED = "#64748B"

STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* Font: applied to text elements only, so icons keep their own font */
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
[data-testid="stMarkdownContainer"], [data-testid="stMetric"],
.stButton button, .stDownloadButton button, input, textarea,
[data-baseweb="select"] {
    font-family: 'Inter', 'Segoe UI', sans-serif;
}

/* Page spacing */
.block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1400px; }
h1 { font-weight: 700; letter-spacing: -0.02em; }
footer { visibility: hidden; }

/* Buttons */
.stButton > button, .stDownloadButton > button {
    border-radius: 10px;
    font-weight: 600;
}

/* Sidebar: brand name above the navigation, rounded links */
[data-testid="stSidebarNav"]::before {
    content: "SpendWise Analytics";
    display: block;
    padding: 1.4rem 1rem 0.6rem 1rem;
    font-size: 1.25rem;
    font-weight: 700;
    letter-spacing: -0.01em;
    color: #FFFFFF;
}
[data-testid="stSidebarNavLink"] { border-radius: 10px; }

/* Cards: any container created with key="card_something" becomes a card */
[class*="st-key-card"] {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 16px;
    padding: 1.1rem 1.25rem;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}

/* HTML metric cards (see metric_card below) */
.sw-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 16px;
    padding: 1.1rem 1.25rem;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}
.sw-label { color: #64748B; font-size: 0.85rem; font-weight: 500; }
.sw-value { color: #0F172A; font-size: 1.75rem; font-weight: 700; letter-spacing: -0.02em; margin-top: 0.15rem; }
.sw-note  { font-size: 0.8rem; margin-top: 0.3rem; font-weight: 500; }
.sw-pill  { display: inline-block; padding: 0.15rem 0.6rem; border-radius: 999px;
            font-size: 0.75rem; font-weight: 600; }
.sw-subtitle { color: #64748B; margin-top: -0.6rem; margin-bottom: 1.25rem; }
</style>
"""

TONES = {"neutral": "#64748B", "good": INCOME, "bad": EXPENSE, "warn": WARNING}
PILLS = {
    "on_track": ("On track", "#D1FAE5", "#047857"),
    "warning": ("Near limit", "#FEF3C7", "#B45309"),
    "over": ("Over budget", "#FEE2E2", "#B91C1C"),
}


def apply_theme():
    """Inject the shared CSS. Call once per page run (app.py does this)."""
    st.markdown(STYLE, unsafe_allow_html=True)


def format_money(amount):
    """1234.5 -> '₹1,234.50'   -1234.5 -> '-₹1,234.50'"""
    sign = "-" if amount < 0 else ""
    return f"{sign}{CURRENCY}{abs(amount):,.2f}"


def page_header(title, subtitle=""):
    st.title(title)
    if subtitle:
        st.markdown(f"<div class='sw-subtitle'>{html.escape(subtitle)}</div>", unsafe_allow_html=True)


def metric_card(label, value, note="", tone="neutral"):
    """A KPI card. tone: 'neutral', 'good', 'bad' or 'warn' colors the small note."""
    color = TONES.get(tone, TONES["neutral"])
    note_html = f"<div class='sw-note' style='color:{color}'>{html.escape(note)}</div>" if note else ""
    st.markdown(
        f"<div class='sw-card'><div class='sw-label'>{html.escape(label)}</div>"
        f"<div class='sw-value'>{html.escape(value)}</div>{note_html}</div>",
        unsafe_allow_html=True,
    )


def status_pill(status):
    """Small colored badge for a budget status ('on_track', 'warning', 'over')."""
    text, background, color = PILLS.get(status, PILLS["on_track"])
    return f"<span class='sw-pill' style='background:{background};color:{color}'>{text}</span>"
def insight_card(title, detail, severity):
    """A compact card with a colored edge. severity: 'bad', 'warn', 'good' or 'info'."""
    colors = {"bad": EXPENSE, "warn": WARNING, "good": INCOME, "info": PRIMARY}
    color = colors.get(severity, PRIMARY)
    st.markdown(
        f"<div style='background:#FFFFFF;border:1px solid #E2E8F0;border-left:4px solid {color};"
        f"border-radius:12px;padding:0.7rem 0.9rem;margin-bottom:0.6rem'>"
        f"<div style='font-weight:600;font-size:0.9rem'>{html.escape(title)}</div>"
        f"<div style='color:#64748B;font-size:0.82rem;margin-top:0.15rem'>{html.escape(detail)}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

def progress_bar(pct, status):
    """A slim progress bar colored by budget status ('on_track', 'warning', 'over')."""
    colors = {"on_track": INCOME, "warning": WARNING, "over": EXPENSE}
    color = colors.get(status, INCOME)
    width = max(0, min(pct, 100))
    st.markdown(
        f"<div style='background:#E2E8F0;border-radius:999px;height:10px;overflow:hidden;margin:0.5rem 0'>"
        f"<div style='width:{width}%;background:{color};height:100%;border-radius:999px'></div></div>",
        unsafe_allow_html=True,
    )