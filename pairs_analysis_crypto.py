"""Стратегия 6 для крипты: ТОП-фильтр + симуляция + сигналы.

2 варианта симуляции:
  A — без проверки ×1.01 (продаём всегда)
  B — с проверкой ×1.01 (только если X подорожал на 1%)
"""
import os
import warnings
warnings.filterwarnings("ignore")
import json
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta

# ---------- НАСТРОЙКИ ----------
TICKERS = ['ADA', 'ICP', 'ETH', 'DOT', 'LINK', 'ZRO', 'AAVE', 'BTC',
           'ATOM', 'NEAR', 'XCH', 'BNB', 'HBAR', 'TRX']

CACHE_DIR = 'cache'
ANALYTICS_FILE = 'analytics_z.xlsx'
OUTPUT_FILE = 'pair_strategies_analysis.xlsx'
STATE_FILE = 'state.json'

# Периоды (дней)
PERIOD_DAYS = {
    '5 лет': 5 * 365,
    '3 года': 3 * 365,
    '1 год': 365,
}

# Фильтр ТОПа
EXTREMA_THRESHOLD = 30

# Торговля
STEP = 0.05          # ±5% от level
CHECK_PROFIT = 1.01  # для варианта B: X должен подорожать на 1%

# Стартовый баланс
INITIAL = 200.0    # $10,000

# Комиссия (0.4% от сделки)
COMMISSION_RATE = 0.004

# Налог (0% для крипты)
TAX_RATE = 0.0

# Telegram
TG_PROXY = os.environ.get("TG_PROXY", "https://tg-proxy.shvaboe.workers.dev")
TG_TOKEN = os.environ.get("TG_TOKEN", "")
TG_CHAT = os.environ.get("TG_CHAT", "")
SEND_TELEGRAM = bool(TG_TOKEN and TG_CHAT)

# Префикс сообщений
PREFIX = "[CRYPTO] "


# ---------- TELEGRAM ----------

def send_telegram(text):
    if not SEND_TELEGRAM:
        print("[telegram] не настроен (нет TG_TOKEN / TG_CHAT)")
        return False
    url = "{}/bot{}/sendMessage".format(TG_PROXY, TG_TOKEN)
    payload = {"chat_id": TG_CHAT, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=30)
        print("[telegram] status={}".format(r.status_code))
        return r.status_code == 200
    except Exception as e:
        print("[telegram] ошибка: {}".format(e))
        return False


# ---------- STATE ----------

def load_state():
    if not os.path.exists(STATE_FILE):
        return {
            'excluded_notified': [],
            'excluded_from_signal': [],
            'analytics_10': {},
        }
    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        data.setdefault('excluded_notified', [])
        data.setdefault('excluded_from_signal', [])
        data.setdefault('analytics_10', {})
        return data
    except Exception as e:
        print("Ошибка state: {}".format(e))
        return {
            'excluded_notified': [],
            'excluded_from_signal': [],
            'analytics_10': {},
        }


def save_state(state):
    state['last_update'] = datetime.now().isoformat()
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ---------- ЗАГРУЗКА ----------

def load_prices():
    """Загружает cache/*.csv → DataFrame с ценами."""
    data = {}
    for ticker in TICKERS:
        path = os.path.join(CACHE_DIR, "{}.csv".format(ticker))
        if not os.path.exists(path):
            continue
        df = pd.read_csv(path, parse_dates=['date'], index_col='date')
        if 'close' in df.columns:
            data[ticker] = df['close']
    prices = pd.DataFrame(data)
    prices.sort_index(inplace=True)
    return prices


def load_analytics():
    """Загружает analytics_z.xlsx → (df5, df10)."""
    try:
        df5 = pd.read_excel(ANALYTICS_FILE, sheet_name='Analytics_Z')
        df10 = pd.read_excel(ANALYTICS_FILE, sheet_name='Analytics_Z_10')
        return df5, df10
    except Exception as e:
        print("Ошибка analytics_z.xlsx: {}".format(e))
        return pd.DataFrame(), pd.DataFrame()


