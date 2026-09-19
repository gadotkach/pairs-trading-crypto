"""Telegram-бот для парного трейдинга (уровни, команды, сделки)."""
import os
import re
import json
import requests
from datetime import datetime, timedelta
import pandas as pd

from tickers import (
    get_base_tickers, get_extended_tickers, is_available,
    add_extended_ticker, parse_pair, parse_pairs, pair_to_str
)
from finance_api import check_ticker
from subscription import (
    STARS_PRICES, PERIOD_DAYS, LEVELS as SUB_LEVELS,
    check_subscription, activate_level, get_subscription_info,
    generate_code, redeem_code, list_codes
)

# ---------- КОНФИГ ----------
TG_PROXY = os.environ.get("TG_PROXY", "https://tg-proxy.shvaboe.workers.dev")
TG_TOKEN = os.environ.get("TG_TOKEN", "")
TG_CHAT = os.environ.get("TG_CHAT", "")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", TG_CHAT)

PRIORITY_CODE = os.environ.get("PRIORITY_CODE", "")
SUPERPRIORITY_CODE = os.environ.get("SUPERPRIORITY_CODE", "")
SSUPERPRIORITY_CODE = os.environ.get("SSUPERPRIORITY_CODE", "")

STATE_FILE = 'user_state.json'
ANALYTICS_FILE = 'analytics_z.xlsx'
STRATEGY_FILE = 'pair_strategies_analysis.xlsx'
CACHE_DIR = 'cache'

# Уровни
LEVELS = ['basic', 'priority', 'superpriority', 'ssuperpriority']

# Лимиты пар для /keep по уровням
KEEP_LIMITS = {
    'basic': 1,
    'priority': 20,
    'superpriority': 999999,
    'ssuperpriority': 999999,
}

# ---------- STATE ----------
def load_state():
    if not os.path.exists(STATE_FILE):
        return {'users': {}}
    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {'users': {}}


def save_state(state):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def get_user(user_id):
    state = load_state()
    uid = str(user_id)
    if uid not in state['users']:
        state['users'][uid] = {
            'level': 'basic',
            'strategy': 'AB',
            'step': 5,
            'period': {'type': 'years', 'value': 1},
            'subscriptions': {
                'check': True,
                'pair': True,
                'signals': True,
            },
            'my_tickers': [],
            'trades': {},
            'priority_pairs': [],
            'keep_only': [],
            'buy_requests_this_month': 0,
            'buy_month': None,
        }
        save_state(state)
    return state['users'][uid]


def set_user_field(user_id, field, value):
    state = load_state()
    uid = str(user_id)
    if uid not in state['users']:
        get_user(user_id)
        state = load_state()
    state['users'][uid][field] = value
    save_state(state)


def is_priority(user_id):
    return check_subscription(user_id) in ['priority', 'superpriority', 'ssuperpriority']


def is_super(user_id):
    return check_subscription(user_id) in ['superpriority', 'ssuperpriority']


def is_ss(user_id):
    return check_subscription(user_id) == 'ssuperpriority'


def is_admin(user_id):
    return str(user_id) == str(ADMIN_CHAT_ID)


# ---------- TELEGRAM ----------
def send_message(chat_id, text, parse_mode='HTML', reply_markup=None):
    url = "{}/bot{}/sendMessage".format(TG_PROXY, TG_TOKEN)
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
    try:
        r = requests.post(url, json=payload, timeout=30)
        return r.status_code == 200
    except Exception as e:
        print("[telegram] error: {}".format(e))
        return False


def pay_menu_keyboard(level):
    """Inline-кнопки для меню оплаты."""
    p1m = STARS_PRICES.get((level, '1m'), 0)
    p1y = STARS_PRICES.get((level, '1y'), 0)

    keyboard = {
        'inline_keyboard': [
            [
                {'text': '📅 1 месяц — {} ⭐'.format(p1m), 'callback_data': 'pay_{}_1m'.format(level)},
            ],
            [
                {'text': '📅 1 год — {} ⭐ (-20%)'.format(p1y), 'callback_data': 'pay_{}_1y'.format(level)},
            ],
            [
                {'text': '🔑 У меня есть код', 'callback_data': 'redeem_start'},
            ],
        ]
    }
    return keyboard


def format_priority_menu():
    """Описание 3 уровней доступа."""
    msg = "[CRYPTO] ⭐ Уровни доступа\n\n"

    msg += "⭐ PRIORITY\n"
    msg += "  • /pair BTC ETH (5/3/1 год)\n"
    msg += "  • /check DOT XCH — анализ\n"
    msg += "  • /find BTC — топ-5 пар\n"
    msg += "  • /keep — фильтр (до 20 пар)\n"
    msg += "  • Уведомления коридора\n"
    msg += "  • Рассылка по 20 парам\n"
    msg += "  💰 154 ⭐ / мес | 1478 ⭐ / год\n\n"

    msg += "⭐⭐ SUPERPRIORITY\n"
    msg += "  • Все функции Priority\n"
    msg += "  • /add BTC NEWCOIN — добавить пару\n"
    msg += "  • /period, /step, /strategy\n"
    msg += "  • /keep без ограничений\n"
    msg += "  💰 770 ⭐ / мес | 7392 ⭐ / год\n\n"

    msg += "⭐⭐⭐ SSUPERPRIORITY\n"
    msg += "  • Все функции Superpriority\n"
    msg += "  • /buy BTC — цена (2/мес)\n"
    msg += "  💰 3846 ⭐ / мес | 36922 ⭐ / год\n\n"

    msg += "→ Нажмите на уровень ниже:"
    return msg


