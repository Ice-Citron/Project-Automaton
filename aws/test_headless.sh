#!/usr/bin/env bash
# test_headless.sh — Headless verification of all 3 sim lanes
#   Lane 1: Gazebo + CheatCode → scoring.yaml
#   Lane 2: MuJoCo scene loads in Python
#   Lane 3: Isaac Lab → AIC-Task-v0 registered
set -eo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AIC="$REPO_ROOT/References/aic"
WS="$HOME/ws_aic"
ISAACLAB="$HOME/IsaacLab"
RESULTS="$HOME/aic_results"
DISPLAY="${DISPLAY:-:1}"; export DISPLAY
export DBX_CONTAINER_MANAGER=docker
export PATH="$HOME/.pixi/bin:$PATH"

PASS_GAZEBO=false PASS_MUJOCO=false PASS_ISAAC=false

# ── Lane 1: Gazebo + CheatCode scoring ──────────────────────────────────────
echo "=== Test 1/3: Gazebo + CheatCode ==="
xhost +local:docker 2>/dev/null || true
distrobox list 2>/dev/null | grep -q "aic_eval" \
    || distrobox create -r --nvidia -i ghcr.io/intrinsic-dev/aic/aic_eval:latest aic_eval

mkdir -p "$RESULTS"
rm -f "$RESULTS/scoring.yaml"
tmux kill-session -t aic_gz 2>/dev/null || true
tmux new-session -d -s aic_gz -x 200 -y 40

# Pane 0: Gazebo eval
tmux send-keys -t aic_gz:0 \
    "export DBX_CONTAINER_MANAGER=docker DISPLAY=$DISPLAY && \
     distrobox enter -r aic_eval -- /entrypoint.sh ground_truth:=true start_aic_engine:=true" Enter
echo "  Waiting 40s for Gazebo ..." && sleep 40

# Pane 1: CheatCode policy
tmux split-window -v -t aic_gz:0
tmux send-keys -t aic_gz:0.1 \
    "export PATH=$HOME/.pixi/bin:\$PATH && cd $WS/src/aic && \
     pixi run ros2 run aic_model aic_model --ros-args \
     -p use_sim_time:=true -p policy:=aic_example_policies.ros.CheatCode" Enter

echo "  Waiting up to 300s for 3 trials to complete ..."
for i in $(seq 1 60); do
    # aic_engine creates scoring.yaml immediately with zeros; wait for trial_3 (all 3 done)
    if grep -q "trial_3:" "$RESULTS/scoring.yaml" 2>/dev/null; then
        PASS_GAZEBO=true; break
    fi
    sleep 5
done
tmux kill-session -t aic_gz 2>/dev/null || true

if $PASS_GAZEBO; then
    SCORE=$(grep "^total:" "$RESULTS/scoring.yaml" 2>/dev/null | awk '{print $2}')
    echo "[OK] Gazebo CheatCode — total score: $SCORE"
else
    echo "[FAIL] Gazebo — 3 trials not completed within 300s"
fi

# ── Lane 2: MuJoCo scene verification ───────────────────────────────────────
echo "=== Test 2/3: MuJoCo scene ==="
SCENE="$AIC/aic_utils/aic_mujoco/mjcf/scene.xml"
if [[ -f "$SCENE" ]]; then
    RESULT=$(python3 -c "
import mujoco
m = mujoco.MjModel.from_xml_path('$SCENE')
d = mujoco.MjData(m)
for _ in range(10): mujoco.mj_step(m, d)
print(f'OK: {m.nbody} bodies, {m.njnt} joints, {m.nu} actuators, 10 steps clean')
" 2>&1)
    if echo "$RESULT" | grep -q "^OK:"; then
        PASS_MUJOCO=true
        echo "[OK] MuJoCo — $RESULT"
    else
        echo "[FAIL] MuJoCo — $RESULT"
    fi
else
    echo "[FAIL] MuJoCo — scene.xml not found"
fi

# ── Lane 3: Isaac Lab AIC-Task-v0 ───────────────────────────────────────────
echo "=== Test 3/3: Isaac Lab ==="
if docker image inspect isaac-lab-base &>/dev/null; then
    # Use docker start directly (container.py start triggers rebuilds)
    docker start isaac-lab-base 2>/dev/null \
        || (cd "$ISAACLAB" && echo "y" | python3 docker/container.py start base 2>/dev/null) || true
    docker update --restart unless-stopped isaac-lab-base 2>/dev/null || true

    # Copy Intrinsic_assets if available on host
    ASSETS="$ISAACLAB/aic/aic_utils/aic_isaac/aic_isaaclab/source/aic_task/aic_task/tasks/manager_based/aic_task/Intrinsic_assets"
    ASSETS_DEST="/workspace/isaaclab/aic/aic_utils/aic_isaac/aic_isaaclab/source/aic_task/aic_task/tasks/manager_based/aic_task/Intrinsic_assets"
    [[ -d "$ASSETS" ]] && docker cp "$ASSETS" "isaac-lab-base:$ASSETS_DEST" 2>/dev/null || true

    PY="/workspace/isaaclab/_isaac_sim/python.sh"
    docker exec isaac-lab-base bash -c "
        $PY -m pip install --no-build-isolation -q -e /workspace/isaaclab/source/isaaclab 2>/dev/null
        $PY -m pip install -q -e /workspace/isaaclab/aic/aic_utils/aic_isaac/aic_isaaclab/source/aic_task 2>/dev/null
    " 2>&1 || true

    RESULT=$(docker exec isaac-lab-base bash -c "
        $PY -u -c '
from isaaclab.app import AppLauncher
import argparse
app = AppLauncher(argparse.Namespace(headless=True))
sim_app = app.app
import gymnasium as gym, aic_task.tasks
found = [s.id for s in gym.registry.values() if \"AIC\" in s.id]
with open(\"/tmp/aic_envs.txt\",\"w\") as f: f.write(\"\n\".join(found))
sim_app.close()
' 2>/dev/null
        cat /tmp/aic_envs.txt
    " 2>&1 | tail -3)

    if echo "$RESULT" | grep -q "AIC-Task-v0"; then
        PASS_ISAAC=true
        echo "[OK] Isaac Lab — AIC-Task-v0 registered"
    else
        echo "[FAIL] Isaac Lab — AIC-Task-v0 not found"
    fi
else
    echo "[FAIL] Isaac Lab — image not built"
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "=== HEADLESS TEST RESULTS ==="
printf "  %-28s %s\n" "Lane 1 · Gazebo CheatCode"  "$($PASS_GAZEBO && echo 'PASS' || echo 'FAIL')"
printf "  %-28s %s\n" "Lane 2 · MuJoCo scene"       "$($PASS_MUJOCO && echo 'PASS' || echo 'FAIL')"
printf "  %-28s %s\n" "Lane 3 · Isaac Lab envs"      "$($PASS_ISAAC  && echo 'PASS' || echo 'FAIL')"
echo ""
