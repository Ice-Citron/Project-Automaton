#!/usr/bin/env bash
# setup_sim_environments.sh
#
# Installs all three AIC simulation lanes then smoke-tests each one.
#
#   Lane 1 — Gazebo/Kilted  : aic_eval distrobox + pixi -> runs WaveArm, checks scoring.yaml
#   Lane 2 — MuJoCo         : colcon source build ~/ws_aic -> runs WaveArm via aic_mujoco_bringup
#   Lane 3 — Isaac Lab       : IsaacLab Docker + aic_task -> runs list_envs (AIC-Task-v0 smoke test)
#
# Usage: bash aws/setup_sim_environments.sh [--skip-install] [--skip-isaac-build]
#
#   --skip-install       jump straight to the test phase (all deps already installed)
#   --skip-isaac-build   skip the IsaacLab Docker image build (takes 20-30 min)

set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
AIC_REPO="$REPO_ROOT/References/aic"
WS_AIC="$HOME/ws_aic"
ISAACLAB_DIR="$HOME/IsaacLab"
RESULTS_DIR="$HOME/aic_results"
TEST_TIMEOUT_GAZEBO=180   # seconds to wait for WaveArm to finish 3 trials
TEST_TIMEOUT_MUJOCO=60    # seconds to let MuJoCo + WaveArm run

SKIP_INSTALL=false
SKIP_ISAAC_BUILD=false
for arg in "$@"; do
    case $arg in
        --skip-install)      SKIP_INSTALL=true ;;
        --skip-isaac-build)  SKIP_ISAAC_BUILD=true ;;
    esac
done

SHELL_RC="$HOME/.bashrc"
[[ "$SHELL" == */zsh ]] && SHELL_RC="$HOME/.zshrc"

# Test results tracking
PASS_GAZEBO=false
PASS_MUJOCO=false
PASS_ISAAC=false

log()  { echo ""; echo "══════════════════════════════════════════════"; echo "  $*"; echo "══════════════════════════════════════════════"; }
info() { echo "  → $*"; }
warn() { echo "  [WARN] $*" >&2; }
ok()   { echo "  [OK] $*"; }
fail() { echo "  [FAIL] $*" >&2; }

