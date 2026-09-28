# WSL2 / Ubuntu Setup Transcript — Project Automaton (AIC)

> **Purpose:** One-shot reference for setting up a fresh Ubuntu instance
> (WSL2 or AWS) for the Intrinsic AI Challenge. Covers ROS 2 Kilted,
> MuJoCo integration, Isaac Lab, Docker, and GPU setup.
>
> **Base OS:** Ubuntu 24.04 (Noble) — amd64
> **GPU:** NVIDIA (tested on RTX 5090, should work on any CUDA 12+ GPU)
> **Last updated:** 2026-03-22

---

## Phase 1: System Basics

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl wget git build-essential software-properties-common
```

---

## Phase 2: NVIDIA GPU + Container Toolkit

> Skip if on a pre-configured GPU instance (e.g. AWS g5/p4 with NVIDIA
> drivers pre-installed). Verify with `nvidia-smi` first.

```bash
# Verify GPU is visible
nvidia-smi

# Install NVIDIA Container Toolkit (for Docker GPU passthrough)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt update && sudo apt install -y nvidia-container-toolkit

# Configure Docker to use NVIDIA runtime
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Verify GPU passthrough works in Docker
docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu24.04 nvidia-smi
```

---

## Phase 3: Docker Engine CE

> **IMPORTANT (WSL2 only):** Do NOT use Docker Desktop — its
> `--network host` is broken on WSL2 (runs in a separate VM).
> Install Docker Engine CE natively instead.
>
> On a real Ubuntu instance (AWS), standard Docker install is fine.

```bash
# Remove any old Docker
sudo apt remove -y docker docker-engine docker.io containerd runc 2>/dev/null

# Install Docker CE
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu noble stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update && sudo apt install -y \
  docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin

# Add yourself to docker group (log out/in after)
sudo usermod -aG docker $USER

# Verify
docker run hello-world
```

---

## Phase 4: ROS 2 Kilted (System Install)

```bash
# Add ROS 2 apt repository
sudo apt install -y software-properties-common
sudo add-apt-repository universe
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
http://packages.ros.org/ros2/ubuntu noble main" | \
  sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

# Install ROS 2 Kilted desktop (~2-3GB)
sudo apt update && sudo apt install -y ros-kilted-desktop

# Install dev tools (colcon, vcs, rosdep, etc.)
sudo apt install -y ros-dev-tools

# Initialize rosdep
sudo rosdep init
rosdep update

# Add to bashrc
echo 'source /opt/ros/kilted/setup.bash' >> ~/.bashrc
source /opt/ros/kilted/setup.bash

# Verify
ros2 topic list
```

---

## Phase 5: Gazebo SDFormat + gz-math Python Bindings

> Required for MuJoCo SDF-to-MJCF conversion.

```bash
# Add OSRF Gazebo apt repo
sudo wget https://packages.osrfoundation.org/gazebo.gpg \
  -O /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] \
http://packages.osrfoundation.org/gazebo/ubuntu-stable noble main" | \
  sudo tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null
sudo apt update

# Install Python bindings + shared library
sudo apt install -y python3-sdformat16 libsdformat16 python3-gz-math9

# Verify (module names don't have version numbers!)
python3 -c "import sdformat; print('sdformat OK')"
python3 -c "from gz.math import Vector3d; print('gz.math OK')"
```

---

## Phase 6: Pixi Package Manager

```bash
curl -fsSL https://pixi.sh/install.sh | bash
# Restart shell or:
export PATH="$HOME/.pixi/bin:$PATH"
pixi --version
```

---

## Phase 7: Clone Project + AIC Submodule

```bash
mkdir -p ~/projects && cd ~/projects
git clone https://github.com/Ice-Citron/Project-Automaton.git
cd Project-Automaton

# Init the AIC submodule
git submodule update --init --recursive

# Install AIC pixi environment (ROS 2 + MuJoCo 3.5 + all deps)
cd References/aic
pixi install
# This pulls ~5GB of conda packages (ROS 2 Kilted, MuJoCo, etc.)

