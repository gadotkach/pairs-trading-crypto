# СПЕЦИФИКАЦИЯ ПРОЕКТА pairs-trading-crypto

Дата: 19.09.2026
Репозиторий: https://github.com/gadotkach/pairs-trading-crypto (Public)
Локально: ~/pairs-trading-crypto/

---

## СТАТУС

- ✅ Базовая аналитика (ZigZag 5%/10%)
- ✅ Стратегия A/B (симуляция)
- ✅ Telegram-бот (4 уровня, команды, оплата Stars)
- ✅ Per-pair настройки (step, strategy, period)
- ✅ Ежедневная рассылка (учитывает per-pair)
- ✅ run.yml (cron */30)
- ✅ bot.yml (cron */10)
- ✅ daily_report.yml (09:00 МСК)
- ⏳ CryptoBot (Этап 2)
- ⏳ ЮKassa (Этап 3)

---

## РАСПИСАНИЕ

| Workflow | Cron | Что делает |
|---|---|---|
| run.yml | */30 | fetch_crypto + z_analytics + pairs_analysis (без TG) |
| bot.yml | */10 | bot_handler (опрос Telegram) |
| daily_report.yml | 0 6 * * * | priority_report (09:00 МСК) |

---

## БОТ (команды)

### Базовые
- /start — приветствие
- /help — справка (кратко + подробно)
- /status — статус + стратегии
- /pair BTC ETH — данные по паре
- /trade T1 P1 Q1 C1 T2 P2 Q2 C2 — ввод сделки + подписка

### Priority+
- /filter — мои пары (STEP/STRATEGY/PERIOD)
- /check BTC ETH — разовый анализ
- /find BTC — найди пару ТОП-5
- /keep BTC ETH — фильтр
- /clear — сбросить все
- /clear BTC SOL — удалить пару
- /remove BTC ETH — удалить из рассылки

### Superpriority+
- /add BTC NEWCOIN — добавить пару
- /step BTC ETH 12 — шаг для пары
- /strategy BTC ETH A — стратегия (A/B/AB)
- /period BTC ETH 1y — период (1y/365d/даты)

### SSuperpriority
- /buy BTC — цена входа (2/мес)

### Админ
- /gencode LEVEL [DAYS] — создать код (days=0 = ∞)
- /activate USER_ID LEVEL [DAYS] — прямая активация
- /codes — список кодов

### Оплата
- /P — меню уровней
- /priority — меню оплаты
- /superpriority — меню оплаты
- /ssuperpriority — меню оплаты
- /redeem CODE — активация по коду

### Reply-меню (внизу)
📊 Данные | 🔍 Проверить
⭐ Приоритет | 📋 Статус
❓ Помощь

---

## ЦЕНЫ (Stars)

| Уровень | 1 мес | 1 год |
|---|---|---|
| Priority | 154 | 1478 |
| Superpriority | 770 | 7392 |
| SSuperpriority | 3846 | 36922 |

---

## КОДЫ

- Формат: PRIO-2026-XXXX, SUPER-2026-XXXX, SS-2026-XXXX
- Срок: 30 дней (бессрочные — days=0 → 2999-12-31)
- Одноразовые
- Хранение: user_state.json (redeem_codes)

---

## ПАРАМЕТРЫ

- TICKERS: ADA, ICP, ETH, DOT, LINK, ZRO, AAVE, BTC, ATOM, NEAR, XCH, BNB, HBAR, TRX
- Периоды: 5/3/1 год
- INITIAL: $200
- Комиссия: 0.4%
- Фильтр ТОПа: Экстремумы >= 30 (5 -> 3 года)
- min_days: int(n_days * 0.8)
- SEND_TELEGRAM = False (аналитика через бота)
- Per-pair: step, strategy, period

---

## СЕКРЕТЫ GITHUB

- TG_TOKEN, TG_CHAT, TG_PROXY
- ADMIN_CHAT_ID = 380946555

---

## ВАЖНЫЕ ПРАВИЛА

1. INITIAL = 200, комиссия 0.4%
2. min_days = int(n_days * 0.8)
3. Фильтр: Старт X = Финал X ИЛИ Старт Y = Финал Y -> исключить
4. Изменение, %: Финал X != 0 -> по X, иначе по Y
5. Пары: BTC ETH (пробел)
6. Ввод: /trade T1 P1 Q1 C1 T2 P2 Q2 C2
7. offset: last_update_id.txt (в репо)
8. Аналитика — только через бота (без авто-рассылки в pairs_analysis)
9. Per-pair настройки в pair_settings

---

## ОСТАЛОСЬ

1. CryptoBot — Этап 2 (оплата криптой)
2. ЮKassa — Этап 3 (оплата картой)

---

Последнее обновление: 19.09.2026
