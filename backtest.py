"""
Backtesting reguł sygnałowych z indicators.py na danych historycznych.

Strategia uproszczona (long-only):
- wejście w pozycję: SMA_CROSS_UP lub RSI_OVERSOLD
- wyjście z pozycji: SMA_CROSS_DOWN, RSI_OVERBOUGHT, lub po max_hold_days
  (żeby nie trzymać pozycji w nieskończoność, jeśli nie ma sygnału wyjścia)

To celowo prosty model bez uwzględnienia prowizji/poślizgu cenowego —
służy do wstępnej oceny, czy reguły w ogóle mają sens, nie do realnej
symulacji zysków.
"""

import pandas as pd
import config
from indicators import add_indicators


def backtest_ticker(df: pd.DataFrame, max_hold_days: int = 30) -> dict:
    """
    Przechodzi dzień po dniu przez historię jednego instrumentu i symuluje
    transakcje według reguł wejścia/wyjścia. Zwraca statystyki strategii
    oraz porównanie z buy-and-hold.
    """
    enriched = add_indicators(df).reset_index(drop=True)
    enriched["sma_cross_up"] = (
        (enriched["sma_short"] > enriched["sma_long"])
        & (enriched["sma_short"].shift(1) <= enriched["sma_long"].shift(1))
    )
    enriched["sma_cross_down"] = (
        (enriched["sma_short"] < enriched["sma_long"])
        & (enriched["sma_short"].shift(1) >= enriched["sma_long"].shift(1))
    )

    trades = []
    in_position = False
    entry_price = None
    entry_idx = None

    for i in range(len(enriched)):
        row = enriched.iloc[i]

        if not in_position:
            entry_signal = bool(row["sma_cross_up"]) or (
                pd.notna(row["rsi"]) and row["rsi"] <= config.RSI_OVERSOLD
            )
            if entry_signal:
                in_position = True
                entry_price = row["close"]
                entry_idx = i
        else:
            days_held = i - entry_idx
            exit_signal = bool(row["sma_cross_down"]) or (
                pd.notna(row["rsi"]) and row["rsi"] >= config.RSI_OVERBOUGHT
            )
            if exit_signal or days_held >= max_hold_days or i == len(enriched) - 1:
                exit_price = row["close"]
                ret_pct = (exit_price - entry_price) / entry_price * 100
                trades.append({
                    "entry_date": str(enriched.iloc[entry_idx]["date"].date()),
                    "exit_date": str(row["date"].date()),
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(exit_price, 2),
                    "return_pct": round(ret_pct, 2),
                    "days_held": days_held,
                })
                in_position = False
                entry_price = None
                entry_idx = None

    if not trades:
        return {
            "ticker": df["ticker"].iloc[0] if not df.empty else "?",
            "n_trades": 0,
            "win_rate_pct": None,
            "avg_return_pct": None,
            "total_return_pct": None,
            "buy_hold_return_pct": None,
            "trades": [],
        }

    trades_df = pd.DataFrame(trades)
    wins = (trades_df["return_pct"] > 0).sum()
    win_rate = wins / len(trades_df) * 100

    # łączny zwrot strategii = złożenie zwrotów kolejnych transakcji
    compounded = (1 + trades_df["return_pct"] / 100).prod() - 1

    first_close = enriched["close"].iloc[0]
    last_close = enriched["close"].iloc[-1]
    buy_hold_return = (last_close - first_close) / first_close * 100

    return {
        "ticker": df["ticker"].iloc[0],
        "n_trades": len(trades_df),
        "win_rate_pct": round(win_rate, 1),
        "avg_return_pct": round(trades_df["return_pct"].mean(), 2),
        "total_return_pct": round(compounded * 100, 2),
        "buy_hold_return_pct": round(buy_hold_return, 2),
        "trades": trades,
    }


def backtest_all(raw: pd.DataFrame, max_hold_days: int = 30) -> pd.DataFrame:
    """Uruchamia backtest dla każdego instrumentu w danych i zwraca zbiorczą tabelę wyników."""
    results = []
    for ticker, group in raw.groupby("ticker"):
        res = backtest_ticker(group, max_hold_days=max_hold_days)
        res.pop("trades", None)  # do zbiorczej tabeli nie wrzucamy szczegółów transakcji
        results.append(res)
    return pd.DataFrame(results).sort_values("total_return_pct", ascending=False, na_position="last")
