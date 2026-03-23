#!/usr/bin/env bash
# setup.sh — Master script: installs everything then runs headless tests
#
# Usage:
#   bash setup.sh                    # full install + headless tests
#   bash setup.sh --skip-install     # headless tests only
#   bash setup.sh --skip-isaac-build # skip 30-min Isaac Lab Docker build
#   bash setup.sh --test-gui         # run GUI tests after headless
set -eo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$HOME/Project-Automaton"
echo "=== Submodules ==="
git submodule update --init --recursive
SKIP_INSTALL=false
SKIP_ISAAC_BUILD=false
TEST_GUI=false

for arg in "$@"; do
    case $arg in
        --skip-install)      SKIP_INSTALL=true ;;
        --skip-isaac-build)  SKIP_ISAAC_BUILD=true ;;
        --test-gui)          TEST_GUI=true ;;
    esac
done

echo "╔══════════════════════════════════════════╗"
echo "║  AIC Setup — Project Automaton           ║"
echo "╚══════════════════════════════════════════╝"
echo ""

if [[ "$SKIP_INSTALL" == false ]]; then
    ISAAC_FLAG=""
    [[ "$SKIP_ISAAC_BUILD" == true ]] && ISAAC_FLAG="--skip-isaac-build"
    bash "$DIR/install_sim.sh" $ISAAC_FLAG
fi

echo ""
bash "$DIR/test_headless.sh"

if [[ "$TEST_GUI" == true ]]; then
    echo ""
    bash "$DIR/test_gui.sh"
fi

echo ""
echo "Done. Source ~/.bashrc for aliases: aic-eval-gt, aic-policy, aic-mujoco, aic-isaac"
