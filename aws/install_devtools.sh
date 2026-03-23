#!/usr/bin/env bash
# install_devtools.sh — Install dev tools (Node via NVM, Claude Code)

set -euo pipefail

echo "=== Installing prerequisites ==="
sudo apt-get update -qq
sudo apt-get install -y curl ca-certificates build-essential

# --------------------------------------------------
# Install NVM (Node Version Manager)
# --------------------------------------------------
if [ ! -d "$HOME/.nvm" ]; then
  echo "=== Installing NVM ==="
  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
fi

# Load NVM into current shell
export NVM_DIR="$HOME/.nvm"
# shellcheck disable=SC1090
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

# --------------------------------------------------
# Install Node (LTS)
# --------------------------------------------------
echo "=== Installing Node.js (LTS) ==="
nvm install --lts
nvm use --lts
nvm alias default 'lts/*'

# --------------------------------------------------
# Install Claude Code
# --------------------------------------------------
echo "=== Installing Claude Code ==="
npm install -g @anthropic-ai/claude-code

# --------------------------------------------------
# Ensure PATH is correct in future shells
# --------------------------------------------------
if ! grep -q 'NVM_DIR' "$HOME/.bashrc"; then
  echo "=== Updating ~/.bashrc ==="
  cat << 'EOF' >> "$HOME/.bashrc"

# NVM setup
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
EOF
fi

echo "=== Installation complete ==="
echo "Run: source ~/.bashrc"
echo "Then: claude"
