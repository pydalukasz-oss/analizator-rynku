"""
Dashboard do przeglądania danych z market_data.db.

Uruchomienie:
    streamlit run dashboard.py
"""

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
from indicators import add_indicators, generate_signals

st.set_page_config(page_title="Analizator rynków", layout="wide")


@st.cache_data(ttl=300)
def load_data(db_path: str) -> pd.DataFrame:
    if not Path(db_path).exists():
        return pd.DataFrame()
    conn = sqlite3.connect(db_path)
    df = pd.read_sql("SELECT * FROM market_data", conn)
    conn.close()
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    df = df.drop_duplicates(subset=["ticker", "date"]).sort_values("date")
    return df


st.title("📊 Analizator rynków — GPW / USA / Krypto")

raw = load_data(config.DB_PATH)

if raw.empty:
    st.warning(
        "Brak danych w `market_data.db`. Uruchom najpierw `python main.py`, "
        "żeby pobrać dane, potem odśwież tę stronę."
    )
    st.stop()

# --- Panel boczny: wybór instrumentu ---
st.sidebar.header("Filtry")
markets = sorted(raw["market"].unique())
selected_market = st.sidebar.selectbox("Rynek", markets)

tickers_on_market = sorted(raw[raw["market"] == selected_market]["ticker"].unique())
selected_ticker = st.sidebar.selectbox("Instrument", tickers_on_market)

ticker_data = raw[
    (raw["market"] == selected_market) & (raw["ticker"] == selected_ticker)
].copy()
enriched = add_indicators(ticker_data)
signals = generate_signals(enriched)

# --- Główny wykres świecowy + SMA ---
col_chart, col_signals = st.columns([3, 1])

with col_chart:
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=enriched["date"], open=enriched["open"], high=enriched["high"],
        low=enriched["low"], close=enriched["close"], name=selected_ticker,
    ))
    fig.add_trace(go.Scatter(
        x=enriched["date"], y=enriched["sma_short"],
        name=f"SMA{config.SMA_SHORT}", line=dict(width=1.5),
    ))
    fig.add_trace(go.Scatter(
        x=enriched["date"], y=enriched["sma_long"],
        name=f"SMA{config.SMA_LONG}", line=dict(width=1.5),
    ))
    fig.update_layout(
        title=f"{selected_ticker} ({selected_market})",
        xaxis_rangeslider_visible=False,
        height=500,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)

    # RSI pod spodem
    fig_rsi = go.Figure()
    fig_rsi.add_trace(go.Scatter(x=enriched["date"], y=enriched["rsi"], name="RSI"))
    fig_rsi.add_hline(y=config.RSI_OVERBOUGHT, line_dash="dot", line_color="red")
    fig_rsi.add_hline(y=config.RSI_OVERSOLD, line_dash="dot", line_color="green")
    fig_rsi.update_layout(height=200, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_rsi, use_container_width=True)

with col_signals:
    st.subheader("Aktualne sygnały")
    if signals:
        for s in signals:
            st.info(s["message"])
    else:
        st.write("Brak aktywnych sygnałów dla tego instrumentu.")

    st.subheader("Ostatnie dane")
    last_row = enriched.iloc[-1]
    st.metric("Kurs zamknięcia", f"{last_row['close']:.2f}")
    st.metric("RSI", f"{last_row['rsi']:.1f}" if pd.notna(last_row["rsi"]) else "—")

# --- Zbiorcza tabela sygnałów ze wszystkich instrumentów ---
st.divider()
st.subheader("Sygnały ze wszystkich śledzonych instrumentów (ostatnie dane)")

all_rows = []
for (market, ticker), group in raw.groupby(["market", "ticker"]):
    enr = add_indicators(group)
    sig = generate_signals(enr)
    for s in sig:
        all_rows.append(s)

if all_rows:
    st.dataframe(pd.DataFrame(all_rows), use_container_width=True, hide_index=True)
else:
    st.write("Brak sygnałów na żadnym śledzonym instrumencie w tej chwili.")
