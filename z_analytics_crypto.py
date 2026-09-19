"""ZigZag-аналитика для криптовалютных пар (HTX + Bybit)."""
import os
import warnings
warnings.filterwarnings("ignore")
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

TICKERS = ['ADA', 'ICP', 'ETH', 'DOT', 'LINK', 'ZRO', 'AAVE', 'BTC',
           'ATOM', 'NEAR', 'XCH', 'BNB', 'HBAR', 'TRX']

CACHE_DIR = 'cache'
OUTPUT_FILE = 'analytics_z.xlsx'

# Периоды (дней)
PERIODS = {
    '5 лет': 5 * 365,
    '3 года': 3 * 365,
    '1 год': 365,
}

# ZigZag пороги
ZIGZAG_5 = 0.05   # 5%
ZIGZAG_10 = 0.10  # 10%

# Окно для count_extrema (не критично)
WINDOW = 5


# ---------- ФУНКЦИИ ----------

def load_prices():
    """Загружает все cache/*.csv, возвращает DataFrame с ценами."""
    data = {}
    for ticker in TICKERS:
        path = os.path.join(CACHE_DIR, "{}.csv".format(ticker))
        if not os.path.exists(path):
            print("  {}: нет файла".format(ticker))
            continue
        df = pd.read_csv(path, parse_dates=['date'], index_col='date')
        if 'close' not in df.columns:
            print("  {}: нет колонки close".format(ticker))
            continue
        data[ticker] = df['close']
    prices = pd.DataFrame(data)
    prices.sort_index(inplace=True)
    return prices


def zigzag(series, threshold):
    """ZigZag-фильтр. Возвращает DataFrame с точками экстремумов.
    
    series: pd.Series с ценами.
    threshold: 0.05 (5%) или 0.10 (10%).
    """
    if len(series) < 2:
        return pd.DataFrame(columns=['price', 'type'])

    vals = series.values
    dates = series.index

    extrema = []
    last_pivot_idx = 0
    last_pivot_price = vals[0]
    direction = 0  # 0=нет, 1=вверх, -1=вниз

    for i in range(1, len(vals)):
        price = vals[i]

        if direction == 0:
            # Ищем первое движение
            if price >= last_pivot_price * (1 + threshold):
                # Дошли до минимума → разворот вверх
                # Найти минимум между last_pivot_idx и i
                min_idx = last_pivot_idx + int(np.argmin(vals[last_pivot_idx:i+1]))
                extrema.append({'date': dates[min_idx], 'price': vals[min_idx], 'type': 'min'})
                last_pivot_idx = min_idx
                last_pivot_price = vals[min_idx]
                direction = 1
            elif price <= last_pivot_price * (1 - threshold):
                max_idx = last_pivot_idx + int(np.argmax(vals[last_pivot_idx:i+1]))
                extrema.append({'date': dates[max_idx], 'price': vals[max_idx], 'type': 'max'})
                last_pivot_idx = max_idx
                last_pivot_price = vals[max_idx]
                direction = -1

        elif direction == 1:
            if price > last_pivot_price:
                last_pivot_price = price
                last_pivot_idx = i
            elif price <= last_pivot_price * (1 - threshold):
                extrema.append({'date': dates[last_pivot_idx], 'price': last_pivot_price, 'type': 'max'})
                last_pivot_idx = i
                last_pivot_price = price
                direction = -1

        elif direction == -1:
            if price < last_pivot_price:
                last_pivot_price = price
                last_pivot_idx = i
            elif price >= last_pivot_price * (1 + threshold):
                extrema.append({'date': dates[last_pivot_idx], 'price': last_pivot_price, 'type': 'min'})
                last_pivot_idx = i
                last_pivot_price = price
                direction = 1

    if not extrema:
        return pd.DataFrame(columns=['date', 'price', 'type'])

    return pd.DataFrame(extrema)


def count_extrema(series, threshold):
    """Возвращает (n_extrema, avg_move, min_move, max_move, vals, dates)."""
    zz = zigzag(series, threshold)
    if zz.empty or len(zz) < 2:
        return 0, None, None, None, [], []

    vals = zz['price'].values
    dates = zz['date'].tolist()

    moves = []
    for i in range(1, len(vals)):
        if vals[i-1] > 0:
            move = abs(vals[i] - vals[i-1]) / vals[i-1] * 100
            moves.append(move)

    if not moves:
        return len(vals), None, None, None, vals.tolist(), dates

    return (len(vals),
            round(np.mean(moves), 2),
            round(np.min(moves), 2),
            round(np.max(moves), 2),
            vals.tolist(),
            dates)