def load_extrema_threshold(df5, threshold=30):
    """Set пар с Экстремумы >= threshold (5 лет → 3 года)."""
    if df5.empty:
        return set()

    pairs_5y = {}
    pairs_3y = {}

    for _, row in df5.iterrows():
        period = row.get('Период')
        pair = row.get('Пара')
        ext = row.get('Экстремумы')
        if pair is None or ext is None or pd.isna(ext):
            continue
        if period == '5 лет':
            pairs_5y[pair] = ext
        elif period == '3 года':
            pairs_3y[pair] = ext

    passed = set()
    all_pairs = set(list(pairs_5y.keys()) + list(pairs_3y.keys()))
    for pair in all_pairs:
        ext = pairs_5y.get(pair)
        if ext is not None:
            if ext >= threshold:
                passed.add(pair)
        else:
            ext3 = pairs_3y.get(pair)
            if ext3 is not None and ext3 >= threshold:
                passed.add(pair)

    print("[extrema_filter] пар с Экстремумы >= {}: {}".format(threshold, len(passed)))
    return passed


def load_excluded(df5, threshold=30):
    """Set пар, где 3 года < threshold, + {pair: extrema}."""
    if df5.empty:
        return set(), {}

    az_3y = df5[df5['Период'] == '3 года']
    excluded = set()
    extrema_3y = {}

    for _, row in az_3y.iterrows():
        pair = row.get('Пара')
        ext = row.get('Экстремумы')
        if pair is None or pd.isna(ext):
            continue
        ext = int(ext)
        extrema_3y[pair] = ext
        if ext < threshold:
            excluded.add(pair)

    print("[excluded_from_signal] пар с 3 года < {}: {}".format(threshold, len(excluded)))
    return excluded, extrema_3y


def build_extrema_by_period(df5):
    """Словарь {(period, pair): extrema} из Analytics_Z (5%)."""
    result = {}
    if df5.empty:
        return result
    for _, row in df5.iterrows():
        period = row.get('Период')
        pair = row.get('Пара')
        ext = row.get('Экстремумы')
        if period is None or pair is None or pd.isna(ext):
            continue
        result[(period, pair)] = int(ext)
    return result


def build_analytics_10(df10):
    """Dict {pair: {min_z_10, max_z_10, p_max_10, p_min_10}} (3 года)."""
    result = {}
    if df10.empty:
        return result

    az_3y = df10[df10['Период'] == '3 года']
    for _, row in az_3y.iterrows():
        pair = row.get('Пара')
        if pair is None or pd.isna(pair):
            continue
        result[pair] = {
            'min_z_10': float(row['min Z 10']) if 'min Z 10' in row and not pd.isna(row['min Z 10']) else None,
            'max_z_10': float(row['max Z 10']) if 'max Z 10' in row and not pd.isna(row['max Z 10']) else None,
            'p_max_10': float(row['P max']) if 'P max' in row and not pd.isna(row['P max']) else None,
            'p_min_10': float(row['P min']) if 'P min' in row and not pd.isna(row['P min']) else None,
        }
    return result


# ---------- СИМУЛЯЦИЯ ----------

