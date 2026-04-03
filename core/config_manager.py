#!/usr/bin/env python3
"""
config_manager.py — CRUD для db.json.
"""

import os
import json
import shutil
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "db.json")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")


def _load():
    with open(DB_PATH, "r") as f:
        return json.load(f)

def _save(db):
    with open(DB_PATH, "w") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


def init_db():
    """Создаёт пустую БД если нет."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    if not os.path.exists(DB_PATH):
        db = {
            "servers": {},
            "modems": {},
            "settings": {
                "public_ip": "",
                "local_ip": "0.0.0.0",
                "dns_servers": ["1.1.1.1", "8.8.8.8"],
                "maxconn": 250,
                "deny_ports": "587,3389,389,53413,465,25,2525",
                "deny_networks": ["172.16.0.0/12", "10.0.0.0/8"],
                "tg_bot_token": "",
                "tg_chat_id": "",
                "check_interval_sec": 60,
                "reconnect_cooldown_sec": 120
            }
        }
        _save(db)
        print(f"[db] Создана: {DB_PATH}")


def backup():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = os.path.join(BACKUP_DIR, f"db_{ts}.json")
    shutil.copy2(DB_PATH, dst)
    return dst


# ── Серверы ──

def add_server(server_id, name, ip, proxmox_url="", router_url=""):
    db = _load()
    db["servers"][server_id] = {
        "name": name, "ip": ip,
        "proxmox_url": proxmox_url,
        "router_url": router_url,
        "status": "unknown"
    }
    _save(db)

def remove_server(server_id):
    db = _load()
    db["servers"].pop(server_id, None)
    to_rm = [k for k, v in db["modems"].items() if v.get("server_id") == server_id]
    for k in to_rm:
        del db["modems"][k]
    _save(db)

def list_servers():
    return _load()["servers"]


# ── Модемы ──

def add_modem(modem_id, server_id, modem_type, ip_local,
              port_http, port_socks, login, password,
              operator="", sim_number="", webui_ip=""):
    db = _load()
    db["modems"][modem_id] = {
        "server_id": server_id,
        "type": modem_type,           # e3372h | b525 | android
        "ip_local": ip_local,         # IP для -e в 3proxy (LAN IP модема, обычно 192.168.X.100)
        "webui_ip": webui_ip or ip_local.rsplit(".", 1)[0] + ".1",  # WebUI (обычно .1)
        "port_http": port_http,
        "port_socks": port_socks,
        "login": login,
        "password": password,
        "operator": operator,
        "sim_number": sim_number,
        "status": "unknown",
        "last_check": None,
        "last_reconnect": None
    }
    _save(db)

def remove_modem(modem_id):
    db = _load()
    db["modems"].pop(modem_id, None)
    _save(db)

def update_modem(modem_id, **fields):
    db = _load()
    if modem_id in db["modems"]:
        db["modems"][modem_id].update(fields)
        _save(db)
    return db["modems"].get(modem_id)

def list_modems(server_id=None):
    db = _load()
    if server_id:
        return {k: v for k, v in db["modems"].items() if v.get("server_id") == server_id}
    return db["modems"]

def get_modem(modem_id):
    return _load()["modems"].get(modem_id)


# ── Настройки ──

def get_settings():
    return _load().get("settings", {})

def update_settings(**fields):
    db = _load()
    db.setdefault("settings", {}).update(fields)
    _save(db)
