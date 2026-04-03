#!/usr/bin/env python3
"""
reconnect_e3372h.py — смена IP на Huawei E3372H (HiLink).

Два метода cell lock (как в server.js от mobileproxy.space):
  soft  — убедиться mode=02 → data off → data on
  full  — data off → mode 02 (изменённые бэнды) → mode 03 (родные) → data on

Fallback: HTTP reboot через API модема (НЕ USB reset).
"""

import requests
import time
import re

TIMEOUT = 8
LTEBAND_DEFAULT = "7FFFFFFFFFFFFFFF"
NETWORKBAND_DEFAULT = "3FFFFFFF"
LTEBAND_CHANGE = "800C5"
NETWORKBAND_CHANGE = "3FFFFFFF"


# ── Huawei HTTP API helpers ──────────────────────

def _get_session_token(base_url):
    """Получает SesTokInfo."""
    try:
        r = requests.get(f"{base_url}/api/webserver/SesTokInfo", timeout=TIMEOUT)
        ses = re.search(r"<SesInfo>([^<]+)</SesInfo>", r.text)
        tok = re.search(r"<TokInfo>([^<]+)</TokInfo>", r.text)
        if ses and tok:
            return tok.group(1), ses.group(1)
    except Exception:
        pass
    return None, None


def _post_xml(base_url, path, xml_body, token, cookie):
    """POST XML к API модема."""
    headers = {
        "__RequestVerificationToken": token,
        "Cookie": cookie,
        "Content-Type": "text/xml; charset=UTF-8",
    }
    r = requests.post(f"{base_url}{path}", data=xml_body.encode("utf-8"),
                      headers=headers, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text


def _get_xml(base_url, path, cookie=None):
    """GET XML от API модема."""
    headers = {}
    if cookie:
        headers["Cookie"] = cookie
    r = requests.get(f"{base_url}{path}", headers=headers, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text


def _xml_val(xml_text, tag):
    """Извлекает значение тега из XML."""
    m = re.search(rf"<{tag}>([^<]*)</{tag}>", xml_text)
    return m.group(1) if m else None


def _api_call(base_url, path, body=None):
    """Универсальный вызов: получает свежий токен, делает POST/GET."""
    token, cookie = _get_session_token(base_url)
    if not token:
        raise RuntimeError("Не удалось получить токен")
    if body:
        return _post_xml(base_url, path, body, token, cookie)
    else:
        return _get_xml(base_url, path, cookie)


# ── Получение текущего режима сети ──────────────

def _get_net_mode(base_url):
    """Возвращает текущие NetworkMode, NetworkBand, LTEBand."""
    xml = _api_call(base_url, "/api/net/net-mode")
    return {
        "NetworkMode": _xml_val(xml, "NetworkMode") or "03",
        "NetworkBand": _xml_val(xml, "NetworkBand") or NETWORKBAND_DEFAULT,
        "LTEBand": _xml_val(xml, "LTEBand") or LTEBAND_DEFAULT,
    }


def _get_dataswitch(base_url):
    """Возвращает текущее состояние dataswitch: '0' или '1'."""
    xml = _api_call(base_url, "/api/dialup/mobile-dataswitch")
    return _xml_val(xml, "dataswitch")


def _get_wan_ip(base_url):
    """WAN IP модема."""
    try:
        xml = _api_call(base_url, "/api/monitoring/status")
        ip = _xml_val(xml, "WanIPAddress")
        return ip
    except Exception:
        return None


# ── Data switch ──────────────────────────────────

def _data_off(base_url):
    body = '<?xml version="1.0" encoding="UTF-8"?><request><dataswitch>0</dataswitch></request>'
    _api_call(base_url, "/api/dialup/mobile-dataswitch", body)


def _data_on(base_url):
    body = '<?xml version="1.0" encoding="UTF-8"?><request><dataswitch>1</dataswitch></request>'
    _api_call(base_url, "/api/dialup/mobile-dataswitch", body)


def _set_net_mode(base_url, mode, nb, lb):
    body = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<request>'
        f'<NetworkMode>{mode}</NetworkMode>'
        f'<NetworkBand>{nb}</NetworkBand>'
        f'<LTEBand>{lb}</LTEBand>'
        f'</request>'
    )
    _api_call(base_url, "/api/net/net-mode", body)


# ── Ожидание data switch on ─────────────────────

def _wait_data_on(base_url, max_attempts=10):
    """Циклически включает data и проверяет, пока не станет '1'."""
    for i in range(max_attempts):
        try:
            _data_on(base_url)
            time.sleep(0.5)
            state = _get_dataswitch(base_url)
            if state == "1":
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


# ── Метод 1: soft cell lock ─────────────────────

def _reconnect_soft(base_url):
    """
    Soft: убедиться mode=02 (WCDMA) → data off → data on.
    Быстрый, но IP может не измениться у некоторых операторов.
    """
    mode = _get_net_mode(base_url)
    if mode["NetworkMode"] != "02":
        _set_net_mode(base_url, "02", mode["NetworkBand"], mode["LTEBand"])
        time.sleep(0.5)

    _data_off(base_url)
    time.sleep(1.0)

    ok = _wait_data_on(base_url)
    return ok


# ── Метод 2: full cell lock ─────────────────────

def _reconnect_full(base_url):
    """
    Full: data off → mode 02 (изменённые бэнды) → mode 03 (родные) → data on.
    Надёжный, IP меняется почти всегда.
    """
    mode = _get_net_mode(base_url)
    orig_nb = mode["NetworkBand"]
    orig_lb = mode["LTEBand"]

    # data off
    _data_off(base_url)
    time.sleep(1.0)

    # переключить в WCDMA с изменёнными бэндами
    change_lb = "5" if LTEBAND_CHANGE == orig_lb else LTEBAND_CHANGE
    _set_net_mode(base_url, "02", NETWORKBAND_CHANGE, change_lb)
    time.sleep(0.5)

    # вернуть auto с родными бэндами
    _set_net_mode(base_url, "03", orig_nb, orig_lb)
    time.sleep(0.5)

    # data on
    ok = _wait_data_on(base_url)
    return ok


# ── Метод 3: HTTP reboot (fallback) ─────────────

def _reconnect_reboot(base_url):
    """
    Перезагрузка модема через HTTP API.
    Долго (~30-60 сек), но гарантированно меняет IP.
    """
    try:
        body = '<?xml version="1.0" encoding="UTF-8"?><request><Control>1</Control></request>'
        _api_call(base_url, "/api/device/control", body)
    except Exception:
        pass  # модем уже перезагружается, соединение оборвётся

    # ждём пока модем вернётся
    time.sleep(20)
    for _ in range(20):
        try:
            ip = _get_wan_ip(base_url)
            if ip:
                return True
        except Exception:
            pass
        time.sleep(3)
    return False


# ── Основная функция ────────────────────────────

def do_reconnect(ip_local, method="full", timeout=30):
    """
    Реконнект E3372H.

    method: "soft" | "full" | "reboot"
      soft  — быстрый cell lock
      full  — полный cell lock (по умолчанию)
      reboot — HTTP reboot (fallback)

    Returns:
        dict: {success, message, new_ip, old_ip}
    """
    base_url = f"http://{ip_local}"

    try:
        old_ip = _get_wan_ip(base_url)
    except Exception:
        old_ip = None

    result = {"success": False, "message": "", "new_ip": None, "old_ip": old_ip}

    try:
        if method == "soft":
            ok = _reconnect_soft(base_url)
        elif method == "reboot":
            ok = _reconnect_reboot(base_url)
        else:
            ok = _reconnect_full(base_url)

        if not ok:
            result["message"] = f"Метод {method}: data switch не подтверждён"
            return result

        # ждём новый IP (до 15 попыток по 1 сек — как в server.js)
        for i in range(15):
            time.sleep(1)
            try:
                new_ip = _get_wan_ip(base_url)
                if new_ip and new_ip != "0.0.0.0":
                    result["new_ip"] = new_ip
                    result["success"] = True
                    if new_ip != old_ip:
                        result["message"] = f"OK: {old_ip} -> {new_ip}"
                    else:
                        result["message"] = f"OK но IP не изменился: {new_ip}"
                        result["success"] = True  # модем ответил, просто тот же IP
                    return result
            except Exception:
                pass

        result["message"] = "Таймаут: новый IP не получен"
        return result

    except Exception as e:
        result["message"] = f"Ошибка: {e}"
        return result