def simulate_pair(prices, ticker_x, ticker_y, check_profit=False):
    """
    Симуляция парного трейдинга.
    check_profit=False → Вариант A (всегда продаём)
    check_profit=True  → Вариант B (только если X подорожал на 1%)

    Возвращает dict или None.
    """
    common = prices[ticker_x].dropna().index.intersection(
        prices[ticker_y].dropna().index
    )
    if len(common) < 50:
        return None

    px = prices[ticker_x].loc[common]
    py = prices[ticker_y].loc[common]
    z = px / py

    start_px = float(px.iloc[0])
    start_py = float(py.iloc[0])
    start_z = start_px / start_py

    # Старт: покупаем X на $10,000
    shares_x = INITIAL / start_px
    shares_y = 0.0
    x_ref = start_px
    y_ref = 0.0

    invested = INITIAL
    cash = 0.0
    trades = 0
    cancelled = 0
    total_commission = 0.0
    total_sold_x = 0.0
    total_bought_y = 0.0
    total_sold_y = 0.0
    total_bought_x = 0.0  # НОВОЕ
    start_shares_x = shares_x  # X в начале
    end_shares_x = 0.0
    start_shares_y = 0.0  # Y при первой сделке
    end_shares_y = 0.0
    first_y_set = False  # флаг: Y ещё не куплен
    level_X = start_z
    level_Y = start_z

    for i in range(1, len(z)):
        v = float(z.iloc[i])
        p_x = float(px.iloc[i])
        p_y = float(py.iloc[i])

        # Сигнал X → Y (Z растёт → покупаем Y)
        if v >= level_X * (1 + STEP):
            if shares_x > 0:
                # Проверка прибыли (только для варианта B)
                if check_profit and p_x < x_ref * CHECK_PROFIT:
                    cancelled += 1
                    continue

                # Продаём X
                sell = shares_x * p_x
                comm = sell * COMMISSION_RATE
                total_commission += comm
                total_sold_x += shares_x
                net = sell - comm
                cash = net

                # Покупаем Y на весь cash
                shares_y = cash / p_y
                total_bought_y += shares_y
                y_ref = p_y
                shares_x = 0
                cash = 0
                trades += 1
                level_X = v
                end_shares_y = shares_y
                if not first_y_set:
                    start_shares_y = shares_y  # первая покупка Y
                    first_y_set = True
            else:
                cancelled += 1

        # Сигнал Y → X (Z падает → покупаем X)
        elif v <= level_Y * (1 - STEP):
            if shares_y > 0:
                # Проверка прибыли (только для варианта B)
                if check_profit and p_y < y_ref * CHECK_PROFIT:
                    cancelled += 1
                    continue

                # Продаём Y
                sell = shares_y * p_y
                comm = sell * COMMISSION_RATE
                total_commission += comm
                total_sold_y += shares_y  # НОВОЕ
                net = sell - comm
                cash = net

                # Покупаем X на весь cash
                shares_x = cash / p_x
                total_bought_x += shares_x  # НОВОЕ
                x_ref = p_x
                shares_y = 0
                cash = 0
                trades += 1
                level_Y = v
                end_shares_x = shares_x
            else:
                cancelled += 1

    # ---------- ИТОГ ----------
    final_px = float(px.iloc[-1])
    final_py = float(py.iloc[-1])

    if shares_x > 0:
        final_value = shares_x * final_px
        holding = "{:.6f} {} + cash {:.2f}".format(shares_x, ticker_x, cash)
    elif shares_y > 0:
        final_value = shares_y * final_py
        holding = "{:.6f} {} + cash {:.2f}".format(shares_y, ticker_y, cash)
    else:
        final_value = cash
        holding = "cash {:.2f}".format(cash)

    profit_pct = (final_value - invested) / invested * 100 if invested > 0 else 0.0

    # Итоговые количества монет
    if shares_x > 0:
        fin_x = shares_x
        fin_y = 0.0
    elif shares_y > 0:
        fin_x = 0.0
        fin_y = shares_y
    else:
        fin_x = 0.0
        fin_y = 0.0

    # Изменение, %:
    #   Если Финал X != 0 → считаем по X
    #   Если Финал X == 0 → считаем по Y
    if fin_x != 0 and start_shares_x > 0:
        change_y_pct = (fin_x - start_shares_x) / start_shares_x * 100
    elif fin_x == 0 and start_shares_y > 0 and fin_y > 0:
        change_y_pct = (fin_y - start_shares_y) / start_shares_y * 100
    else:
        change_y_pct = None

    # Цены монет
    if final_value > 0:
        if shares_x > 0:
            price_start = start_px
            price_end = final_px
        elif shares_y > 0:
            price_start = start_py
            price_end = final_py
        else:
            price_start = 0.0
            price_end = 0.0
    else:
        price_start = 0.0
        price_end = 0.0

    return {
        'Сделок': trades,
        'Отменено': cancelled,
        'Довнесений': 0,
        'Старт X, монет': round(start_shares_x, 8),
        'Финал X, монет': round(fin_x, 8),
        'Старт Y, монет': round(start_shares_y, 8),
        'Финал Y, монет': round(fin_y, 8),
        'Продано X': round(total_sold_x, 8),
        'Куплено Y': round(total_bought_y, 8),
        'Продано Y': round(total_sold_y, 8),
        'Куплено X': round(total_bought_x, 8),
        'Изменение, %': round(change_y_pct, 2) if change_y_pct is not None else None,
        'Внесено, $': round(invested, 2),
        'Деньги в конце, $': round(final_value, 2),
        'Налог, $': 0.0,
        'Комиссия, $': round(total_commission, 2),
        'Заработано (после), $': round(final_value - invested, 2),
        'Доходность (после), %': round(profit_pct, 2),
        'Где деньги в конце': holding,
        'Цена монеты начало': round(price_start, 6) if price_start else None,
        'Цена монеты конец': round(price_end, 6) if price_end else None,
    }




# ---------- MAIN ----------

