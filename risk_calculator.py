"""
Kalkulator scenariuszy zysku/straty oparty na HISTORYCZNEJ zmienności
danego instrumentu.

WAŻNE — czym to jest, a czym nie jest:
- To NIE jest prognoza przyszłej ceny. Nikt nie zna przyszłej ceny.
- To jest odpowiedź na pytanie: "gdybym w przeszłości wchodził losowo
  na X dni w ten instrument, jakie wyniki bym historycznie uzyskiwał?"
- Zakłada, że przyszła zmienność będzie z grubsza podobna do historycznej
  — to założenie bywa błędne (kryzysy, newsy, zmiana fundamentów spółki).

Metoda: rolling window historycznych zwrotów N-dniowych (bootstrap
z rzeczywistych danych, nie z modelu teoretycznego typu rozkład normalny).

Użycie:
    python risk_calculator.py --ticker CDR --amount 5000 --days 30
"""

import argparse
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

import config


def load_ticker_data(db_path: str, ticker: str) -> pd.DataFrame:
    if not Path(db_path).exists():
        raise FileNotFoundError(
            f"Nie znaleziono {db_path}. Uruchom najpierw `python main.py`, "
            "żeby zebrać dane historyczne."
        )
    conn = sqlite3.connect(db_path)
    df = pd.read_sql(
        "SELECT * FROM market_data WHERE ticker = ?", conn, params=(ticker.upper(),)
    )
    conn.close()
    if df.empty:
        raise ValueError(f"Brak danych dla {ticker} w bazie. Sprawdź config.py i uruchom main.py.")
    df["date"] = pd.to_datetime(df["date"])
    return df.drop_duplicates(subset="date").sort_values("date").reset_index(drop=True)


def historical_n_day_returns(df: pd.DataFrame, n_days: int) -> np.ndarray:
    """
    Liczy wszystkie historyczne zwroty procentowe dla okien N-dniowych
    (rolling), np. dla n_days=30: zwrot z każdego możliwego 30-dniowego
    okresu w dostępnej historii.
    """
    closes = df["close"].values
    if len(closes) <= n_days:
        return np.array([])
    returns = (closes[n_days:] - closes[:-n_days]) / closes[:-n_days]
    return returns


def calculate_scenarios(returns: np.ndarray, amount: float) -> dict:
    """Liczy percentyle historycznych zwrotów i przekłada je na kwoty."""
    if len(returns) == 0:
        return {}

    percentiles = [5, 25, 50, 75, 95]
    pct_values = np.percentile(returns, percentiles)

    scenarios = {}
    labels = {
        5: "Bardzo pesymistyczny (gorsze niż 95% historycznych przypadków)",
        25: "Pesymistyczny",
        50: "Środkowy (mediana historyczna)",
        75: "Optymistyczny",
        95: "Bardzo optymistyczny (lepsze niż 95% historycznych przypadków)",
    }
    for p, val in zip(percentiles, pct_values):
        result_amount = amount * (1 + val)
        scenarios[p] = {
            "label": labels[p],
            "return_pct": round(val * 100, 1),
            "final_amount": round(result_amount, 2),
            "gain_loss": round(result_amount - amount, 2),
        }

    scenarios["_meta"] = {
        "n_historical_windows": len(returns),
        "worst_observed_pct": round(float(returns.min()) * 100, 1),
        "best_observed_pct": round(float(returns.max()) * 100, 1),
        "prob_loss_pct": round(float((returns < 0).mean()) * 100, 1),
    }
    return scenarios


def print_report(ticker: str, amount: float, n_days: int, scenarios: dict):
    if not scenarios:
        print(f"Za mało danych historycznych dla {ticker}, żeby policzyć scenariusze "
              f"dla okresu {n_days} dni. Potrzeba więcej historii w market_data.db.")
        return

    meta = scenarios.pop("_meta")
    print(f"\n=== Scenariusze dla {ticker}: inwestycja {amount:.2f} na {n_days} dni ===")
    print(f"(na podstawie {meta['n_historical_windows']} historycznych okresów {n_days}-dniowych)\n")

    for p in [5, 25, 50, 75, 95]:
        s = scenarios[p]
        sign = "+" if s["gain_loss"] >= 0 else ""
        print(f"  {s['label']}:")
        print(f"    Zwrot: {sign}{s['return_pct']}%  →  {sign}{s['gain_loss']:.2f} "
              f"(kapitał końcowy: {s['final_amount']:.2f})")

    print(f"\nNajgorszy historyczny wynik w tym okresie: {meta['worst_observed_pct']}%")
    print(f"Najlepszy historyczny wynik w tym okresie: {meta['best_observed_pct']}%")
    print(f"Odsetek historycznych okresów ze stratą: {meta['prob_loss_pct']}%")
    print("\nUWAGA: to nie jest prognoza. To rozkład tego, co historycznie się zdarzało.")
    print("Przyszłość może wyglądać inaczej niż przeszłość — szczególnie w kryzysie")
    print("lub przy istotnej zmianie sytuacji spółki.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True, help="Ticker instrumentu, np. CDR, AAPL, BITCOIN")
    parser.add_argument("--amount", type=float, required=True, help="Kwota inwestycji")
    parser.add_argument("--days", type=int, default=30, help="Horyzont czasowy w dniach (domyślnie 30)")
    args = parser.parse_args()

    try:
        df = load_ticker_data(config.DB_PATH, args.ticker)
    except (FileNotFoundError, ValueError) as e:
        print(f"Błąd: {e}")
        return

    returns = historical_n_day_returns(df, args.days)
    scenarios = calculate_scenarios(returns, args.amount)
    print_report(args.ticker.upper(), args.amount, args.days, scenarios)


if __name__ == "__main__":
    main()