require_tmux() {
    if ! command -v tmux &>/dev/null; then
        sudo apt-get install -y tmux
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# Preflight
# ─────────────────────────────────────────────────────────────────────────────
log "Preflight"

if [[ ! -d "$AIC_REPO" ]]; then
    echo "ERROR: AIC submodule not found at $AIC_REPO"
    echo "Run: git submodule update --init --recursive"
    exit 1
fi

ok "AIC repo at $AIC_REPO"
ok "Docker $(docker --version | awk '{print $3}' | tr -d ',')"
ok "GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 || echo 'not detected')"

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1 — INSTALL
# ─────────────────────────────────────────────────────────────────────────────
if [[ "$SKIP_INSTALL" == false ]]; then

# ── 1a. System packages ───────────────────────────────────────────────────────
log "1a · System packages"
sudo apt-get update -qq
sudo apt-get install -y \
    curl wget git ca-certificates gnupg lsb-release \
    build-essential python3 python3-pip python3-vcstool \
    distrobox tmux
ok "System packages installed"

# ── 1b. Pixi ─────────────────────────────────────────────────────────────────
log "1b · Pixi"
if ! command -v pixi &>/dev/null; then
    curl -fsSL https://pixi.sh/install.sh | sh
fi
export PATH="$HOME/.pixi/bin:$PATH"
grep -q '/.pixi/bin' "$SHELL_RC" 2>/dev/null \
    || echo 'export PATH="$HOME/.pixi/bin:$PATH"' >> "$SHELL_RC"
ok "Pixi $(pixi --version)"

# ── 1c. Pixi workspace + pixi install ────────────────────────────────────────
log "1c · Pixi workspace (~/ws_aic)"
mkdir -p "$WS_AIC/src"
if [[ ! -e "$WS_AIC/src/aic" ]]; then
    ln -s "$AIC_REPO" "$WS_AIC/src/aic"
    info "Symlinked $AIC_REPO -> $WS_AIC/src/aic"
fi
info "Running pixi install (ROS 2 Kilted + all Python deps) ..."
cd "$WS_AIC/src/aic"
pixi install
ok "Pixi workspace ready"

# ── 1d. aic_eval distrobox container ─────────────────────────────────────────
log "1d · aic_eval distrobox container"
export DBX_CONTAINER_MANAGER=docker
info "Pulling ghcr.io/intrinsic-dev/aic/aic_eval:latest ..."
docker pull ghcr.io/intrinsic-dev/aic/aic_eval:latest
if ! distrobox list 2>/dev/null | grep -q "aic_eval"; then
    distrobox create -r --nvidia -i ghcr.io/intrinsic-dev/aic/aic_eval:latest aic_eval
    ok "distrobox aic_eval created"
else
    ok "distrobox aic_eval already exists"
fi

# ── 1e. ROS 2 Kilted host install ────────────────────────────────────────────
log "1e · ROS 2 Kilted (host, for MuJoCo colcon build)"
if [[ ! -f /opt/ros/kilted/setup.bash ]]; then
    sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
        -o /usr/share/keyrings/ros-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
        http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" \
        | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
    sudo apt-get update -qq
    sudo apt-get install -y ros-kilted-ros-base python3-rosdep python3-colcon-common-extensions
    sudo rosdep init 2>/dev/null || true
    rosdep update
else
    ok "ROS 2 Kilted already installed"
fi

# OSRF Gazebo repo — needed for sdformat Python bindings (sdf2mjcf)
if ! dpkg -l python3-sdformat16 &>/dev/null 2>&1; then
    sudo wget -q https://packages.osrfoundation.org/gazebo.gpg \
        -O /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] \
        http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" \
        | sudo tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null
    sudo apt-get update -qq
    sudo apt-get install -y python3-sdformat16 python3-gz-math9
fi
ok "ROS 2 Kilted + sdformat bindings ready"

# ── 1f. MuJoCo colcon build ───────────────────────────────────────────────────
log "1f · MuJoCo workspace colcon build"
info "Importing mujoco.repos ..."
cd "$WS_AIC/src"
vcs import < aic/aic_utils/aic_mujoco/mujoco.repos

# Check for conflicting MUJOCO env vars from previous installs
if env | grep -qE '^MUJOCO_(PATH|DIR|PLUGIN_PATH)'; then
    warn "Existing MUJOCO_* vars found — these can conflict with mujoco_vendor:"
    env | grep -E '^MUJOCO_(PATH|DIR|PLUGIN_PATH)' || true
    warn "Remove them from $SHELL_RC and run: source $SHELL_RC"
fi

info "Running rosdep ..."
cd "$WS_AIC"
source /opt/ros/kilted/setup.bash
rosdep install --from-paths src --ignore-src --rosdistro kilted -yr \
    --skip-keys "gz-cmake3 DART libogre-dev libogre-next-2.3-dev"

info "colcon build (Release, ~10 min) ..."
GZ_BUILD_FROM_SOURCE=1 colcon build \
    --cmake-args -DCMAKE_BUILD_TYPE=Release \
    --merge-install \
    --symlink-install \
    --packages-ignore lerobot_robot_aic
ok "MuJoCo workspace built"

# ── 1g. IsaacLab ─────────────────────────────────────────────────────────────
log "1g · IsaacLab"
if [[ ! -d "$ISAACLAB_DIR" ]]; then
    info "Cloning IsaacLab ..."
    git clone https://github.com/isaac-sim/IsaacLab.git "$ISAACLAB_DIR"
    cd "$ISAACLAB_DIR"
    git checkout v2.3.2 2>/dev/null || warn "v2.3.2 tag not found — using default branch"