def main():
    print("=" * 80)
    print("PAIRS ANALYSIS CRYPTO — Стратегия 6")
    print("=" * 80)

    # 1. Загрузка
    print("\n[1] Загрузка цен...")
    prices = load_prices()
    if prices.empty:
        print("Нет данных — выход.")
        return
    print("Тикеров: {}".format(len(prices.columns)))
    print("Период: {} -> {} ({} дней)".format(
        prices.index.min().date(), prices.index.max().date(), len(prices)))

    print("\n[2] Загрузка аналитики...")
    df5, df10 = load_analytics()
    if df5.empty:
        print("Нет analytics_z.xlsx — выход.")
        return

    # 2. Фильтр ТОПа
    passed_extrema = load_extrema_threshold(df5, threshold=EXTREMA_THRESHOLD)
    excluded_from_signal, extrema_3y = load_excluded(df5, threshold=EXTREMA_THRESHOLD)
    extrema_by_period = build_extrema_by_period(df5)
    print("[extrema] пар в словаре: {}".format(len(extrema_by_period)))

    # Состояние — было раньше?
    state = load_state()
    prev_excluded = set(state.get('excluded_from_signal', []))
    newly_excluded = excluded_from_signal - prev_excluded
    returned = prev_excluded - excluded_from_signal

    if newly_excluded:
        print("  Новые исключения: {}".format(', '.join(sorted(newly_excluded))))
    if returned:
        print("  Вернулись в сигнал: {}".format(', '.join(sorted(returned))))

    print("\n" + "=" * 60)
    print("ПАР, ПРОШЕДШИХ ФИЛЬТР: {}".format(len(passed_extrema)))
    print("=" * 60)

    # 3. Симуляция (2 варианта × 3 периода × все пары)
    tickers = list(prices.columns)
    all_results = {}  # {'A_5 лет': [...], 'B_5 лет': [...], ...}

    for period_name, n_days in PERIOD_DAYS.items():
        print("\n" + "=" * 60)
        print("ПЕРИОД: {}".format(period_name))
        print("=" * 60)

        cutoff = prices.index.max() - timedelta(days=n_days)
        period_prices = prices[prices.index >= cutoff]

        rows_a = []
        rows_b = []

        n_processed = 0
        min_days = int(n_days * 0.8)  # 80% от периода

        for i in range(len(tickers)):
            for j in range(i + 1, len(tickers)):
                ta, tb = tickers[i], tickers[j]
                pair_name = "{}/{}".format(ta, tb)

                # Проверка: достаточно ли дней для периода
                common = period_prices[ta].dropna().index.intersection(
                    period_prices[tb].dropna().index
                )
                if len(common) < min_days:
                    continue

                # Вариант A (без проверки)
                res_a = simulate_pair(period_prices, ta, tb, check_profit=False)
                if res_a:
                    # ФИЛЬТР: если сделок не было (Старт = Финал) — исключить
                    if (abs(res_a['Старт X, монет'] - res_a['Финал X, монет']) < 1e-9 or
                            abs(res_a['Старт Y, монет'] - res_a['Финал Y, монет']) < 1e-9):
                        pass
                    else:
                        res_a['Период'] = period_name
                        res_a['Пара'] = pair_name
                        res_a['Экстремумы'] = extrema_by_period.get((period_name, pair_name), 0)
                        rows_a.append(res_a)

                # Вариант B (с проверкой ×1.01)
                res_b = simulate_pair(period_prices, ta, tb, check_profit=True)
                if res_b:
                    # ФИЛЬТР: если сделок не было (Старт = Финал) — исключить
                    if (abs(res_b['Старт X, монет'] - res_b['Финал X, монет']) < 1e-9 or
                            abs(res_b['Старт Y, монет'] - res_b['Финал Y, монет']) < 1e-9):
                        pass
                    else:
                        res_b['Период'] = period_name
                        res_b['Пара'] = pair_name
                        res_b['Экстремумы'] = extrema_by_period.get((period_name, pair_name), 0)
                        rows_b.append(res_b)

                n_processed += 1

        print("  Пар обработано: {}".format(n_processed))

        if rows_a:
            df_a = pd.DataFrame(rows_a)
            df_a = df_a[['Период', 'Пара', 'Экстремумы',
                         'Сделок', 'Отменено', 'Довнесений',
                         'Старт X, монет', 'Финал X, монет',
                         'Старт Y, монет', 'Финал Y, монет',
                         'Продано X', 'Куплено Y', 'Продано Y', 'Куплено X',
                         'Изменение, %',
                         'Внесено, $', 'Деньги в конце, $',
                         'Налог, $', 'Комиссия, $', 'Заработано (после), $',
                         'Доходность (после), %', 'Где деньги в конце',
                         'Цена монеты начало', 'Цена монеты конец']]
            df_a = df_a.sort_values('Доходность (после), %',
                                    ascending=False).reset_index(drop=True)
            all_results['A_' + period_name] = df_a

        if rows_b:
            df_b = pd.DataFrame(rows_b)
            df_b = df_b[['Период', 'Пара', 'Экстремумы',
                         'Сделок', 'Отменено', 'Довнесений',
                         'Старт X, монет', 'Финал X, монет',
                         'Старт Y, монет', 'Финал Y, монет',
                         'Продано X', 'Куплено Y', 'Продано Y', 'Куплено X',
                         'Изменение, %',
                         'Внесено, $', 'Деньги в конце, $',
                         'Налог, $', 'Комиссия, $', 'Заработано (после), $',
                         'Доходность (после), %', 'Где деньги в конце',
                         'Цена монеты начало', 'Цена монеты конец']]
            df_b = df_b.sort_values('Доходность (после), %',
                                    ascending=False).reset_index(drop=True)
            all_results['B_' + period_name] = df_b

    # 4. Excel
    print("\n" + "=" * 60)
    print("Запись в {}".format(OUTPUT_FILE))
    print("=" * 60)

    with pd.ExcelWriter(OUTPUT_FILE, engine='openpyxl') as w:
        for sheet_name, df in all_results.items():
            sheet_name_safe = sheet_name.replace(' ', '_')[:31]
            df.to_excel(w, sheet_name=sheet_name_safe, index=False)

    print("OK: {}".format(OUTPUT_FILE))
    for k, v in all_results.items():
        print("  {}: {} строк".format(k, len(v)))

    # 5. state.json — analytics_10
    current_analytics_10 = build_analytics_10(df10)
    print("\n[analytics_10] загружено пар (3 года): {}".format(len(current_analytics_10)))

    # 6. Telegram — изменения analytics_10
    prev_analytics_10 = state.get('analytics_10', {})
    changes = []
    for pair, cur in current_analytics_10.items():
        prev = prev_analytics_10.get(pair)
        if prev is None:
            continue
        pair_changes = []
        for key, label in [('min_z_10', 'min Z'), ('max_z_10', 'max Z'),
                           ('p_max_10', 'P max'), ('p_min_10', 'P min')]:
            old_v = prev.get(key)
            new_v = cur.get(key)
            if old_v is None or new_v is None:
                continue
            if abs(old_v - new_v) > 1e-6:
                pair_changes.append((label, old_v, new_v))
        if pair_changes:
            changes.append((pair, pair_changes))

    if SEND_TELEGRAM:
        # Изменения analytics_10
        if changes:
            msg = "{}📊 Analytics_Z (10%): изменения\n\n".format(PREFIX)
            for i, (pair, pair_changes) in enumerate(changes, 1):
                msg += "{}. {}\n".format(i, pair)
                for label, old_v, new_v in pair_changes:
                    msg += "   {}: {:.4f} → {:.4f}\n".format(label, old_v, new_v)
                msg += "\n"
            send_telegram(msg)
            print("[telegram] изменения analytics_10: {}".format(len(changes)))

        # Исключения / возвраты
        if newly_excluded or returned:
            msg = "{}🔔 Analytics_Z: изменения фильтра (3 года)\n\n".format(PREFIX)
            if newly_excluded:
                msg += "⚠️ Исключены из сигнала (Экстремумы 3 года &lt; 30):\n"
                for pair in sorted(newly_excluded):
                    ext = extrema_3y.get(pair, '?')
                    msg += "  • {} (Экстремумы 3 года = {})\n".format(pair, ext)
                msg += "\n"
            if returned:
                msg += "✅ Вернулись в сигнал (Экстремумы 3 года >= 30):\n"
                for pair in sorted(returned):
                    msg += "  • {}\n".format(pair)
                msg += "\n"
            send_telegram(msg)
            print("[telegram] исключения/возвраты отправлены")

    # 7. Сохранение state
    new_state = {
        'excluded_notified': state.get('excluded_notified', []),
        'excluded_from_signal': sorted(excluded_from_signal),
        'analytics_10': current_analytics_10,
        'last_update': datetime.now().isoformat(),
    }
    save_state(new_state)
    print("\n✓ state.json обновлён")


if __name__ == "__main__":
    main()
