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

# --- Telegram (alerty) ---
# 1. Napisz do @BotFather na Telegramie, komenda /newbot, skopiuj token.
# 2. Napisz cokolwiek do swojego nowego bota (musi dostać pierwszą wiadomość).
# 3. Wejdź na https://api.telegram.org/bot<TWÓJ_TOKEN>/getUpdates
#    i znajdź "chat":{"id": ...} — to Twój TELEGRAM_CHAT_ID.
# Oba pola najlepiej trzymać w zmiennych środowiskowych, nie na sztywno w kodzie.
import os

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
