"""Трассировка DOT/XCH, вариант A, 1 год (INITIAL=200$, без отмен)."""
import warnings
warnings.filterwarnings("ignore")
import pandas as pd
import numpy as np
from datetime import timedelta

TICKER_X = 'DOT'
TICKER_Y = 'XCH'
CHECK_PROFIT = False   # Вариант A
STEP = 0.05
COMMISSION_RATE = 0.004
INITIAL = 200.0         # ← 200$
PERIOD_DAYS = 365

CACHE_DIR = 'cache'


def load_pair():
    px = pd.read_csv('{}/{}.csv'.format(CACHE_DIR, TICKER_X),
                     parse_dates=['date'], index_col='date')['close']
    py = pd.read_csv('{}/{}.csv'.format(CACHE_DIR, TICKER_Y),
                     parse_dates=['date'], index_col='date')['close']
    common = px.index.intersection(py.index)
    px = px.loc[common]
    py = py.loc[common]
    cutoff = px.index.max() - timedelta(days=PERIOD_DAYS)
    px = px[px.index >= cutoff]
    py = py[py.index >= cutoff]
    return px, py


def trace():
    px, py = load_pair()
    z = px / py

    print("=" * 170)
    print("ТРАССИРОВКА {} / {} (вариант A, 1 год, ${})".format(TICKER_X, TICKER_Y, INITIAL))
    print("=" * 170)
    print("Дней: {}".format(len(z)))
    print("Период: {} -> {}".format(z.index.min().date(), z.index.max().date()))
    print()

    start_px = float(px.iloc[0])
    start_py = float(py.iloc[0])
    start_z = start_px / start_py

    shares_x = INITIAL / start_px
    shares_y = 0.0
    cash = 0.0
    invested = INITIAL
    commission_total = 0.0
    trades = 0
    cancelled = 0
    level_X = start_z
    level_Y = start_z

    print("Старт: X={:.6f} монет ({:.2f}$), Y={:.6f}, Z={:.6f}".format(
        shares_x, INITIAL, shares_y, start_z))
    print()

    header = "{:<12} {:>10} {:>12} {:>12} {:>12} {:>12} {:>20} {:>20} {:>20} {:>20}".format(
        "Date", "Z", "level_X", "level_Y", "p_x", "p_y",
        "Продано X", "Куплено Y", "Продано Y", "Куплено X")
    print(header)
    print("-" * 170)

    n_events = 0
    for i in range(1, len(z)):
        d = z.index[i]
        v = float(z.iloc[i])
        p_x = float(px.iloc[i])
        p_y = float(py.iloc[i])

        sold_x = 0.0
        bought_y = 0.0
        sold_y = 0.0
        bought_x = 0.0
        show = False

        # X → Y
        if v >= level_X * (1 + STEP):
            if shares_x > 0:
                sold_x = shares_x
                sell = shares_x * p_x
                comm = sell * COMMISSION_RATE
                commission_total += comm
                cash = sell - comm
                bought_y = cash / p_y
                cash = 0
                shares_x = 0
                shares_y = bought_y
                trades += 1
                level_X = v
                show = True
            else:
                cancelled += 1

        # Y → X
        elif v <= level_Y * (1 - STEP):
            if shares_y > 0:
                sold_y = shares_y
                sell = shares_y * p_y
                comm = sell * COMMISSION_RATE
                commission_total += comm
                cash = sell - comm
                bought_x = cash / p_x
                cash = 0
                shares_y = 0
                shares_x = bought_x
                trades += 1
                level_Y = v
                show = True
            else:
                cancelled += 1

        if show:
            row = "{:<12} {:>10.4f} {:>12.4f} {:>12.4f} {:>12.6f} {:>12.6f} {:>20.6f} {:>20.6f} {:>20.6f} {:>20.6f}".format(
                str(d.date()), v, level_X, level_Y, p_x, p_y,
                sold_x, bought_y, sold_y, bought_x)
            print(row)
            n_events += 1

    print()
    print("=" * 170)
    print("ИТОГ")
    print("=" * 170)
    print("Сделок: {}".format(trades))
    print("Отменено: {}".format(cancelled))
    print("Комиссия: {:.4f}$".format(commission_total))

    final_px = float(px.iloc[-1])
    final_py = float(py.iloc[-1])
    if shares_x > 0:
        final_value = shares_x * final_px
        print("Финал: X={:.6f} монет * {:.6f} = {:.4f}$".format(shares_x, final_px, final_value))
    elif shares_y > 0:
        final_value = shares_y * final_py
        print("Финал: Y={:.6f} монет * {:.6f} = {:.4f}$".format(shares_y, final_py, final_value))
    else:
        final_value = cash
        print("Финал: cash={:.4f}$".format(cash))

    profit_pct = (final_value - invested) / invested * 100
    print("Доходность: {:.2f}%".format(profit_pct))


if __name__ == "__main__":
    trace()
