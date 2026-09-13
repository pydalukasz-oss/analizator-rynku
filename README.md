# Analizator rynków — MVP

Narzędzie pobiera dane z GPW (Stooq), rynków zagranicznych (Yahoo Finance)
i krypto (CoinGecko), liczy wskaźniki techniczne (SMA20/SMA50, RSI14,
skok wolumenu) i wypisuje sygnały.

## Uruchomienie lokalne

```bash
pip install -r requirements.txt
python main.py
```

Wynik: dane trafiają do pliku `market_data.db` (SQLite), a w konsoli
pojawiają się wygenerowane sygnały, np.:

```
[SMA_CROSS_UP] AAPL (US): SMA20 przebiła SMA50 od dołu — sygnał wzrostowy
[RSI_OVERSOLD] CDR (GPW): RSI=27.4 — wyprzedanie, możliwe odbicie
```

## Konfiguracja

Wszystkie śledzone instrumenty i progi wskaźników są w `config.py`.
Dodanie nowej spółki/krypto = dopisanie jednej linii w liście.

## Struktura plików

- `config.py` — lista instrumentów i parametry wskaźników
- `data_fetcher.py` — pobieranie danych z 3 źródeł (GPW/USA/krypto)
- `indicators.py` — SMA, RSI, skok wolumenu, generowanie sygnałów
- `main.py` — spina wszystko, zapisuje do bazy, wypisuje sygnały
- `market_data.db` — powstaje po pierwszym uruchomieniu (SQLite)

## Alerty na Telegram (już działa)

1. Napisz do `@BotFather` na Telegramie → `/newbot` → skopiuj token.
2. Napisz cokolwiek do nowo utworzonego bota (musi dostać pierwszą wiadomość).
3. Wejdź na `https://api.telegram.org/bot<TWÓJ_TOKEN>/getUpdates` i znajdź
   `"chat":{"id": ...}` — to Twój chat ID.
4. Ustaw zmienne środowiskowe przed uruchomieniem:

```bash
export TELEGRAM_BOT_TOKEN="1234567:ABC..."
export TELEGRAM_CHAT_ID="987654321"
python main.py
```

Bez tych zmiennych skrypt działa normalnie, tylko pomija wysyłkę i informuje o tym w konsoli.

## Automatyzacja przez GitHub Actions (już gotowa)

Workflow `.github/workflows/analiza-rynku.yml` uruchamia `main.py` co godzinę
w dni robocze (8:00-17:00 UTC), bez potrzeby posiadania serwera.

### Wdrożenie (5 minut)

1. Załóż nowe repozytorium na GitHubie (może być prywatne) i wrzuć do niego
   całą zawartość tego folderu (łącznie z `.github/`).
2. W repo: **Settings → Secrets and variables → Actions → New repository secret**
   i dodaj:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
3. Gotowe. Workflow sam odpali się według harmonogramu, albo ręcznie:
   zakładka **Actions → Analiza rynku → Run workflow**.

### Ważne ograniczenie

Każde uruchomienie w GitHub Actions startuje z czystego repo — plik
`market_data.db` NIE narasta automatycznie między uruchomieniami (trafia
tylko jako artefakt danego runu, do wglądu/pobrania przez 90 dni).
Jeśli zależy Ci na ciągłej historii cen w jednej bazie, dwie opcje:
- commituj `market_data.db` z powrotem do repo po każdym runie (prosty krok
  `git commit && push` na końcu workflow — mogę dopisać),
- albo przejdź na bazę zewnętrzną (np. Supabase/Postgres) zamiast SQLite.

## Dashboard (już gotowy)

```bash
streamlit run dashboard.py
```

Otwiera się w przeglądarce: wykres świecowy z SMA20/SMA50, wykres RSI,
lista aktywnych sygnałów dla wybranego instrumentu i zbiorcza tabela
sygnałów ze wszystkich śledzonych spółek/krypto. Wymaga uprzednio
zapełnionej bazy `market_data.db` (czyli chociaż jednego uruchomienia
`python main.py`).

## Backtesting (już gotowy)

```bash
python run_backtest.py                # domyślnie max 30 dni trzymania pozycji
python run_backtest.py --max-hold 45  # własny limit
```

Wymaga zebranej historii w `market_data.db` — im więcej danych, tym
wiarygodniejszy wynik (kilka-kilkanaście uruchomień `main.py` to za mało,
potrzeba tygodni/miesięcy zbierania danych albo jednorazowego pobrania
dłuższej historii).

Strategia testowana: wejście na SMA_CROSS_UP lub RSI_OVERSOLD, wyjście na
SMA_CROSS_DOWN, RSI_OVERBOUGHT lub po przekroczeniu `--max-hold` dni.
Model celowo uproszczony — bez prowizji i poślizgu cenowego — służy do
wstępnej oceny, czy reguły w ogóle mają sens, **nie** do dokładnej symulacji
realnych zysków.

Wynik pokazuje per instrument: liczbę transakcji, win rate, średni zwrot,
łączny zwrot strategii i zwrot z buy-and-hold dla porównania. Jeśli
strategia regularnie przegrywa z buy-and-hold — sygnały wymagają
przemyślenia progów w `config.py`, zanim zaczniesz na nich polegać.

## Kalkulator scenariuszy ryzyka (już gotowy)

```bash
python risk_calculator.py --ticker CDR --amount 5000 --days 30
```

Odpowiada na pytanie: *"gdybym historycznie wchodził na X dni w ten
instrument, jaki rozrzut wyników bym uzyskiwał?"* — na podstawie
rzeczywistych, zebranych danych (rolling window zwrotów N-dniowych),
nie teoretycznego modelu.

Zwraca 5 scenariuszy (bardzo pesymistyczny → bardzo optymistyczny) w
złotówkach i procentach, plus najgorszy/najlepszy historycznie
zaobserwowany wynik i odsetek okresów, które zakończyły się stratą.

**To nie jest prognoza.** To pokazuje, co się historycznie zdarzało w
podobnych oknach czasowych — przyszłość może wyglądać inaczej, zwłaszcza
przy kryzysie rynkowym albo istotnej zmianie sytuacji spółki. Im więcej
historii w `market_data.db`, tym wiarygodniejszy rozkład (potrzeba
tygodni/miesięcy zbierania danych albo jednorazowego doładowania dłuższej
historii, żeby liczby miały sens).

## Co dalej (kolejne fazy)

1. ~~Alerty na Telegram~~ ✅ gotowe.
2. ~~Automatyzacja (GitHub Actions)~~ ✅ gotowe.
3. ~~Dashboard (Streamlit)~~ ✅ gotowe.
4. ~~Backtesting~~ ✅ gotowe.
5. ~~Kalkulator scenariuszy ryzyka~~ ✅ gotowe.

## Uwaga

To narzędzie analityczne — nie jest doradztwem inwestycyjnym. Sygnały
techniczne bywają fałszywe, szczególnie bez backtestingu i kontekstu
fundamentalnego.