def priority_levels_keyboard():
    """Inline-кнопки для выбора уровня."""
    keyboard = {
        'inline_keyboard': [
            [{'text': '⭐ Priority — 154 ⭐', 'callback_data': 'show_priority'}],
            [{'text': '⭐⭐ Superpriority — 770 ⭐', 'callback_data': 'show_superpriority'}],
            [{'text': '⭐⭐⭐ SSuperpriority — 3846 ⭐', 'callback_data': 'show_ssuperpriority'}],
        ]
    }
    return keyboard


def reply_main_menu():
    """Reply-клавиатура (внизу, как на фото)."""
    keyboard = {
        'keyboard': [
            [{'text': '📊 Данные'}, {'text': '🔍 Проверить'}],
            [{'text': '⭐ Приоритет'}, {'text': '📋 Статус'}],
            [{'text': '❓ Помощь'}],
        ],
        'resize_keyboard': True,
        'one_time_keyboard': False,
    }
    return keyboard


def send_message_with_reply_keyboard(chat_id, text):
    """Отправка с Reply-клавиатурой."""
    url = "{}/bot{}/sendMessage".format(TG_PROXY, TG_TOKEN)
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": 'HTML',
        "reply_markup": json.dumps(reply_main_menu()),
    }
    try:
        r = requests.post(url, json=payload, timeout=30)
        return r.status_code == 200
    except Exception as e:
        print("[telegram] error: {}".format(e))
        return False


def main_menu_keyboard(user_id):
    """Главное меню (inline-кнопки)."""
    keyboard = {
        'inline_keyboard': [
            [
                {'text': '📊 Данные по паре', 'callback_data': 'menu_pair'},
                {'text': '🔍 Проверить', 'callback_data': 'menu_check'},
            ],
            [
                {'text': '⭐ Приоритет', 'callback_data': 'menu_priority'},
                {'text': '📋 Статус', 'callback_data': 'menu_status'},
            ],
            [
                {'text': '❓ Помощь', 'callback_data': 'menu_help'},
            ],
        ]
    }
    return keyboard


def format_pay_menu(level):
    """Меню оплаты для уровня."""
    titles = {
        'priority': '⭐ Priority',
        'superpriority': '⭐⭐ Superpriority',
        'ssuperpriority': '⭐⭐⭐ SSuperpriority',
    }

    msg = "[CRYPTO] {} доступ\n\n".format(titles.get(level, level))
    msg += "Выберите период:"
    return msg


def get_updates(offset=None):
    url = "{}/bot{}/getUpdates".format(TG_PROXY, TG_TOKEN)
    params = {'timeout': 5}
    if offset:
        params['offset'] = offset
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print("[telegram] getUpdates error: {}".format(e))
    return {'result': []}


# ---------- ПАРСИНГ ВВОДА ----------
def parse_trade(text):
    """
    'DOT 1.1316 44.3566 0.10038 XCH 1.5045 33.2957 0.0665'
    -> dict или None.
    """
    tokens = text.strip().split()
    if len(tokens) != 8:
        return None

    t1, p1, q1, c1, t2, p2, q2, c2 = tokens

    try:
        p1 = float(p1.replace(',', '.'))
        q1 = float(q1.replace(',', '.'))
        c1 = float(c1.replace(',', '.'))
        p2 = float(p2.replace(',', '.'))
        q2 = float(q2.replace(',', '.'))
        c2 = float(c2.replace(',', '.'))
    except ValueError:
        return None

    if not is_available(t1.upper()) or not is_available(t2.upper()):
        return None

    return {
        't1': t1.upper(), 'p1': p1, 'q1': q1, 'c1': c1,
        't2': t2.upper(), 'p2': p2, 'q2': q2, 'c2': c2,
    }


def check_trade(trade):
    """
    Проверка сходимости (0.5%).
    Если q2 > 0 и p2 > 0 → проверяем.
    Если q2 = 0 или p2 = 0 → это "только X" (ок).
    Если q1 = 0 или p1 = 0 → это "только Y" (ок).
    """
    q1, p1, c1 = trade['q1'], trade['p1'], trade['c1']
    q2, p2, c2 = trade['q2'], trade['p2'], trade['c2']

    # Только X
    if q2 == 0 and p2 == 0:
        return True, None

    # Только Y
    if q1 == 0 and p1 == 0:
        return True, None

    # Полная
    sold = q1 * p1 - c1
    bought = q2 * p2

    if sold <= 0:
        return False, 'Некорректная сумма продажи'

    diff = abs(sold - bought) / sold
    if diff > 0.005:
        return False, 'Не сходится: продано {:.4f}, куплено {:.4f}, разница {:.2%}'.format(
            sold, bought, diff)

    return True, None




# ---------- АНАЛИТИКА ----------
def load_analytics_df(sheet='Analytics_Z'):
    try:
        return pd.read_excel(ANALYTICS_FILE, sheet_name=sheet)
    except Exception as e:
        print("analytics error: {}".format(e))
        return pd.DataFrame()


def load_strategy_df(sheet):
    try:
        return pd.read_excel(STRATEGY_FILE, sheet_name=sheet)
    except Exception as e:
        print("strategy error: {}".format(e))
        return pd.DataFrame()


def calc_period_label(user):
    period = user.get('period', {'type': 'years', 'value': 1})
    ptype = period.get('type', 'years')
    pvalue = period.get('value', 1)
    if ptype == 'years':
        return '{} год'.format(pvalue) if pvalue == 1 else '{} лет'.format(pvalue)
    elif ptype == 'days':
        return '{} дней'.format(pvalue)
    elif ptype == 'dates':
        return '{} -> {}'.format(period.get('start', '?'), period.get('end', '?'))
    return '1 год'


