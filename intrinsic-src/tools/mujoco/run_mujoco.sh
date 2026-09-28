#!/bin/bash
# Run full MuJoCo AIC pipeline: Zenoh + MuJoCo + Policy + Trigger
# Usage: bash ~/projects/Project-Automaton/Intrinsic-AI/tools/mujoco/run_mujoco.sh [policy_name]
#   Default policy: WaveArm
#   Example: bash run_mujoco.sh CheatCode
#
# Press Ctrl+C to stop everything.

POLICY=${1:-WaveArm}
echo "Policy: $POLICY"

cleanup() {
    echo ""
    echo "Shutting down..."
    pkill -f rmw_zenohd 2>/dev/null
    pkill -f mujoco_ros2_control 2>/dev/null
    pkill -f aic_model 2>/dev/null
    pkill -f trigger_policy 2>/dev/null
    pkill -f robot_state_publisher 2>/dev/null
    pkill -f rviz2 2>/dev/null
    echo "Done."
    exit 0
}
trap cleanup SIGINT SIGTERM

# Kill any leftover processes from previous runs
echo "Cleaning up old processes..."
pkill -9 -f rmw_zenohd 2>/dev/null
pkill -9 -f mujoco_ros2_control 2>/dev/null
pkill -9 -f aic_model 2>/dev/null
pkill -9 -f robot_state_publisher 2>/dev/null
pkill -9 -f rviz2 2>/dev/null
pkill -9 -f trigger_policy 2>/dev/null
sleep 2

source ~/ws_aic/install/setup.bash
export RMW_IMPLEMENTATION=rmw_zenoh_cpp

echo "=== [1/4] Zenoh router ==="
ros2 run rmw_zenoh_cpp rmw_zenohd &
sleep 3

echo "=== [2/4] MuJoCo sim ==="
ros2 launch aic_mujoco aic_mujoco_bringup.launch.py &
sleep 12

echo "=== [3/4] Policy: $POLICY ==="
ros2 run aic_model aic_model --ros-args -p use_sim_time:=true \
    -p policy:=aic_example_policies.ros.$POLICY &
sleep 5

echo "=== [4/4] Triggering ==="
export ZENOH_ROUTER_CHECK_ATTEMPTS=10
python3 ~/projects/Project-Automaton/Intrinsic-AI/tools/mujoco/trigger_policy.py 2>&1 | grep -v zenoh

echo ""
echo "========================================="
echo "  Policy finished. MuJoCo still running."
echo "  Press Ctrl+C to stop everything."
echo "========================================="

wait
