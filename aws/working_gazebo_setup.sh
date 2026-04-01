#### STEP 1: installs #################

sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

sudo apt install distrobox

curl -fsSL https://pixi.sh/install.sh | sh
# Restart your terminal after installation
source ~/.bashrc

# Clone this repo
mkdir -p ~/ws_aic/src
cd ~/ws_aic/src
git clone https://github.com/intrinsic-dev/aic

# Install and build dependencies
cd ~/ws_aic/src/aic
pixi install

#### STEP 2: run eval container #################
# Indicate distrobox to use Docker as container manager
export DBX_CONTAINER_MANAGER=docker

# Create and enter the eval container
docker pull ghcr.io/intrinsic-dev/aic/aic_eval:latest
# If you do *not* have an NVIDIA GPU, remove the --nvidia flag for GPU support
distrobox create -r --nvidia -i ghcr.io/intrinsic-dev/aic/aic_eval:latest aic_eval
distrobox enter -r aic_eval
### INTERACTIVE SET MATCHING PASSWORD HERE

# Inside the container, start the environment
/entrypoint.sh ground_truth:=false start_aic_engine:=true

# STEP 3: IN A SEPARATE TERMINAL
cd ~/ws_aic/src/aic
pixi run ros2 run aic_model aic_model --ros-args -p use_sim_time:=true -p policy:=aic_example_policies.ros.WaveArm

# STEP 4: Run Ground Truth
/entrypoint.sh ground_truth:=true start_aic_engine:=true

pixi run ros2 run aic_model aic_model --ros-args -p use_sim_time:=true -p policy:=aic_example_policies.ros.CheatCode