def calc_pair_data(pair_str, period_label='1 год', step=5):
    df5 = load_analytics_df('Analytics_Z')
    df10 = load_analytics_df('Analytics_Z_10')

    if df5.empty:
        return None

    row5 = df5[(df5['Период'] == period_label) & (df5['Пара'] == pair_str)]
    row10 = df10[(df10['Период'] == period_label) & (df10['Пара'] == pair_str)]

    if row5.empty:
        return None

    r5 = row5.iloc[0]

    result = {
        'pair': pair_str,
        'period': period_label,
        'sminZ': float(r5.get('sminZ', 0)),
        'smaxZ': float(r5.get('smaxZ', 0)),
        'min_z': float(r5.get('Мин Z', 0)),
        'max_z': float(r5.get('Макс Z', 0)),
        'mean_z': float(r5.get('Z средняя', 0)),
        'extrema_5': int(r5.get('Экстремумы', 0)),
        'pmin_5': float(r5.get('P min')) if not pd.isna(r5.get('P min')) else None,
        'pmax_5': float(r5.get('P max')) if not pd.isna(r5.get('P max')) else None,
        'repeats_5': int(r5.get('Уровней с повтором', 0)),
        'pmin_10': None,
        'pmax_10': None,
        'extrema_10': 0,
        'repeats_10': 0,
    }

    if not row10.empty:
        r10 = row10.iloc[0]
        result['extrema_10'] = int(r10.get('Экстремумы', 0))
        result['repeats_10'] = int(r10.get('Уровней с повтором', 0))
        if not pd.isna(r10.get('P min')):
            result['pmin_10'] = float(r10.get('P min'))
        if not pd.isna(r10.get('P max')):
            result['pmax_10'] = float(r10.get('P max'))

    sub = load_strategy_df('A_1_год')
    if not sub.empty:
        srow = sub[sub['Пара'] == pair_str]
        if not srow.empty:
            result['trades'] = int(srow.iloc[0].get('Сделок', 0))
            result['profit_a'] = float(srow.iloc[0].get('Доходность (после), %', 0))
        else:
            result['trades'] = 0
            result['profit_a'] = 0.0
    else:
        result['trades'] = 0
        result['profit_a'] = 0.0

    sub_b = load_strategy_df('B_1_год')
    if not sub_b.empty:
        srow = sub_b[sub_b['Пара'] == pair_str]
        if not srow.empty:
            result['profit_b'] = float(srow.iloc[0].get('Доходность (после), %', 0))
        else:
            result['profit_b'] = 0.0
    else:
        result['profit_b'] = 0.0

    return result


def format_pair_short(data, level='basic'):
    msg = "[CRYPTO] /pair {}\n\n".format(data['pair'])
    msg += "Период: {}\n".format(data['period'])
    msg += "Z: {:.4f} (min {:.4f}, max {:.4f})\n".format(
        data['mean_z'], data['min_z'], data['max_z'])
    msg += "\n"
    msg += "Границы:\n"
    msg += "  Pmin (5%): {} | Pmax (5%): {}\n".format(data['pmin_5'], data['pmax_5'])
    msg += "  Pmin (10%): {} | Pmax (10%): {}\n".format(data['pmin_10'], data['pmax_10'])
    msg += "\n"
    msg += "Сделок: {}\n".format(data['trades'])
    msg += "Доходность: A: {:+.2f}%, B: {:+.2f}%\n".format(
        data['profit_a'], data['profit_b'])
    return msg


def format_pair_full(data, level='priority', step=5):
    msg = "[CRYPTO] /pair {}\n\n".format(data['pair'])
    msg += "STEP: {}% | Период: {}\n".format(step, data['period'])
    msg += "Z: {:.4f}\n".format(data['mean_z'])
    msg += "\n"
    msg += "sminZ: {:.4f} | smaxZ: {:.4f}\n".format(data['sminZ'], data['smaxZ'])
    msg += "\n"
    msg += "Границы:\n"
    msg += "  Pmin (5%): {} | Pmax (5%): {}\n".format(data['pmin_5'], data['pmax_5'])
    msg += "  Pmin (10%): {} | Pmax (10%): {}\n".format(data['pmin_10'], data['pmax_10'])
    msg += "\n"
    msg += "Сделок: {} | Повтор: {}\n".format(data['trades'], data['repeats_5'])
    msg += "Доходность: A: {:+.2f}%, B: {:+.2f}%\n".format(
        data['profit_a'], data['profit_b'])
    return msg




# ---------- МЕНЮ (ТЕКСТ) ----------
def format_start(user_id):
    user = get_user(user_id)
    level = user.get('level', 'basic')

    msg = "[CRYPTO] 👋 Добро пожаловать!\n\n"
    msg += "📊 Парный трейдинг: Z = X/Y.\n"
    msg += "Используйте меню ниже.\n\n"

    if level == 'basic':
        msg += "🔒 Стандартный доступ:\n"
        msg += "  • /pair BTC ETH — данные (1 год)\n"
        msg += "  • /keep BTC ETH — фильтр (1 пара)\n"
        msg += "  • /help\n\n"
        msg += "📨 Рассылка:\n"
        msg += "  • Только по 1 паре\n"
        msg += "  • Общие сигналы\n\n"


    elif level == 'priority':
        msg += "⭐ Приоритетный доступ:\n"
        msg += "  • /pair BTC ETH — данные (5/3/1 год)\n"
        msg += "  • /check DOT XCH — анализ + рекомендация\n"
        msg += "  • /find BTC — топ-5 пар\n"
        msg += "  • /keep — фильтр (до 20 пар)\n"
        msg += "  • /status\n\n"
        msg += "📨 Рассылка:\n"
        msg += "  • Отдельно по каждой паре (до 20)\n"
        msg += "  • Рекомендация старта\n"
        msg += "  • Уведомления коридора\n\n"
        msg += "⭐⭐ Расширение — /superpriority CODE\n"

    elif level == 'superpriority':
        msg += "⭐⭐ Супер-приоритетный доступ:\n"
        msg += "  • Все функции priority\n"
        msg += "  • /add BTC NEWCOIN — добавить пару\n"
        msg += "  • /period, /step, /strategy\n"
        msg += "  • /keep (без ограничений)\n\n"
        msg += "📨 Рассылка:\n"
        msg += "  • Неограниченное количество пар\n\n"
        msg += "⭐⭐⭐ Расширение — /ssuperpriority CODE\n"

    elif level == 'ssuperpriority':
        msg += "⭐⭐⭐ СС-приоритетный доступ:\n"
        msg += "  • Все функции superpriority\n"
        msg += "  • /buy BTC — рекомендованная цена (2/мес)\n\n"
        msg += "📨 Рассылка:\n"
        msg += "  • Неограниченное количество пар\n"

    return msg


