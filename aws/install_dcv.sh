#!/usr/bin/env bash
# install_dcv.sh — Install NICE DCV remote desktop on Ubuntu 24.04
set -eo pipefail

echo "=== Installing Ubuntu Desktop ==="
sudo apt-get update -qq
sudo apt-get install -y ubuntu-desktop

echo "=== Installing NICE DCV ==="
cd /tmp
ARCH=$(dpkg --print-architecture)
# Use ubuntu2404 for Noble; fall back to ubuntu2204
DCV_URL="https://d1uj6qtbmh3dt5.cloudfront.net/nice-dcv-ubuntu2404-${ARCH}.tgz"
wget -q "$DCV_URL" -O nice-dcv.tgz 2>/dev/null \
    || wget -q "https://d1uj6qtbmh3dt5.cloudfront.net/nice-dcv-ubuntu2204-${ARCH}.tgz" -O nice-dcv.tgz
tar -xzf nice-dcv.tgz
cd nice-dcv-*/
sudo apt-get install -y ./nice-dcv-server_*.deb ./nice-dcv-web-viewer_*.deb

echo "=== Starting DCV ==="
sudo systemctl enable --now dcvserver

echo "=== Set the ubuntu user password (required for DCV login) ==="
sudo passwd ubuntu

echo "DCV installed. Connect via https://<instance-ip>:8443"
