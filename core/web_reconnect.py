#!/usr/bin/env python3
"""
web_reconnect.py — HTTP-сервер для приёма запросов на реконнект.
Каждый модем слушает на своём порту (как в старом main.py),
либо один сервер на все модемы через query-параметры.

Режим single-port (рекомендуемый):
  GET http://server:8800/reconnect?modem=mdm-001&login=xxx&pass=yyy

Режим multi-port (совместимость с агрегаторами):
  GET http://server:PORT/reconnect
"""

import json
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from core import reconnect_core, config_manager


class ReconnectHandler(BaseHTTPRequestHandler):
    """Обработчик HTTP-запросов на реконнект."""

    def do_GET(self):
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/reconnect"):
            self.send_response(404)
            self.end_headers()
            return

        params = parse_qs(parsed.query)
        modem_id = params.get("modem", [None])[0]
        method = params.get("method", ["full"])[0]

        # Если порт привязан к конкретному модему — берём из server context
        if not modem_id and hasattr(self.server, "modem_id"):
            modem_id = self.server.modem_id

        if not modem_id:
            self._json_response(400, {"ok": False, "msg": "modem не указан"})
            return

        modem = config_manager.get_modem(modem_id)
        if not modem:
            self._json_response(404, {"ok": False, "msg": f"модем {modem_id} не найден"})
            return

        result = reconnect_core.reconnect(
            modem_id=modem_id,
            modem_type=modem.get("type", "e3372h"),
            ip_local=modem.get("webui_ip", modem.get("ip_local", "")),
            cooldown=config_manager.get_settings().get("reconnect_cooldown_sec", 120),
            method=method
        )

        status = 200 if result["success"] else 500
        self._json_response(status, {
            "ok": result["success"],
            "msg": result.get("message", ""),
            "new_ip": result.get("new_ip"),
            "old_ip": result.get("old_ip"),
        })

    def _json_response(self, code, data):
        payload = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        return  # тишина в логах


# ── Запуск ───────────────────────────────────────

_servers = {}


def start_single_server(bind="0.0.0.0", port=8800):
    """Один сервер для всех модемов (рекомендуемый)."""
    httpd = ThreadingHTTPServer((bind, port), ReconnectHandler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    _servers["main"] = httpd
    print(f"[reconnect] HTTP сервер: http://{bind}:{port}/reconnect?modem=ID")


def start_per_modem_server(modem_id, port, bind="0.0.0.0"):
    """Отдельный порт на модем (совместимость с агрегаторами)."""
    httpd = ThreadingHTTPServer((bind, port), ReconnectHandler)
    httpd.modem_id = modem_id
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    _servers[modem_id] = httpd
    print(f"[reconnect] {modem_id} -> http://{bind}:{port}/reconnect")


def stop_all():
    for key, httpd in _servers.items():
        httpd.shutdown()
    _servers.clear()