def format_help(user_id):
    user = get_user(user_id)
    level = user.get('level', 'basic')

    msg = "[CRYPTO] 📋 Справка\n\n"
    msg += "📋 Ввод сделки (8 полей):\n"
    msg += "  T1 P1 Q1 C1 T2 P2 Q2 C2\n"
    msg += "  Пример:\n"
    msg += "  DOT 1.1316 44.3566 0.10038 XCH 1.5045 33.2957 0.0665\n\n"

    msg += "📋 Команды (базовые):\n"
    msg += "  /start — приветствие\n"
    msg += "  /help — справка\n"
    msg += "  /status — статус\n"
    msg += "  /pair BTC ETH — данные по паре\n"
    msg += "  /keep BTC ETH — фильтр (1 пара)\n"

    if is_priority(user_id):
        msg += "\n📋 Команды (priority):\n"
        msg += "  /check DOT XCH — анализ\n"
        msg += "  /find BTC [N] — топ-N пар\n"
        msg += "  /keep ... — фильтр (до 20)\n"

    if is_super(user_id):
        msg += "\n📋 Команды (superpriority):\n"
        msg += "  /add BTC NEWCOIN — добавить пару\n"
        msg += "  /period — период\n"
        msg += "  /step — шаг\n"
        msg += "  /strategy — стратегия\n"

    if is_ss(user_id):
        msg += "\n📋 Команды (ssuperpriority):\n"
        msg += "  /buy BTC — рекомендованная цена (2/мес)\n"

    msg += "\n📋 Активация:\n"
    msg += "  /priority CODE\n"
    msg += "  /superpriority CODE\n"
    msg += "  /ssuperpriority CODE\n"

    return msg


def format_status(user_id):
    user = get_user(user_id)
    level = user.get('level', 'basic')

    msg = "[CRYPTO] /status\n\n"
    msg += "👤 Уровень: {}\n".format(level)
    msg += "📊 Стратегия: {}\n".format(user.get('strategy', 'AB'))
    msg += "📊 STEP: {}%\n".format(user.get('step', 5))

    period = user.get('period', {})
    msg += "📅 Период: {} {}\n".format(
        period.get('type', 'years'), period.get('value', 1))

    msg += "\n📋 Рассылки:\n"
    subs = user.get('subscriptions', {})
    for k, v in subs.items():
        msg += "  • {}: {}\n".format(k, "✅" if v else "❌")

    trades = user.get('trades', {})
    if trades:
        msg += "\n📋 Сделки ({}):\n".format(len(trades))
        for pair in trades:
            msg += "  • {}\n".format(pair)

    pp = user.get('priority_pairs', [])
    if pp:
        msg += "\n📋 Приоритетные ({}):\n".format(len(pp))
        for p in pp:
            msg += "  • {}\n".format(p)

    ko = user.get('keep_only', [])
    if ko:
        msg += "\n📋 Фильтр:\n"
        for p in ko:
            msg += "  • {}\n".format(p)

    return msg




# ---------- ОБРАБОТЧИКИ КОМАНД ----------
def handle_command(user_id, text):
    """Обрабатывает команду. Возвращает ответ (или None)."""
    parts = text.strip().split()
    if not parts:
        return None

    cmd = parts[0].lower()
    args = parts[1:]

    # /start
    if cmd == '/start':
        msg_text = format_start(user_id)
        send_message_with_reply_keyboard(user_id, msg_text)
        return None

    # /help
    if cmd == '/help':
        return format_help(user_id)

    # /status
    if cmd == '/status':
        return format_status(user_id)

    # /priority CODE
    if cmd == '/priority':
        if not args:
            return "[CRYPTO] Введите код: /priority CODE"
        code = args[0]
        if PRIORITY_CODE and code == PRIORITY_CODE:
            set_user_field(user_id, 'level', 'priority')
            return "[CRYPTO] ⭐ Приоритет активирован!"
        return "[CRYPTO] ❌ Неверный код."

    # /superpriority CODE
    if cmd == '/superpriority':
        if not args:
            return "[CRYPTO] Введите код: /superpriority CODE"
        code = args[0]
        if SUPERPRIORITY_CODE and code == SUPERPRIORITY_CODE:
            set_user_field(user_id, 'level', 'superpriority')
            return "[CRYPTO] ⭐⭐ Супер-приоритет активирован!"
        return "[CRYPTO] ❌ Неверный код."

    # /ssuperpriority CODE
    if cmd == '/ssuperpriority':
        if not args:
            return "[CRYPTO] Введите код: /ssuperpriority CODE"
        code = args[0]
        if SSUPERPRIORITY_CODE and code == SSUPERPRIORITY_CODE:
            set_user_field(user_id, 'level', 'ssuperpriority')
            return "[CRYPTO] ⭐⭐⭐ СС-приоритет активирован!"
        return "[CRYPTO] ❌ Неверный код."

    # /pair BTC ETH
    if cmd == '/pair':
        if len(args) < 2:
            return "[CRYPTO] Введите пару: /pair BTC ETH"
        pair = parse_pair(' '.join(args))
        if not pair:
            return "[CRYPTO] ❌ Неизвестная пара. Проверьте тикеры."
        pair_str = pair_to_str(pair)

        user = get_user(user_id)
        step = user.get('step', 5)

        if is_priority(user_id):
            period_label = calc_period_label(user)
        else:
            period_label = '1 год'

        data = calc_pair_data(pair_str, period_label, step)
        if not data:
            return "[CRYPTO] ❌ Нет данных по паре {} за {}.".format(pair_str, period_label)

        if is_priority(user_id):
            return format_pair_full(data, user.get('level', 'basic'), step)
        return format_pair_short(data)

    # /keep ...
    if cmd == '/keep':
        if not args:
            return "[CRYPTO] Введите пары: /keep BTC ETH"
        pairs = parse_pairs(' '.join(args))
        if not pairs:
            return "[CRYPTO] ❌ Неверный формат или неизвестные тикеры."

        user = get_user(user_id)
        limit = KEEP_LIMITS.get(user.get('level', 'basic'), 1)
        if len(pairs) > limit:
            return "[CRYPTO] ❌ Лимит {} пар для вашего уровня. Запрошено: {}.".format(
                limit, len(pairs))

        keep = [pair_to_str(p) for p in pairs]
        set_user_field(user_id, 'keep_only', keep)
        return "[CRYPTO] ✅ Фильтр обновлён:\n" + "\n".join("  • " + p for p in keep)

    # /clear
    if cmd == '/clear':
        set_user_field(user_id, 'keep_only', [])
        return "[CRYPTO] ✅ Фильтр сброшен."

    # Всё остальное — None (обработается как сделка)
    return None




