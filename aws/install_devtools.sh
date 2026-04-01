#!/usr/bin/env bash
# install_devtools.sh — Install dev tools (Node via NVM, Claude Code)

set -eo pipefail

echo "=== Installing prerequisites ==="
sudo apt-get update -qq
sudo apt-get install -y curl ca-certificates build-essential

# Install NVM
if [ ! -d "$HOME/.nvm" ]; then
  echo "=== Installing NVM ==="
  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
fi

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

# Install Node
echo "=== Installing Node.js (LTS) ==="
nvm install --lts
nvm use --lts
nvm alias default 'lts/*'

# Install Claude
echo "=== Installing Claude Code ==="
npm install -g @anthropic-ai/claude-code

# Persist NVM
if ! grep -q 'NVM_DIR' "$HOME/.bashrc"; then
  echo "=== Updating ~/.bashrc ==="
  cat << 'EOF' >> "$HOME/.bashrc"

# NVM setup
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
EOF
fi

# add hf hub login
echo "=== Done ==="
echo "Run: source ~/.bashrc"
echo "Then: claude"

echo "=== Hugging Face CLI (pipx) ==="
pipx ensurepath
export PATH="$HOME/.local/bin:$PATH"
if ! command -v hf &>/dev/null; then
    pipx install "huggingface_hub[cli]"
fi
export PATH="$HOME/.local/bin:$PATH"
grep -q '.local/bin' "$SHELL_RC" 2>/dev/null \
    || echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_RC"
echo ""
echo "  Hugging Face: open a new shell (or: source ~/.bashrc), then run once:"
echo "    hf auth login"
echo "  Non-interactive / CI: export HF_TOKEN=hf_..."
echo ""
