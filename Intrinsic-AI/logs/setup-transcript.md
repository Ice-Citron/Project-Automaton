# Project Automaton — Setup Transcript & Commands Reference

> **Purpose:** Reference for replicating this setup on a fresh Ubuntu 24.04 instance (e.g., AWS with NVIDIA GPU).
> **Last updated:** 2026-03-22

---

## System Requirements

- Ubuntu 24.04 (Noble)
- NVIDIA GPU (RTX 2070+ / L4 / A10G / etc.)
- 32GB+ RAM recommended
- 100GB+ disk (Isaac Lab Docker image alone is ~25GB)

---

## 1. Docker Engine CE (NOT Docker Desktop)

Docker Desktop's `--network host` is broken on WSL2 (and unnecessary on native Linux). Use Docker Engine CE.

```bash
# Remove conflicting packages
for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do
    sudo apt remove -y $pkg 2>/dev/null
done

# Add Docker's official repo
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker run --rm hello-world
```

## 2. NVIDIA Container Toolkit

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt update && sudo apt install -y nvidia-container-toolkit

# Configure Docker to use NVIDIA runtime
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Verify GPU in Docker
docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu24.04 nvidia-smi
```

## 3. Pixi (Package Manager for ROS 2 / AIC)

```bash
curl -fsSL https://pixi.sh/install.sh | sh
# Restart terminal after installation
```

## 4. Gazebo Ionic (comes from OSRF repo)

```bash
sudo curl -sSL https://packages.osrfoundation.org/gazebo.gpg \
  -o /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg

echo "deb [arch=amd64 signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] \
  http://packages.osrfoundation.org/gazebo/ubuntu-stable noble main" \
  | sudo tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null

sudo apt update && sudo apt install -y gz-ionic

# Verify
gz sim --version  # Should show 9.x
```

## 5. Clone Project & AIC Toolkit

```bash
mkdir -p ~/projects
cd ~/projects
git clone https://github.com/Ice-Citron/Project-Automaton.git
cd Project-Automaton

# Initialize AIC submodule
git submodule update --init --recursive

# Install AIC dependencies via pixi
cd References/aic
pixi install
```

## 6. Pull AIC Eval Docker Image

```bash
docker pull ghcr.io/intrinsic-dev/aic/aic_eval:latest
```

## 7. Run AIC Gazebo Evaluation (Two Terminals)

```bash
# Terminal 1: Eval environment
POLICY_NAME=WaveArm GT=false
RUN_DIR=~/projects/Project-Automaton/aic_results/${POLICY_NAME}_$(date +%Y%m%d_%H%M%S)
mkdir -p "$RUN_DIR"

docker run -it --rm \
  --name aic_eval \
  --network host \
  --gpus all \
  -e DISPLAY=:0 \
  -e AIC_RESULTS_DIR=/aic_results \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v "$RUN_DIR":/aic_results \
  ghcr.io/intrinsic-dev/aic/aic_eval:latest \
  ground_truth:=$GT start_aic_engine:=true

# Terminal 2: Policy
cd ~/projects/Project-Automaton/References/aic
pixi run ros2 run aic_model aic_model --ros-args \
  -p use_sim_time:=true \
  -p policy:=aic_example_policies.ros.$POLICY_NAME
```

### WSL2-specific flags (add these if running on WSL2, not needed on native Linux)
```bash
  -e WAYLAND_DISPLAY=wayland-0 \
  -e XDG_RUNTIME_DIR=/mnt/wslg/runtime-dir \
  -e PULSE_SERVER=/mnt/wslg/PulseServer \
  -e GALLIUM_DRIVER=d3d12 \
  -e LD_LIBRARY_PATH=/usr/lib/wsl/lib \
  -v /mnt/wslg:/mnt/wslg \
  -v /usr/lib/wsl:/usr/lib/wsl \
  --device /dev/dxg \
```

---

## 8. MuJoCo Mirror Setup

### Prerequisites
```bash
sudo apt install -y python3-sdformat16 python3-gz-math9

# Also need dm-control and converter deps (system-wide)
pip3 install --break-system-packages dm-control trimesh pycollada
```

### Clone and install the SDF→MJCF converter
```bash
cd /tmp
git clone https://github.com/gazebosim/gz-mujoco.git --branch aic --depth 1

