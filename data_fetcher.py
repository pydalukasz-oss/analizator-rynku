"""
Moduł pobierania danych rynkowych z trzech niezależnych źródeł.
Każda funkcja zwraca ustandaryzowany DataFrame z kolumnami:
date, open, high, low, close, volume
"""

import io
import time
import requests
import pandas as pd
import yfinance as yf

# Wiele darmowych API blokuje domyślny User-Agent biblioteki requests
# (rozpoznaje go jako bota). Udajemy zwykłą przeglądarkę.
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}


# ---------------------------------------------------------------------------
# GPW — dane EOD ze stooq.pl (darmowe, bez limitów, bez klucza API)
# ---------------------------------------------------------------------------
def fetch_gpw(ticker: str, days: int = 120) -> pd.DataFrame:
    """
    Pobiera dane dzienne dla spółki z GPW ze Stooq.
    ticker np. 'cdr' dla CD Projekt.
    """
    url = f"https://stooq.pl/q/d/l/?s={ticker}&i=d"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        df.columns = [c.lower() for c in df.columns]
        df = df.rename(columns={"data": "date", "otwarcie": "open",
                                 "najwyzszy": "high", "najnizszy": "low",
                                 "zamkniecie": "close", "wolumen": "volume"})
        df["date"] = pd.to_datetime(df["date"])
        df["ticker"] = ticker.upper()
        df["market"] = "GPW"
        return df.tail(days).reset_index(drop=True)
    except Exception as e:
        print(f"[GPW] Błąd pobierania {ticker}: {e}")
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# USA / rynki zagraniczne — Yahoo Finance przez yfinance
# ---------------------------------------------------------------------------
def fetch_us(ticker: str, days: int = 120) -> pd.DataFrame:
    """
    Pobiera dane dzienne dla spółki/ETF z Yahoo Finance.
    ticker np. 'AAPL'.
    """
    try:
        data = yf.Ticker(ticker).history(period=f"{days}d", interval="1d")
        if data.empty:
            return
