#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail

pkg update -y
pkg install -y python git
python -m pip install --upgrade pip
python -m pip install -e .
centinal26 init
centinal26 demo
centinal26 status
