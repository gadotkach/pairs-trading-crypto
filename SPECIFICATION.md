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

## РАСПИСАНИЕ

| Workflow | Cron | Что делает |
|---|---|---|
| run.yml | */30 | fetch_crypto + z_analytics + pairs_analysis (без TG) |
| bot.yml | */10 | bot_handler (опрос Telegram, ответы) |

---

## БОТ

### Уровни
- basic: /pair (1 год), /keep (1 пара), /help
- priority: + /check, /find, /keep (20), /P
- superpriority: + /add, /period, /step, /strategy, /keep (inf)
- ssuperpriority: + /buy (2/мес)

### Команды
- /start, /P, /help, /status
- /pair, /check, /find, /add, /keep
- /period, /step, /strategy
- /priority, /superpriority, /ssuperpriority (оплата)
- /gencode, /activate, /codes (админ)
- /redeem CODE

### Reply-меню
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
- PRIO-2026-XXXX, SUPER-2026-XXXX, SS-2026-XXXX
- 30 дней, одноразовые
- Хранение: user_state.json (redeem_codes)

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
6. Ввод сделки: T1 P1 Q1 C1 T2 P2 Q2 C2
7. SEND_TELEGRAM = False (аналитика через бота)
8. offset: last_update_id.txt (в репо)

---

## ОСТАЛОСЬ

1. priority_report.py — рассылка в 09:00 МСК
2. CryptoBot — Этап 2
3. ЮKassa — Этап 3

---

Последнее обновление: 19.09.2026
