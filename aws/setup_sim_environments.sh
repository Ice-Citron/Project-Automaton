#!/usr/bin/env bash
# setup_sim_environments.sh
#
# Installs all three AIC simulation lanes then smoke-tests each one.
# Consolidated from:
#   - Official AIC docs/getting_started.md
#   - Official AIC aic_utils/aic_mujoco/README.md
#   - Official AIC aic_utils/aic_isaac/README.md
#   - Intrinsic-AI/setup-transcript.md
#
#   Lane 1 — Gazebo/Kilted  : aic_eval distrobox + pixi -> runs CheatCode, checks scoring.yaml
#   Lane 2 — MuJoCo         : colcon source build ~/ws_aic -> runs CheatCode via aic_mujoco_bringup
#   Lane 3 — Isaac Lab      : IsaacLab Docker + aic_task -> runs list_envs (AIC-Task-v0 smoke test)
#
# Usage: bash setup_sim_environments.sh [--skip-install] [--skip-isaac-build]
#
#   --skip-install       jump straight to the test phase (all deps already installed)
#   --skip-isaac-build   skip the IsaacLab Docker image build (takes 20-30 min)

set -eo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
AIC_REPO="$REPO_ROOT/References/aic"
WS_AIC="$HOME/ws_aic"
ISAACLAB_DIR="$HOME/IsaacLab"
RESULTS_DIR="$HOME/aic_results"
TEST_TIMEOUT_GAZEBO=300   # seconds to wait for CheatCode to finish 3 trials
TEST_TIMEOUT_MUJOCO=120   # seconds to let MuJoCo + CheatCode run
DISPLAY="${DISPLAY:-:1}"
export DISPLAY

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
ok "Display: $DISPLAY"

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1 — INSTALL
# ─────────────────────────────────────────────────────────────────────────────
if [[ "$SKIP_INSTALL" == false ]]; then

# ── 1a. System packages ───────────────────────────────────────────────────────
log "1a · System packages"
sudo apt-get update -qq
# Remove Ubuntu's vcstool if present — it conflicts with python3-vcstool from
# the ROS repo (which ros-kilted-ament-cmake-vendor-package depends on).
if dpkg -l vcstool 2>/dev/null | grep -q "^ii"; then
    sudo dpkg --remove --force-remove-reinstreq vcstool 2>/dev/null || true
    sudo apt --fix-broken install -y 2>/dev/null || true
fi
sudo apt-get install -y \
    curl wget git ca-certificates gnupg lsb-release \
    build-essential python3 python3-pip \
    g++-14 gcc-14 \
    distrobox \
    x11-xserver-utils \
    tmux
ok "System packages installed"

# ── 1b. NVIDIA Container Toolkit ──────────────────────────────────────────────
log "1b · NVIDIA Container Toolkit"
if ! dpkg -l nvidia-container-toolkit &>/dev/null 2>&1; then
    info "Installing NVIDIA Container Toolkit ..."
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
        | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg 2>/dev/null || true
    curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
        | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
        | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list > /dev/null
    sudo apt-get update -qq
    sudo apt-get install -y nvidia-container-toolkit
    sudo nvidia-ctk runtime configure --runtime=docker
    sudo systemctl restart docker
    ok "NVIDIA Container Toolkit installed and configured"
else
    ok "NVIDIA Container Toolkit already installed"
fi

# ── 1c. Pixi ─────────────────────────────────────────────────────────────────
log "1c · Pixi"
if ! command -v pixi &>/dev/null; then
    curl -fsSL https://pixi.sh/install.sh | sh
fi
export PATH="$HOME/.pixi/bin:$PATH"
grep -q '/.pixi/bin' "$SHELL_RC" 2>/dev/null \
    || echo 'export PATH="$HOME/.pixi/bin:$PATH"' >> "$SHELL_RC"
ok "Pixi $(pixi --version)"

# ── 1d. Pixi workspace + pixi install ────────────────────────────────────────
log "1d · Pixi workspace (~/ws_aic)"
mkdir -p "$WS_AIC/src"
if [[ ! -e "$WS_AIC/src/aic" ]]; then
    ln -s "$AIC_REPO" "$WS_AIC/src/aic"
    info "Symlinked $AIC_REPO -> $WS_AIC/src/aic"
