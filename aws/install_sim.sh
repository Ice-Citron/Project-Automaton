#!/usr/bin/env bash
# install_sim.sh — Install all 3 AIC simulation lanes
#   Lane 1: Gazebo (distrobox + pixi)
#   Lane 2: MuJoCo (ROS 2 colcon + SDF→MJCF conversion)
#   Lane 3: Isaac Lab (Docker)
#
# Usage: bash install_sim.sh [--skip-isaac-build]
set -eo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AIC="$REPO_ROOT/References/aic"
WS="$HOME/ws_aic"
ISAACLAB="$HOME/IsaacLab"
MUJOCO_WORLD="$HOME/aic_mujoco_world"
MJCF="$AIC/aic_utils/aic_mujoco/mjcf"
DISPLAY="${DISPLAY:-:1}"; export DISPLAY
SHELL_RC="$HOME/.bashrc"

SKIP_ISAAC_BUILD=false
[[ "${1:-}" == "--skip-isaac-build" ]] && SKIP_ISAAC_BUILD=true

die() { echo "[FAIL] $*" >&2; exit 1; }

[[ -d "$AIC" ]] || die "AIC submodule not found at $AIC. Run: git submodule update --init --recursive"

# ── System packages ──────────────────────────────────────────────────────────
echo "=== System packages ==="
sudo apt-get update -qq
# Remove Ubuntu vcstool if present (conflicts with ROS python3-vcstool)
dpkg -l vcstool 2>/dev/null | grep -q "^ii" && sudo dpkg --remove --force-remove-reinstreq vcstool 2>/dev/null && sudo apt --fix-broken install -y 2>/dev/null || true
sudo apt-get install -y \
    curl wget git ca-certificates gnupg lsb-release \
    build-essential python3 python3-pip g++-14 gcc-14 \
    distrobox x11-xserver-utils tmux

# ── NVIDIA Container Toolkit ─────────────────────────────────────────────────
echo "=== NVIDIA Container Toolkit ==="
if ! dpkg -l nvidia-container-toolkit &>/dev/null; then
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
        | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg 2>/dev/null || true
    curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
        | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
        | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null
    sudo apt-get update -qq && sudo apt-get install -y nvidia-container-toolkit
    sudo nvidia-ctk runtime configure --runtime=docker
    sudo systemctl restart docker
fi

# ── Pixi ─────────────────────────────────────────────────────────────────────
echo "=== Pixi ==="
if ! command -v pixi &>/dev/null; then
    curl -fsSL https://pixi.sh/install.sh | sh
fi
export PATH="$HOME/.pixi/bin:$PATH"
grep -q '/.pixi/bin' "$SHELL_RC" 2>/dev/null \
    || echo 'export PATH="$HOME/.pixi/bin:$PATH"' >> "$SHELL_RC"

# ── Pixi workspace ──────────────────────────────────────────────────────────
echo "=== Pixi workspace ==="
# bwrap needs setuid for rattler-build's sandbox to create user namespaces
[[ -u /usr/bin/bwrap ]] || sudo chmod u+s /usr/bin/bwrap
mkdir -p "$WS/src"
[[ -e "$WS/src/aic" ]] || ln -s "$AIC" "$WS/src/aic"
cd "$WS/src/aic" && pixi install

# ── Lane 1: Gazebo distrobox ────────────────────────────────────────────────
echo "=== Lane 1: Gazebo (distrobox) ==="
export DBX_CONTAINER_MANAGER=docker
docker pull ghcr.io/intrinsic-dev/aic/aic_eval:latest
distrobox list 2>/dev/null | grep -q "aic_eval" \
    || distrobox create -r --nvidia -i ghcr.io/intrinsic-dev/aic/aic_eval:latest aic_eval

# ── Lane 2: ROS 2 Kilted + MuJoCo ──────────────────────────────────────────
echo "=== Lane 2: ROS 2 Kilted ==="
if ! dpkg -l ros-kilted-ros-base 2>/dev/null | grep -q "^ii"; then
    sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
        -o /usr/share/keyrings/ros-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
      http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo "$UBUNTU_CODENAME") main" \
      | sudo tee /etc/apt/sources.list.d/ros2.list >/dev/null
    sudo apt-get update -qq
    sudo apt-get install -y ros-kilted-desktop python3-rosdep python3-colcon-common-extensions
    sudo rosdep init 2>/dev/null || true
    rosdep update --rosdistro kilted 2>/dev/null || true