else
    ok "IsaacLab already cloned at $ISAACLAB_DIR"
fi
if [[ ! -d "$ISAACLAB_DIR/aic" ]]; then
    info "Cloning AIC inside IsaacLab ..."
    git clone https://github.com/intrinsic-dev/aic.git "$ISAACLAB_DIR/aic"
else
    ok "AIC already cloned inside IsaacLab"
fi

if [[ "$SKIP_ISAAC_BUILD" == false ]]; then
    info "Building IsaacLab base Docker image (~20-30 min) ..."
    cd "$ISAACLAB_DIR"
    ./docker/container.py build base
    ok "IsaacLab base image built"
else
    warn "Skipping IsaacLab Docker build (--skip-isaac-build). Run manually:"
    info "  cd $ISAACLAB_DIR && ./docker/container.py build base"
fi

# ── 1h. Shell aliases ─────────────────────────────────────────────────────────
log "1h · Shell aliases"
if ! grep -q 'aic-policy()' "$SHELL_RC" 2>/dev/null; then
cat >> "$SHELL_RC" << 'ALIASES'

# ── AIC sim aliases (setup_sim_environments.sh) ──────────────────────────────
export DBX_CONTAINER_MANAGER=docker

alias aic-eval-gt='distrobox enter -r aic_eval -- /entrypoint.sh ground_truth:=true start_aic_engine:=true'
alias aic-eval-no-gt='distrobox enter -r aic_eval -- /entrypoint.sh ground_truth:=false start_aic_engine:=true'

aic-policy() {
    local policy="${1:-aic_example_policies.ros.WaveArm}"
    [[ "$policy" != *.* ]] && policy="aic_example_policies.ros.$policy"
    cd "$HOME/ws_aic/src/aic"
    pixi run ros2 run aic_model aic_model --ros-args \
        -p use_sim_time:=true -p policy:="$policy"
}

alias aic-zenoh='source "$HOME/ws_aic/install/setup.bash" && export RMW_IMPLEMENTATION=rmw_zenoh_cpp && ros2 run rmw_zenoh_cpp rmw_zenohd'
alias aic-mujoco='source "$HOME/ws_aic/install/setup.bash" && export RMW_IMPLEMENTATION=rmw_zenoh_cpp && ros2 launch aic_mujoco aic_mujoco_bringup.launch.py'
alias aic-isaac='cd "$HOME/IsaacLab" && ./docker/container.py start base && ./docker/container.py enter base'
ALIASES
    ok "Aliases written to $SHELL_RC"
else
    ok "Aliases already present in $SHELL_RC"
fi

fi  # end SKIP_INSTALL

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 — TEST: Gazebo + WaveArm
# ─────────────────────────────────────────────────────────────────────────────
log "TEST 1/3 · Gazebo — WaveArm (3 trials)"

require_tmux
export DBX_CONTAINER_MANAGER=docker
mkdir -p "$RESULTS_DIR"
GAZEBO_RESULTS="$RESULTS_DIR/wavearm_gazebo_$(date +%F_%H%M%S)"

# Kill any leftover session from a previous run
tmux kill-session -t aic_gazebo_test 2>/dev/null || true

# Pane 0: eval container (Gazebo + aic_engine + ground_truth)
tmux new-session -d -s aic_gazebo_test -x 220 -y 50
tmux send-keys -t aic_gazebo_test:0 \
    "export DBX_CONTAINER_MANAGER=docker && distrobox enter -r aic_eval -- \
     /entrypoint.sh ground_truth:=true start_aic_engine:=true" Enter

info "Waiting 25s for Gazebo + aic_engine to initialise ..."
sleep 25

# Pane 1: WaveArm policy via pixi
tmux split-window -v -t aic_gazebo_test:0
tmux send-keys -t aic_gazebo_test:0.1 \
    "AIC_RESULTS_DIR=$GAZEBO_RESULTS \
     cd $WS_AIC/src/aic && pixi run ros2 run aic_model aic_model \
     --ros-args -p use_sim_time:=true \
     -p policy:=aic_example_policies.ros.WaveArm" Enter

