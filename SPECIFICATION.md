# СПЕЦИФИКАЦИЯ ПРОЕКТА pairs-trading-crypto

Дата: 19.09.2026
Репозиторий: https://github.com/gadotkach/pairs-trading-crypto (Public)
Локально: ~/pairs-trading-crypto/

---

## СТАТУС

- ✅ Базовая аналитика (ZigZag 5%/10%)
- ✅ Стратегия A/B (симуляция)
- ✅ Telegram-бот (уровни, коды, оплата Stars)
- ✅ run.yml — cron */30 (без TG)
- ✅ bot.yml — cron */10 (single poll)
- ⏳ Рассылка приоритетным (priority_report.py)
- ⏳ CryptoBot (Этап 2)
- ⏳ ЮKassa (Этап 3)

---

## СТРУКТУРА

pairs-trading-crypto/
- fetch_crypto.py            - HTX + Bybit
- z_analytics_crypto.py      - ZigZag 5%/10%, sminZ/smaxZ
- pairs_analysis_crypto.py   - стратегия A/B (SEND_TELEGRAM=False)
- tickers.py                 - BASE + EXTENDED
- finance_api.py             - CoinGecko
- subscription.py            - подписки, коды
- bot_handler.py             - Telegram-бот (~1300 строк)
- user_state.json            - per-user (users + redeem_codes)
- extended_tickers.json      - добавленные тикеры
- last_update_id.txt         - offset (обновляется Actions)
- state.json                 - глобальный
- .github/workflows/
  - run.yml                  - cron */30 (без TG)
  - bot.yml                  - cron */10 (single poll)

---

## ПАРАМЕТРЫ

- TICKERS: ADA, ICP, ETH, DOT, LINK, ZRO, AAVE, BTC, ATOM, NEAR, XCH, BNB, HBAR, TRX
- Периоды: 5/3/1 год
- INITIAL: $200
- Комиссия: 0.4%
- Фильтр ТОПа: Экстремумы >= 30 (5 -> 3 года)
- min_days: int(n_days * 0.8)
- SEND_TELEGRAM = False (аналитика через бота)

---

## БОТ

### Уровни
- basic: /pair (1 год), /keep (1 пара), /help
- priority: + /check, /find, /keep (20), /P
- superpriority: + /add, /period, /step, /strategy, /keep (inf)
- ssuperpriority: + /buy (2/мес)

### Команды
- /start — приветствие
- /P — меню уровней (3 inline-кнопки)
- /priority, /superpriority, /ssuperpriority — меню оплаты
- /gencode LEVEL [DAYS] — админ
- /activate USER_ID LEVEL [DAYS] — админ
- /codes — админ
- /redeem CODE — активировать

### Reply-меню (внизу)
📊 Данные | 🔍 Проверить
⭐ Приоритет | 📋 Статус
❓ Помощь

### Цены (Stars)
| Уровень | 1 мес | 1 год |
|---|---|---|
| Priority | 154 | 1478 |
| Superpriority | 770 | 7392 |
| SSuperpriority | 3846 | 36922 |

### Коды
- Формат: PRIO-2026-XXXX, SUPER-2026-XXXX, SS-2026-XXXX
- Срок: 30 дней
- Одноразовые
- Хранение: user_state.json (ключ redeem_codes)

### Технические
- offset: last_update_id.txt (в репо, обновляется Actions)
- bot.yml: cron */10, single poll
- run.yml: cron */30 (цены + аналитика, БЕЗ TG)
- 1 команда = 1 ответ (без дублей)

---

## РАСПИСАНИЕ

| Workflow | Cron | Что |
|---|---|---|
| run.yml | */30 | fetch_crypto + z_analytics + pairs_analysis (без TG) |
| bot.yml | */10 | bot_handler (опрос Telegram) |

---

## СЕКРЕТЫ GITHUB

- TG_TOKEN (бот)
- TG_CHAT = 380946555
- TG_PROXY = https://tg-proxy.shvaboe.workers.dev
- ADMIN_CHAT_ID = 380946555

---

## ВАЖНЫЕ ПРАВИЛА

1. INITIAL = 200
2. min_days = int(n_days * 0.8)
3. Фильтр: если Старт X = Финал X ИЛИ Старт Y = Финал Y -> исключить
4. Изменение, %: Финал X != 0 -> по X; Финал X = 0 -> по Y
5. Пары: BTC ETH (через пробел)
6. Ввод сделки: T1 P1 Q1 C1 T2 P2 Q2 C2
7. Кэш: date,close
8. Telegram: [CRYPTO] в начале
9. Админ-команды: ADMIN_CHAT_ID
10. Один ответ на команду (offset)
11. Аналитика — только через бота (без авто-рассылки)

---

## ОСТАЛОСЬ

1. priority_report.py — рассылка раз в день в 09:00 МСК
2. CryptoBot — Этап 2
3. ЮKassa — Этап 3

---

Последнее обновление: 19.09.2026
