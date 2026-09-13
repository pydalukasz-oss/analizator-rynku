"""
Generuje statyczną stronę HTML (index.html) z wykresami dla wszystkich
śledzonych instrumentów — do publikacji przez GitHub Pages.

W przeciwieństwie do Streamlit, to NIE jest działająca aplikacja/serwer —
to zwykła strona internetowa (HTML + JS od Plotly), którą przeglądarka
po prostu wyświetla. Dlatego nie potrzeba żadnego hostingu poza GitHub Pages.

Użycie:
    python generate_report.py
Tworzy plik docs/index.html (folder docs/ to standardowe miejsce,
z którego GitHub Pages umie publikować stronę).
"""

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import config
from indicators import add_indicators, generate_signals


def load_data(db_path: str) -> pd.DataFrame:
    if not Path(db_path).exists():
        raise FileNotFoundError(f"Nie znaleziono {db_path}.")
    conn = sqlite3.connect(db_path)
    df = pd.read_sql("SELECT * FROM market_data", conn)
    conn.close()
    df["date"] = pd.to_datetime(df["date"])
    return df.drop_duplicates(subset=["ticker", "date"]).sort_values("date")


def build_chart_html(ticker: str, market: str, enriched: pd.DataFrame) -> str:
    """Buduje pojedynczy wykres (świece + SMA + RSI) jako fragment HTML."""
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3],
        vertical_spacing=0.03,
        subplot_titles=(f"{ticker} ({market})", "RSI"),
    )
    fig.add_trace(go.Candlestick(
        x=enriched["date"], open=enriched["open"], high=enriched["high"],
        low=enriched["low"], close=enriched["close"], name=ticker,
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=enriched["date"], y=enriched["sma_short"],
        name=f"SMA{config.SMA_SHORT}", line=dict(width=1.5),
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=enriched["date"], y=enriched["sma_long"],
        name=f"SMA{config.SMA_LONG}", line=dict(width=1.5),
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=enriched["date"], y=enriched["rsi"], name="RSI",
        line=dict(color="orange"),
    ), row=2, col=1)
    fig.add_hline(y=config.RSI_OVERBOUGHT, line_dash="dot", line_color="red", row=2, col=1)
    fig.add_hline(y=config.RSI_OVERSOLD, line_dash="dot", line_color="green", row=2, col=1)

    fig.update_layout(
        height=500, xaxis_rangeslider_visible=False,
        margin=dict(l=40, r=20, t=40, b=20),
        template="plotly_dark",
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)


def main():
    raw = load_data(config.DB_PATH)
    print(f"Wczytano {len(raw)} wierszy dla {raw['ticker'].nunique()} instrumentów.")

    charts_html = []
    all_signals = []

    for (market, ticker), group in raw.groupby(["market", "ticker"]):
        enriched = add_indicators(group)
        signals = generate_signals(enriched)
        for s in signals:
            all_signals.append(s)
        charts_html.append(build_chart_html(ticker, market, enriched))

    signals_html = "".join(
        f"<li><b>[{s['type']}]</b> {s['message']}</li>" for s in all_signals
    ) or "<li>Brak aktywnych sygnałów w tej chwili.</li>"

    page = f"""<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="utf-8">
<title>Analizator rynków</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>
  body {{ background: #0e1117; color: #eee; font-family: system-ui, sans-serif;
         max-width: 1000px; margin: 0 auto; padding: 20px; }}
  h1 {{ font-size: 1.6em; }}
  ul {{ background: #1a1d24; padding: 16px 24px; border-radius: 8px; }}
  .updated {{ color: #888; font-size: 0.85em; margin-bottom: 24px; }}
</style>
</head>
<body>
<h1>📊 Analizator rynków</h1>
<p class="updated">Ostatnia aktualizacja danych: automatycznie, przy każdym uruchomieniu workflow.</p>
<h2>Aktualne sygnały</h2>
<ul>{signals_html}</ul>
<h2>Wykresy</h2>
{"".join(charts_html)}
</body>
</html>"""

    out_dir = Path("docs")
    out_dir.mkdir(exist_ok=True)
    (out_dir / "index.html").write_text(page, encoding="utf-8")
    print(f"Zapisano docs/index.html ({len(charts_html)} wykresów, {len(all_signals)} sygnałów).")


if __name__ == "__main__":
    main()