def count_repeated_extrema(vals, decimals=4):
    """Считает повторяющиеся уровни (по округлению).
    
    Возвращает (P_max, P_min, n_repeat_levels).
    """
    if not vals:
        return None, None, 0

    rounded = [round(v, decimals) for v in vals]
    from collections import Counter
    cnt = Counter(rounded)

    # Уровни с повтором (встречаются >= 2 раз)
    repeated = {v: c for v, c in cnt.items() if c >= 2}

    if not repeated:
        return None, None, 0

    p_max = max(repeated.keys())
    p_min = min(repeated.keys())
    return p_max, p_min, len(repeated)


def get_last_repeat_date(vals, dates, decimals=4):
    """Дата последнего повтора."""
    if not vals or not dates:
        return None

    rounded = [round(v, decimals) for v in vals]
    from collections import Counter
    cnt = Counter(rounded)

    last_date = None
    for i, v in enumerate(reversed(rounded)):
        if cnt[v] >= 2:
            last_date = dates[len(dates) - 1 - i]
            break
    return last_date


def count_mean_crossings(series):
    """Сколько раз цена пересекала среднюю."""
    if len(series) < 2:
        return 0
    mean = series.mean()
    above = series > mean
    crossings = ((above != above.shift()).sum()) - 1
    return int(crossings) if crossings > 0 else 0


def compute_r2_trend(series):
    """R² линейного тренда."""
    if len(series) < 2:
        return 0.0
    x = np.arange(len(series))
    y = series.values
    coeffs = np.polyfit(x, y, 1)
    y_pred = np.polyval(coeffs, x)
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    if ss_tot == 0:
        return 0.0
    return float(1 - ss_res / ss_tot)


def compute_trend_ratio(series):
    """Trend ratio = (конец - начало) / начало."""
    if len(series) < 2:
        return 0.0
    start = series.iloc[0]
    end = series.iloc[-1]
    if start == 0:
        return 0.0
    return float((end - start) / start)


def get_period_data(prices, n_days):
    """Обрезает цены по периоду."""
    cutoff = prices.index.max() - timedelta(days=n_days)
    return prices[prices.index >= cutoff]


# ---------- MAIN ----------

