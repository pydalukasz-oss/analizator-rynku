"""
JEDNORAZOWE doładowanie długiej historii (domyślnie ~2 lata) do market_data.db,
żeby backtest i kalkulator ryzyka miały wiarygodne dane od razu, zamiast
czekać tygodniami, aż main.py naturalnie zbierze historię dzień po dniu.

Uwaga: CoinGecko na darmowym planie ogranicza historyczne dane do ok. 365 dni
wstecz — dla krypto dostaniesz rok, nie dwa lata. To ograniczenie ich API,
nie da się tego obejść bez płatnego klucza.

Użycie:
    python backfill.py                # domyślnie 730 dni (GPW/USA), 365 (krypto)
    python backfill.py --days 500     # własna liczba dni dla GPW/USA
"""

import argparse
import sqlite3
from pathlib import Path

import pandas as pd

import config
from data_fetcher import fetch_all


def save_to_db(df: pd.DataFrame, db_path: str):
    df_to_save = df.copy()
    df_to_save["date"] = df_to_save["date"].astype(str)

    # WAŻNE: sprawdzamy istnienie pliku PRZED otwarciem połączenia —
    # samo sqlite3.connect() tworzy pusty plik, więc sprawdzenie "po"
    # zawsze zwracałoby True, nawet dla świeżo utworzonej, pustej bazy.
    file_exists = Path(db_path).exists()

    conn = sqlite3.connect(db_path)

    # Jeśli baza już istnieje i ma dane — dociągamy, usuwając ewentualne
    # duplikaty (ten sam ticker + data), żeby nie liczyć wskaźników
    # dwa razy na tych samych dniach.
    if file_exists:
        try:
            existing = pd.read_sql("SELECT * FROM market_data", conn)
        except Exception:
            # Plik istniał, ale bez tabeli market_data (np. pusty plik) —
            # traktujemy jak brak istniejących danych.
            existing = pd.DataFrame()

        if not existing.empty:
            combined = pd.concat([existing, df_to_save], ignore_index=True)
            combined = combined.drop_duplicates(subset=["ticker", "date"])
            combined.to_sql("market_data", conn, if_exists="replace", index=False)
            print(f"Baza istniała — po scaleniu: {len(combined)} wierszy (usunięto duplikaty).")
        else:
            df_to_save.to_sql("market_data", conn, if_exists="replace", index=False)
            print(f"Utworzono nową bazę: {len(df_to_save)} wierszy.")
    else:
        df_to_save.to_sql("market_data", conn, if_exists="replace", index=False)
        print(f"Utworzono nową bazę: {len(df_to_save)} wierszy.")

    conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=730,
                         help="Liczba dni historii dla GPW/USA (domyślnie 730 = ok. 2 lata). "
                              "Krypto i tak ograniczone do ok. 365 dni przez darmowe API CoinGecko.")
    args = parser.parse_args()

    print(f"=== Doładowanie historii: {args.days} dni dla GPW/USA ===")
    print("To może potrwać kilka minut (dużo danych, limity API).\n")

    raw = fetch_all(
        gpw_tickers=config.GPW_TICKERS,
        us_tickers=config.US_TICKERS,
        crypto_ids=config.CRYPTO_IDS,
        days=args.days,
    )

    if raw.empty:
        print("Nie udało się pobrać żadnych danych. Sprawdź połączenie internetowe.")
        return

    print(f"\nPobrano {len(raw)} wierszy dla {raw['ticker'].nunique()} instrumentów.")
    for ticker, group in raw.groupby("ticker"):
        print(f"  {ticker}: {len(group)} dni ({group['date'].min().date()} → {group['date'].max().date()})")

    save_to_db(raw, config.DB_PATH)
    print("\nGotowe. Teraz można uruchomić: python run_backtest.py lub python risk_calculator.py")


if __name__ == "__main__":
    main()
