"""
Główny skrypt: pobiera dane z GPW / USA / krypto, liczy wskaźniki,
generuje sygnały i zapisuje wszystko do lokalnej bazy SQLite.

Uruchomienie:
    python main.py

Docelowo ten skrypt ma być odpalany cyklicznie (cron / Make.com / Task Scheduler).
"""

import sqlite3
import pandas as pd

import config
from data_fetcher import fetch_all
from indicators import add_indicators, generate_signals
from alerts import send_signals


def save_to_db(df: pd.DataFrame, db_path: str):
    conn = sqlite3.connect(db_path)
    df_to_save = df.copy()
    df_to_save["date"] = df_to_save["date"].astype(str)
    df_to_save.to_sql("market_data", conn, if_exists="append", index=False)
    conn.close()


def run():
    print("=== Pobieranie danych ===")
    raw = fetch_all(
        gpw_tickers=config.GPW_TICKERS,
        us_tickers=config.US_TICKERS,
        crypto_ids=config.CRYPTO_IDS,
        days=120,
    )

    if raw.empty:
        print("Brak danych — sprawdź połączenie lub źródła.")
        return

    print(f"Pobrano {len(raw)} wierszy dla {raw['ticker'].nunique()} instrumentów.\n")

    print("=== Zapis do bazy (market_data.db) ===")
    save_to_db(raw, config.DB_PATH)

    print("\n=== Analiza i sygnały ===")
    all_signals = []
    for ticker, group in raw.groupby("ticker"):
        enriched = add_indicators(group)
        signals = generate_signals(enriched)
        all_signals.extend(signals)

    if not all_signals:
        print("Brak sygnałów w tej turze.")
    else:
        for s in all_signals:
            print(f"[{s['type']}] {s['message']}")
        send_signals(all_signals)

    return all_signals


if __name__ == "__main__":
    run()