# The converter imports `import sdformat` which maps to the system sdformat15/16 package.
# If sdformat16 fails (missing libsdformat16), create a wrapper:
# Copy system gz + sdformat modules into the converter's Python path, or use
# PYTHONPATH=/tmp/gz-mujoco/sdformat_mjcf/src with system python3.
```

### Export Gazebo world and convert to MJCF
```bash
# 1. Start Gazebo briefly to export world
docker run -d --rm \
  --name aic_export \
  --network host \
  --gpus all \
  ghcr.io/intrinsic-dev/aic/aic_eval:latest \
  spawn_task_board:=true spawn_cable:=true cable_type:=sfp_sc_cable \
  attach_cable_to_gripper:=true ground_truth:=true start_aic_engine:=false

sleep 15

# 2. Copy SDF out and kill container
docker cp aic_export:/tmp/aic.sdf /tmp/aic.sdf
docker rm -f aic_export

# 3. Fix paths in the exported SDF
#    The SDF has paths like /ws_aic/install/share/... (from inside Docker).
#    Replace with your local paths:
sed -i "s|/ws_aic/install/share/aic_assets|$HOME/projects/Project-Automaton/References/aic/aic_assets|g" /tmp/aic.sdf
sed -i "s|file:///ws_aic/install/share/ur_description|file://$HOME/aic_mujoco_world/ur_description|g" /tmp/aic.sdf
sed -i "s|/ws_aic/install/share/aic_bringup|$HOME/projects/Project-Automaton/References/aic/aic_bringup|g" /tmp/aic.sdf
sed -i 's|file:///model://|model://|g' /tmp/aic.sdf
sed -i 's|file:///lc_plug_visual.glb|model://LC Plug/lc_plug_visual.glb|g' /tmp/aic.sdf
sed -i 's|file:///sc_plug_visual.glb|model://SC Plug/sc_plug_visual.glb|g' /tmp/aic.sdf
sed -i 's|file:///sfp_module_visual.glb|model://SFP Module/sfp_module_visual.glb|g' /tmp/aic.sdf

# 4. Copy UR5e meshes from Docker (they only exist in the container)
docker create --name aic_mesh_copy ghcr.io/intrinsic-dev/aic/aic_eval:latest
docker cp aic_mesh_copy:/ws_aic/install/share/ur_description ~/aic_mujoco_world/ur_description
docker rm aic_mesh_copy

# 5. Run conversion
mkdir -p ~/aic_mujoco_world
export PYTHONPATH=/tmp/gz-mujoco/sdformat_mjcf/src:$PYTHONPATH
python3 -m sdformat_mjcf.sdformat_to_mjcf.cli /tmp/aic.sdf ~/aic_mujoco_world/aic_world.xml

# 6. Run add_cable_plugin.py to split and configure
cd ~/projects/Project-Automaton/References/aic
python3 aic_utils/aic_mujoco/scripts/add_cable_plugin.py \
  --input ~/aic_mujoco_world/aic_world.xml \
  --output ~/aic_mujoco_world/aic_world_final.xml \
  --robot_output ~/aic_mujoco_world/aic_robot_final.xml \
  --scene_output ~/aic_mujoco_world/scene_final.xml

