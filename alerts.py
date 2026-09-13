"""
Wysyłka sygnałów jako wiadomości na Telegram przez Telegram Bot API.
Wymaga TELEGRAM_BOT_TOKEN i TELEGRAM_CHAT_ID ustawionych w zmiennych
środowiskowych (patrz komentarz w config.py, jak je zdobyć).
"""

import requests
import config


def send_telegram_message(text: str) -> bool:
    """Wysyła pojedynczą wiadomość tekstową na Telegram. Zwraca True/False."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("[Telegram] Brak TELEGRAM_BOT_TOKEN lub TELEGRAM_CHAT_ID — pomijam wysyłkę.")
        return False

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"[Telegram] Błąd wysyłki: {e}")
        return False


def send_signals(signals: list[dict]):
    """Wysyła listę sygnałów jako jedną zbiorczą wiadomość (żeby nie zalać czatu)."""
    if not signals:
        return

    lines = ["<b>📊 Nowe sygnały rynkowe</b>", ""]
    for s in signals:
        lines.append(f"• {s['message']}")

    text = "\n".join(lines)
    ok = send_telegram_message(text)
    if ok:
        print(f"[Telegram] Wysłano {len(signals)} sygnałów.")
