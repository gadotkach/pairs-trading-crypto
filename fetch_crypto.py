"""Загрузка цен: HTX (основной) + Bybit (fallback)."""
import os
import warnings
warnings.filterwarnings("ignore")
import requests
import pandas as pd
from datetime import datetime, timedelta
import time

TICKERS = ['ADA', 'ICP', 'ETH', 'DOT', 'LINK', 'ZRO', 'AAVE', 'BTC',
           'ATOM', 'NEAR', 'XCH', 'BNB', 'HBAR', 'TRX']

CACHE_DIR = 'cache'
HTX_HOSTS = [
    'https://api.huobi.pro',
    'https://api-aws.huobi.pro',
]
BYBIT_HOST = 'https://api.bybit.com'


def htx_symbol(ticker):
    return ticker.lower() + 'usdt'


def bybit_symbol(ticker):
    return ticker.upper() + 'USDT'


def get_last_date(ticker):
    path = os.path.join(CACHE_DIR, "{}.csv".format(ticker))
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path, parse_dates=['date'], index_col='date')
        return df.index.max().date() if len(df) else None
    except Exception:
        return None


def load_existing(ticker):
    path = os.path.join(CACHE_DIR, "{}.csv".format(ticker))
    if os.path.exists(path):
        df = pd.read_csv(path, parse_dates=['date'], index_col='date')
        if 'close' in df.columns:
            return df[['close']].copy()
        return pd.DataFrame(columns=['close'])
    return pd.DataFrame(columns=['close'])


def save_cache(ticker, df):
    path = os.path.join(CACHE_DIR, "{}.csv".format(ticker))
    df = df[['close']].copy()
    df.to_csv(path, index_label='date')


def fetch_htx(ticker):
    symbol = htx_symbol(ticker)
    for host in HTX_HOSTS:
        url = "{}/market/history/kline".format(host)
        params = {'symbol': symbol, 'period': '1day', 'size': 2000}
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print("    HTX {} ошибка: {}".format(host, str(e)[:60]))
            continue

        if data.get('status') != 'ok' or 'data' not in data:
            continue

        klines = data['data']
        if not klines:
            return None

        rows = []
        for k in klines:
            rows.append({
                'date': datetime.fromtimestamp(k['id']),
                'close': float(k['close']),
            })

        df = pd.DataFrame(rows)
        df['date'] = pd.to_datetime(df['date']).dt.normalize()
        df.set_index('date', inplace=True)
        df.sort_index(inplace=True)
        return df

    return None


def fetch_bybit(ticker):
    symbol = bybit_symbol(ticker)
    url = "{}/v5/market/kline".format(BYBIT_HOST)

    all_rows = []
    end_ms = None

    for _ in range(3):
        params = {
            'category': 'spot',
            'symbol': symbol,
            'interval': 'D',
            'limit': 1000,
        }
        if end_ms:
            params['end'] = end_ms

        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print("    Bybit ошибка: {}".format(str(e)[:60]))
            break

        if data.get('retCode') != 0:
            break

        klines = data['result']['list']
        if not klines:
            break

        all_rows.extend(klines)

        oldest_ts = int(klines[-1][0])
        end_ms = oldest_ts - 1

        if len(klines) < 1000:
            break
        time.sleep(0.3)

    if not all_rows:
        return None

    rows = []
    for k in all_rows:
        rows.append({
            'date': datetime.fromtimestamp(int(k[0]) / 1000),
            'close': float(k[4]),
        })

    df = pd.DataFrame(rows)
    df['date'] = pd.to_datetime(df['date']).dt.normalize()
    df.set_index('date', inplace=True)
    df = df[~df.index.duplicated(keep='first')]
    df.sort_index(inplace=True)
    return df


def update_cache(ticker):
    print("  {}:".format(ticker), end=' ')

    last_date = get_last_date(ticker)
    if last_date is None:
        print("кэш пуст, загружаем полностью", end=' -> ')
    else:
        print("последняя {}".format(last_date), end=' -> ')

    new_df = None
    source = None

    try:
        new_df = fetch_htx(ticker)
        source = 'HTX'
    except Exception as e:
        print("HTX ошибка: {}".format(str(e)[:60]), end=' -> ')

    if new_df is None or new_df.empty:
        try:
            new_df = fetch_bybit(ticker)
            source = 'Bybit'
        except Exception as e:
            print("Bybit ошибка: {}".format(str(e)[:60]), end=' -> ')

    if new_df is None or new_df.empty:
        print("нет данных")
        return

    existing = load_existing(ticker)
    if not existing.empty:
        combined = pd.concat([existing, new_df])
        combined = combined[~combined.index.duplicated(keep='last')]
    else:
        combined = new_df

    combined.sort_index(inplace=True)
    save_cache(ticker, combined)

    print("{}: {} свечей, всего {}".format(source, len(new_df), len(combined)))


if __name__ == "__main__":
    print("Начало обновления: {}".format(datetime.now()))
    for t in TICKERS:
        update_cache(t)
    print("Обновление завершено.")
