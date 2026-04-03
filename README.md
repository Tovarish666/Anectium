# Anectium

Система управления 4G прокси-фермами на Linux.

## Структура

```
/anectium/
├── 3proxy/                     # Прокси-ядро
│   ├── 3proxy                  # бинарник (собирается из исходников)
│   ├── config.cfg              # автогенерация (не редактировать)
│   ├── users                   # автогенерация
│   └── logs/
│
├── core/                       # Основная логика (Python)
│   ├── proxy_engine.py         # генерация конфига 3proxy + управление
│   ├── config_manager.py       # CRUD для db.json
│   ├── reconnect_core.py       # диспетчер реконнектов (cooldown, circuit breaker)
│   ├── reconnect_e3372h.py     # Huawei E3372H: cell lock (soft/full) + HTTP reboot
│   ├── reconnect_b525.py       # Huawei B525 (TODO)
│   ├── reconnect_android.py    # Android (TODO)
│   ├── web_reconnect.py        # HTTP-сервер для реконнектов
│   ├── checker.py              # мониторинг (ping + proxy check)
│   └── tg_dispatcher.py        # Telegram-алерты
│
├── web/                        # Веб-дашборд (TODO)
│
├── data/
│   ├── db.json                 # основная БД
│   ├── deny_list_domain.txt    # домены операторов для блокировки
│   ├── reconnect_log.json      # лог реконнектов
│   └── backups/
│
├── scripts/
│   ├── install.sh              # полная установка
│   ├── install_3proxy.sh       # сборка 3proxy
│   └── anectium.service        # systemd
│
├── anectium.py                 # точка входа
└── requirements.txt
```

## Установка

```bash
# На чистый Debian/Ubuntu:
curl -fsSL https://raw.githubusercontent.com/Tovarish666/Anectium/main/scripts/install.sh | bash

# Или вручную:
git clone https://github.com/Tovarish666/Anectium.git /anectium
cd /anectium
bash scripts/install.sh
```

## Запуск

```bash
cd /anectium && python3 anectium.py
```

## Systemd

```bash
cp /anectium/scripts/anectium.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now anectium
```

## Реконнект модема

```
GET http://SERVER:8800/reconnect?modem=mdm-001
GET http://SERVER:8800/reconnect?modem=mdm-001&method=soft
GET http://SERVER:8800/reconnect?modem=mdm-001&method=reboot
```

Методы: `soft` (быстрый cell lock), `full` (полный cell lock, по умолчанию), `reboot` (HTTP перезагрузка модема).
