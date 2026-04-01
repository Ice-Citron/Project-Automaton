#!/usr/bin/env bash
# convert_rosbags_to_lerobot.sh — Session of per-trial ros2 bags → LeRobot v3 (ACT layout)
#
# Usage:
#   bash aws/convert_rosbags_to_lerobot.sh <session-dir> <output-dataset-dir> [--extra-args...]
#
# Example:
#   bash aws/convert_rosbags_to_lerobot.sh ~/bags/run1 ~/datasets/aic_act --repo-id local/aic_run1
#
# Requires: AIC pixi env with lerobot + rosbag2_py (see aws/install_sim.sh).
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION="${1:?Usage: $0 <session-dir> <output-dataset-dir> [-- args for rosbag_to_lerobot_aic.py]}"
OUTPUT="${2:?Usage: $0 <session-dir> <output-dataset-dir> [-- args...]}"
shift 2

if [[ -n "${AIC_WS:-}" ]]; then
  A="$AIC_WS"
elif [[ -d "$SCRIPT_DIR/../References/aic" ]]; then
  A="$(cd "$SCRIPT_DIR/../References/aic" && pwd)"
else
  A="$HOME/ws_aic/src/aic"
fi

[[ -d "$A" ]] || { echo "[ERROR] AIC workspace not found: $A (set AIC_WS)" >&2; exit 1; }
[[ -d "$SESSION" ]] || { echo "[ERROR] Session directory not found: $SESSION" >&2; exit 1; }

SESSION_ABS="$(cd "$SESSION" && pwd)"
OUT_PARENT="$(dirname "$OUTPUT")"
OUT_LEAF="$(basename "$OUTPUT")"
mkdir -p "$OUT_PARENT"
OUTPUT_ABS="$(cd "$OUT_PARENT" && pwd)/$OUT_LEAF"

cd "$A"
exec pixi run python "$SCRIPT_DIR/rosbag_to_lerobot_aic.py" \
  --session-dir "$SESSION_ABS" \
  --output-dir "$OUTPUT_ABS" \
  "$@"
