"""
Generuje statyczną stronę HTML (docs/index.html) z wykresami, szczegółowymi
wyjaśnieniami metodologii, tabelą backtestu i interaktywnym kalkulatorem
scenariuszy ryzyka — do publikacji przez GitHub Pages.

To NIE jest działająca aplikacja/serwer jak Streamlit — to zwykła strona
internetowa. Kalkulator ryzyka liczy w przeglądarce (JavaScript), na
danych historycznych wbudowanych w stronę przy generowaniu.

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


SIGNAL_EXPLANATIONS = {
    "SMA_CROSS_UP": (
        "SMA (Simple Moving Average) to średnia cena zamknięcia z ostatnich N dni. "
        f"Mamy dwie: krótką (SMA{config.SMA_SHORT}, ostatnie {config.SMA_SHORT} dni) i długą "
        f"(SMA{config.SMA_LONG}, ostatnie {config.SMA_LONG} dni). Ten sygnał pojawia się, gdy "
        "krótka średnia PRZEBIJA długą OD DOŁU — czyli krótkoterminowa cena zaczyna rosnąć "
        "szybciej niż długoterminowy trend. Przykład: jeśli SMA20 wynosi 105 zł, a SMA50 wynosi "
        "103 zł, i wcześniej było odwrotnie — to jest właśnie ten sygnał. Bywa interpretowany "
        "jako początek trendu wzrostowego, ale to tylko wzorzec statystyczny, nie gwarancja."
    ),
    "SMA_CROSS_DOWN": (
        "To samo co wyżej, tylko w drugą stronę: krótka średnia (SMA{}) przebija długą "
        "(SMA{}) OD GÓRY, czyli krótkoterminowa cena zaczyna spadać szybciej niż długoterminowy "
        "trend. Bywa interpretowany jako początek trendu spadkowego."
    ).format(config.SMA_SHORT, config.SMA_LONG),
    "RSI_OVERSOLD": (
        f"RSI (Relative Strength Index) to wskaźnik od 0 do 100, liczony ze stosunku "
        f"średnich wzrostów do średnich spadków ceny z ostatnich {config.RSI_PERIOD} dni. "
        f"Poniżej {config.RSI_OVERSOLD} uznaje się instrument za \"wyprzedany\" — cena spadała "
        "ostatnio silnie i szybko. Przykład: RSI=25 oznacza, że w ostatnich dniach dominowały "
        "duże spadki nad wzrostami. Czasem poprzedza to odbicie (bo \"za dużo\" sprzedających), "
        "ale równie dobrze cena może dalej spadać — RSI nie zna przyszłości, tylko opisuje "
        "niedawną przeszłość."
    ),
    "RSI_OVERBOUGHT": (
        f"To samo co wyżej, tylko odwrotnie: RSI powyżej {config.RSI_OVERBOUGHT} oznacza "
        "instrument \"wykupiony\" — cena rosła ostatnio silnie i szybko. Czasem poprzedza to "
        "korektę, ale nie zawsze — silny trend wzrostowy potrafi utrzymywać wysokie RSI "
        "tygodniami."
    ),
    "VOLUME_SPIKE": (
        f"Wolumen to liczba akcji/jednostek, które zmieniły właściciela danego dnia. Ten "
        f"sygnał pojawia się, gdy dzienny wolumen jest ponad {config.VOLUME_SPIKE_MULTIPLIER}x "
        "wyższy niż średnia z ostatnich 20 dni. Oznacza to nietypowo duże zainteresowanie "
        "instrumentem — może to być reakcja na wiadomość, wynik finansowy, albo coś innego. "
        "Kierunek (wzrost czy spadek) nie jest tu określony, tylko sama intensywność obrotu."
    ),
}


def main():
    raw = load_data(config.DB_PATH)
    print(f"Wczytano {len(raw)} wierszy dla {raw['ticker'].nunique()} instrumentów.")

    charts_html = []
    all_signals = []
    price_data = {}

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

    if all_signals:
        signals_html = "".join(
            f"<li><b>[{s['type']}] {s['ticker']} ({s['market']})</b><br>"
            f"<span class='msg'>{s['message']}</span><br>"
            f"<span class='explain'>{SIGNAL_EXPLANATIONS.get(s['type'], '')}</span></li>"
            for s in all_signals
        )
    else:
        signals_html = (
            "<li>Brak aktywnych sygnałów w tej chwili. To normalne — sygnały pojawiają się "
            "tylko gdy cena/wolumen zachowują się nietypowo względem swojej niedawnej historii, "
            "co nie zdarza się codziennie dla każdego instrumentu.</li>"
        )

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
    beat_market = int((bt["total_return_pct"] > bt["buy_hold_return_pct"]).sum())
    total_with_trades = int((bt["n_trades"] > 0).sum())

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
         max-width: 1000px; margin: 0 auto; padding: 20px; line-height: 1.6; }}
  h1 {{ font-size: 1.8em; }}
  h2 {{ font-size: 1.35em; margin-top: 2.5em; border-top: 1px solid #333; padding-top: 1em; }}
  h3 {{ font-size: 1.1em; margin-top: 1.5em; color: #ccc; }}
  p.lead {{ color: #bbb; }}
  ul {{ background: #1a1d24; padding: 18px 24px; border-radius: 8px; list-style: none; }}
  ul li {{ margin-bottom: 18px; padding-bottom: 14px; border-bottom: 1px solid #2a2d34; }}
  ul li:last-child {{ border-bottom: none; margin-bottom: 0; }}
  .msg {{ color: #ddd; }}
  .explain {{ color: #999; font-size: 0.88em; display: block; margin-top: 6px; }}
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
  .example {{ background: #16261b; border: 1px solid #2e5138; padding: 14px 18px;
             border-radius: 8px; font-size: 0.92em; margin-top: 12px; }}
  code {{ background: #22252c; padding: 2px 6px; border-radius: 4px; }}
</style>
</head>
<body>

<h1>📊 Analizator rynków</h1>
<p class="lead">Automatyczna analiza GPW, rynków USA i (opcjonalnie) krypto —
wskaźniki techniczne, backtest strategii i kalkulator scenariuszy ryzyka.</p>
<p class="updated">Dane aktualizowane automatycznie przy każdym uruchomieniu workflow w GitHub Actions.</p>

<h2>1. Co tu w ogóle jest i skąd się bierze</h2>
<p>
Ta strona składa się z czterech części, w tej kolejności: <b>aktualne sygnały</b>
(co dzieje się teraz), <b>backtest</b> (czy te sygnały historycznie się sprawdzały),
<b>kalkulator ryzyka</b> (jaki rozrzut wyników dawała inwestycja w przeszłości) i
<b>wykresy</b> (surowe dane, żebyś mógł zweryfikować wszystko sam).
Dane pochodzą z trzech darmowych źródeł: GPW ze Stooq, rynki USA z Yahoo Finance,
krypto (opcjonalnie) z CoinGecko. Wszystko liczone jest automatycznie, bez
ingerencji człowieka — więc traktuj to jako punkt wyjścia do własnej analizy,
nie gotową odpowiedź.
</p>

<h2>2. Jak czytać wskaźniki techniczne</h2>
<h3>Średnie kroczące (SMA)</h3>
<p>
SMA{config.SMA_SHORT} to średnia cena zamknięcia z ostatnich {config.SMA_SHORT} dni,
SMA{config.SMA_LONG} — z ostatnich {config.SMA_LONG} dni. Krótsza średnia reaguje
szybciej na zmiany ceny, dłuższa wolniej. Kiedy się przecinają, traderzy technicy
uznają to za potencjalną zmianę trendu.
</p>
<div class="example">
<b>Przykład liczbowy:</b> jeśli ceny zamknięcia z ostatnich 5 dni to 100, 102, 101, 103, 104 zł,
to SMA5 = (100+102+101+103+104)/5 = 102 zł. To po prostu średnia arytmetyczna — nic bardziej
skomplikowanego.
</div>

<h3>RSI (Relative Strength Index)</h3>
<p>
Liczba od 0 do 100 opisująca, czy w ostatnich {config.RSI_PERIOD} dniach dominowały
wzrosty czy spadki ceny, i jak silnie. RSI blisko 100 = same silne wzrosty (rynek
"rozgrzany"), RSI blisko 0 = same silne spadki (rynek "wyprzedany"). Próg
{config.RSI_OVERSOLD} i {config.RSI_OVERBOUGHT} to umowne granice, po przekroczeniu
których mówi się o "wyprzedaniu" i "wykupieniu".
</p>

<h3>Wolumen</h3>
<p>
Liczba jednostek (akcji, kontraktów) wymienionych danego dnia. Nagły skok wolumenu
(u nas: ponad {config.VOLUME_SPIKE_MULTIPLIER}x średniej z 20 dni) oznacza, że
"coś się dzieje" — wzmożone zainteresowanie, niezależnie od kierunku ceny.
</p>

<h2>3. Aktualne sygnały</h2>
<p class="lead">
Poniżej lista instrumentów, które WŁAŚNIE TERAZ (na dzień ostatniego uruchomienia)
spełniają któryś z powyższych wzorców.
</p>
<ul>{signals_html}</ul>

<h2>4. Backtest — czy te sygnały historycznie biły rynek?</h2>
<p class="lead">
Backtest symuluje: "gdybym kupował za każdym razem, gdy pojawia się sygnał wejścia
(SMA_CROSS_UP lub RSI_OVERSOLD), i sprzedawał przy sygnale wyjścia (SMA_CROSS_DOWN,
RSI_OVERBOUGHT, albo po 30 dniach jeśli nic się nie wydarzy) — jak by mi poszło
w przeszłości?" To NIE uwzględnia prowizji maklerskich ani poślizgu cenowego —
służy do wstępnej oceny, nie do dokładnej symulacji zysków.
</p>
<h3>Jak czytać kolumny</h3>
<ul>
<li><b>Transakcje</b> — ile razy strategia kupiła i sprzedała w dostępnej historii.</li>
<li><b>Win rate %</b> — odsetek transakcji zakończonych na plusie. WAŻNE: wysoki win
rate nie oznacza dobrej strategii, jeśli pojedyncze straty są duże a zyski małe.</li>
<li><b>Śr. zwrot %</b> — średni wynik pojedynczej transakcji.</li>
<li><b>Zwrot strategii %</b> — złożony (nie prosty) zwrot ze wszystkich transakcji
razem, tak jakby każdy zysk/strata reinwestowały się w kolejną transakcję.</li>
<li><b>Buy&amp;hold %</b> — dla porównania: ile dałoby zwykłe kupienie na początku
dostępnej historii i trzymanie do końca, bez żadnych sygnałów.</li>
</ul>
<table>
<tr><th>Ticker</th><th>Transakcje</th><th>Win rate %</th><th>Śr. zwrot %</th>
<th>Zwrot strategii %</th><th>Buy&amp;hold %</th></tr>
{bt_rows}
</table>
<div class="example">
<b>Jak interpretować ten konkretny wynik:</b> strategia pobiła zwykłe kupienie-i-trzymanie
na {beat_market} z {total_with_trades} instrumentów z aktywnymi transakcjami. Jeśli ta
liczba jest niska (0 lub blisko zera) — oznacza to, że mechaniczne sygnały SMA/RSI
w obecnej konfiguracji progów, na tych konkretnych instrumentach, w tym okresie,
NIE dawały przewagi nad najprostszym możliwym podejściem (kup i trzymaj). To ważna,
uczciwa informacja — nie każda strategia techniczna działa, nawet jeśli "brzmi dobrze".
</div>

<h2>5. Kalkulator scenariuszy ryzyka</h2>
<p class="lead">
Wybierz instrument, kwotę i horyzont czasowy (liczbę dni). Kalkulator przeszuka
CAŁĄ dostępną historię cen tego instrumentu, znajdzie wszystkie okresy o wybranej
długości (np. wszystkie możliwe 30-dniowe okna), policzy zwrot procentowy w każdym
z nich, i pokaże Ci rozkład tych wyników — od najgorszego do najlepszego przypadku,
zamiast jednej "prognozowanej" liczby.
</p>
<div class="example">
<b>Przykład interpretacji:</b> jeśli dla kwoty 5000 zł i 30 dni kalkulator pokaże
scenariusz "pesymistyczny: -10%" i "optymistyczny: +12%", to znaczy: w historycznych
danych, spośród wszystkich możliwych 30-dniowych okresów, 25% z nich zakończyło się
wynikiem gorszym niż -10%, a 25% lepszym niż +12%. To NIE są granice tego, co może
się zdarzyć w przyszłości — mogą się zdarzyć wyniki jeszcze gorsze lub lepsze,
zwłaszcza w nietypowych warunkach rynkowych (krach, hossa, nagła wiadomość o spółce).
</div>
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
⚠️ <b>To nie jest prognoza ani porada inwestycyjna.</b> Pokazuje wyłącznie rozkład
tego, co historycznie się zdarzało w podobnych oknach czasowych — przyszłość może
wyglądać zupełnie inaczej, szczególnie przy kryzysie rynkowym, zmianie stóp
procentowych, czy istotnej zmianie sytuacji samej spółki (np. wyniki finansowe,
zmiana zarządu, skandal). Żadna analiza techniczna nie zna przyszłości. Inwestuj
tylko środki, których utratę możesz przetrwać bez problemu, i rozważ konsultację
z licencjonowanym doradcą finansowym przed podjęciem decyzji.
</div>

<h2>6. Wykresy — surowe dane do własnej weryfikacji</h2>
<p class="lead">
Świece pokazują dzienne otwarcie/maksimum/minimum/zamknięcie. Linie to SMA{config.SMA_SHORT}
i SMA{config.SMA_LONG}. Pod spodem RSI z zaznaczonymi progami {config.RSI_OVERSOLD} i
{config.RSI_OVERBOUGHT}. Najedź kursorem na wykres, żeby zobaczyć dokładne wartości
dla konkretnego dnia.
</p>
{"".join(charts_html)}

<h2>7. Podsumowanie i uwagi końcowe</h2>
<p class="lead">
Ten dashboard to narzędzie analityczne, zbudowane na darmowych, publicznie dostępnych
danych, z prostymi, mechanicznymi regułami sygnałowymi. Nie jest to system tradingowy
gotowy do ślepego naśladowania — to punkt wyjścia do własnego myślenia. Warto traktować
sygnały jako "coś się dzieje, sprawdź dlaczego", a nie "kup/sprzedaj teraz". Backtest
pokazuje, że proste reguły SMA/RSI nie zawsze biją rynek — to normalne i oczekiwane,
większość prostych strategii technicznych nie daje trwałej przewagi bez dodatkowego
kontekstu (fundamenty spółki, sytuacja makroekonomiczna, zarządzanie ryzykiem pozycji).
</p>

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
    {{p: 5, label: 'Bardzo pesymistyczny (gorsze niż 95% historycznych przypadków)'}},
    {{p: 25, label: 'Pesymistyczny'}},
    {{p: 50, label: 'Środkowy (mediana historyczna)'}},
    {{p: 75, label: 'Optymistyczny'}},
    {{p: 95, label: 'Bardzo optymistyczny (lepsze niż 95% historycznych przypadków)'}},
  ];

  let html = `<p style="color:#888; font-size:0.85em;">Na podstawie ${{returns.length}} historycznych okresów ${{days}}-dniowych dla ${{ticker}}</p>`;
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
    Najgorszy historyczny wynik w tym okresie: ${{worst}}% &nbsp;|&nbsp; Najlepszy: ${{best}}% &nbsp;|&nbsp;
    Odsetek historycznych okresów ze stratą: ${{lossPct}}%</p>`;

  resultsDiv.innerHTML = html;
}}

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
