#!/usr/bin/env bash
# test_gui.sh — Visual tests on DCV desktop (requires DISPLAY)
#   Lane 1: Gazebo + CheatCode (Gazebo GUI)
#   Lane 2: MuJoCo viewer + CheatCode via ros2_control
#   Lane 3: Isaac Lab random_agent (Isaac Sim GUI)
#
# Usage: bash test_gui.sh [lane1|lane2|lane3]  (default: all)
set -eo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AIC="$REPO_ROOT/References/aic"
WS="$HOME/ws_aic"
ISAACLAB="$HOME/IsaacLab"
DISPLAY="${DISPLAY:-:1}"; export DISPLAY
export DBX_CONTAINER_MANAGER=docker
export PATH="$HOME/.pixi/bin:$PATH"

LANE="${1:-all}"
xhost +local:docker 2>/dev/null || true

run_lane1() {
    echo "=== Lane 1: Gazebo + CheatCode (GUI) ==="
    tmux kill-session -t aic_gz_gui 2>/dev/null || true
    tmux new-session -d -s aic_gz_gui -x 200 -y 40

    tmux send-keys -t aic_gz_gui:0 \
        "export DBX_CONTAINER_MANAGER=docker DISPLAY=$DISPLAY && \
         distrobox enter -r aic_eval -- /entrypoint.sh ground_truth:=true start_aic_engine:=true" Enter
    sleep 40

    tmux split-window -v -t aic_gz_gui:0
    tmux send-keys -t aic_gz_gui:0.1 \
        "export PATH=$HOME/.pixi/bin:\$PATH && cd $WS/src/aic && \
         pixi run ros2 run aic_model aic_model --ros-args \
         -p use_sim_time:=true -p policy:=aic_example_policies.ros.CheatCode" Enter

    echo "  Gazebo running in tmux session 'aic_gz_gui'"
    echo "  Attach: tmux attach -t aic_gz_gui"
    echo "  Kill:   tmux kill-session -t aic_gz_gui"
}

run_lane2() {
    echo "=== Lane 2: MuJoCo + CheatCode (GUI) ==="
    tmux kill-session -t aic_mj_gui 2>/dev/null || true
    tmux new-session -d -s aic_mj_gui -x 200 -y 40

    # Pane 0: Zenoh router
    tmux send-keys -t aic_mj_gui:0 \
        "source $WS/install/setup.bash && \
         export RMW_IMPLEMENTATION=rmw_zenoh_cpp ZENOH_CONFIG_OVERRIDE='transport/shared_memory/enabled=true' && \
         ros2 run rmw_zenoh_cpp rmw_zenohd" Enter
    sleep 5

    # Pane 1: MuJoCo bringup (includes viewer)
    tmux split-window -v -t aic_mj_gui:0
    tmux send-keys -t aic_mj_gui:0.1 \
        "export DISPLAY=$DISPLAY && source $WS/install/setup.bash && \
         export RMW_IMPLEMENTATION=rmw_zenoh_cpp ZENOH_CONFIG_OVERRIDE='transport/shared_memory/enabled=true' && \
         ros2 launch aic_mujoco aic_mujoco_bringup.launch.py" Enter
    sleep 20

    # Pane 2: CheatCode policy
    tmux split-window -v -t aic_mj_gui:0
    tmux send-keys -t aic_mj_gui:0.2 \
        "export PATH=$HOME/.pixi/bin:\$PATH && cd $WS/src/aic && \
         pixi run ros2 run aic_model aic_model --ros-args \
         -p use_sim_time:=true -p policy:=aic_example_policies.ros.CheatCode" Enter

    echo "  MuJoCo running in tmux session 'aic_mj_gui'"
    echo "  Attach: tmux attach -t aic_mj_gui"
    echo "  Kill:   tmux kill-session -t aic_mj_gui"
}

run_lane3() {
    echo "=== Lane 3: Isaac Lab random_agent (GUI) ==="
    docker start isaac-lab-base 2>/dev/null \
        || (cd "$ISAACLAB" && echo "y" | python3 docker/container.py start base 2>/dev/null) || true

    # Copy Intrinsic_assets if available
    ASSETS="$ISAACLAB/aic/aic_utils/aic_isaac/aic_isaaclab/source/aic_task/aic_task/tasks/manager_based/aic_task/Intrinsic_assets"
    ASSETS_DEST="/workspace/isaaclab/aic/aic_utils/aic_isaac/aic_isaaclab/source/aic_task/aic_task/tasks/manager_based/aic_task/Intrinsic_assets"
    [[ -d "$ASSETS" ]] && docker cp "$ASSETS" "isaac-lab-base:$ASSETS_DEST" 2>/dev/null || true

    PY="/workspace/isaaclab/_isaac_sim/python.sh"
    docker exec isaac-lab-base bash -c "
        $PY -m pip install --no-build-isolation -q -e /workspace/isaaclab/source/isaaclab 2>/dev/null
        $PY -m pip install -q -e /workspace/isaaclab/aic/aic_utils/aic_isaac/aic_isaaclab/source/aic_task 2>/dev/null
    " || true

    echo "  Starting random_agent with GUI ..."
    docker exec -d isaac-lab-base bash -c "
        export DISPLAY=$DISPLAY
        $PY /workspace/isaaclab/aic/aic_utils/aic_isaac/aic_isaaclab/scripts/random_agent.py \
            --task AIC-Task-v0 --num_envs 1 --enable_cameras
    "
    echo "  Isaac Lab running inside isaac-lab-base container"
    echo "  Check: docker exec isaac-lab-base ps aux | grep random_agent"
    echo "  Kill:  docker exec isaac-lab-base pkill -f random_agent"
}

case "$LANE" in
    lane1) run_lane1 ;;
    lane2) run_lane2 ;;
    lane3) run_lane3 ;;
    all)   run_lane1; run_lane2; run_lane3 ;;
    *)     echo "Usage: $0 [lane1|lane2|lane3|all]"; exit 1 ;;
esac
