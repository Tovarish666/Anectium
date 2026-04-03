#!/usr/bin/env python3
"""
proxy_engine.py — генерация config.cfg для 3proxy + управление процессом.
Формат конфига приближен к боевому.
"""

import os
import json
import subprocess
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROXY_DIR = os.path.join(BASE_DIR, "3proxy")
CONFIG_PATH = os.path.join(PROXY_DIR, "config.cfg")
BINARY_PATH = os.path.join(PROXY_DIR, "3proxy")
LOG_DIR = os.path.join(PROXY_DIR, "logs")
USERS_PATH = os.path.join(PROXY_DIR, "users")
DENY_LIST_PATH = os.path.join(BASE_DIR, "data", "deny_list_domain.txt")
DB_PATH = os.path.join(BASE_DIR, "data", "db.json")

# ── Маппинг оператор → домены для блокировки ──

OPERATOR_DENY = {
    "yota":       "yota.ru,*.yota.ru",
    "мтс":        "mts.ru,*.mts.ru",
    "mts":        "mts.ru,*.mts.ru",
    "билайн":     "beeline.ru,*.beeline.ru",
    "beeline":    "beeline.ru,*.beeline.ru",
    "мегафон":    "megafon.ru,*.megafon.ru",
    "megafon":    "megafon.ru,*.megafon.ru",
    "tele2":      "tele2.ru,*.tele2.ru",
    "теле2":      "tele2.ru,*.tele2.ru",
    "ростелеком": "rt.ru,*.rt.ru",
}


def _load_db():
    with open(DB_PATH, "r") as f:
        return json.load(f)


def _operator_deny(operator):
    op = (operator or "").strip().lower()
    for key, domains in OPERATOR_DENY.items():
        if key in op:
            return domains
    return ""


def generate_users_file(modems):
    """Генерирует файл users: login:CL:password через пробел."""
    entries = []
    for m in modems.values():
        login = m.get("login", "")
        password = m.get("password", "")
        if login and password:
            entries.append(f"{login}:CL:{password}")
    os.makedirs(os.path.dirname(USERS_PATH), exist_ok=True)
    with open(USERS_PATH, "w") as f:
        f.write(" ".join(entries) + "\n")


def generate_config():
    """Генерирует config.cfg из db.json."""
    db = _load_db()
    modems = db.get("modems", {})
    s = db.get("settings", {})

    public_ip = s.get("public_ip", "")
    local_ip = s.get("local_ip", "0.0.0.0")
    dns_list = s.get("dns_servers", ["1.1.1.1", "8.8.8.8"])
    maxconn = s.get("maxconn", 250)
    deny_ports = s.get("deny_ports", "587,3389,389,53413,465,25,2525")
    deny_networks = s.get("deny_networks", ["172.16.0.0/12", "10.0.0.0/8"])

    generate_users_file(modems)

    L = []
    L.append(f"# Anectium — auto {time.strftime('%Y-%m-%d %H:%M:%S')}")
    L.append(f"# modems: {len(modems)}")
    L.append("")
    L.append(f'monitor "{CONFIG_PATH}"')
    L.append("")

    for dns in dns_list:
        L.append(f"nserver {dns}")
    L.append("")
    L.append("nscache 65536")
    L.append("nscache6 65536")
    L.append("")

    if public_ip:
        L.append(f"public_ip {public_ip}")
        L.append("")

    L.append("timeouts 1 5 30 60 180 1800 15 60")
    L.append("")
    L.append(f'log "{LOG_DIR}/3proxy.log" H')
    L.append('logformat "L%Y-%m-%d %H:%M:%S %N.%p %E %U %C:%c %R:%r %Q:%q %O %I %n %T"')
    L.append("rotate 30")
    L.append("")
    L.append(f'users $"{USERS_PATH}"')
    L.append("")

    deny_file = DENY_LIST_PATH if os.path.exists(DENY_LIST_PATH) else None

    for mid, m in modems.items():
        login = m.get("login", "")
        modem_ip = m.get("ip_local", "")
        port_http = m.get("port_http")
        port_socks = m.get("port_socks")
        operator = m.get("operator", "")

        if not all([login, modem_ip, port_http, port_socks]):
            continue

        L.append(f"# {mid} | {operator} | {modem_ip}")
        L.append("auth strong")

        # allow по IP (без точек — формат iponly)
        ip_allow = modem_ip.replace(".", "")
        L.append(f"allow {ip_allow}")

        # deny домены оператора
        op_deny = _operator_deny(operator)
        if op_deny:
            L.append(f'deny * * "{op_deny}" * *')

        # deny порты
        if deny_ports:
            L.append(f"deny * * * {deny_ports}")

        # deny сети
        for net in deny_networks:
            L.append(f"deny * * {net} * *")

        # deny list файл
        if deny_file:
            L.append(f'deny * * $"{deny_file}" * *')

        # allow по логину
        L.append(f"allow {login}")
        L.append(f"maxconn {maxconn}")
        L.append(f"proxy -n -a -p{port_http} -i{local_ip} -e{modem_ip}")
        L.append(f"socks -n -a -p{port_socks} -i{local_ip} -e{modem_ip}")
        L.append("flush")
        L.append("")

    os.makedirs(PROXY_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        f.write("\n".join(L))

    print(f"[3proxy] Конфиг: {len(modems)} модемов -> {CONFIG_PATH}")
    return CONFIG_PATH


# ── Управление процессом ─────────────────────────

def start():
    if not os.path.exists(BINARY_PATH):
        print(f"[3proxy] Бинарник не найден: {BINARY_PATH}")
        return False
    if not os.path.exists(CONFIG_PATH):
        generate_config()
    subprocess.Popen([BINARY_PATH, CONFIG_PATH],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)
    print(f"[3proxy] Запущен")
    return True


def stop():
    subprocess.run(["killall", "3proxy"], capture_output=True)
    time.sleep(0.3)
    print("[3proxy] Остановлен")


def restart():
    stop()
    generate_config()
    start()


def reload_config():
    """Hot-reload: перегенерировать конфиг, 3proxy подхватит через monitor."""
    generate_config()


def is_running():
    return subprocess.run(["pgrep", "-x", "3proxy"], capture_output=True).returncode == 0


def ensure_running():
    if not is_running():
        print("[3proxy] Не запущен, запускаю...")
        start()
