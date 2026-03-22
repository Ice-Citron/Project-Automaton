git clone https://github.com/Ice-Citron/Project-Automaton

# Install npm@11.12.0
sudo apt install -y nodejs
sudo npm install -g npm@11.12.0

# Install Claude Code
echo "=== Installing Claude Code CLI ==="
npm install -g @anthropic-ai/claude-code --unsafe-perm || true

# Add NodeJS to PATH
export PATH=$PATH:/usr/local/bin
export PATH=$PATH:/usr/local/nvm/versions/node/v24.13.0/bin
echo 'export PATH=$PATH:/usr/local/bin' >> ~/.bashrc
source ~/.bashrc

# Test Claude Code
claude