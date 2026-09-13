"""
Moduł liczenia wskaźników technicznych i generowania sygnałów
bez zewnętrznych bibliotek TA — czysty pandas, żeby nie zależeć
od niestabilnych paczek.
"""

import pandas as pd
import config


def compute_sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window).mean()


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Dodaje kolumny SMA20, SMA50, RSI14, avg_volume20 dla pojedynczego tickera."""
    df = df.sort_values("date").copy()
    df["sma_short"] = compute_sma(df["close"], config.SMA_SHORT)
    df["sma_long"] = compute_sma(df["close"], config.SMA_LONG)
    df["rsi"] = compute_rsi(df["close"], config.RSI_PERIOD)
    df["avg_volume20"] = df["volume"].rolling(window=20).mean()
    return df


def generate_signals(df: pd.DataFrame) -> list[dict]:
    """
    Analizuje ostatni wiersz danych (po dodaniu wskaźników) i zwraca
    listę sygnałów w formie słowników gotowych do wysłania jako alert.
    """
    signals = []
    if df.empty or len(df) < config.SMA_LONG:
        return signals

    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else last
    ticker = last["ticker"]
    market = last["market"]

    # Przecięcie SMA (złoty / śmierci krzyż uproszczony)
    if pd.notna(last["sma_short"]) and pd.notna(last["sma_long"]):
        crossed_up = prev["sma_short"] <= prev["sma_long"] and last["sma_short"] > last["sma_long"]
        crossed_down = prev["sma_short"] >= prev["sma_long"] and last["sma_short"] < last["sma_long"]
        if crossed_up:
            signals.append({
                "ticker": ticker, "market": market, "type": "SMA_CROSS_UP",
                "message": f"{ticker} ({market}): SMA{config.SMA_SHORT} przebiła SMA{config.SMA_LONG} od dołu — sygnał wzrostowy"
            })
        if crossed_down:
            signals.append({
                "ticker": ticker, "market": market, "type": "SMA_CROSS_DOWN",
                "message": f"{ticker} ({market}): SMA{config.SMA_SHORT} przebiła SMA{config.SMA_LONG} od góry — sygnał spadkowy"
            })

    # RSI — wykupienie / wyprzedanie
    if pd.notna(last["rsi"]):
        if last["rsi"] <= config.RSI_OVERSOLD:
            signals.append({
                "ticker": ticker, "market": market, "type": "RSI_OVERSOLD",
                "message": f"{ticker} ({market}): RSI={last['rsi']:.1f} — wyprzedanie, możliwe odbicie"
            })
        elif last["rsi"] >= config.RSI_OVERBOUGHT:
            signals.append({
                "ticker": ticker, "market": market, "type": "RSI_OVERBOUGHT",
                "message": f"{ticker} ({market}): RSI={last['rsi']:.1f} — wykupienie, ryzyko korekty"
            })

    # Skok wolumenu
    if pd.notna(last["avg_volume20"]) and last["avg_volume20"] > 0:
        ratio = last["volume"] / last["avg_volume20"]
        if ratio >= config.VOLUME_SPIKE_MULTIPLIER:
            signals.append({
                "ticker": ticker, "market": market, "type": "VOLUME_SPIKE",
                "message": f"{ticker} ({market}): wolumen {ratio:.1f}x średniej z 20 dni — wzmożone zainteresowanie"
            })

    return signals