info "Waiting up to ${TEST_TIMEOUT_GAZEBO}s for 3 trials to complete ..."
ELAPSED=0
while [[ $ELAPSED -lt $TEST_TIMEOUT_GAZEBO ]]; do
    if [[ -f "$GAZEBO_RESULTS/scoring.yaml" ]]; then
        PASS_GAZEBO=true
        break
    fi
    sleep 5
    ELAPSED=$((ELAPSED + 5))
done

tmux kill-session -t aic_gazebo_test 2>/dev/null || true

if [[ "$PASS_GAZEBO" == true ]]; then
    ok "Gazebo test PASSED — scoring.yaml at $GAZEBO_RESULTS/scoring.yaml"
    cat "$GAZEBO_RESULTS/scoring.yaml" 2>/dev/null || true
else
    fail "Gazebo test: scoring.yaml not found within ${TEST_TIMEOUT_GAZEBO}s"
    info "Check: distrobox enter -r aic_eval and run /entrypoint.sh manually"
fi

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 3 — GENERATE MuJoCo scene (requires one Gazebo launch to export SDF)
# ─────────────────────────────────────────────────────────────────────────────
log "SETUP · Generate MuJoCo scene from Gazebo SDF"

MUJOCO_SCENE="$WS_AIC/src/aic/aic_utils/aic_mujoco/mjcf/scene.xml"

if [[ -f "$MUJOCO_SCENE" ]]; then
    ok "MuJoCo scene.xml already exists — skipping generation"
else
    info "Launching Gazebo briefly inside aic_eval to export /tmp/aic.sdf ..."
    tmux kill-session -t aic_sdf_export 2>/dev/null || true
    tmux new-session -d -s aic_sdf_export -x 220 -y 50
    tmux send-keys -t aic_sdf_export:0 \
        "export DBX_CONTAINER_MANAGER=docker && distrobox enter -r aic_eval -- bash -c \
         'source /ws_aic/install/setup.bash && \
          ros2 launch aic_bringup aic_gz_bringup.launch.py \
          spawn_task_board:=true spawn_cable:=true cable_type:=sfp_sc_cable \
          attach_cable_to_gripper:=true ground_truth:=true \
          gazebo_gui:=false launch_rviz:=false start_aic_engine:=false'" Enter

    info "Waiting 30s for Gazebo to export /tmp/aic.sdf ..."
    sleep 30

    # Copy SDF from inside the rootful distrobox container (Docker container named aic_eval)
    if docker cp aic_eval:/tmp/aic.sdf /tmp/aic.sdf 2>/dev/null; then
        ok "Copied /tmp/aic.sdf from container"
    else
        warn "docker cp failed — checking if /tmp/aic.sdf appeared on host (shared /tmp) ..."
        if [[ ! -f /tmp/aic.sdf ]]; then
            fail "Could not get /tmp/aic.sdf — skipping MuJoCo test"
            tmux kill-session -t aic_sdf_export 2>/dev/null || true
        fi
    fi
    tmux kill-session -t aic_sdf_export 2>/dev/null || true

    if [[ -f /tmp/aic.sdf ]]; then
        info "Fixing exported SDF URI corruption ..."
        sed -i 's|file://<urdf-string>/model://|model://|g'          /tmp/aic.sdf
        sed -i 's|file:///lc_plug_visual.glb|model://LC Plug/lc_plug_visual.glb|g'   /tmp/aic.sdf
        sed -i 's|file:///sc_plug_visual.glb|model://SC Plug/sc_plug_visual.glb|g'   /tmp/aic.sdf
        sed -i 's|file:///sfp_module_visual.glb|model://SFP Module/sfp_module_visual.glb|g' /tmp/aic.sdf

        info "Converting SDF → MJCF ..."
        source "$WS_AIC/install/setup.bash"
        mkdir -p "$HOME/aic_mujoco_world"
        sdf2mjcf /tmp/aic.sdf "$HOME/aic_mujoco_world/aic_world.xml"
        cp "$HOME/aic_mujoco_world/"* "$WS_AIC/src/aic/aic_utils/aic_mujoco/mjcf/"

        info "Running add_cable_plugin.py (must run without ROS workspace sourced) ..."
        # Use a subprocess with a clean environment to avoid ROS workspace interference
        env -i HOME="$HOME" PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
            python3 "$WS_AIC/src/aic/aic_utils/aic_mujoco/scripts/add_cable_plugin.py" \
                --input  "$WS_AIC/src/aic/aic_utils/aic_mujoco/mjcf/aic_world.xml" \
                --output "$WS_AIC/src/aic/aic_utils/aic_mujoco/mjcf/aic_world.xml" \
                --robot_output "$WS_AIC/src/aic/aic_utils/aic_mujoco/mjcf/aic_robot.xml" \
                --scene_output "$WS_AIC/src/aic/aic_utils/aic_mujoco/mjcf/scene.xml"

        info "Rebuilding aic_mujoco package ..."
        cd "$WS_AIC"
        source /opt/ros/kilted/setup.bash
        colcon build --packages-select aic_mujoco --symlink-install

        ok "MuJoCo scene.xml generated"
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 4 — TEST: MuJoCo + WaveArm
# ─────────────────────────────────────────────────────────────────────────────
log "TEST 2/3 · MuJoCo — WaveArm"

