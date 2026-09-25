"""Графики Plotly, генерируются в Python (п.7 ТЗ).

plotly.js отдаётся с нашего домена (/static/plotly.min.js, копия из пакета plotly), inline-скрипты
графиков получают CSP-nonce. Сторонних скриптов нет.
"""

from datetime import datetime

import plotly.graph_objects as go


def _render(fig: go.Figure, title: str, nonce: str) -> str:
    fig.update_layout(
        title=title,
        margin={"l": 40, "r": 10, "t": 40, "b": 30},
        height=320,
        legend={"orientation": "h"},
    )
    html = fig.to_html(full_html=False, include_plotlyjs=False, config={"displayModeBar": False})
    return html.replace("<script", f'<script nonce="{nonce}"')


def apy_chart(series: dict[str, list[tuple[datetime, float]]], title: str, nonce: str) -> str:
    fig = go.Figure()
    for slug, pts in series.items():
        fig.add_scatter(x=[p[0] for p in pts], y=[p[1] for p in pts], mode="lines", name=slug)
    return _render(fig, title, nonce)


def spread_chart(points: list[tuple[datetime, float]], title: str, nonce: str) -> str:
    fig = go.Figure()
    fig.add_scatter(x=[p[0] for p in points], y=[p[1] for p in points], mode="lines", name="spread")
    fig.add_hline(y=0, line_dash="dot")
    return _render(fig, title, nonce)
