"""
Generuje statyczną stronę HTML (docs/index.html) z wykresami, wyjaśnieniami,
tabelą backtestu i interaktywnym kalkulatorem scenariuszy ryzyka —
do publikacji przez GitHub Pages.

To NIE jest działająca aplikacja/serwer jak Streamlit — to zwykła strona
internetowa. Kalkulator ryzyka liczy w przeglądarce (JavaScript), na
danych historycznych wbudowanych w stronę przy generowaniu — nie potrzeba
żadnego backendu ani hostingu poza GitHub Pages.

Użycie:
    python generate_report.py
"""

import json
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import config
from indicators import add_indicators, generate_signals
from backtest import backtest_all


def load_data(db_path: str) -> pd.DataFrame:
    if not Path(db_path).exists():
        raise FileNotFoundError(f"Nie znaleziono {db_path}.")
    conn = sqlite3.connect(db_path)
    df = pd.read_sql("SELECT * FROM market_data", conn)
    conn.close()
    df["date"] = pd.to_datetime(df["date"])
    return df.drop_duplicates(subset=["ticker", "date"]).sort_values("date")


def build_chart_html(ticker: str, market: str, enriched: pd.DataFrame) -> str:
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
        height=450, xaxis_rangeslider_visible=False,
        margin=dict(l=40, r=20, t=40, b=20),
        template="plotly_dark",
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)


def signal_explanation(signal_type: str) -> str:
    return {
        "SMA_CROSS_UP": "krótsza średnia krocząca przebiła dłuższą od dołu — "
                        "historycznie bywa to interpretowane jako sygnał wzrostowy.",
        "SMA_CROSS_DOWN": "krótsza średnia krocząca przebiła dłuższą od góry — "
                           "historycznie bywa to interpretowane jako sygnał spadkowy.",
        "RSI_OVERSOLD": "wskaźnik RSI jest bardzo nisko — instrument bywa uznawany "
                         "za \"wyprzedany\", co czasem poprzedza odbicie (ale nie zawsze).",
        "RSI_OVERBOUGHT": "wskaźnik RSI jest bardzo wysoko — instrument bywa uznawany "
                           "za \"wykupiony\", co czasem poprzedza korektę (ale nie zawsze).",
        "VOLUME_SPIKE": "wolumen obrotu jest znacznie wyższy niż zwykle — oznacza "
                         "wzmożone zainteresowanie inwestorów, w dowolnym kierunku.",
    }.get(signal_type, "")