# ---------- ОБРАБОТКА СДЕЛКИ ----------
def handle_trade(user_id, text):
    """Записывает сделку + добавляет в priority_pairs + отвечает."""
    trade = parse_trade(text)
    if not trade:
        return None

    ok, err = check_trade(trade)
    if not ok:
        return "[CRYPTO] ❌ Ошибка в сделке:\n{}".format(err)

    pair_str = '{}/{}'.format(trade['t1'], trade['t2'])
    today = datetime.now().strftime('%Y-%m-%d')

    user = get_user(user_id)
    trades = user.get('trades', {})

    initial = trade['q1'] * trade['p1']

    # Если q1 = 0 — только Y
    if trade['q1'] == 0:
        initial = trade['q2'] * trade['p2']

    trades[pair_str] = {
        'date': today,
        't1': trade['t1'], 'p1': trade['p1'], 'q1': trade['q1'], 'c1': trade['c1'],
        't2': trade['t2'], 'p2': trade['p2'], 'q2': trade['q2'], 'c2': trade['c2'],
        'initial': initial,
        'z_start': None,
        'level_X': None,
        'level_Y': None,
    }
    set_user_field(user_id, 'trades', trades)

    # В priority_pairs
    pp = user.get('priority_pairs', [])
    if pair_str not in pp:
        pp.append(pair_str)
        set_user_field(user_id, 'priority_pairs', pp)

    # Проверяем, есть ли вторая сторона
    warn = ""
    if trade['q1'] > 0 and (trade['q2'] == 0 or trade['p2'] == 0):
        warn = "\n⚠️ Y не выбран.\n→ /find {} — подбор\n→ /add {} NEWCOIN — добавить".format(
            trade['t1'], trade['t1'])
    elif trade['q2'] > 0 and (trade['q1'] == 0 or trade['p1'] == 0):
        warn = "\n⚠️ X не выбран.\n→ /find {} — подбор".format(trade['t2'])

    # Ответ
    msg = "[CRYPTO] ✅ Сделка записана\n\n"
    msg += "📅 Дата: {}\n".format(today)

    if trade['q1'] > 0:
        msg += "💰 Продано: {} {}  {}\n".format(
            trade['q1'], trade['t1'], trade['p1'])
    else:
        msg += "💰 Продано: —\n"

    if trade['q2'] > 0:
        msg += "💰 Куплено: {} {}  {}\n".format(
            trade['q2'], trade['t2'], trade['p2'])
    else:
        msg += "💰 Куплено: —\n"

    msg += "\n⭐ Добавлено в приоритет"
    msg += warn
    msg += "\n\n→ /check {} {}".format(trade['t1'], trade['t2'])

    return msg


# ---------- /check ----------
def handle_check(user_id, args):
    if not is_priority(user_id):
        return "[CRYPTO] ❌ /check — только для приоритетных.\n→ /priority CODE"

    if len(args) < 2:
        return "[CRYPTO] Введите пару: /check DOT XCH"

    pair = parse_pair(' '.join(args))
    if not pair:
        return "[CRYPTO] ❌ Неизвестная пара."

    pair_str = pair_to_str(pair)
    user = get_user(user_id)
    period_label = calc_period_label(user)
    step = user.get('step', 5)

    data = calc_pair_data(pair_str, period_label, step)
    if not data:
        return "[CRYPTO] ❌ Нет данных по паре {}.".format(pair_str)

    msg = "[CRYPTO] /check {}\n\n".format(pair_str)
    msg += "📅 Период: {}\n".format(period_label)
    msg += "📈 Z: {:.4f}\n".format(data['mean_z'])
    msg += "\n"
    msg += "sminZ: {:.4f} | smaxZ: {:.4f}\n".format(data['sminZ'], data['smaxZ'])
    msg += "\n"

    # Рекомендация старта
    z = data['mean_z']
    sminZ = data['sminZ']
    smaxZ = data['smaxZ']

    if smaxZ > 0 and abs(z - smaxZ) / smaxZ < 0.05:
        msg += "🔔 Z ≈ smaxZ ({}):\n   → X → Y (перелив)\n".format(smaxZ)
    elif sminZ > 0 and abs(z - sminZ) / sminZ < 0.05:
        msg += "🔔 Z ≈ sminZ ({}):\n   → Y → X (перелив)\n".format(sminZ)
    else:
        msg += "🔔 Z между границами.\n"

    msg += "\n📊 Границы:\n"
    msg += "  Pmin (5%): {} | Pmax (5%): {}\n".format(data['pmin_5'], data['pmax_5'])
    msg += "  Pmin (10%): {} | Pmax (10%): {}\n".format(data['pmin_10'], data['pmax_10'])
    msg += "\n📈 Сделок: {} | Повтор: {}\n".format(data['trades'], data['repeats_5'])
    msg += "💰 Доходность: A: {:+.2f}%, B: {:+.2f}%".format(
        data['profit_a'], data['profit_b'])
    return msg


