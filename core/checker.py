#!/usr/bin/env python3
"""
checker.py — мониторинг модемов: жив/мёртв, WAN IP, статус.
"""

import time
import subprocess
import requests
from core import config_manager

CHECK_IP_URLS = [
    "http://checkip.amazonaws.com/",
    "https://api.ipify.org/?format=json",
    "https://ip.seeip.org/jsonip",
    "http://ipinfo.io/json",
    "https://api.myip.com",
]


def check_modem_ping(ip_local):
    """Пинг модема."""
    try:
        r = subprocess.run(["ping", "-c", "1", "-W", "2", ip_local],
                           capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def check_proxy_alive(login, password, port_http):
    """Проверяет прокси через тестовый HTTP-запрос."""
    proxy_url = f"http://{login}:{password}@127.0.0.1:{port_http}"
    for url in CHECK_IP_URLS[:2]:
        try:
            r = requests.get(url, proxies={"http": proxy_url, "https": proxy_url},
                             timeout=10)
            if r.status_code == 200:
                return True, r.text.strip()
        except Exception:
            continue
    return False, None


def get_status(modem):
    """
    🟢 online   — модем пингуется, прокси работает
    🟡 degraded — модем пингуется, прокси нет
    🔴 offline  — модем не пингуется
    """
    if not check_modem_ping(modem.get("ip_local", "")):
        return "offline", None

    ok, wan_ip = check_proxy_alive(
        modem.get("login", ""),
        modem.get("password", ""),
        modem.get("port_http", 0)
    )
    if ok:
        return "online", wan_ip
    return "degraded", None


def run_check_cycle():
    """Один цикл проверки всех модемов."""
    modems = config_manager.list_modems()
    results = {}

    for modem_id, modem in modems.items():
        status, wan_ip = get_status(modem)
        config_manager.update_modem(modem_id, status=status, last_check=time.time())
        results[modem_id] = {"status": status, "wan_ip": wan_ip}

        if status == "offline":
            from core.tg_dispatcher import send_alert
            send_alert(f"🔴 {modem_id} OFFLINE — {modem.get('ip_local')}")
        elif status == "degraded":
            from core.tg_dispatcher import send_alert
            send_alert(f"🟡 {modem_id} degraded — прокси не отвечает")

    return results


def run_loop(interval=60):
    """Бесконечный цикл проверки."""
    print(f"[checker] Запущен, интервал: {interval}с")
    while True:
        try:
            results = run_check_cycle()
            online = sum(1 for r in results.values() if r["status"] == "online")
            print(f"[checker] {online}/{len(results)} онлайн")
        except Exception as e:
            print(f"[checker] Ошибка: {e}")
        time.sleep(interval)
