"""
Konfiguracja narzędzia do analizy rynków.
Tu dodajesz/usuwasz instrumenty, które ma śledzić program.
"""

# --- GPW (dane z stooq.pl, EOD - koniec dnia poprzedniej sesji) ---
GPW_TICKERS = [
    "cdr",   # CD Projekt
    "pkn",   # Orlen
    "pko",   # PKO BP
    "kgh",   # KGHM
    "alr",   # Allegro
]

# --- Rynki zagraniczne (dane z Yahoo Finance przez yfinance) ---
US_TICKERS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "SPY",   # ETF na S&P 500
]

# --- Krypto (dane z CoinGecko, darmowe API, bez klucza) ---
CRYPTO_IDS = [
    "bitcoin",
    "ethereum",
    "solana",
]

# --- Parametry wskaźników technicznych ---
SMA_SHORT = 20
SMA_LONG = 50
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
VOLUME_SPIKE_MULTIPLIER = 2.0  # sygnał gdy wolumen > 2x średniej z 20 dni

# --- Baza danych ---
DB_PATH = "market_data.db"

# --- E-mail (alerty) ---
# Jeśli używasz Gmaila:
# 1. Włącz weryfikację dwuetapową na koncie Google (jeśli jeszcze nie masz).
# 2. Wejdź na https://myaccount.google.com/apppasswords i wygeneruj "hasło aplikacji".
# 3. Użyj TEGO hasła (nie swojego zwykłego hasła do Gmaila) jako EMAIL_PASSWORD.
import os

EMAIL_SMTP_HOST = os.environ.get("EMAIL_SMTP_HOST", "smtp.gmail.com")
EMAIL_SMTP_PORT = int(os.environ.get("EMAIL_SMTP_PORT", "587"))
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS", "")      # np. twoj.mail@gmail.com
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")    # hasło aplikacji, nie zwykłe hasło
EMAIL_TO = os.environ.get("EMAIL_TO", "")                # gdzie wysyłać alerty (może być ten sam adres)