# ---------- /find ----------
def handle_find(user_id, args):
    if not is_priority(user_id):
        return "[CRYPTO] ❌ /find — только для приоритетных.\n→ /priority CODE"

    if not args:
        return "[CRYPTO] Введите тикер: /find BTC"

    ticker = args[0].upper()
    top_n = 5
    if len(args) >= 2:
        try:
            top_n = min(int(args[1]), 10)
        except ValueError:
            pass

    if not is_available(ticker):
        return "[CRYPTO] ❌ Тикер {} неизвестен.\n→ /add {} NEWCOIN".format(ticker, ticker)

    df = load_strategy_df('A_5_лет')
    if df.empty:
        return "[CRYPTO] ❌ Нет данных."

    # Пары с тикером
    mask = df['Пара'].str.contains(ticker, case=False, na=False)
    sub = df[mask]

    if sub.empty:
        return "[CRYPTO] ⚠️ По тикеру {} ничего не найдено.\n→ /add {} NEWCOIN".format(ticker, ticker)

    # ТОП по доходности
    top_profit = sub.nlargest(top_n, 'Доходность (после), %')

    msg = "[CRYPTO] 🔍 Подбор пары для {}\n\n".format(ticker)
    msg += "📊 Всего пар с {}: {}\n\n".format(ticker, len(sub))

    msg += "🏆 ТОП-{} по доходности (A, 5 лет):\n".format(top_n)
    for i, (_, r) in enumerate(top_profit.iterrows(), 1):
        msg += "  {}. {}  {:+.2f}%\n".format(i, r['Пара'], r['Доходность (после), %'])

    msg += "\n→ /pair {} XCH\n→ /check {} XCH".format(ticker, ticker)
    return msg


# ---------- /add ----------
def handle_add(user_id, args):
    if not is_super(user_id):
        return "[CRYPTO] ❌ /add — только для superpriority+.\n→ /superpriority CODE"

    if len(args) < 2:
        return "[CRYPTO] Введите: /add BTC NEWCOIN"

    t1, t2 = args[0].upper(), args[1].upper()

    if not is_available(t1):
        return "[CRYPTO] ❌ {} неизвестен.".format(t1)

    if is_available(t2):
        return "[CRYPTO] ✅ {} уже доступен.\n→ /pair {} {}".format(t2, t1, t2)

    # Проверка через CoinGecko
    coin = check_ticker(t2)
    if not coin:
        return "[CRYPTO] ❌ Инструмент {} не найден.".format(t2)

    # Добавляем в EXTENDED
    add_extended_ticker(t2)

    msg = "[CRYPTO] ✅ {} добавлен.\n".format(t2)
    msg += "CoinGecko: {} ({})\n\n".format(coin.get('name'), coin.get('id'))
    msg += "⚠️ Пара {} / {} пока не в кэше.\n".format(t1, t2)
    msg += "Она появится после следующего запуска workflow.\n\n"
    msg += "→ /status — проверить\n"
    msg += "→ /pair {} {} — через 1 час".format(t1, t2)
    return msg


# ---------- /buy ----------
def handle_buy(user_id, args):
    if not is_ss(user_id):
        return "[CRYPTO] ❌ /buy — только для ssuperpriority.\n→ /ssuperpriority CODE"

    if not args:
        return "[CRYPTO] Введите: /buy BTC"

    ticker = args[0].upper()
    if not is_available(ticker):
        return "[CRYPTO] ❌ Тикер {} неизвестен.".format(ticker)

    user = get_user(user_id)
    month = datetime.now().strftime('%Y-%m')

    used = user.get('buy_requests_this_month', 0)
    if user.get('buy_month') != month:
        used = 0
        set_user_field(user_id, 'buy_requests_this_month', 0)
        set_user_field(user_id, 'buy_month', month)

    if used >= 2:
        return "[CRYPTO] ❌ Лимит 2 запроса в месяц.\nОсталось: 0"

    # Отправляем запрос админу
    today = datetime.now().strftime('%Y-%m-%d')
    admin_msg = "[CRYPTO] 📩 /buy запрос\n\n"
    admin_msg += "👤 User: {}\n".format(user_id)
    admin_msg += "📊 Инструмент: {}\n".format(ticker)
    admin_msg += "📅 Дата: {}\n".format(today)
    send_message(ADMIN_CHAT_ID, admin_msg)

    # Увеличиваем счётчик
    set_user_field(user_id, 'buy_requests_this_month', used + 1)
    set_user_field(user_id, 'buy_month', month)

    msg = "[CRYPTO] 🛒 Запрос рекомендованной цены\n\n"
    msg += "📊 Инструмент: {}\n".format(ticker)
    msg += "📅 Дата: {}\n\n".format(today)
    msg += "Запрос отправлен.\n"
    msg += "Ответ придёт в течение дня.\n\n"
    msg += "(осталось запросов в этом месяце: {})".format(2 - (used + 1))
    return msg


