#!/usr/bin/env python3
"""tg_dispatcher.py — Telegram-уведомления."""

import requests
from core import config_manager


def send_alert(message):
    s = config_manager.get_settings()
    token = s.get("tg_bot_token", "")
    chat_id = s.get("tg_chat_id", "")
    if not token or not chat_id:
        print(f"[tg] (не настроен) {message}")
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": f"⚡ Anectium\n\n{message}", "parse_mode": "HTML"},
            timeout=10
        )
        return r.status_code == 200
    except Exception as e:
        print(f"[tg] Ошибка: {e}")
        return False
