# СПЕЦИФИКАЦИЯ ПРОЕКТА pairs-trading-crypto

Дата: 19.09.2026
Репозиторий: https://github.com/gadotkach/pairs-trading-crypto (Public)
Локально: ~/pairs-trading-crypto/

---

## ЦЕЛЬ

Парный трейдинг криптовалют (стратегия 6). Анализ пар, симуляция A/B, Telegram-бот с уровнями, GitHub Actions.

---

## СТРУКТУРА

pairs-trading-crypto/
- .github/workflows/run.yml      - cron 0 * * * *
- .github/workflows/bot.yml      - cron */10 [TODO]
- cache/                         - 14 CSV (date,close)
- analytics_z.xlsx               - 4 листа
- pair_strategies_analysis.xlsx  - 6 листов
- state.json                     - глобальный
- user_state.json                - [TODO]
- extended_tickers.json          - [TODO]
- coingecko_cache.json           - [TODO]
- fetch_crypto.py                - HTX + Bybit
- z_analytics_crypto.py          - ZigZag (нужно sminZ/smaxZ)
- pairs_analysis_crypto.py       - стратегия A/B
- tickers.py                     - [TODO]
- finance_api.py                 - CoinGecko [TODO]
- bot_handler.py                 - [TODO]
- priority_report.py             - [TODO]

---

## ПАРАМЕТРЫ

TICKERS: ADA, ICP, ETH, DOT, LINK, ZRO, AAVE, BTC, ATOM, NEAR, XCH, BNB, HBAR, TRX
Пар: 91
Периоды: 5/3/1 год (ZRO - только 1 год)
STEP: 5%
INITIAL: 200
Комиссия: 0.4%
Налог: 0%
Плечо: 1x
Фильтр ТОПа: Экстремумы >= 30 (5 -> 3 года)
min_days: int(n_days * 0.8)

---

## УРОВНИ ПОЛЬЗОВАТЕЛЕЙ

basic: /start /help /status /pair (1 год) /keep (1)
priority: + /check /find (до 10) /keep (20) /pair (5/3/1) рассылка 20
superpriority: + /add /period /step /strategy /keep (inf) EXTENDED
ssuperpriority: + /buy (2/мес)

Активация: /priority /superpriority /ssuperpriority CODE

---

## ФОРМАТЫ

Ввод сделки: DOT 1.1316 44.3566 0.10038 XCH 1.5045 33.2957 0.0665
8 полей: T1 P1 Q1 C1 T2 P2 Q2 C2. Проверка 0.5%.

Пары: BTC ETH (пробел). Несколько: SOL ADA BTC ETH.

---

## API

HTX: api.huobi.pro/market/history/kline (2000 свечей)
Bybit: api.bybit.com/v5/market/kline (1000, пагинация)
CoinGecko: api.coingecko.com/api/v3/coins/list (кэш 24ч)

---

## ВАЖНЫЕ ПРАВИЛА

1. INITIAL = 200
2. min_days = int(n_days * 0.8)
3. Фильтр: если Старт X = Финал X ИЛИ Старт Y = Финал Y -> исключить
4. Изменение, %: Финал X != 0 -> по X; Финал X = 0 -> по Y
5. Пары: BTC ETH (пробел)
6. Ввод: T1 P1 Q1 C1 T2 P2 Q2 C2
7. Кэш: date,close
8. Telegram: [CRYPTO] в начале

---

## СЕКРЕТЫ GitHub

TG_TOKEN, TG_CHAT, TG_PROXY
PRIORITY_CODE, SUPERPRIORITY_CODE, SSUPERPRIORITY_CODE
ADMIN_CHAT_ID

---

Последнее обновление: 19.09.2026
