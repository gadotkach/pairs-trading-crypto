"""Управление тикерами: BASE + EXTENDED."""
import os
import json

BASE_TICKERS = ['ADA', 'ICP', 'ETH', 'DOT', 'LINK', 'ZRO', 'AAVE', 'BTC',
                'ATOM', 'NEAR', 'XCH', 'BNB', 'HBAR', 'TRX']

EXTENDED_FILE = 'extended_tickers.json'


def get_base_tickers():
    """Базовые 14."""
    return BASE_TICKERS[:]


def get_extended_tickers():
    """BASE + добавленные через /add."""
    result = get_base_tickers()
    if os.path.exists(EXTENDED_FILE):
        try:
            with open(EXTENDED_FILE, 'r', encoding='utf-8') as f:
                extra = json.load(f)
            for t in extra:
                if t not in result:
                    result.append(t)
        except Exception:
            pass
    return result


def is_available(ticker):
    """Проверка: доступен ли тикер (BASE или EXTENDED)."""
    return ticker.upper() in get_extended_tickers()


def add_extended_ticker(ticker):
    """Добавить тикер в EXTENDED. True — добавлен, False — уже есть."""
    ticker = ticker.upper()
    if ticker in get_base_tickers():
        return False
    extra = []
    if os.path.exists(EXTENDED_FILE):
        try:
            with open(EXTENDED_FILE, 'r', encoding='utf-8') as f:
                extra = json.load(f)
        except Exception:
            extra = []
    if ticker in extra:
        return False
    extra.append(ticker)
    with open(EXTENDED_FILE, 'w', encoding='utf-8') as f:
        json.dump(extra, f, indent=2)
    return True


def parse_pair(text):
    """'BTC ETH' -> ('BTC', 'ETH')."""
    tokens = text.upper().strip().split()
    if len(tokens) != 2:
        return None
    t1, t2 = tokens
    if not is_available(t1) or not is_available(t2):
        return None
    return (t1, t2)


def parse_pairs(text):
    """'SOL ADA BTC ETH' -> [('SOL','ADA'), ('BTC','ETH')]."""
    tokens = text.upper().strip().split()
    if len(tokens) % 2 != 0 or len(tokens) == 0:
        return None
    pairs = []
    for i in range(0, len(tokens), 2):
        t1, t2 = tokens[i], tokens[i+1]
        if not is_available(t1) or not is_available(t2):
            return None
        pairs.append((t1, t2))
    return pairs


def pair_to_str(pair):
    """('BTC','ETH') -> 'BTC/ETH'."""
    return '{}/{}'.format(pair[0], pair[1])


if __name__ == '__main__':
    print("BASE: {}".format(get_base_tickers()))
    print("EXTENDED: {}".format(get_extended_tickers()))
    print("parse_pair('BTC ETH'): {}".format(parse_pair('BTC ETH')))
    print("parse_pairs('SOL ADA BTC ETH'): {}".format(parse_pairs('SOL ADA BTC ETH')))
