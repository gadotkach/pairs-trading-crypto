"""Ежедневная рассылка приоритетным пользователям."""
import os
import json
import requests
import pandas as pd
from datetime import datetime

TG_PROXY = os.environ.get("TG_PROXY", "https://tg-proxy.shvaboe.workers.dev")
TG_TOKEN = os.environ.get("TG_TOKEN", "")

STATE_FILE = 'user_state.json'
ANALYTICS_FILE = 'analytics_z.xlsx'

PREFIX = "[CRYPTO] "


def load_state():
    if not os.path.exists(STATE_FILE):
        return {'users': {}}
    with open(STATE_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def send_message(chat_id, text):
    url = "{}/bot{}/sendMessage".format(TG_PROXY, TG_TOKEN)
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=30)
        return r.status_code == 200
    except Exception as e:
        print("[telegram] error: {}".format(e))
        return False


def check_subscription(user):
    level = user.get('level', 'basic')
    if level == 'basic':
        return False
    expires = user.get('level_expires_at')
    if not expires:
        return False
    try:
        exp = datetime.fromisoformat(expires)
        if datetime.now() > exp:
            return False
    except Exception:
        return False
    return True


def format_pair_msg(pair, r5, r10):
    msg = "\n📊 {}".format(pair) + "\n"
    msg += "  Z: {:.4f}\n".format(r5.get('Z средняя', 0))
    msg += "  sminZ: {:.4f} | smaxZ: {:.4f}\n".format(
        r5.get('sminZ', 0), r5.get('smaxZ', 0))

    pmin5 = r5.get('P min')
    pmax5 = r5.get('P max')
    pmin10 = r10.get('P min') if r10 is not None else None
    pmax10 = r10.get('P max') if r10 is not None else None

    if not pd.isna(pmin5) and not pd.isna(pmax5):
        msg += "  P 5%: {} | {}\n".format(pmin5, pmax5)
    if pmin10 is not None and pmax10 is not None and not pd.isna(pmin10) and not pd.isna(pmax10):
        msg += "  P 10%: {} | {}\n".format(pmin10, pmax10)

    z = r5.get('Z средняя', 0)
    sminZ = r5.get('sminZ', 0)
    smaxZ = r5.get('smaxZ', 0)
    if smaxZ > 0 and abs(z - smaxZ) / smaxZ < 0.05:
        msg += "  🔔 Z ≈ smaxZ → X → Y\n"
    elif sminZ > 0 and abs(z - sminZ) / sminZ < 0.05:
        msg += "  🔔 Z ≈ sminZ → Y → X\n"

    return msg


def main():
    print("=" * 60)
    print("Priority report: {}".format(datetime.now()))
    print("=" * 60)

    state = load_state()
    users = state.get('users', {})

    if not users:
        print("Нет пользователей")
        return

    try:
        df5 = pd.read_excel(ANALYTICS_FILE, sheet_name='Analytics_Z')
        df10 = pd.read_excel(ANALYTICS_FILE, sheet_name='Analytics_Z_10')
    except Exception as e:
        print("Ошибка analytics: {}".format(e))
        return

    n_sent = 0
    for user_id, user in users.items():
        if not check_subscription(user):
            continue

        pairs = user.get('priority_pairs', []) or user.get('keep_only', [])
        if not pairs:
            continue

        msg = "{}📊 Ежедневный отчёт".format(PREFIX) + "\n"
        msg += "📅 {}\n".format(datetime.now().strftime('%d.%m.%Y'))

        has_data = False
        for pair in pairs:
            row5 = df5[(df5['Период'] == '3 года') & (df5['Пара'] == pair)]
            row10 = df10[(df10['Период'] == '3 года') & (df10['Пара'] == pair)]
            if row5.empty:
                continue
            r5 = row5.iloc[0]
            r10 = row10.iloc[0] if not row10.empty else None
            msg += format_pair_msg(pair, r5, r10)
            has_data = True

        if has_data and send_message(user_id, msg):
            n_sent += 1
            print("Sent to {}".format(user_id))

    print("=" * 60)
    print("Отправлено: {}".format(n_sent))
    print("=" * 60)


if __name__ == '__main__':
    main()
