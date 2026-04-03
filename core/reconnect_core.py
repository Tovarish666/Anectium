#!/usr/bin/env python3
"""
reconnect_core.py — центральный диспетчер реконнектов.

- Кулдаун (по умолчанию 120 сек)
- Защита от дублирующих операций
- Circuit breaker (5 фейлов подряд → пауза 60 сек)
- Лог реконнектов
"""

import time
import json
import os
import threading

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECONNECT_LOG = os.path.join(BASE_DIR, "data", "reconnect_log.json")

# {modem_id: timestamp} — последний реконнект
_last_reconnect = {}

# {modem_id: True} — активная операция
_active = {}
_lock = threading.Lock()

# Circuit breaker: {modem_id: {"fails": int, "last_fail": float}}
_circuit = {}
CIRCUIT_THRESHOLD = 5
CIRCUIT_TIMEOUT = 60


def _load_log():
    if os.path.exists(RECONNECT_LOG):
        try:
            with open(RECONNECT_LOG, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_log(data):
    os.makedirs(os.path.dirname(RECONNECT_LOG), exist_ok=True)
    with open(RECONNECT_LOG, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _check_circuit(modem_id):
    """Проверяет circuit breaker. True = можно, False = заблокирован."""
    cb = _circuit.get(modem_id)
    if not cb:
        return True
    if cb["fails"] >= CIRCUIT_THRESHOLD:
        if time.time() - cb["last_fail"] < CIRCUIT_TIMEOUT:
            return False
        # таймаут прошёл — сбрасываем
        del _circuit[modem_id]
    return True


def _record_fail(modem_id):
    cb = _circuit.get(modem_id, {"fails": 0, "last_fail": 0})
    cb["fails"] += 1
    cb["last_fail"] = time.time()
    _circuit[modem_id] = cb


def _record_success(modem_id):
    _circuit.pop(modem_id, None)


def reconnect(modem_id, modem_type, ip_local, cooldown=120, method="full"):
    """
    Реконнект модема.

    Args:
        modem_id: идентификатор модема
        modem_type: "e3372h" | "b525" | "android"
        ip_local: IP модема в локальной сети
        cooldown: минимальный интервал между реконнектами (сек)
        method: "soft" | "full" | "reboot"

    Returns:
        dict: {success, message, new_ip, old_ip}
    """
    now = time.time()

    # кулдаун
    last = _last_reconnect.get(modem_id, 0)
    if now - last < cooldown:
        remaining = int(cooldown - (now - last))
        return {
            "success": False,
            "message": f"Кулдаун: ещё {remaining} сек",
            "new_ip": None, "old_ip": None
        }

    # circuit breaker
    if not _check_circuit(modem_id):
        return {
            "success": False,
            "message": f"Circuit breaker: {CIRCUIT_THRESHOLD} фейлов подряд, пауза {CIRCUIT_TIMEOUT}с",
            "new_ip": None, "old_ip": None
        }

    # защита от дублирующих операций
    with _lock:
        if _active.get(modem_id):
            return {
                "success": False,
                "message": "Реконнект уже выполняется",
                "new_ip": None, "old_ip": None
            }
        _active[modem_id] = True

    try:
        # выбор драйвера
        if modem_type in ("e3372", "e3372h"):
            from core.reconnect_e3372h import do_reconnect
        elif modem_type == "b525":
            from core.reconnect_b525 import do_reconnect
        elif modem_type == "android":
            from core.reconnect_android import do_reconnect
        else:
            return {
                "success": False,
                "message": f"Неизвестный тип: {modem_type}",
                "new_ip": None, "old_ip": None
            }

        result = do_reconnect(ip_local, method=method)

        # обновляем метрики
        _last_reconnect[modem_id] = now
        if result["success"]:
            _record_success(modem_id)
        else:
            _record_fail(modem_id)

        # логируем
        log = _load_log()
        log.setdefault(modem_id, []).append({
            "time": now,
            "method": method,
            "success": result["success"],
            "new_ip": result.get("new_ip"),
            "old_ip": result.get("old_ip"),
            "message": result.get("message", "")
        })
        log[modem_id] = log[modem_id][-100:]
        _save_log(log)

        return result

    finally:
        with _lock:
            _active.pop(modem_id, None)