fi

echo "=== Lane 2: SDFormat bindings ==="
if [[ ! -f /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg ]]; then
    sudo wget -q https://packages.osrfoundation.org/gazebo.gpg \
        -O /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] \
      http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" \
      | sudo tee /etc/apt/sources.list.d/gazebo-stable.list >/dev/null
    sudo apt-get update -qq
fi
sudo apt-get install -y python3-sdformat16 python3-gz-math9 libsdformat16

echo "=== Lane 2: MuJoCo colcon build ==="
cd "$WS"
[[ -d "$WS/src/mujoco" ]] || (cd "$WS/src" && vcs import < aic/aic_utils/aic_mujoco/mujoco.repos)
source /opt/ros/kilted/setup.bash
rosdep install --from-paths src --ignore-src --rosdistro kilted -yr \
    --skip-keys "gz-cmake3 DART libogre-dev libogre-next-2.3-dev" 2>/dev/null || true
export CC=gcc-14 CXX=g++-14
GZ_BUILD_FROM_SOURCE=1 colcon build \
    --cmake-args -DCMAKE_BUILD_TYPE=Release \
    --merge-install --symlink-install \
    --packages-ignore lerobot_robot_aic 2>&1 | tail -5
source "$WS/install/setup.bash"

echo "=== Lane 2: SDF→MJCF conversion ==="
mkdir -p "$MUJOCO_WORLD"
xhost +local:docker 2>/dev/null || true

# Start Gazebo to export expanded SDF
docker rm -f aic_sdf_export 2>/dev/null || true
docker run -d --rm --name aic_sdf_export --network host --gpus all \
    -e DISPLAY="$DISPLAY" -v /tmp/.X11-unix:/tmp/.X11-unix \
    ghcr.io/intrinsic-dev/aic/aic_eval:latest \
    spawn_task_board:=true spawn_cable:=true cable_type:=sfp_sc_cable \
    attach_cable_to_gripper:=true ground_truth:=true start_aic_engine:=false
echo "  Waiting 25s for Gazebo ..." && sleep 25

docker exec aic_sdf_export bash -c '
    source /ws_aic/install/setup.bash
    gz service -s /world/aic_world/generate_world_sdf \
        --reqtype gz.msgs.SdfGeneratorConfig --reptype gz.msgs.StringMsg --timeout 10000 \
        -r "global_entity_gen_config { expand_include_tags { data: true } }" \
    | sed "s/data: \"//" | sed "s/\"$//" | sed "s/\\\\n/\n/g" | sed "s/\\\\\x27/'"'"'/g" \
    > /tmp/aic_expanded.sdf
'
docker cp aic_sdf_export:/tmp/aic_expanded.sdf /tmp/aic_expanded.sdf
docker rm -f aic_sdf_export 2>/dev/null || true
[[ -s /tmp/aic_expanded.sdf ]] || die "SDF export failed"

# Fix SDF paths
python3 -c "
import re
with open('/tmp/aic_expanded.sdf') as f: c = f.read()
c = re.sub(r'<include>.*?<uri>file://<urdf-string>.*?</include>', '', c, flags=re.DOTALL)
c = c.replace('file://<urdf-string>/model://', 'model://')
for name in ['lc_plug_visual.glb','sc_plug_visual.glb','sfp_module_visual.glb']:
    label = name.replace('_visual.glb','').replace('_',' ').title().replace('Sfp','SFP').replace('Lc','LC').replace('Sc','SC')
    c = c.replace(f'file:///{name}', f'model://{label}/{name}')
with open('/tmp/aic_expanded.sdf','w') as f: f.write(c)
"

# Extract UR5e meshes from Docker image
if [[ ! -d "$MUJOCO_WORLD/ur_description" ]]; then
    docker create --name aic_mesh_copy ghcr.io/intrinsic-dev/aic/aic_eval:latest
    docker cp aic_mesh_copy:/ws_aic/install/share/ur_description "$MUJOCO_WORLD/ur_description"
    docker rm aic_mesh_copy