fi
info "Running pixi install (ROS 2 Kilted + all Python deps) ..."
cd "$WS_AIC/src/aic"
pixi install
ok "Pixi workspace ready"

# ── 1e. aic_eval distrobox container (official approach) ──────────────────────
# Ref: docs/getting_started.md Step 2
log "1e · aic_eval distrobox container"
export DBX_CONTAINER_MANAGER=docker
info "Pulling ghcr.io/intrinsic-dev/aic/aic_eval:latest ..."
docker pull ghcr.io/intrinsic-dev/aic/aic_eval:latest
if ! distrobox list 2>/dev/null | grep -q "aic_eval"; then
    distrobox create -r --nvidia -i ghcr.io/intrinsic-dev/aic/aic_eval:latest aic_eval
    ok "distrobox aic_eval created"
else
    ok "distrobox aic_eval already exists"
fi

# ##########################################################################
# # TODO: LANE 2 (MuJoCo) IS BROKEN — DO NOT UNCOMMENT UNTIL FIXED
# #
# # The SDF→MJCF conversion pipeline produces mismatched mesh hashes and
# # broken physics (robot falls over, task board missing, glass panes gone).
# # The add_cable_plugin.py script + sdf2mjcf converter generate XML that
# # references mesh filenames with different hash prefixes than what the
# # converter actually outputs. Even when hashes match, the resulting scene
# # has incorrect joint positions and missing collision geometry.
# #
# # To fix: upstream needs to ship pre-built MJCF files with matching meshes,
# # or the sdf2mjcf + add_cable_plugin.py pipeline needs debugging.
# #
# # What was here: steps 1f (ROS 2 Kilted install), 1f+ (sdformat bindings),
# # 1g (MuJoCo colcon build with mujoco_vendor, mujoco_ros2_control, gcc-14).
# # See git history for the full implementation.
# ##########################################################################

: # ── 1f. ROS 2 Kilted host install (for MuJoCo colcon build) ── SKIPPED (BROKEN)
: # ── 1g. MuJoCo colcon build ── SKIPPED (BROKEN)

# ── 1h. IsaacLab ─────────────────────────────────────────────────────────────
# Ref: aic_utils/aic_isaac/README.md
log "1h · IsaacLab"
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

# ── 1i. Shell aliases ─────────────────────────────────────────────────────────
log "1i · Shell aliases"
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

alias aic-zenoh='source "$HOME/ws_aic/install/setup.bash" && export RMW_IMPLEMENTATION=rmw_zenoh_cpp && export ZENOH_CONFIG_OVERRIDE="transport/shared_memory/enabled=true" && ros2 run rmw_zenoh_cpp rmw_zenohd'
alias aic-mujoco='source "$HOME/ws_aic/install/setup.bash" && export RMW_IMPLEMENTATION=rmw_zenoh_cpp && export ZENOH_CONFIG_OVERRIDE="transport/shared_memory/enabled=true" && ros2 launch aic_mujoco aic_mujoco_bringup.launch.py'
alias aic-isaac='cd "$HOME/IsaacLab" && ./docker/container.py start base && ./docker/container.py enter base'
ALIASES
    ok "Aliases written to $SHELL_RC"
else
    ok "Aliases already present in $SHELL_RC"
fi

fi  # end SKIP_INSTALL

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 — TEST: Gazebo + CheatCode
# ─────────────────────────────────────────────────────────────────────────────
log "TEST 1/3 · Gazebo — CheatCode (ground_truth:=true, 3 trials)"

require_tmux
export DBX_CONTAINER_MANAGER=docker
# Allow Docker/distrobox containers to use the X11 display
xhost +local:docker 2>/dev/null || true

# Ensure distrobox aic_eval exists (may have been destroyed by docker rm)
if ! distrobox list 2>/dev/null | grep -q "aic_eval"; then
    info "Recreating distrobox aic_eval ..."
    distrobox create -r --nvidia -i ghcr.io/intrinsic-dev/aic/aic_eval:latest aic_eval
fi

mkdir -p "$RESULTS_DIR"
# aic_engine writes scoring.yaml to $HOME/aic_results/ by default (inside distrobox
# the host $HOME is shared). We check both the default and AIC_RESULTS_DIR locations.
GAZEBO_RESULTS="$RESULTS_DIR"

# Kill any leftover session from a previous run
tmux kill-session -t aic_gazebo_test 2>/dev/null || true