def main():
    raw = load_data(config.DB_PATH)
    print(f"Wczytano {len(raw)} wierszy dla {raw['ticker'].nunique()} instrumentów.")

    charts_html = []
    all_signals = []
    price_data = {}  # do kalkulatora ryzyka w JS: {ticker: {dates, closes, market}}

    for (market, ticker), group in raw.groupby(["market", "ticker"]):
        enriched = add_indicators(group)
        signals = generate_signals(enriched)
        all_signals.extend(signals)
        charts_html.append(build_chart_html(ticker, market, enriched))
        price_data[ticker] = {
            "market": market,
            "dates": group["date"].dt.strftime("%Y-%m-%d").tolist(),
            "closes": group["close"].round(4).tolist(),
        }

    signals_html = "".join(
        f"<li><b>[{s['type']}]</b> {s['message']}<br>"
        f"<span class='explain'>{signal_explanation(s['type'])}</span></li>"
        for s in all_signals
    ) or "<li>Brak aktywnych sygnałów w tej chwili.</li>"

    # --- Backtest ---
    bt = backtest_all(raw, max_hold_days=30)
    bt_rows = "".join(
        f"<tr><td>{r.ticker}</td><td>{r.n_trades}</td>"
        f"<td>{r.win_rate_pct if pd.notna(r.win_rate_pct) else '—'}</td>"
        f"<td>{r.avg_return_pct if pd.notna(r.avg_return_pct) else '—'}</td>"
        f"<td class='{'pos' if (r.total_return_pct or 0) >= 0 else 'neg'}'>{r.total_return_pct if pd.notna(r.total_return_pct) else '—'}</td>"
        f"<td>{r.buy_hold_return_pct if pd.notna(r.buy_hold_return_pct) else '—'}</td></tr>"
        for r in bt.itertuples()
    )

    ticker_options = "".join(f'<option value="{t}">{t} ({d["market"]})</option>' for t, d in price_data.items())
    price_data_json = json.dumps(price_data)

    page = f"""<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Analizator rynków</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>
  body {{ background: #0e1117; color: #eee; font-family: system-ui, sans-serif;
         max-width: 1000px; margin: 0 auto; padding: 20px; line-height: 1.5; }}
  h1 {{ font-size: 1.7em; }}
  h2 {{ font-size: 1.3em; margin-top: 2.2em; border-top: 1px solid #333; padding-top: 1em; }}
  p.lead {{ color: #bbb; }}
  ul {{ background: #1a1d24; padding: 16px 24px; border-radius: 8px; list-style: none; }}
  ul li {{ margin-bottom: 12px; }}
  .explain {{ color: #999; font-size: 0.9em; }}
  .updated {{ color: #888; font-size: 0.85em; margin-bottom: 24px; }}
  table {{ width: 100%; border-collapse: collapse; background: #1a1d24; border-radius: 8px; overflow: hidden; }}
  th, td {{ padding: 10px 14px; text-align: right; border-bottom: 1px solid #2a2d34; }}
  th:first-child, td:first-child {{ text-align: left; }}
  th {{ background: #22252c; color: #aaa; font-weight: 600; }}
  .pos {{ color: #4caf50; }}
  .neg {{ color: #f44336; }}
  .calc-box {{ background: #1a1d24; padding: 20px; border-radius: 8px; }}
  .calc-box label {{ display: block; margin-top: 12px; margin-bottom: 4px; color: #bbb; font-size: 0.9em; }}
  .calc-box select, .calc-box input {{
    width: 100%; padding: 8px 10px; background: #0e1117; border: 1px solid #333;
    color: #eee; border-radius: 6px; font-size: 1em; box-sizing: border-box;
  }}
  .calc-box button {{
    margin-top: 16px; padding: 10px 20px; background: #4c8bf5; color: white;
    border: none; border-radius: 6px; cursor: pointer; font-size: 1em;
  }}
  .calc-box button:hover {{ background: #3a75db; }}
  #calc-results {{ margin-top: 20px; }}
  .scenario {{ padding: 10px 14px; margin-bottom: 8px; border-radius: 6px; background: #22252c; }}
  .scenario .label {{ color: #aaa; font-size: 0.85em; }}
  .disclaimer {{ background: #2a1f0e; border: 1px solid #5a3d0e; padding: 14px 18px;
                border-radius: 8px; color: #d9b878; font-size: 0.9em; margin-top: 16px; }}
  code {{ background: #22252c; padding: 2px 6px; border-radius: 4px; }}
</style>
</head>
<body>

<h1>📊 Analizator rynków</h1>
<p class="lead">Automatyczna analiza GPW, rynków USA i (opcjonalnie) krypto —
wskaźniki techniczne, backtest strategii i kalkulator scenariuszy ryzyka.</p>
<p class="updated">Dane aktualizowane automatycznie przy każdym uruchomieniu workflow w GitHub Actions.</p>

<h2>Co tu widzisz — krótkie wyjaśnienie</h2>
<p>
Ta strona pokazuje trzy rzeczy: (1) <b>aktualne sygnały techniczne</b> —
wzorce w cenie i wolumenie, które mogą (ale nie muszą) coś zapowiadać;
(2) <b>wyniki backtestu</b> — jak te same sygnały radziły sobie historycznie
w porównaniu do zwykłego kupienia i trzymania; (3) <b>kalkulator ryzyka</b> —
jaki rozrzut wyników historycznie dawała inwestycja danej kwoty na dany okres.
Żadna z tych rzeczy nie jest prognozą przyszłości — to statystyka przeszłości.
</p>

<h2>Aktualne sygnały</h2>
<ul>{signals_html}</ul>

<h2>Backtest — czy sygnały historycznie biły rynek?</h2>
<p class="lead">
<b>win_rate</b> = odsetek zyskownych transakcji. <b>avg_return</b> = średni zwrot
na transakcję. <b>total_return (strategia)</b> = złożony zwrot ze wszystkich
transakcji sygnałowych. <b>buy_hold</b> = zwrot z samego kupienia i trzymania
przez cały okres, dla porównania. Wysoki win_rate NIE oznacza dobrej strategii —
strategia może wygrywać większość małych transakcji, a i tak przegrywać z rynkiem,
jeśli zbyt wcześnie wychodzi z pozycji i przegapia duże ruchy (dokładnie to
widać poniżej, jeśli total_return jest niższy niż buy_hold).
</p>
<table>
<tr><th>Ticker</th><th>Transakcje</th><th>Win rate %</th><th>Śr. zwrot %</th>
<th>Zwrot strategii %</th><th>Buy&amp;hold %</th></tr>
{bt_rows}
</table>

<h2>Kalkulator scenariuszy ryzyka</h2>
<p class="lead">
Wybierz instrument, kwotę i horyzont czasowy. Kalkulator przeliczy WSZYSTKIE
historyczne okresy o takiej długości w zebranych danych i pokaże rozrzut
wyników (nie jedną liczbę) — od najgorszego do najlepszego przypadku.
</p>
<div class="calc-box">
  <label for="calc-ticker">Instrument</label>
  <select id="calc-ticker">{ticker_options}</select>

  <label for="calc-amount">Kwota inwestycji</label>
  <input type="number" id="calc-amount" value="5000" min="1">

  <label for="calc-days">Horyzont (dni)</label>
  <input type="number" id="calc-days" value="30" min="1">

  <button onclick="runCalculator()">Oblicz scenariusze</button>

  <div id="calc-results"></div>
</div>
<div class="disclaimer">
⚠️ To nie jest prognoza ani porada inwestycyjna. Pokazuje wyłącznie rozkład
tego, co historycznie się zdarzało w podobnych oknach czasowych — przyszłość
może wyglądać inaczej, szczególnie przy kryzysie rynkowym lub istotnej
zmianie sytuacji spółki. Inwestuj tylko środki, których utratę możesz
przetrwać bez problemu.
</div>

<h2>Wykresy</h2>
{"".join(charts_html)}

<script>
const PRICE_DATA = {price_data_json};

function percentile(sortedArr, p) {{
  const idx = (p / 100) * (sortedArr.length - 1);
  const lo = Math.floor(idx), hi = Math.ceil(idx);
  if (lo === hi) return sortedArr[lo];
  return sortedArr[lo] + (sortedArr[hi] - sortedArr[lo]) * (idx - lo);
}}

function runCalculator() {{
  const ticker = document.getElementById('calc-ticker').value;
  const amount = parseFloat(document.getElementById('calc-amount').value);
  const days = parseInt(document.getElementById('calc-days').value);
  const resultsDiv = document.getElementById('calc-results');

  const data = PRICE_DATA[ticker];
  const closes = data.closes;

  if (closes.length <= days) {{
    resultsDiv.innerHTML = '<p style="color:#f44336">Za mało danych historycznych dla tego instrumentu i horyzontu.</p>';
    return;
  }}

  const returns = [];
  for (let i = days; i < closes.length; i++) {{
    const r = (closes[i] - closes[i - days]) / closes[i - days];
    returns.push(r);
  }}
  const sorted = [...returns].sort((a, b) => a - b);

  const scenarios = [
    {{p: 5, label: 'Bardzo pesymistyczny'}},
    {{p: 25, label: 'Pesymistyczny'}},
    {{p: 50, label: 'Środkowy (mediana)'}},
    {{p: 75, label: 'Optymistyczny'}},
    {{p: 95, label: 'Bardzo optymistyczny'}},
  ];

  let html = `<p style="color:#888; font-size:0.85em;">Na podstawie ${{returns.length}} historycznych okresów ${{days}}-dniowych</p>`;
  for (const s of scenarios) {{
    const ret = percentile(sorted, s.p);
    const finalAmount = amount * (1 + ret);
    const gainLoss = finalAmount - amount;
    const sign = gainLoss >= 0 ? '+' : '';
    const cls = gainLoss >= 0 ? 'pos' : 'neg';
    html += `<div class="scenario">
      <div class="label">${{s.label}}</div>
      <div class="${{cls}}">${{sign}}${{(ret*100).toFixed(1)}}% &nbsp;→&nbsp; ${{sign}}${{gainLoss.toFixed(2)}}
      (kapitał końcowy: ${{finalAmount.toFixed(2)}})</div>
    </div>`;
  }}

  const worst = (sorted[0] * 100).toFixed(1);
  const best = (sorted[sorted.length - 1] * 100).toFixed(1);
  const lossCount = returns.filter(r => r < 0).length;
  const lossPct = (lossCount / returns.length * 100).toFixed(1);
  html += `<p style="color:#888; font-size:0.85em; margin-top:12px;">
    Najgorszy historyczny wynik: ${{worst}}% &nbsp;|&nbsp; Najlepszy: ${{best}}% &nbsp;|&nbsp;
    Odsetek okresów ze stratą: ${{lossPct}}%</p>`;

  resultsDiv.innerHTML = html;
}}

// policz od razu dla domyślnych wartości
window.addEventListener('DOMContentLoaded', runCalculator);
</script>

</body>
</html>"""

    out_dir = Path("docs")
    out_dir.mkdir(exist_ok=True)
    (out_dir / "index.html").write_text(page, encoding="utf-8")
    print(f"Zapisano docs/index.html ({len(charts_html)} wykresów, {len(all_signals)} sygnałów, kalkulator dla {len(price_data)} instrumentów).")


if __name__ == "__main__":
    main()
