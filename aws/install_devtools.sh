#!/usr/bin/env bash
# install_devtools.sh — Install dev tools (Node, Claude Code)
set -eo pipefail

echo "=== Node.js + npm ==="
if ! command -v node &>/dev/null; then
    sudo apt-get update -qq
    sudo apt-get install -y nodejs npm
fi
echo 'export PATH="$(npm bin -g):$PATH"' >> ~/.bashrc
sudo npm install -g npm@latest 2>/dev/null || true

echo "=== Claude Code ==="
npm install -g @anthropic-ai/claude-code --unsafe-perm 2>/dev/null || true
echo "Done. Run 'claude' to start."
