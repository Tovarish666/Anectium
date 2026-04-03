#!/bin/bash
# Anectium — установка на Debian / Ubuntu
set -e

INSTALL_DIR="/anectium"
REPO_URL="https://github.com/Tovarish666/Anectium.git"

echo "=========================================="
echo "  Anectium — установка"
echo "=========================================="

if [ "$EUID" -ne 0 ]; then
    echo "[!] Запусти от root"
    exit 1
fi

# ── Базовые пакеты ──
echo "[1/6] Пакеты..."
apt update -y
apt install -y \
    python3 python3-pip git curl wget jq \
    usb-modeswitch usb-modeswitch-data \
    net-tools udhcpc build-essential gcc make

# ── Репозиторий ──
echo "[2/6] Репозиторий..."
if [ -d "$INSTALL_DIR/.git" ]; then
    cd "$INSTALL_DIR" && git pull
else
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# ── Python ──
echo "[3/6] Python-зависимости..."
pip3 install -r requirements.txt --break-system-packages 2>/dev/null || \
pip3 install -r requirements.txt

# ── 3proxy ──
echo "[4/6] 3proxy..."
bash scripts/install_3proxy.sh

# ── Директории ──
echo "[5/6] Директории..."
mkdir -p "$INSTALL_DIR/data/backups"
mkdir -p "$INSTALL_DIR/3proxy/logs"

# ── Системная оптимизация ──
echo "[6/6] Оптимизация системы..."

# sysctl — на основе mobileproxy.space
cat > /etc/sysctl.d/99-anectium.conf << 'EOF'
net.ipv4.ip_forward = 1
fs.file-max = 4194304
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 65536
net.core.rmem_max = 134217728
net.core.wmem_max = 134217728
net.ipv4.tcp_rmem = 4096 262144 134217728
net.ipv4.tcp_wmem = 4096 262144 134217728
net.ipv4.tcp_max_tw_buckets = 2000000
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 15
net.ipv4.tcp_keepalive_time = 300
net.ipv4.tcp_keepalive_intvl = 30
net.ipv4.tcp_keepalive_probes = 5
net.ipv4.tcp_syncookies = 1
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.tcp_slow_start_after_idle = 0
net.ipv4.conf.all.rp_filter = 0
net.ipv4.conf.default.rp_filter = 0
net.ipv4.conf.all.src_valid_mark = 1
net.ipv4.conf.all.arp_ignore = 1
net.ipv4.conf.all.arp_announce = 2
net.ipv4.ip_local_port_range = 1024 65535
vm.swappiness = 10
EOF

# BBR
modprobe tcp_bbr 2>/dev/null && {
    echo "net.ipv4.tcp_congestion_control = bbr" >> /etc/sysctl.d/99-anectium.conf
    echo "net.core.default_qdisc = fq" >> /etc/sysctl.d/99-anectium.conf
}

sysctl -p /etc/sysctl.d/99-anectium.conf 2>/dev/null || true

# limits
cat > /etc/security/limits.d/99-anectium.conf << 'EOF'
* soft nofile 2097152
* hard nofile 2097152
root soft nofile 2097152
root hard nofile 2097152
EOF

# systemd limits
mkdir -p /etc/systemd/system.conf.d/
cat > /etc/systemd/system.conf.d/99-anectium.conf << 'EOF'
[Manager]
DefaultLimitNOFILE=2097152
EOF
systemctl daemon-reload

# отключить auto-upgrades
systemctl disable --now apt-daily-upgrade.timer 2>/dev/null || true
systemctl disable --now apt-daily.timer 2>/dev/null || true

echo ""
echo "=========================================="
echo "  Готово!"
echo "=========================================="
echo "  Директория:  $INSTALL_DIR"
echo "  Запуск:      cd $INSTALL_DIR && python3 anectium.py"
echo ""