# 7. Copy to mjcf directory
cp ~/aic_mujoco_world/aic_world_final.xml References/aic/aic_utils/aic_mujoco/mjcf/aic_world.xml
cp ~/aic_mujoco_world/aic_robot_final.xml References/aic/aic_utils/aic_mujoco/mjcf/aic_robot.xml
cp ~/aic_mujoco_world/scene_final.xml References/aic/aic_utils/aic_mujoco/mjcf/scene.xml
cp ~/aic_mujoco_world/*.obj ~/aic_mujoco_world/*.stl References/aic/aic_utils/aic_mujoco/mjcf/

# 8. Fix scene.xml includes (the script writes *_final.xml names)
sed -i 's/aic_robot_final.xml/aic_robot.xml/; s/aic_world_final.xml/aic_world.xml/' \
  References/aic/aic_utils/aic_mujoco/mjcf/scene.xml

# 9. View scene
pixi run python3 aic_utils/aic_mujoco/scripts/view_scene.py aic_utils/aic_mujoco/mjcf/scene.xml
```

### Gotcha: sdformat version mismatch
- `python3-sdformat16` package installs but requires `libsdformat16.so` which may not be in the repo
- `python3-sdformat15` + `libsdformat15` work fine on Noble
- The converter imports `import sdformat` — you may need a shim:
  ```python
  # /path/to/venv/site-packages/sdformat.py
  from sdformat15 import *
  ```
- Also copy the `gz` module from system site-packages into your venv

---

## 9. Isaac Lab Setup

### Prerequisites
- Docker Engine CE (done above)
- NVIDIA Container Toolkit (done above)
- ~50GB free disk

### Setup
```bash
cd ~
git clone https://github.com/isaac-sim/IsaacLab.git
cd ~/IsaacLab
git clone https://github.com/intrinsic-dev/aic.git

# Download NVIDIA asset pack (requires NVIDIA developer login)
# URL: https://developer.nvidia.com/downloads/Omniverse/learning/Events/Hackathons/Intrinsic_assets.zip
# Extract to:
#   ~/IsaacLab/aic/aic_utils/aic_isaac/aic_isaaclab/source/aic_task/aic_task/tasks/manager_based/aic_task/Intrinsic_assets/

# Build Docker container (~30-60 min)
./docker/container.py build base

# Start and enter container
./docker/container.py start base
./docker/container.py enter base

# Inside container: install AIC task
python -m pip install -e aic/aic_utils/aic_isaac/aic_isaaclab/source/aic_task
```

### Usage (inside Isaac Lab container)
```bash
# List environments
isaaclab -p aic/aic_utils/aic_isaac/aic_isaaclab/scripts/list_envs.py

# Teleop
isaaclab -p aic/aic_utils/aic_isaac/aic_isaaclab/scripts/teleop.py \
    --task AIC-Task-v0 --num_envs 1 --teleop_device keyboard --enable_cameras

# Record demos
isaaclab -p aic/aic_utils/aic_isaac/aic_isaaclab/scripts/record_demos.py \
    --task AIC-Task-v0 --teleop_device keyboard --enable_cameras \
    --dataset_file ./datasets/aic_demo.hdf5 --num_demos 10

# Replay demos
isaaclab -p aic/aic_utils/aic_isaac/aic_isaaclab/scripts/replay_demos.py \
    --dataset_file ./datasets/aic_demo.hdf5

# RL training (start with num_envs=1, scale up: 64, 128, 256)
isaaclab -p aic/aic_utils/aic_isaac/aic_isaaclab/scripts/rsl_rl/train.py \
    --task AIC-Task-v0 --num_envs 1 --enable_cameras
```

### Notes
- Isaac Lab is tested with version **2.3.2**
- Requires **Python 3.11** (handled by Docker container)
- AIC Isaac README lists "Add SDF World to USD asset export pipeline" as future work — use the provided NVIDIA assets, don't try to build a Gazebo→USD exporter

---

## 10. Known Issues & Gotchas

1. **Docker Desktop `--network host` broken on WSL2** — Use Docker Engine CE instead
2. **Gazebo CPU rendering in Docker** — Add `GALLIUM_DRIVER=d3d12` and `LD_LIBRARY_PATH=/usr/lib/wsl/lib` (WSL2 only)
3. **Zenoh timestamp errors** — Cosmetic, caused by clock drift. Don't affect scoring.
4. **MuJoCo rendering is bare** — Expected. MuJoCo is for physics/controller work, not visual fidelity.
5. **RTX 50xx PyTorch issue** — AIC troubleshooting says override pixi PyTorch to `>=2.7.1`:
   ```toml
   # Add to pixi.toml
   [pypi-options.dependency-overrides]
   torch = ">=2.7.1"
   torchvision = ">=0.22.1"
   ```
6. **AIC eval scores to Gazebo only** — Train anywhere, but always validate in Gazebo.
7. **WSL2 mount propagation** — Run `sudo mount --make-rshared /` before using distrobox.