# Pane 0: eval container (Gazebo + aic_engine + ground_truth) via distrobox
tmux new-session -d -s aic_gazebo_test -x 220 -y 50
tmux send-keys -t aic_gazebo_test:0 \
    "export DBX_CONTAINER_MANAGER=docker && export DISPLAY=$DISPLAY && \
     distrobox enter -r aic_eval -- \
     /entrypoint.sh ground_truth:=true start_aic_engine:=true" Enter

info "Waiting 40s for Gazebo + aic_engine to initialise ..."
sleep 40

# Pane 1: CheatCode policy via pixi (runs on host, communicates over Zenoh)
# Ref: aic_example_policies/README.md — CheatCode needs ground_truth:=true
tmux split-window -v -t aic_gazebo_test:0
tmux send-keys -t aic_gazebo_test:0.1 \
    "export PATH=$HOME/.pixi/bin:\$PATH && \
     cd $WS_AIC/src/aic && pixi run ros2 run aic_model aic_model \
     --ros-args -p use_sim_time:=true \
     -p policy:=aic_example_policies.ros.CheatCode" Enter

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
    ok "Gazebo+CheatCode PASSED — scoring.yaml at $GAZEBO_RESULTS/scoring.yaml"
    cat "$GAZEBO_RESULTS/scoring.yaml" 2>/dev/null || true
else
    fail "Gazebo test: scoring.yaml not found within ${TEST_TIMEOUT_GAZEBO}s"
    info "Debug: tmux attach -t aic_gazebo_test (if still running)"
    info "Or manually: distrobox enter -r aic_eval -- /entrypoint.sh ground_truth:=true start_aic_engine:=true"
fi

# ##########################################################################
# # TODO: PHASE 3 & 4 (MuJoCo scene generation + test) — BROKEN
# # See TODO note above in Lane 2 install section for details.
# # The SDF→MJCF pipeline (sdf2mjcf + add_cable_plugin.py) produces
# # broken scenes with wrong joint positions and missing geometry.
# ##########################################################################
log "SKIPPED · MuJoCo scene generation + test (BROKEN — see TODO in script)"
warn "Lane 2 (MuJoCo) is disabled. SDF→MJCF conversion pipeline needs fixing."
PASS_MUJOCO=false

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 5 — TEST: Isaac Lab — list_envs smoke test
# ─────────────────────────────────────────────────────────────────────────────
# Ref: aic_utils/aic_isaac/README.md "Usage"
log "TEST 3/3 · Isaac Lab — AIC-Task-v0 list_envs"

if [[ "$SKIP_ISAAC_BUILD" == true ]] && ! docker image inspect isaac-lab-base &>/dev/null 2>&1; then
    fail "Isaac Lab test skipped — image not built (run without --skip-isaac-build)"
else
    if [[ ! -d "$ISAACLAB_DIR" ]]; then
        fail "Isaac Lab test skipped — $ISAACLAB_DIR not found"
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
            info "  Extract to: $ISAACLAB_DIR/aic/aic_utils/aic_isaac/aic_isaaclab/source/aic_task/aic_task/tasks/manager_based/aic_task/"
        fi
        rm -f "$ISAAC_LOG"
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
log "SUMMARY"

echo ""
printf "  %-30s %s\n" "Lane 1 · Gazebo + CheatCode"   "$( [[ $PASS_GAZEBO  == true ]] && echo '✓ PASS' || echo '✗ FAIL')"
printf "  %-30s %s\n" "Lane 2 · MuJoCo + CheatCode"   "$( [[ $PASS_MUJOCO  == true ]] && echo '✓ PASS' || echo '✗ FAIL')"
printf "  %-30s %s\n" "Lane 3 · Isaac Lab list_envs"   "$( [[ $PASS_ISAAC   == true ]] && echo '✓ PASS' || echo '✗ FAIL')"
echo ""
echo "  Aliases active after: source $SHELL_RC"
echo ""
echo "  Quick reference:"
echo "    aic-eval-gt              # start Gazebo eval (ground_truth:=true)"
echo "    aic-policy CheatCode     # ground-truth oracle policy"
echo "    aic-policy WaveArm       # wave arm demo"
echo "    aic-zenoh                # terminal 1 for MuJoCo lane"
echo "    aic-mujoco               # terminal 2 for MuJoCo lane"
echo "    aic-isaac                # enter Isaac Lab container"
echo ""