# Verify pixi ROS 2 works
pixi run ros2 topic list
```

---

## Phase 8: MuJoCo Standalone Venv (MJX + Warp + JAX)

> Optional — for standalone MuJoCo/MJX/Warp experiments outside the
> AIC pixi environment.

```bash
python3 -m venv ~/envs/mujoco
source ~/envs/mujoco/bin/activate
pip install --upgrade pip
pip install mujoco==3.6.0 mujoco-mjx==3.6.0
pip install jax[cuda12]==0.9.1
pip install warp-lang==1.12.0

# Verify
python3 -c "import mujoco; print(f'MuJoCo {mujoco.__version__}')"
python3 -c "import jax; print(jax.devices())"  # should show GPU
python3 -c "import warp as wp; wp.init(); print(wp.get_cuda_devices())"
```

---

## Phase 9: MuJoCo AIC Integration (colcon workspace)

> Requires system ROS 2 Kilted from Phase 4.

```bash
# Create the colcon workspace
mkdir -p ~/ws_aic/src && cd ~/ws_aic/src

# Symlink or clone the AIC repo
ln -s ~/projects/Project-Automaton/References/aic aic

# Import MuJoCo repos (mujoco_vendor, mujoco_ros2_control, gz-mujoco)
vcs import < aic/aic_utils/aic_mujoco/mujoco.repos

# Install rosdep dependencies
cd ~/ws_aic
rosdep install --from-paths src --ignore-src --rosdistro kilted -yr \
  --skip-keys "gz-cmake3 DART libogre-dev libogre-next-2.3-dev"

# Build sdformat_mjcf converter first
source /opt/ros/kilted/setup.bash
colcon build --packages-select sdformat_mjcf
source install/setup.bash

# Full workspace build (takes a while)
GZ_BUILD_FROM_SOURCE=1 colcon build \
  --cmake-args -DCMAKE_BUILD_TYPE=Release \
  --merge-install --symlink-install \
  --packages-ignore lerobot_robot_aic

source install/setup.bash

# Verify
echo $MUJOCO_DIR        # should point to ws_aic/install/opt/mujoco_vendor
echo $MUJOCO_PLUGIN_PATH  # should point to .../mujoco_vendor/lib
```

---

## Phase 10: Isaac Lab Setup (Docker-based, WSL2 only)

> **IMPORTANT:** Isaac Sim ROS 2 launch is NOT supported on WSL2.
> However, the AIC Isaac Lab integration does NOT need ROS 2 — it runs
> entirely via standalone Python scripts (`isaaclab -p`). It outputs
> HDF5 datasets and policy checkpoints that get loaded into a separate
> Kilted/Gazebo policy for evaluation. The two systems never talk over
> ROS 2.
>
> Do NOT install Isaac Sim standalone in WSL2. Use the Docker container.
> Do NOT try to install IsaacLab on Windows.
> The Docker container bundles Isaac Sim + IsaacLab + Python 3.11.

```bash
# Clone Isaac Lab
cd ~
git clone https://github.com/isaac-sim/IsaacLab.git
cd ~/IsaacLab

# Clone AIC inside Isaac Lab
git clone https://github.com/intrinsic-dev/aic.git

# Build the Docker container (~30-60 min, ~25GB)
# Check disk space first!
df -h

# Answer 'n' to X11 prompt (we run headless)
echo 'n' | python3 docker/container.py build base

# Start and enter the container
echo 'n' | python3 docker/container.py start base
docker exec -it isaac-lab-base bash

# Inside the container: install AIC task
/workspace/isaaclab/_isaac_sim/python.sh -m pip install -e \
  aic/aic_utils/aic_isaac/aic_isaaclab/source/aic_task
```

### NVIDIA Asset Pack (manual download required)

> Requires NVIDIA developer login — download in a browser:
> https://developer.nvidia.com/downloads/Omniverse/learning/Events/Hackathons/Intrinsic_assets.zip

Extract and place at:
```
~/IsaacLab/aic/aic_utils/aic_isaac/aic_isaaclab/source/\
aic_task/aic_task/tasks/manager_based/aic_task/Intrinsic_assets/
```

### Isaac Lab Smoke Tests (inside container, headless)

```bash
# List available environments (no rendering needed)
isaaclab -p aic/aic_utils/aic_isaac/aic_isaaclab/scripts/list_envs.py

