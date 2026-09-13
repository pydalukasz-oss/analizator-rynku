"""
Uruchamia backtesting reguł sygnałowych na danych już zebranych
w market_data.db (czyli po wcześniejszych uruchomieniach main.py —
im więcej historii, tym wiarygodniejszy wynik).

Użycie:
    python run_backtest.py
    python run_backtest.py --max-hold 45
"""

import argparse
import sqlite3
from pathlib import Path

import pandas as pd

import config
from backtest import backtest_all, backtest_ticker


def load_data(db_path: str) -> pd.DataFrame:
    if not Path(db_path).exists():
        raise FileNotFoundError(
            f"Nie znaleziono {db_path}. Uruchom najpierw `python main.py`, "
            "żeby zebrać dane historyczne."
        )
    conn = sqlite3.connect(db_path)
    df = pd.read_sql("SELECT * FROM market_data", conn)
    conn.close()
    df["date"] = pd.to_datetime(df["date"])
    return df.drop_duplicates(subset=["ticker", "date"]).sort_values("date")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-hold", type=int, default=30,
                         help="Maksymalna liczba dni trzymania pozycji, jeśli nie ma sygnału wyjścia.")
    args = parser.parse_args()

    try:
        raw = load_data(config.DB_PATH)
    except FileNotFoundError as e:
        print(f"Błąd: {e}")
        return

    print(f"Wczytano {len(raw)} wierszy dla {raw['ticker'].nunique()} instrumentów.\n")

    summary = backtest_all(raw, max_hold_days=args.max_hold)
    print("=== Podsumowanie backtestu (posortowane po zwrocie strategii) ===")
    print(summary.to_string(index=False))

    print("\n=== Wnioski ===")
    beat_market = (summary["total_return_pct"] > summary["buy_hold_return_pct"]).sum()
    total = summary["n_trades"].gt(0).sum()
    print(f"Strategia pobiła buy-and-hold na {beat_market}/{total} instrumentach z aktywnymi transakcjami.")
    avg_win_rate = summary["win_rate_pct"].mean()
    if pd.notna(avg_win_rate):
        print(f"Średni win rate: {avg_win_rate:.1f}%")


if __name__ == "__main__":
    main()