if [[ ! -f "$MUJOCO_SCENE" ]]; then
    fail "MuJoCo test skipped — scene.xml not found (SDF export failed above)"
else
    tmux kill-session -t aic_mujoco_test 2>/dev/null || true

    # Pane 0: Zenoh router
    tmux new-session -d -s aic_mujoco_test -x 220 -y 50
    tmux send-keys -t aic_mujoco_test:0 \
        "source $WS_AIC/install/setup.bash && \
         export RMW_IMPLEMENTATION=rmw_zenoh_cpp && \
         export ZENOH_CONFIG_OVERRIDE='transport/shared_memory/enabled=true' && \
         ros2 run rmw_zenoh_cpp rmw_zenohd" Enter
    sleep 5

    # Pane 1: MuJoCo bringup
    tmux split-window -v -t aic_mujoco_test:0
    tmux send-keys -t aic_mujoco_test:0.1 \
        "source $WS_AIC/install/setup.bash && \
         export RMW_IMPLEMENTATION=rmw_zenoh_cpp && \
         export ZENOH_CONFIG_OVERRIDE='transport/shared_memory/enabled=true' && \
         ros2 launch aic_mujoco aic_mujoco_bringup.launch.py" Enter

    info "Waiting 20s for MuJoCo + ros2_control to initialise ..."
    sleep 20

    # Pane 2: WaveArm policy
    tmux split-window -v -t aic_mujoco_test:0.1
    MUJOCO_LOG=$(mktemp /tmp/aic_mujoco_test.XXXXXX)
    tmux send-keys -t aic_mujoco_test:0.2 \
        "cd $WS_AIC/src/aic && \
         pixi run ros2 run aic_model aic_model \
         --ros-args -p use_sim_time:=true \
         -p policy:=aic_example_policies.ros.WaveArm 2>&1 | tee $MUJOCO_LOG" Enter

    info "Running WaveArm in MuJoCo for ${TEST_TIMEOUT_MUJOCO}s ..."
    sleep "$TEST_TIMEOUT_MUJOCO"

    # Success = aic_model started and no "Error" / "Traceback" in its output
    if [[ -f "$MUJOCO_LOG" ]] && grep -q "aic_model" "$MUJOCO_LOG" 2>/dev/null \
       && ! grep -qi "traceback\|Error\|fatal" "$MUJOCO_LOG" 2>/dev/null; then
        PASS_MUJOCO=true
        ok "MuJoCo test PASSED — WaveArm ran for ${TEST_TIMEOUT_MUJOCO}s without errors"
    else
        fail "MuJoCo test: unexpected output or aic_model did not start"
        [[ -f "$MUJOCO_LOG" ]] && tail -20 "$MUJOCO_LOG" >&2 || true
    fi
    rm -f "$MUJOCO_LOG"

    tmux kill-session -t aic_mujoco_test 2>/dev/null || true