# ---------- MAIN LOOP ----------
def process_updates(offset=None):
    updates = get_updates(offset)
    result = updates.get('result', [])
    max_id = offset

    # Если offset=None — пропускаем ВСЕ старые (первый запуск)
    skip_old = (offset is None and len(result) > 0)

    if skip_old:
        # Только сохраняем max_id, не обрабатываем
        for upd in result:
            max_id = upd['update_id'] + 1
        print("SKIP old updates: {}".format(len(result)))
        return max_id

    for upd in result:
        max_id = upd['update_id'] + 1

        # Callback query (inline-кнопки)
        if 'callback_query' in upd:
            cb = upd['callback_query']
            user_id = cb['from']['id']
            data = cb.get('data', '')
            response = handle_callback(user_id, data)
            if response:
                send_message(user_id, response)
            continue

        msg = upd.get('message')
        if not msg:
            continue

        # Успешная оплата
        if 'successful_payment' in msg:
            user_id = msg['from']['id']
            payment = msg['successful_payment']
            payload = payment.get('invoice_payload', '')

            parts = payload.split('_')
            if len(parts) >= 4 and parts[0] == 'level':
                level = parts[1]
                days = int(parts[3])

                from subscription import activate_level
                activate_level(user_id, level, days)

                send_message(user_id,
                    "[CRYPTO] ⭐ Уровень активирован!\n\n"
                    "Уровень: {}\n"
                    "На {} дней".format(level, days))

                send_message(ADMIN_CHAT_ID,
                    "[CRYPTO] 💰 Оплата\n\n"
                    "👤 User: {}\n"
                    "⭐ Уровень: {}\n"
                    "📅 {} дней".format(user_id, level, days))
            continue

        user_id = msg['from']['id']
        text = msg.get('text', '').strip()
        if not text:
            continue

        # Reply-кнопки (📊 Данные, 🔍 Проверить, ...)
        # Reply-кнопка ⭐ Приоритет — отдельная обработка
        if text == '⭐ Приоритет':
            msg_text = format_priority_menu()
            keyboard = priority_levels_keyboard()
            url = "{}/bot{}/sendMessage".format(TG_PROXY, TG_TOKEN)
            payload = {
                "chat_id": user_id,
                "text": msg_text,
                "parse_mode": 'HTML',
                "reply_markup": json.dumps(keyboard),
            }
            try:
                requests.post(url, json=payload, timeout=30)
            except Exception as e:
                print("Error: {}".format(e))
            continue

        reply_map = {
            '📊 Данные': '/pair',
            '🔍 Проверить': '/check',
            '📋 Статус': '/status',
            '❓ Помощь': '/help',
        }
        if text in reply_map:
            text = reply_map[text]

        # Команда?
        if text.startswith('/'):
            parts = text.split()
            cmd = parts[0].lower()
            args = parts[1:]

            # Админ-команды
            if cmd in ['/gencode', '/activate', '/codes']:
                response = handle_admin_command(user_id, cmd, args)
            # Оплата
            elif cmd in ['/priority', '/superpriority', '/ssuperpriority']:
                level = cmd.replace('/', '')
                msg_text = format_pay_menu(level)
                keyboard = pay_menu_keyboard(level)
                send_message(user_id, msg_text, reply_markup=keyboard)
                continue
            elif cmd == '/redeem':
                if not args:
                    response = "[CRYPTO] Отправьте код: /redeem PRIO-2026-XXXX"
                else:
                    ok, msg = redeem_code(user_id, args[0])
                    if ok:
                        response = "[CRYPTO] ⭐ " + msg
                    else:
                        response = "[CRYPTO] ❌ " + msg
            # Остальные
            elif cmd == '/check':
                response = handle_check(user_id, args)
            elif cmd == '/find':
                response = handle_find(user_id, args)
            elif cmd == '/add':
                response = handle_add(user_id, args)
            elif cmd == '/buy':
                response = handle_buy(user_id, args)
            else:
                response = handle_command(user_id, text)

            if response:
                send_message(user_id, response)
            continue

        # Сделка?
        trade_msg = handle_trade(user_id, text)
        if trade_msg:
            send_message(user_id, trade_msg)
            continue

        # Не понял
        send_message(user_id, "[CRYPTO] ❌ Не понимаю. Используйте /start.")

    return max_id


def load_offset():
    if os.path.exists('last_update_id.txt'):
        try:
            with open('last_update_id.txt', 'r') as f:
                return int(f.read().strip())
        except Exception:
            pass
    return None


def save_offset(offset):
    if offset:
        with open('last_update_id.txt', 'w') as f:
            f.write(str(offset))


if __name__ == '__main__':
    print("Bot: single poll...")
    offset = load_offset()
    print("Offset: {}".format(offset))
    try:
        new_offset = process_updates(offset)
        save_offset(new_offset)
        print("New offset: {}".format(new_offset))
    except Exception as e:
        print("Error: {}".format(e))
        import traceback
        traceback.print_exc()
    print("Bot: done.")


# ---------- ОПЛАТА (STARS) ----------
def send_invoice_stars(chat_id, level, period):
    """Отправляет инвойс Stars."""
    price = STARS_PRICES.get((level, period), 0)
    if price <= 0:
        return False

    days = PERIOD_DAYS.get(period, 30)
    titles = {
        'priority': 'Priority',
        'superpriority': 'Superpriority',
        'ssuperpriority': 'SSuperpriority',
    }
    period_label = '1 месяц' if period == '1m' else '1 год'

    url = "{}/bot{}/sendInvoice".format(TG_PROXY, TG_TOKEN)
    payload = {
        "chat_id": chat_id,
        "title": "{} — {}".format(titles[level], period_label),
        "description": "Активация уровня {} на {}".format(level, period_label),
        "payload": "level_{}_{}_{}".format(level, period, days),
        "currency": "XTR",
        "prices": [{"label": titles[level], "amount": price}],
    }
    try:
        r = requests.post(url, json=payload, timeout=30)
        return r.status_code == 200
    except Exception as e:
        print("[invoice] error: {}".format(e))
        return False


