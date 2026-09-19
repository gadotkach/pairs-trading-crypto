"""Модуль подписок: активация, проверка, коды."""
import os
import json
import random
import string
from datetime import datetime, timedelta

STATE_FILE = 'user_state.json'

# Цены в Stars (level, period) -> stars
STARS_PRICES = {
    ('priority', '1m'): 154,
    ('priority', '1y'): 1478,
    ('superpriority', '1m'): 770,
    ('superpriority', '1y'): 7392,
    ('ssuperpriority', '1m'): 3846,
    ('ssuperpriority', '1y'): 36922,
}

# Срок в днях
PERIOD_DAYS = {
    '1m': 30,
    '1y': 365,
}

LEVELS = ['basic', 'priority', 'superpriority', 'ssuperpriority']
PAID_LEVELS = ['priority', 'superpriority', 'ssuperpriority']

# Срок действия кода (дней)
CODE_TTL_DAYS = 30


# ---------- STATE ----------
def load_state():
    if not os.path.exists(STATE_FILE):
        return {'users': {}, 'redeem_codes': {}}
    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        data.setdefault('users', {})
        data.setdefault('redeem_codes', {})
        return data
    except Exception:
        return {'users': {}, 'redeem_codes': {}}


def save_state(state):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def get_user(user_id):
    state = load_state()
    uid = str(user_id)
    if uid not in state['users']:
        state['users'][uid] = {
            'level': 'basic',
            'level_expires_at': None,
            'strategy': 'AB',
            'step': 5,
            'period': {'type': 'years', 'value': 1},
            'subscriptions': {'check': True, 'pair': True, 'signals': True},
            'my_tickers': [],
            'trades': {},
            'priority_pairs': [],
            'keep_only': [],
            'buy_requests_this_month': 0,
            'buy_month': None,
        }
        save_state(state)
    return state['users'][uid]


# ---------- ПОДПИСКА ----------
def check_subscription(user_id):
    """Проверяет подписку. Возвращает уровень (basic если истекла)."""
    state = load_state()
    uid = str(user_id)
    if uid not in state['users']:
        return 'basic'

    user = state['users'][uid]
    level = user.get('level', 'basic')

    if level == 'basic':
        return 'basic'

    expires = user.get('level_expires_at')
    if not expires:
        return 'basic'

    try:
        exp_dt = datetime.fromisoformat(expires)
    except Exception:
        return 'basic'

    if datetime.now() > exp_dt:
        # Истекла
        state['users'][uid]['level'] = 'basic'
        state['users'][uid]['level_expires_at'] = None
        save_state(state)
        return 'basic'

    return level


def activate_level(user_id, level, days=30):
    """Активирует уровень на N дней (0 = бесконечный)."""
    if level not in LEVELS:
        return False

    state = load_state()
    uid = str(user_id)
    if uid not in state['users']:
        state['users'][uid] = {}

    if days == 0:
        expires = "2999-12-31T23:59:59"
    else:
        expires = (datetime.now() + timedelta(days=days)).isoformat()

    state['users'][uid]['level'] = level
    state['users'][uid]['level_expires_at'] = expires
    save_state(state)
    return True


def get_subscription_info(user_id):
    """Возвращает (level, expires_at)."""
    state = load_state()
    uid = str(user_id)
    if uid not in state['users']:
        return ('basic', None)
    user = state['users'][uid]
    return (user.get('level', 'basic'), user.get('level_expires_at'))


# ---------- КОДЫ ----------
def generate_code(level, days=30):
    """Генерирует код типа PRIO-2026-A3F9."""
    prefix_map = {
        'priority': 'PRIO',
        'superpriority': 'SUPER',
        'ssuperpriority': 'SS',
    }
    prefix = prefix_map.get(level, 'CODE')
    year = datetime.now().year
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    code = '{}-{}-{}'.format(prefix, year, suffix)

    state = load_state()
    state['redeem_codes'][code] = {
        'level': level,
        'days': days,
        'created_at': datetime.now().isoformat(),
        'used_by': None,
        'used_at': None,
    }
    save_state(state)
    return code


def redeem_code(user_id, code):
    """Активация по коду. Возвращает (success, message)."""
    state = load_state()
    code = code.strip().upper()

    if code not in state['redeem_codes']:
        return False, 'Код не найден.'

    info = state['redeem_codes'][code]

    if info.get('used_by'):
        return False, 'Код уже использован.'

    # Проверка срока действия кода
    created = info.get('created_at')
    if created:
        try:
            created_dt = datetime.fromisoformat(created)
            if datetime.now() - created_dt > timedelta(days=CODE_TTL_DAYS):
                return False, 'Код истёк (старше {} дней).'.format(CODE_TTL_DAYS)
        except Exception:
            pass

    # Активация
    level = info['level']
    days = info.get('days', 30)

    uid = str(user_id)
    if uid not in state['users']:
        state['users'][uid] = {}

    if days == 0:
        expires = "2999-12-31T23:59:59"
        period_str = "∞ (бесконечный)"
    else:
        expires = (datetime.now() + timedelta(days=days)).isoformat()
        period_str = "{} дней".format(days)

    state['users'][uid]['level'] = level
    state['users'][uid]['level_expires_at'] = expires

    info['used_by'] = uid
    info['used_at'] = datetime.now().isoformat()

    save_state(state)

    return True, 'Уровень {} активирован на {}.'.format(level, period_str)


def list_codes():
    """Список всех кодов."""
    state = load_state()
    return state.get('redeem_codes', {})


if __name__ == '__main__':
    print("subscription.py loaded")
    print("STARS_PRICES:")
    for k, v in STARS_PRICES.items():
        print("  {} = {} ⭐".format(k, v))
    print("LEVELS: {}".format(LEVELS))
    print("PERIOD_DAYS: {}".format(PERIOD_DAYS))
