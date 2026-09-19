"""CoinGecko API — список тикеров + проверка."""
import os
import json
import requests
from datetime import datetime, timedelta

BASE_URL = 'https://api.coingecko.com/api/v3'
CACHE_FILE = 'coingecko_cache.json'
CACHE_TTL_HOURS = 24

# Приоритетные id (для точного матча)
PREFERRED_IDS = {
    'BTC': 'bitcoin',
    'ETH': 'ethereum',
    'DOT': 'polkadot',
    'XCH': 'chia',
    'ADA': 'cardano',
    'SOL': 'solana',
    'XRP': 'ripple',
    'BNB': 'binancecoin',
    'TRX': 'tron',
    'LINK': 'chainlink',
    'AAVE': 'aave',
    'ATOM': 'cosmos',
    'NEAR': 'near',
    'HBAR': 'hedera-hashgraph',
    'ICP': 'internet-computer',
    'ZRO': 'layerzero',
    'LTC': 'litecoin',
    'BCH': 'bitcoin-cash',
    'UNI': 'uniswap',
    'DOGE': 'dogecoin',
    'AVAX': 'avalanche-2',
}


def _load_cache():
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        ts = datetime.fromisoformat(data['timestamp'])
        if datetime.now() - ts < timedelta(hours=CACHE_TTL_HOURS):
            return data['coins']
    except Exception:
        pass
    return None


def _save_cache(coins):
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'coins': coins
        }, f, ensure_ascii=False)


def get_all_coins():
    """Список всех монет (кэш 24ч)."""
    cached = _load_cache()
    if cached:
        return cached
    try:
        r = requests.get('{}/coins/list'.format(BASE_URL), timeout=30)
        if r.status_code == 200:
            coins = r.json()
            _save_cache(coins)
            return coins
    except Exception as e:
        print("CoinGecko error: {}".format(e))
    return []


def check_ticker(ticker):
    """Проверить существование тикера.
    Сначала пробуем PREFERRED_IDS, потом symbol.
    """
    coins = get_all_coins()
    tl = ticker.upper()

    # 1. По приоритетному id
    preferred = PREFERRED_IDS.get(tl)
    if preferred:
        for c in coins:
            if c.get('id') == preferred:
                return c

    # 2. Точное совпадение по symbol (id == symbol_lower)
    for c in coins:
        if c.get('symbol', '').upper() == tl and c.get('id', '') == tl.lower():
            return c

    # 3. Первое совпадение по symbol
    for c in coins:
        if c.get('symbol', '').upper() == tl:
            return c

    return None


def search_tickers(query, limit=20):
    """Поиск тикеров по части символа/имени."""
    coins = get_all_coins()
    q = query.upper()
    result = []
    for c in coins:
        if q in c.get('symbol', '').upper() or q in c.get('name', '').upper():
            result.append(c)
            if len(result) >= limit:
                break
    return result


if __name__ == '__main__':
    print("Загрузка списка монет...")
    coins = get_all_coins()
    print("Всего монет: {}".format(len(coins)))
    print()
    for t in ['BTC', 'ETH', 'DOT', 'XCH', 'ADA', 'SOL', 'NEWCOIN']:
        c = check_ticker(t)
        if c:
            print("  {}: {} ({})".format(t, c.get('name'), c.get('id')))
        else:
            print("  {}: НЕ НАЙДЕН".format(t))
