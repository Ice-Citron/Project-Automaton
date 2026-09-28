#!/usr/bin/env bash
# cheatcode_record.sh — Start AIC eval with ground truth (CheatCode), optional ROS bag recording
#
# Matches the distrobox + CheatCode flow in working_gazebo_setup.sh, plus ros2 bag topics for imitation/offline use.
#
# Usage:
#   bash aws/cheatcode_record.sh help          # print all terminal commands (default)
#   bash aws/cheatcode_record.sh policy        # run CheatCode (requires sim already up)
#   bash aws/cheatcode_record.sh record        # record bag (requires sim + policy)
#
# Optional env:
#   AIC_WS   — pixi workspace root (default: References/aic in repo, else ~/ws_aic/src/aic)
#   BAG_DIR  — output directory for bags (default: ~/bags)

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REF_AIC="$REPO_ROOT/References/aic"
if [[ -n "${AIC_WS:-}" ]]; then
  :
elif [[ -d "$REF_AIC" ]]; then
  AIC_WS="$REF_AIC"
else
  AIC_WS="$HOME/ws_aic/src/aic"
fi
BAG_DIR="${BAG_DIR:-$HOME/bags}"

print_help() {
  cat <<EOF
CheatCode eval + ROS bag recording (three terminals)

=== Terminal 1 — eval container (Gazebo + stack, ground truth) ===
export DBX_CONTAINER_MANAGER=docker
distrobox enter -r aic_eval

Inside the container:
/entrypoint.sh ground_truth:=true start_aic_engine:=true

=== Terminal 2 — CheatCode policy ===
cd $AIC_WS
pixi run ros2 run aic_model aic_model --ros-args -p use_sim_time:=true -p policy:=aic_example_policies.ros.CheatCode

(If ROS discovery fails from the host, run Terminal 2 inside the same distrobox shell and use:
 ros2 run aic_model aic_model --ros-args -p use_sim_time:=true -p policy:=aic_example_policies.ros.CheatCode )

=== Terminal 3 — record (ROS 2 bag) ===
cd $AIC_WS
pixi run ros2 bag record -o $BAG_DIR/cheatcode_run_\$(date +%Y%m%d_%H%M%S) /observations /aic_controller/pose_commands /joint_states

Sanity check (optional):
pixi run ros2 topic list | grep -E 'observations|pose_commands|joint_states'

Note: This produces a ROS bag, not a Hugging Face LeRobot dataset. For ACT/LeRobot format use lerobot-record + teleop (see References/aic/aic_utils/lerobot_robot_aic/README.md).

One bag per InsertCable trial (manifest + trial_NNNN_* dirs):
  bash $SCRIPT_DIR/bag_record_per_trial.sh ~/bags/my_session

Runnable shortcuts from repo (with AIC_WS=$AIC_WS):
  bash aws/cheatcode_record.sh policy
  bash aws/cheatcode_record.sh record
EOF
}

run_policy() {
  [[ -d "$AIC_WS" ]] || {
    echo "[ERROR] AIC workspace not found: $AIC_WS" >&2
    echo "Set AIC_WS or clone aic to ~/ws_aic/src/aic (see working_gazebo_setup.sh)." >&2
    exit 1
  }
  cd "$AIC_WS"
  exec pixi run ros2 run aic_model aic_model --ros-args -p use_sim_time:=true -p policy:=aic_example_policies.ros.CheatCode
}

run_record() {
  [[ -d "$AIC_WS" ]] || {
    echo "[ERROR] AIC workspace not found: $AIC_WS" >&2
    exit 1
  }
  mkdir -p "$BAG_DIR"
  local out="$BAG_DIR/cheatcode_run_$(date +%Y%m%d_%H%M%S)"
  cd "$AIC_WS"
  exec pixi run ros2 bag record -o "$out" /observations /aic_controller/pose_commands /joint_states
}

case "${1:-help}" in
  help|-h|--help) print_help ;;
  policy|cheatcode) run_policy ;;
  record|bag) run_record ;;
  *)
    echo "Unknown command: $1" >&2
    print_help >&2
    exit 1
    ;;
esac