fi

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 5 — TEST: Isaac Lab — list_envs smoke test
# ─────────────────────────────────────────────────────────────────────────────
log "TEST 3/3 · Isaac Lab — AIC-Task-v0 list_envs"

if [[ "$SKIP_ISAAC_BUILD" == true ]] && ! docker image inspect isaac-lab-base &>/dev/null 2>&1; then
    fail "Isaac Lab test skipped — image not built (run without --skip-isaac-build)"
else
    cd "$ISAACLAB_DIR"

    # Start the container if not already running
    ./docker/container.py start base 2>/dev/null || true

    ISAAC_LOG=$(mktemp /tmp/aic_isaac_test.XXXXXX)

    info "Installing aic_task and running list_envs inside container ..."
    docker exec isaac-lab-base bash -c "
        python -m pip install -q -e /workspace/isaaclab/aic/aic_utils/aic_isaac/aic_isaaclab/source/aic_task && \
        python /workspace/isaaclab/aic/aic_utils/aic_isaac/aic_isaaclab/scripts/list_envs.py
    " 2>&1 | tee "$ISAAC_LOG" || true

    if grep -q "AIC-Task-v0" "$ISAAC_LOG" 2>/dev/null; then
        PASS_ISAAC=true
        ok "Isaac Lab test PASSED — AIC-Task-v0 registered"
    else
        fail "Isaac Lab test: AIC-Task-v0 not found in list_envs output"
        tail -20 "$ISAAC_LOG" >&2 || true
        info "Note: download Intrinsic_assets.zip before running the full task:"
        info "  https://developer.nvidia.com/downloads/Omniverse/learning/Events/Hackathons/Intrinsic_assets.zip"
        info "  Extract to: $ISAACLAB_DIR/aic/aic_utils/aic_isaac/aic_isaaclab/source/aic_task/aic_task/tasks/manager_based/aic_task/"
    fi
    rm -f "$ISAAC_LOG"
fi

# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
log "SUMMARY"

echo ""
printf "  %-30s %s\n" "Lane 1 · Gazebo + WaveArm"    "$( [[ $PASS_GAZEBO  == true ]] && echo '✓ PASS' || echo '✗ FAIL')"
printf "  %-30s %s\n" "Lane 2 · MuJoCo + WaveArm"    "$( [[ $PASS_MUJOCO  == true ]] && echo '✓ PASS' || echo '✗ FAIL')"
printf "  %-30s %s\n" "Lane 3 · Isaac Lab list_envs"  "$( [[ $PASS_ISAAC   == true ]] && echo '✓ PASS' || echo '✗ FAIL')"
echo ""
echo "  Aliases active after: source $SHELL_RC"
echo ""
echo "  Quick reference:"
echo "    aic-eval-gt              # start Gazebo eval (ground_truth:=true)"
echo "    aic-policy WaveArm       # run any example policy"
echo "    aic-policy CheatCode     # ground-truth oracle"
echo "    aic-zenoh                # terminal 1 for MuJoCo lane"
echo "    aic-mujoco               # terminal 2 for MuJoCo lane"
echo "    aic-isaac                # enter Isaac Lab container"
echo ""
echo "  Next: run CheatCode in Gazebo to collect oracle demos"
echo "    aic-eval-gt  (terminal 1)"
echo "    aic-policy CheatCode     (terminal 2)"