fi

# Convert SDF→MJCF
source "$WS/install/setup.bash"
export GZ_SIM_RESOURCE_PATH="$AIC/aic_assets/models:$MUJOCO_WORLD"
sdf2mjcf /tmp/aic_expanded.sdf "$MUJOCO_WORLD/aic_world.xml" 2>&1 | tail -3

# Copy to mjcf dir and run add_cable_plugin.py
cp "$MUJOCO_WORLD"/*.xml "$MUJOCO_WORLD"/*.obj "$MUJOCO_WORLD"/*.png "$MUJOCO_WORLD"/*.stl "$MJCF/" 2>/dev/null || true
cd "$AIC"
python3 aic_utils/aic_mujoco/scripts/add_cable_plugin.py \
    --input "$MJCF/aic_world.xml" --output "$MJCF/aic_world.xml" \
    --robot_output "$MJCF/aic_robot.xml" --scene_output "$MJCF/scene.xml" 2>&1 | tail -3

# ── Lane 3: Isaac Lab ───────────────────────────────────────────────────────
echo "=== Lane 3: Isaac Lab ==="
if [[ ! -d "$ISAACLAB" ]]; then
    git clone https://github.com/isaac-sim/IsaacLab.git "$ISAACLAB"
    cd "$ISAACLAB" && git checkout v2.3.2 2>/dev/null || true
fi
[[ -d "$ISAACLAB/aic" ]] || git clone https://github.com/intrinsic-dev/aic.git "$ISAACLAB/aic"

ASSETS="$ISAACLAB/aic/aic_utils/aic_isaac/aic_isaaclab/source/aic_task/aic_task/tasks/manager_based/aic_task/Intrinsic_assets"
[[ -d "$ASSETS" ]] || echo "[WARN] Intrinsic_assets missing — download from NVIDIA developer portal and extract to: $ASSETS"

if [[ "$SKIP_ISAAC_BUILD" == false ]]; then
    cd "$ISAACLAB"
    echo "  Building IsaacLab Docker image (~20-30 min) ..."
    echo "y" | python3 docker/container.py build base
fi

# ── Shell aliases ────────────────────────────────────────────────────────────
echo "=== Shell aliases ==="
if ! grep -q 'aic-policy()' "$SHELL_RC" 2>/dev/null; then
cat >> "$SHELL_RC" << 'ALIASES'

# ── AIC sim aliases ──────────────────────────────────────────────────────────
export DBX_CONTAINER_MANAGER=docker
alias aic-eval-gt='distrobox enter -r aic_eval -- /entrypoint.sh ground_truth:=true start_aic_engine:=true'
alias aic-eval-no-gt='distrobox enter -r aic_eval -- /entrypoint.sh ground_truth:=false start_aic_engine:=true'
aic-policy() {
    local policy="${1:-aic_example_policies.ros.WaveArm}"
    [[ "$policy" != *.* ]] && policy="aic_example_policies.ros.$policy"
    cd "$HOME/ws_aic/src/aic"
    pixi run ros2 run aic_model aic_model --ros-args -p use_sim_time:=true -p policy:="$policy"
}
alias aic-zenoh='source "$HOME/ws_aic/install/setup.bash" && export RMW_IMPLEMENTATION=rmw_zenoh_cpp && export ZENOH_CONFIG_OVERRIDE="transport/shared_memory/enabled=true" && ros2 run rmw_zenoh_cpp rmw_zenohd'
alias aic-mujoco='source "$HOME/ws_aic/install/setup.bash" && export RMW_IMPLEMENTATION=rmw_zenoh_cpp && export ZENOH_CONFIG_OVERRIDE="transport/shared_memory/enabled=true" && ros2 launch aic_mujoco aic_mujoco_bringup.launch.py'
alias aic-isaac='cd "$HOME/IsaacLab" && echo y | python3 docker/container.py start base && python3 docker/container.py enter base'
ALIASES
fi

echo "=== install_sim.sh complete ==="
