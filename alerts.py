
"""
Wysyłka sygnałów mailem przez SMTP (domyślnie skonfigurowane pod Gmail).
Wymaga EMAIL_ADDRESS, EMAIL_PASSWORD (hasło aplikacji!) i EMAIL_TO
ustawionych w zmiennych środowiskowych — patrz komentarz w config.py.
"""

import smtplib
from email.mime.text import MIMEText

import config


def send_email(subject: str, body: str) -> bool:
    """Wysyła pojedynczego maila. Zwraca True/False."""
    if not config.EMAIL_ADDRESS or not config.EMAIL_PASSWORD or not config.EMAIL_TO:
        print("[Email] Brak EMAIL_ADDRESS/EMAIL_PASSWORD/EMAIL_TO — pomijam wysyłkę.")
        return False

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = config.EMAIL_ADDRESS
    msg["To"] = config.EMAIL_TO

    try:
        with smtplib.SMTP(config.EMAIL_SMTP_HOST, config.EMAIL_SMTP_PORT) as server:
            server.starttls()
            server.login(config.EMAIL_ADDRESS, config.EMAIL_PASSWORD)
            server.sendmail(config.EMAIL_ADDRESS, [config.EMAIL_TO], msg.as_string())
        return True
    except Exception as e:
        print(f"[Email] Błąd wysyłki: {e}")
        return False


def send_signals(signals: list[dict]):
    """Wysyła listę sygnałów jako jednego zbiorczego maila."""
    if not signals:
        return

    lines = [f"• {s['message']}" for s in signals]
    body = "Nowe sygnały rynkowe:\n\n" + "\n".join(lines)
    subject = f"📊 Analizator rynków — {len(signals)} nowych sygnałów"

    ok = send_email(subject, body)
    if ok:
        print(f"[Email] Wysłano {len(signals)} sygnałów.")