# RL training headless (start small, scale up)
isaaclab -p aic/aic_utils/aic_isaac/aic_isaaclab/scripts/rsl_rl/train.py \
  --task AIC-Task-v0 --num_envs 1 --headless

# Teleop (needs display — may not work headless)
isaaclab -p aic/aic_utils/aic_isaac/aic_isaaclab/scripts/teleop.py \
  --task AIC-Task-v0 --num_envs 1 \
  --teleop_device keyboard --enable_cameras

# Record 10 demos
isaaclab -p aic/aic_utils/aic_isaac/aic_isaaclab/scripts/record_demos.py \
  --task AIC-Task-v0 --teleop_device keyboard --enable_cameras \
  --dataset_file ./datasets/aic_demo.hdf5 --num_demos 10

# Replay demos
isaaclab -p aic/aic_utils/aic_isaac/aic_isaaclab/scripts/replay_demos.py \
  --dataset_file ./datasets/aic_demo.hdf5

# Scale up RL: --num_envs 64, 128, 256 — find stable max
```

Extract to:
```
~/IsaacLab/aic/aic_utils/aic_isaac/aic_isaaclab/source/aic_task/aic_task/tasks/manager_based/aic_task/Intrinsic_assets/
```

---

## Phase 11: AIC Eval Docker Run (Gazebo Scoring)

```bash
POLICY_NAME=WaveArm
GT=false
RUN_DIR=~/projects/Project-Automaton/aic_results/${POLICY_NAME}_$(date +%Y%m%d_%H%M%S)
mkdir -p "$RUN_DIR"

# Terminal 1: Start eval environment
docker run -it --rm \
  --name aic_eval \
  --network host \
  --gpus all \
  -e DISPLAY=:0 \
  -e GALLIUM_DRIVER=d3d12 \
  -e LD_LIBRARY_PATH=/usr/lib/wsl/lib \
  -e AIC_RESULTS_DIR=/aic_results \
  -v "$RUN_DIR":/aic_results \
  ghcr.io/intrinsic-dev/aic/aic_eval:latest \
  ground_truth:=$GT start_aic_engine:=true

# Terminal 2: Run policy (wait for "No node with name 'aic_model' found")
cd ~/projects/Project-Automaton/References/aic
pixi run ros2 run aic_model aic_model \
  --ros-args -p use_sim_time:=true \
  -p policy:=aic_example_policies.ros.$POLICY_NAME
```

---

## WSL2-Specific Notes

> Skip this section for AWS/bare-metal Ubuntu.

- Use Docker Engine CE, NOT Docker Desktop (`--network host` broken)
- GPU rendering env vars: `GALLIUM_DRIVER=d3d12`,
  `LD_LIBRARY_PATH=/usr/lib/wsl/lib`
- WSL2 needs `mount --make-rshared /` for Docker (create systemd service)
- Work in `~/` (ext4), not `/mnt/c/` (slow 9P bridge)
- Zenoh timestamp errors are cosmetic (WSL2 clock drift)

---

## Useful Aliases

```bash
# Add to ~/.bashrc
alias automaton="cd ~/projects/Project-Automaton"
alias aic="cd ~/projects/Project-Automaton/References/aic"
alias mujoco="source ~/envs/mujoco/bin/activate"
```

---

## Gotchas & Troubleshooting

| Issue | Fix |
|-------|-----|
| `python3-sdformat16` installed but `import sdformat16` fails | Module name is `sdformat`, not `sdformat16`. Also install `libsdformat16`. |
| `MUJOCO_PATH` conflicts with `mujoco_vendor` | Remove old `MUJOCO_*` env vars from `~/.bashrc` before building |
| RTX 50xx PyTorch failures | Add to `pixi.toml`: `[pypi-options.dependency-overrides]` with `torch = ">=2.7.1"` |
| Docker `--network host` not working (WSL2) | Switch from Docker Desktop to Docker Engine CE |
| Gazebo CPU rendering (laggy) | Set `GALLIUM_DRIVER=d3d12` + `LD_LIBRARY_PATH=/usr/lib/wsl/lib` |
| Isaac Lab container build fails | Check `df -h` — needs ~25GB free |
| `colcon` not found | Install `ros-dev-tools` (Phase 4) or system ROS 2 |
