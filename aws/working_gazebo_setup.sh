# INSTALL RANGERS REPO!!! OFC
git clone https://github.com/rangers-intrinsic/aic-rangers.git

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
# extra policies
git clone https://github.com/rangers-intrinsic/aic-rangers.git
cd aic-rangers
git switch fix/cable-tangling-issue-38
cd ..
cp -v ~/ws_aic/src/aic-rangers/aic_example_policies/aic_example_policies/ros/CheatCode*.py   ~/ws_aic/src/aic/aic_example_policies/aic_example_policies/ros/

# Install and build dependencies
cd ~/ws_aic/src/aic
# Host-side `pixi run ros2 bag record` needs ros2bag + storage plugins (not in ros-core alone).
grep -q 'ros-kilted-ros2bag' pixi.toml 2>/dev/null || pixi add ros-kilted-ros2bag
grep -q 'ros-kilted-rosbag2-storage-default-plugins' pixi.toml 2>/dev/null || pixi add ros-kilted-rosbag2-storage-default-plugins
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

# STEP 3: Inside the container, start the environment
/entrypoint.sh ground_truth:=false start_aic_engine:=true

# STEP 3: IN A SEPARATE TERMINAL
cd ~/ws_aic/src/aic
pixi run ros2 run aic_model aic_model --ros-args -p use_sim_time:=true -p policy:=aic_example_policies.ros.WaveArm

# RUNNING POLICY TO RECORD EXPERT TRAJECTORY BAG

# STEP 4: Record Expert Trajectory Bag
cd ~/ws_aic/src/aic && mkdir -p ~/bags && pixi run ros2 bag record -o ~/bags/cheatcode_run_$(date +%Y%m%d_%H%M%S) /observations /aic_controller/pose_commands /joint_states

# STEP 4: Run EVal Container with Ground Truth Enabled
/entrypoint.sh ground_truth:=true start_aic_engine:=true

# STEP 4: Run Policy in EVal Container with Ground Truth Enabled
pixi run ros2 run aic_model aic_model --ros-args -p use_sim_time:=true -p policy:=aic_example_policies.ros.CheatCode

