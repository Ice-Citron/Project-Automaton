# AWS Setup — AIC Simulation Environment

Scripts to set up all 3 AIC simulation lanes on a fresh Ubuntu 24.04 AWS instance with NVIDIA GPU.

## Quick Start

```bash
# From a fresh instance after cloning the repo:
cd Project-Automaton

# 1. DCV remote desktop (run first, then connect via browser)
bash aws/install_dcv.sh

# 2. Dev tools (Node.js, Claude Code)
bash aws/install_devtools.sh

# 3. Everything else (all 3 sim lanes + headless tests)
bash aws/setup.sh
```

## Scripts

| Script | Purpose | Time |
|--------|---------|------|
| `install_dcv.sh` | NICE DCV remote desktop + Ubuntu Desktop | ~10 min |
| `install_devtools.sh` | Node.js, npm, Claude Code CLI | ~2 min |
| `install_sim.sh` | All 3 sim lanes (Gazebo, MuJoCo, Isaac Lab) | ~45 min |
| `test_headless.sh` | Headless verification + scoring | ~6 min |
| `test_gui.sh` | Visual tests on DCV desktop | manual |
| `setup.sh` | Master: runs `install_sim.sh` then `test_headless.sh` | ~50 min |

## Master Script (`setup.sh`)

```bash
bash aws/setup.sh                      # full install + headless tests
bash aws/setup.sh --skip-install       # headless tests only (already installed)
bash aws/setup.sh --skip-isaac-build   # skip 30-min Isaac Lab Docker build
bash aws/setup.sh --test-gui           # include GUI tests after headless
```

## The 3 Simulation Lanes

### Lane 1 — Gazebo (Official Eval)

The official AIC evaluation environment. Uses a distrobox container wrapping the `aic_eval` Docker image. Scoring happens here — train anywhere, but always validate in Gazebo.

```bash
# Terminal 1: Start Gazebo eval
aic-eval-gt                          # ground_truth:=true (for CheatCode/dev)
aic-eval-no-gt                       # ground_truth:=false (for real policies)

# Terminal 2: Run a policy
aic-policy CheatCode                 # ground-truth oracle (needs gt=true)
aic-policy WaveArm                   # wave arm demo
```

### Lane 2 — MuJoCo (Fast Physics)

MuJoCo with `ros2_control` — same controller interface as Gazebo. Good for fast iteration on policies. Uses the same ROS topics so policy code is simulator-agnostic.

```bash
# Terminal 1: Zenoh router
aic-zenoh

# Terminal 2: MuJoCo bringup (launches viewer + ros2_control)
aic-mujoco

# Terminal 3: Policy
aic-policy CheatCode
```

**Note:** Only use the bringup (`aic-mujoco`). Don't also launch the standalone `simulate` binary — that creates two viewer windows. The bringup already includes the viewer.

### Lane 3 — Isaac Lab (RL Training)

Isaac Lab with Isaac Sim for RL training. Runs inside Docker. Requires `Intrinsic_assets` from NVIDIA for the full AIC task scene.

```bash
# Enter the container
aic-isaac

# Inside container:
isaaclab -p aic/aic_utils/aic_isaac/aic_isaaclab/scripts/random_agent.py \
    --task AIC-Task-v0 --num_envs 1 --enable_cameras

# RL training (scale num_envs: 1 → 64 → 128 → 256)
isaaclab -p aic/aic_utils/aic_isaac/aic_isaaclab/scripts/rsl_rl/train.py \
    --task AIC-Task-v0 --num_envs 1 --enable_cameras
```

### Intrinsic_assets (Required for Isaac Lab)

The NVIDIA asset pack is not included in the repo. Download manually:

1. Go to [NVIDIA Developer Portal](https://developer.nvidia.com) (requires login)
2. Download `Intrinsic_assets.zip`
3. Extract to: `~/IsaacLab/aic/aic_utils/aic_isaac/aic_isaaclab/source/aic_task/aic_task/tasks/manager_based/aic_task/Intrinsic_assets/`

The test scripts will `docker cp` the assets into the container automatically if they exist on the host.

## GUI Tests (`test_gui.sh`)

Run individual lanes or all at once. Requires DCV connection to see the GUI.

```bash
bash aws/test_gui.sh lane1    # Gazebo + CheatCode
bash aws/test_gui.sh lane2    # MuJoCo + CheatCode via ros2_control
bash aws/test_gui.sh lane3    # Isaac Lab random_agent
bash aws/test_gui.sh          # all 3
```

Each lane runs in a tmux session:
- `tmux attach -t aic_gz_gui` / `tmux attach -t aic_mj_gui` to monitor
- `tmux kill-session -t aic_gz_gui` / `tmux kill-session -t aic_mj_gui` to stop

## System Requirements

- Ubuntu 24.04 (Noble)
- NVIDIA GPU (L4 / A10G / L40S recommended)
- 32GB+ RAM
- 100GB+ disk (Isaac Lab Docker image alone is ~26GB)
- DCV or X11 for GUI tests

## What Survives a Reboot

| Component | Persists? | How to Restore |
|-----------|-----------|----------------|
| DCV server | Yes (systemd) | Automatic |
| Docker daemon | Yes (systemd) | Automatic |
| `aic_eval` distrobox | Yes (Docker container) | `distrobox enter -r aic_eval` |
| `isaac-lab-base` container | Yes (restart=unless-stopped) | Automatic, but re-run `pip install` inside |
| Pixi workspace | Yes (on disk) | Nothing needed |
| MuJoCo colcon workspace | Yes (on disk) | `source ~/ws_aic/install/setup.bash` |
| MJCF scene files | Yes (on disk) | Nothing needed |
| `/tmp/*.sdf` exports | No | Re-run `install_sim.sh` or the conversion section |
| Isaac Lab pip installs | No (container layer) | `test_headless.sh` re-installs automatically |
| Intrinsic_assets in container | No (docker cp) | Test scripts re-copy automatically |
| Shell aliases | Yes (~/.bashrc) | `source ~/.bashrc` |

## Troubleshooting

**DCV shows blank screen:** Run `xhost +local:docker` on the DCV desktop terminal.

**Gazebo CheatCode scores 0:** CheatCode needs `ground_truth:=true`. Use `aic-eval-gt`, not `aic-eval-no-gt`.

**MuJoCo "DOF 33 unstable" warning:** Cable physics warning — cosmetic, doesn't affect robot control.

**Two MuJoCo windows:** You launched both `aic-mujoco` (bringup) and the standalone `simulate` binary. Only use one — the bringup includes its own viewer.

**Isaac Lab "ModuleNotFoundError: isaaclab":** Run inside the container: `/workspace/isaaclab/_isaac_sim/python.sh -m pip install --no-build-isolation -e /workspace/isaaclab/source/isaaclab`

**Isaac Lab "enable_cameras" crash:** Add `--enable_cameras` flag to any script that uses cameras.
