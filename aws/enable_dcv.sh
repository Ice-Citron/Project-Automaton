# Install Ubuntu Desktop
sudo apt update
sudo apt install -y ubuntu-desktop

# Download and extract Nice DCV
wget https://d1uj6qtbmh3dt5.cloudfront.net/nice-dcv-ubuntu2204-x86_64.tgz
tar -xvzf nice-dcv-ubuntu2204-x86_64.tgz
cd nice-dcv-2025.0-20103-ubuntu2204-x86_64

# Install Nice DCV
sudo apt install -y ./nice-dcv-server_*.deb
sudo apt install -y ./nice-dcv-web-viewer_*.deb

# Start Nice DCV
sudo systemctl start dcvserver
sudo systemctl enable dcvserver

# List Sessions
dcv list-sessions # Session: 'console' (owner:ubuntu type:console)

sudo passwd ubuntu # Set password for ubuntu user