#!/usr/bin/env python3
"""
Anectium — точка входа.
"""

import os
import sys
import time
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from core import config_manager
from core import proxy_engine
from core import checker
from core import web_reconnect


def main():
    print("=" * 50)
    print("  Anectium")
    print("=" * 50)

    # 1. БД
    config_manager.init_db()
    settings = config_manager.get_settings()

    # 2. 3proxy
    proxy_engine.generate_config()
    proxy_engine.start()

    # 3. HTTP reconnect сервер
    web_reconnect.start_single_server(port=8800)

    # 4. Checker в фоне
    interval = settings.get("check_interval_sec", 60)
    checker_thread = threading.Thread(
        target=checker.run_loop, args=(interval,), daemon=True
    )
    checker_thread.start()

    print()
    print("[ok] Все сервисы запущены")
    print(f"  3proxy:     {'работает' if proxy_engine.is_running() else 'НЕ запущен'}")
    print(f"  Reconnect:  http://0.0.0.0:8800/reconnect?modem=ID")
    print(f"  Checker:    каждые {interval}с")
    print()

    # 5. Основной цикл — следит за 3proxy
    try:
        while True:
            proxy_engine.ensure_running()
            time.sleep(30)
    except KeyboardInterrupt:
        print("\n[stop] Завершение...")
        proxy_engine.stop()
        web_reconnect.stop_all()


if __name__ == "__main__":
    main()
