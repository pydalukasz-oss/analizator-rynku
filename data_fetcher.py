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

import config

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
        if "date" not in df.columns:
            # Stooq czasem zwraca stronę błędu/limitu zamiast CSV z danymi —
            # wtedy kolumny są inne niż oczekiwane. Pokazujemy surową
            # odpowiedź, żeby było wiadomo co faktycznie przyszło.
            print(f"[GPW] {ticker}: nieoczekiwana odpowiedź (brak kolumny 'date'). "
                  f"Kolumny: {list(df.columns)}. Początek odpowiedzi: {resp.text[:200]!r}")
            return pd.DataFrame()
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
            return pd.DataFrame()
        data = data.reset_index()
        data.columns = [c.lower() for c in data.columns]
        data = data.rename(columns={"date": "date"})
        # Yahoo Finance zwraca daty ze strefą czasową (np. America/New_York),
        # a pozostałe źródła (Stooq, CoinGecko) — bez strefy. Ujednolicamy
        # do "naiwnych" dat, inaczej mieszanie danych z różnych rynków
        # wywala pd.to_datetime błędem "Mixed timezones detected".
        if isinstance(data["date"].dtype, pd.DatetimeTZDtype):
            data["date"] = data["date"].dt.tz_localize(None)
        data["ticker"] = ticker.upper()
        data["market"] = "US"
        return data[["date", "open", "high", "low", "close", "volume", "ticker", "market"]]
    except Exception as e:
        print(f"[US] Błąd pobierania {ticker}: {e}")
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# Krypto — CoinGecko (darmowe API, bez klucza, limit ~10-30 zapytań/min)
# ---------------------------------------------------------------------------
def fetch_crypto(coin_id: str, days: int = 120) -> pd.DataFrame:
    """
    Pobiera dane dzienne dla kryptowaluty z CoinGecko.
    coin_id np. 'bitcoin'.
    """
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": "usd", "days": days, "interval": "daily"}
    headers = dict(HEADERS)
    if config.COINGECKO_API_KEY:
        headers["x-cg-demo-api-key"] = config.COINGECKO_API_KEY
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        if resp.status_code == 401:
            print(f"[CRYPTO] {coin_id}: CoinGecko wymaga teraz darmowego klucza API "
                  f"nawet do podstawowego dostępu (zmiana zasad z ich strony). "
                  f"Pomijam — patrz README, sekcja o kluczu CoinGecko.")
            return pd.DataFrame()
        resp.raise_for_status()
        raw = resp.json()
        prices = raw.get("prices", [])
        volumes = raw.get("total_volumes", [])
        if not prices:
            return pd.DataFrame()

        df = pd.DataFrame(prices, columns=["ts", "close"])
        vol_df = pd.DataFrame(volumes, columns=["ts", "volume"])
        df["volume"] = vol_df["volume"]
        df["date"] = pd.to_datetime(df["ts"], unit="ms").dt.normalize()

        # CoinGecko nie daje OHLC w tym endponcie — przybliżamy open/high/low
        # przesuniętym close, żeby zachować spójny format z resztą źródeł.
        df["open"] = df["close"].shift(1).fillna(df["close"])
        df["high"] = df[["open", "close"]].max(axis=1)
        df["low"] = df[["open", "close"]].min(axis=1)
        df["ticker"] = coin_id.upper()
        df["market"] = "CRYPTO"
        return df[["date", "open", "high", "low", "close", "volume", "ticker", "market"]]
    except Exception as e:
        print(f"[CRYPTO] Błąd pobierania {coin_id}: {e}")
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# Zbiorcze pobranie wszystkich rynków naraz
# ---------------------------------------------------------------------------
def fetch_all(gpw_tickers, us_tickers, crypto_ids, days: int = 120) -> pd.DataFrame:
    frames = []

    for t in gpw_tickers:
        frames.append(fetch_gpw(t, days))
        time.sleep(1.0)  # uprzejmość wobec darmowego API, zmniejsza ryzyko limitowania

    for t in us_tickers:
        frames.append(fetch_us(t, days))
        time.sleep(0.3)

    for c in crypto_ids:
        frames.append(fetch_crypto(c, days))
        time.sleep(1.2)  # CoinGecko ma niski darmowy limit zapytań/min

    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)
