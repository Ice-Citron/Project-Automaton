#!/usr/bin/env bash
# bag_record_per_trial.sh — One ros2 bag per InsertCable trial (wraps rosbag_per_trial.py)
#
# Usage (from host, AIC already in PATH via pixi):
#   export AIC_WS=~/ws_aic/src/aic    # or Project-Automaton/References/aic
#   bash aws/bag_record_per_trial.sh ~/bags/my_session
#
# Prerequisites: sim + aic_engine running; policy (e.g. CheatCode) up; same Zenoh as usual.
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${1:?Usage: $0 <output-directory>}"

if [[ -n "${AIC_WS:-}" ]]; then
  A="$AIC_WS"
elif [[ -d "$SCRIPT_DIR/../References/aic" ]]; then
  A="$(cd "$SCRIPT_DIR/../References/aic" && pwd)"
else
  A="$HOME/ws_aic/src/aic"
fi

[[ -d "$A" ]] || { echo "[ERROR] AIC workspace not found: $A (set AIC_WS)" >&2; exit 1; }

cd "$A"
exec pixi run python "$SCRIPT_DIR/rosbag_per_trial.py" --output-dir "$(mkdir -p "$OUT" && cd "$OUT" && pwd)"