def main():
    print("=" * 80)
    print("ZIGZAG-АНАЛИТИКА КРИПТОПАР")
    print("=" * 80)

    # 1. Загрузка цен
    print("\nЗагрузка цен...")
    prices = load_prices()
    if prices.empty:
        print("Нет данных — выход.")
        return
    print("Тикеров: {}".format(len(prices.columns)))
    print("Период: {} -> {} ({} дней)".format(
        prices.index.min().date(), prices.index.max().date(), len(prices)))

    tickers = list(prices.columns)
    n_pairs = len(tickers) * (len(tickers) - 1) // 2
    print("Пар для анализа: {}".format(n_pairs))

    # 2. Списки для результатов
    rows_5 = []    # ZigZag 5%
    rows_10 = []   # ZigZag 10%

    # 3. Цикл по периодам
    for period_name, n_days in PERIODS.items():
        print("\n" + "=" * 60)
        print("ПЕРИОД: {}".format(period_name))
        print("=" * 60)

        period_prices = get_period_data(prices, n_days)
        if len(period_prices) < 50:
            print("  Мало данных — пропуск.")
            continue

        # Требуется минимум 80% от периода (иначе пара слишком молодая)
        min_days = int(n_days * 0.8)

        # Цикл по парам
        for i in range(len(tickers)):
            for j in range(i + 1, len(tickers)):
                ta, tb = tickers[i], tickers[j]
                pair_name = "{}/{}".format(ta, tb)

                sa = period_prices[ta].dropna()
                sb = period_prices[tb].dropna()
                common = sa.index.intersection(sb.index)

                # Проверка: достаточно ли дней данных для этого периода
                if len(common) < min_days:
                    continue

                sa = sa.loc[common]
                sb = sb.loc[common]

                # Проверка на нули
                if (sb == 0).any() or (sa == 0).any():
                    continue

                # Z-score (отношение)
                z = sa / sb

                # ---- ZigZag 5% ----
                n5, avg5, min5, max5, vals5, dates5 = count_extrema(z, ZIGZAG_5)
                p_max5, p_min5, n_rep5 = count_repeated_extrema(vals5, decimals=4)
                last_rep5 = get_last_repeat_date(vals5, dates5, decimals=4)
                min_z5 = round(min(vals5), 4) if vals5 else None
                max_z5 = round(max(vals5), 4) if vals5 else None

                # ---- ZigZag 10% ----
                n10, avg10, min10, max10, vals10, dates10 = count_extrema(z, ZIGZAG_10)
                p_max10, p_min10, n_rep10 = count_repeated_extrema(vals10, decimals=4)
                last_rep10 = get_last_repeat_date(vals10, dates10, decimals=4)
                min_z10 = round(min(vals10), 4) if vals10 else None
                max_z10 = round(max(vals10), 4) if vals10 else None

                # ---- Общие метрики ----
                n_crossings = count_mean_crossings(z)
                r2 = compute_r2_trend(z)
                tr = compute_trend_ratio(z)

                # ---- Общая часть ----
                base = {
                    'Период': period_name,
                    'Пара': pair_name,
                    'Дней': len(z),
                    'Мин Z': round(z.min(), 4),
                    'Макс Z': round(z.max(), 4),
                    'sminZ': round(z.min(), 4),
                    'smaxZ': round(z.max(), 4),
                    'Z средняя': round(z.mean(), 4),
                    'Mean-crossings': n_crossings,
                    'R2': round(r2, 4),
                    'Trend ratio': round(tr, 4),
                    'Z start': round(z.iloc[0], 4),
                    'Z end': round(z.iloc[-1], 4),
                }

                # ---- 5% ----
                rows_5.append({**base,
                    'Экстремумы': n5,
                    'P max': p_max5,
                    'P min': p_min5,
                    'Шаг, %': round((p_max5 - p_min5) / p_min5 * 100, 2) if (p_max5 and p_min5 and p_min5 > 0) else None,
                    'Уровней с повтором': n_rep5,
                    'Последний повтор': last_rep5,
                    'min Z 5': min_z5,
                    'max Z 5': max_z5,
                    'Мин движение %': min5,
                    'Макс движение %': max5,
                    'Среднее движение %': avg5,
                })

                # ---- 10% ----
                rows_10.append({**base,
                    'Экстремумы': n10,
                    'P max': p_max10,
                    'P min': p_min10,
                    'Шаг, %': round((p_max10 - p_min10) / p_min10 * 100, 2) if (p_max10 and p_min10 and p_min10 > 0) else None,
                    'Уровней с повтором': n_rep10,
                    'Последний повтор': last_rep10,
                    'min Z 10': min_z10,
                    'max Z 10': max_z10,
                    'Мин движение %': min10,
                    'Макс движение %': max10,
                    'Среднее движение %': avg10,
                })

    # 4. DataFrame
    df_5 = pd.DataFrame(rows_5)
    df_10 = pd.DataFrame(rows_10)

    if not df_5.empty:
        df_5 = df_5.sort_values(['Период', 'Экстремумы'],
                                ascending=[True, False]).reset_index(drop=True)
    if not df_10.empty:
        df_10 = df_10.sort_values(['Период', 'Экстремумы'],
                                  ascending=[True, False]).reset_index(drop=True)

    # 5. Листы "Повторы"
    repeats_cols = ['Период', 'Пара', 'Экстремумы', 'P max', 'P min',
                    'Шаг, %', 'Уровней с повтором', 'Последний повтор']
    if not df_5.empty:
        repeats_5 = df_5[df_5['Уровней с повтором'] > 0][repeats_cols].copy()
    else:
        repeats_5 = pd.DataFrame(columns=repeats_cols)

    if not df_10.empty:
        repeats_10 = df_10[df_10['Уровней с повтором'] > 0][repeats_cols].copy()
    else:
        repeats_10 = pd.DataFrame(columns=repeats_cols)

    # 6. Запись Excel
    print("\n" + "=" * 60)
    print("Запись в {}".format(OUTPUT_FILE))
    print("=" * 60)

    with pd.ExcelWriter(OUTPUT_FILE, engine='openpyxl') as w:
        df_5.to_excel(w, sheet_name='Analytics_Z', index=False)
        df_10.to_excel(w, sheet_name='Analytics_Z_10', index=False)
        repeats_5.to_excel(w, sheet_name='Повторы', index=False)
        repeats_10.to_excel(w, sheet_name='Повторы_10', index=False)

    print("OK: {}".format(OUTPUT_FILE))
    print("  Analytics_Z:    {} строк".format(len(df_5)))
    print("  Analytics_Z_10: {} строк".format(len(df_10)))
    print("  Повторы:        {} строк".format(len(repeats_5)))
    print("  Повторы_10:     {} строк".format(len(repeats_10)))


if __name__ == "__main__":
    main()