def format_pay_menu(level):
    """Меню оплаты для уровня."""
    titles = {
        'priority': '⭐ Priority',
        'superpriority': '⭐⭐ Superpriority',
        'ssuperpriority': '⭐⭐⭐ SSuperpriority',
    }

    msg = "[CRYPTO] {} доступ\n\n".format(titles.get(level, level))
    msg += "Выберите период:\n\n"

    p1m = STARS_PRICES.get((level, '1m'), 0)
    p1y = STARS_PRICES.get((level, '1y'), 0)

    msg += "📅 1 месяц — {} ⭐\n".format(p1m)
    msg += "📅 1 год — {} ⭐ (-20%)\n".format(p1y)
    msg += "\nВыберите или /redeem CODE"
    return msg


# ---------- ОБРАБОТКА CALLBACK ----------
def handle_callback(user_id, data):
    """Обработка inline-кнопок."""
    # Главное меню
    if data == 'menu_pair':
        return "[CRYPTO] 📊 Введите пару:\n/pair BTC ETH"

    if data == 'menu_check':
        return "[CRYPTO] 🔍 Введите пару:\n/check BTC ETH"

    if data == 'menu_priority':
        return None

    if data == 'show_priority':
        msg_text = format_pay_menu('priority')
        keyboard = pay_menu_keyboard('priority')
        # Отправляем отдельно
        url = "{}/bot{}/sendMessage".format(TG_PROXY, TG_TOKEN)
        payload = {
            "chat_id": user_id,
            "text": msg_text,
            "parse_mode": 'HTML',
            "reply_markup": json.dumps(keyboard),
        }
        try:
            requests.post(url, json=payload, timeout=30)
        except Exception:
            pass
        return None

    if data == 'show_superpriority':
        msg_text = format_pay_menu('superpriority')
        keyboard = pay_menu_keyboard('superpriority')
        url = "{}/bot{}/sendMessage".format(TG_PROXY, TG_TOKEN)
        payload = {
            "chat_id": user_id,
            "text": msg_text,
            "parse_mode": 'HTML',
            "reply_markup": json.dumps(keyboard),
        }
        try:
            requests.post(url, json=payload, timeout=30)
        except Exception:
            pass
        return None

    if data == 'show_ssuperpriority':
        msg_text = format_pay_menu('ssuperpriority')
        keyboard = pay_menu_keyboard('ssuperpriority')
        url = "{}/bot{}/sendMessage".format(TG_PROXY, TG_TOKEN)
        payload = {
            "chat_id": user_id,
            "text": msg_text,
            "parse_mode": 'HTML',
            "reply_markup": json.dumps(keyboard),
        }
        try:
            requests.post(url, json=payload, timeout=30)
        except Exception:
            pass
        return None

    if data == 'menu_status':
        return format_status(user_id)

    if data == 'menu_help':
        return format_help(user_id)

    # pay_priority_1m
    if data.startswith('pay_'):
        parts = data.split('_')
        if len(parts) >= 3:
            level = parts[1]
            period = parts[2]  # '1m' или '1y'
            send_invoice_stars(user_id, level, period)
        return None

    # redeem_start
    if data == 'redeem_start':
        return "[CRYPTO] Отправьте код:\n/redeem PRIO-2026-XXXX"

    return None


# ---------- АДМИН-КОМАНДЫ ----------
def handle_admin_command(user_id, cmd, args):
    """Обработка админ-команд."""
    if not is_admin(user_id):
        return "[CRYPTO] ❌ Только для админа."

    # /gencode LEVEL [DAYS]
    if cmd == '/gencode':
        if not args:
            return "[CRYPTO] Формат: /gencode LEVEL [DAYS]\nПример: /gencode priority 30"
        level = args[0].lower()
        days = 30
        if len(args) >= 2:
            try:
                days = int(args[1])
            except ValueError:
                pass
        if level not in ['priority', 'superpriority', 'ssuperpriority']:
            return "[CRYPTO] ❌ Неверный уровень. Доступно: priority, superpriority, ssuperpriority."
        code = generate_code(level, days)
        return "[CRYPTO] 🔑 Код создан\n\nКод: {}\nУровень: {}\nПериод: {} дней\n\nПередайте пользователю.".format(
            code, level, days)

    # /activate USER_ID LEVEL [DAYS]
    if cmd == '/activate':
        if len(args) < 2:
            return "[CRYPTO] Формат: /activate USER_ID LEVEL [DAYS]"
        target_id = args[0]
        level = args[1].lower()
        days = 30
        if len(args) >= 3:
            try:
                days = int(args[2])
            except ValueError:
                pass
        if level not in SUB_LEVELS:
            return "[CRYPTO] ❌ Неверный уровень."
        activate_level(target_id, level, days)
        send_message(target_id, "[CRYPTO] ⭐ Уровень активирован: {} на {} дней.".format(level, days))
        return "[CRYPTO] ✅ Активирован {} → {} ({})".format(target_id, level, days)

    # /codes
    if cmd == '/codes':
        codes = list_codes()
        if not codes:
            return "[CRYPTO] Нет кодов."
        msg = "[CRYPTO] 🔑 Коды ({}):\n\n".format(len(codes))
        for code, info in list(codes.items())[-10:]:
            used = "✅ использован" if info.get('used_by') else "🔓 активен"
            msg += "{}  {}  {}д  {}\n".format(code, info['level'], info['days'], used)
        return msg

    return None


