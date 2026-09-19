"""Графики Z для пар с DOT (ZigZag 5% и 10%, период 5 лет)."""
import warnings
warnings.filterwarnings("ignore")
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from datetime import timedelta

PAIRS = [
    ('DOT', 'XCH'),
    ('DOT', 'TRX'),
    ('DOT', 'HBAR'),
    ('DOT', 'BNB'),
    ('DOT', 'AAVE'),
    ('ADA', 'DOT'),
    ('DOT', 'NEAR'),
    ('DOT', 'BTC'),
]

CACHE_DIR = 'cache'
OUT_DIR = 'dot_plots'
PERIOD_DAYS = 5 * 365


def zigzag_extrema(series, threshold):
    """Возвращает точки экстремумов (date, price, type)."""
    if len(series) < 2:
        return []

    vals = series.values
    dates = series.index

    extrema = []
    last_pivot_idx = 0
    last_pivot_price = vals[0]
    direction = 0

    for i in range(1, len(vals)):
        price = vals[i]

        if direction == 0:
            if price >= last_pivot_price * (1 + threshold):
                min_idx = last_pivot_idx + int(np.argmin(vals[last_pivot_idx:i+1]))
                extrema.append((dates[min_idx], vals[min_idx], 'min'))
                last_pivot_idx = min_idx
                last_pivot_price = vals[min_idx]
                direction = 1
            elif price <= last_pivot_price * (1 - threshold):
                max_idx = last_pivot_idx + int(np.argmax(vals[last_pivot_idx:i+1]))
                extrema.append((dates[max_idx], vals[max_idx], 'max'))
                last_pivot_idx = max_idx
                last_pivot_price = vals[max_idx]
                direction = -1

        elif direction == 1:
            if price > last_pivot_price:
                last_pivot_price = price
                last_pivot_idx = i
            elif price <= last_pivot_price * (1 - threshold):
                extrema.append((dates[last_pivot_idx], last_pivot_price, 'max'))
                last_pivot_idx = i
                last_pivot_price = price
                direction = -1

        elif direction == -1:
            if price < last_pivot_price:
                last_pivot_price = price
                last_pivot_idx = i
            elif price >= last_pivot_price * (1 + threshold):
                extrema.append((dates[last_pivot_idx], last_pivot_price, 'min'))
                last_pivot_idx = i
                last_pivot_price = price
                direction = 1

    return extrema


def load_pair(tx, ty):
    px = pd.read_csv('{}/{}.csv'.format(CACHE_DIR, tx),
                     parse_dates=['date'], index_col='date')['close']
    py = pd.read_csv('{}/{}.csv'.format(CACHE_DIR, ty),
                     parse_dates=['date'], index_col='date')['close']
    common = px.index.intersection(py.index)
    px = px.loc[common]
    py = py.loc[common]
    cutoff = px.index.max() - timedelta(days=PERIOD_DAYS)
    px = px[px.index >= cutoff]
    py = py[py.index >= cutoff]
    z = px / py
    return z


def plot_pair(tx, ty, z, threshold, pct, extrema):
    fig, ax = plt.subplots(figsize=(14, 7))

    # Основная линия Z
    ax.plot(z.index, z.values, color='steelblue', linewidth=1.2,
            label='Z = {} / {}'.format(tx, ty))

    # P_max / P_min (уровни повтора из аналитики)
    # Найдём повторяющиеся уровни
    from collections import Counter
    vals = [e[1] for e in extrema]
    if vals:
        rounded = [round(v, 4) for v in vals]
        cnt = Counter(rounded)
        repeated = [v for v, c in cnt.items() if c >= 2]
        if repeated:
            p_max = max(repeated)
            p_min = min(repeated)

            ax.axhline(y=p_max, color='red', linestyle='--', linewidth=1.5,
                       label='P max = {:.4f}'.format(p_max))
            ax.axhline(y=p_min, color='red', linestyle='--', linewidth=1.5,
                       label='P min = {:.4f}'.format(p_min))

    # Точки экстремумов
    if extrema:
        ext_dates = [e[0] for e in extrema]
        ext_vals = [e[1] for e in extrema]
        ext_types = [e[2] for e in extrema]

        max_dates = [d for d, t in zip(ext_dates, ext_types) if t == 'max']
        max_vals = [v for v, t in zip(ext_vals, ext_types) if t == 'max']
        min_dates = [d for d, t in zip(ext_dates, ext_types) if t == 'min']
        min_vals = [v for v, t in zip(ext_vals, ext_types) if t == 'min']

        if max_dates:
            ax.scatter(max_dates, max_vals, color='red', marker='^', s=40,
                       zorder=5, label='Max экстремумы ({})'.format(len(max_dates)))
        if min_dates:
            ax.scatter(min_dates, min_vals, color='green', marker='v', s=40,
                       zorder=5, label='Min экстремумы ({})'.format(len(min_dates)))

    ax.set_title('{} / {} — ZigZag {:.0f}% (5 лет, {} экстремумов)'.format(
        tx, ty, pct, len(extrema)), fontsize=13)
    ax.set_xlabel('Дата')
    ax.set_ylabel('Z = {} / {}'.format(tx, ty))
    ax.grid(True, alpha=0.3)
    ax.legend(loc='best', fontsize=9)

    plt.tight_layout()

    # Сохранить
    fn = '{}/{}_{}_zigzag{}.png'.format(OUT_DIR, tx, ty, int(pct))
    plt.savefig(fn, dpi=100)
    plt.close()
    return fn


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print("=" * 100)
    print("ГРАФИКИ Z ДЛЯ ПАР С DOT (5 лет)")
    print("=" * 100)

    for tx, ty in PAIRS:
        print()
        print("--- {} / {} ---".format(tx, ty))

        try:
            z = load_pair(tx, ty)
        except Exception as e:
            print("  Ошибка загрузки: {}".format(e))
            continue

        print("  Дней: {}".format(len(z)))

        # ZigZag 5%
        extrema5 = zigzag_extrema(z, 0.05)
        fn5 = plot_pair(tx, ty, z, 0.05, 5, extrema5)
        print("  ZigZag 5%: {} экстремумов -> {}".format(len(extrema5), fn5))

        # ZigZag 10%
        extrema10 = zigzag_extrema(z, 0.10)
        fn10 = plot_pair(tx, ty, z, 0.10, 10, extrema10)
        print("  ZigZag 10%: {} экстремумов -> {}".format(len(extrema10), fn10))

    print()
    print("=" * 100)
    print("Готово. Графики в {}".format(OUT_DIR))
    print("=" * 100)


if __name__ == "__main__":
    main()
