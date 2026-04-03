#!/bin/bash
# Сборка 3proxy из исходников и установка в /anectium/3proxy/
set -e

INSTALL_DIR="/anectium/3proxy"
TMP="/tmp/3proxy-build"

echo "[3proxy] Сборка..."

apt install -y build-essential gcc make 2>/dev/null || true

rm -rf "$TMP"
git clone https://github.com/3proxy/3proxy.git "$TMP"
cd "$TMP"
ln -sf Makefile.Linux Makefile
make -f Makefile.Linux

mkdir -p "$INSTALL_DIR"
cp bin/3proxy "$INSTALL_DIR/3proxy"
chmod +x "$INSTALL_DIR/3proxy"
rm -rf "$TMP"

echo "[3proxy] Установлен: $INSTALL_DIR/3proxy"
"$INSTALL_DIR/3proxy" --version 2>/dev/null || true
