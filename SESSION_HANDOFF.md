# Project Automaton — Session Handoff & Continuation Guide

> **Last updated:** 2026-03-20 (Session 4)
> **Purpose:** Drop this file into a new Claude Code chat to seamlessly continue where we left off.

---

## What This Project Is

**Project Automaton** is a multi-target robotics + AI initiative hitting 3 goals with 1 codebase:

1. **Intrinsic AI Challenge (AIC)** — Training a UR5e robot to autonomously insert fiber optic cables (SFP, LC, SC connectors) into electronics assembly workstations. Competition runs Mar 2 - Sep 8, 2026. Qualification phase is active now (ends May 27).
2. **Revel x NVIDIA Hackathon** — SO-101 robot arm assembling Lego sets via Isaac Sim + LeRobot.
3. **Interceptor Drone** — ArduPilot/ROS autonomous drone.

---

## Environment Setup (COMPLETED 2026-03-20)

### Dual-System Architecture

The project spans **Windows** (browsing, notes, Git) and **WSL2 Ubuntu 24.04** (building, running, training). Both have copies of Project-Automaton synced via Git.

```
WINDOWS (C:\Users\StarForge-SF\Black_Projects\Project-Automaton)
  Purpose: File Explorer browsing, notes, Git operations, VS Code
  AIC: References/aic/ exists but pixi CANNOT run here (linux-64 only)

WSL2 (~/projects/Project-Automaton)
  Purpose: All building, running, training, pixi shell, ROS 2, Gazebo
  AIC: References/aic/ with pixi installed and working
  Sync: Both point to same GitHub remote — push from one, pull from other
```

### What's Installed Where

| Component | Location | Version | Status |
|-----------|----------|---------|--------|
| **Pixi** | WSL2 `~/.pixi/bin/pixi` | v0.65.0 | Working |
| **Pixi** | Windows `%LOCALAPPDATA%\pixi\bin\pixi.exe` | v0.65.0 | Installed (can't use for AIC) |
| **ROS 2 Kilted** | WSL2 via pixi (AIC workspace) | Kilted | Working (`pixi run ros2 topic list`) |
| **MuJoCo** | WSL2 pixi (AIC workspace) | 3.5.0 | Working (bundled in AIC pixi.toml) |
| **MuJoCo** | WSL2 `~/envs/mujoco` venv | 3.6.0 | Working |
| **MJX** (GPU parallel) | WSL2 `~/envs/mujoco` venv | 3.6.0 | Working |
| **MuJoCo Warp** (NVIDIA native) | WSL2 `~/envs/mujoco` venv | 3.6.0 | Working |
| **JAX + CUDA 12** | WSL2 `~/envs/mujoco` venv | 0.9.1 | Working (sees RTX 5090) |
| **Warp** | WSL2 `~/envs/mujoco` venv | 1.12.0 | Working (sees RTX 5090, sm_120) |
| **Gazebo Ionic** | WSL2 system | 9.5.0 | Working |
| **ROS 2 Kilted (system-level)** | WSL2 system | — | **NOT INSTALLED** (optional, pixi handles it for AIC) |
| **GPU** | WSL2 passthrough | RTX 5090, CUDA 12.9, 32GB VRAM | Working |
| **Docker Engine CE** | WSL2 native (systemd) | 29.x | Working (replaced Docker Desktop — see Session 4 notes) |
| **Distrobox** | WSL2 system | 1.7.0 | Installed (not used — see Session 4 notes) |
| **NVIDIA Container Toolkit** | WSL2 system | 1.19.0 | Working (`docker run --gpus all` sees RTX 5090) |

### MuJoCo vs MJX vs MuJoCo Warp

- **MuJoCo** = core physics engine. CPU-based, single-threaded. Great for testing individual policies.
- **MJX** = MuJoCo's GPU-accelerated parallel simulation via JAX/XLA. Runs 4096+ environments simultaneously on the 5090. Ideal for RL sweeps.
- **MuJoCo Warp** = NVIDIA's GPU-native fork built on Warp (CUDA). Potentially better raw throughput on NVIDIA hardware than MJX.
- All three share the same MJCF XML model format — swap backends without rewriting sims.

### Aliases

**WSL2 (`~/.bashrc`):**
```bash
alias automaton="cd ~/projects/Project-Automaton"
alias aic="cd ~/projects/Project-Automaton/References/aic"
alias automaton-win="cd /mnt/c/Users/StarForge-SF/Black_Projects/Project-Automaton"
alias mujoco="source ~/envs/mujoco/bin/activate"
```

**Windows PowerShell (`Microsoft.PowerShell_profile.ps1`):**
```powershell
function black { Set-Location "C:\Users\StarForge-SF\Black_Projects" }
function automaton { Set-Location "C:\Users\StarForge-SF\Black_Projects\Project-Automaton" }
function aic { Set-Location "C:\Users\StarForge-SF\Black_Projects\Project-Automaton\References\aic" }
function liberty { Set-Location "C:\Users\StarForge-SF\Black_Projects\Project-Liberty" }
```

### Key File Locations

```
WINDOWS:
  C:\Users\StarForge-SF\Black_Projects\Project-Automaton\          ← Main repo (browsing/notes)
  C:\Users\StarForge-SF\Black_Projects\Project-Automaton\WSL2-Automaton.url  ← Shortcut to WSL2 copy
  C:\Users\StarForge-SF\AppData\Local\pixi\bin\pixi.exe            ← Windows pixi
  C:\Users\StarForge-SF\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1  ← PS aliases

WSL2 (ALL WORK HAPPENS HERE):
  ~/projects/Project-Automaton/                    ← Working repo (build/run/train)
  ~/projects/Project-Automaton/References/aic/     ← AIC workspace (pixi installed)
  ~/projects/Project-Automaton/References/aic/.pixi/  ← Pixi environment (ROS 2, MuJoCo 3.5.0, deps)
  ~/projects/Project-Automaton/aic_results/        ← Scoring results (gitignored, timestamped subdirs)
  ~/envs/mujoco/                                   ← venv with MuJoCo 3.6.0 + MJX + Warp + JAX CUDA
  ~/.pixi/bin/pixi                                 ← Pixi binary
  ~/.bashrc                                        ← Aliases
  /etc/docker/daemon.json                          ← Docker config with NVIDIA runtime
```

### WSL2 Performance Note

- Working inside `~/` (ext4) = fast native Linux speed
- Working inside `/mnt/c/` = slow due to 9P filesystem bridge
- That's why the working copy is in `~/projects/`, not `/mnt/c/`
- Access WSL2 files from Windows Explorer: `\\wsl.localhost\Ubuntu-24.04\home\starforge-sf\projects\`
- Use `code .` from WSL2 terminal to open VS Code Remote-WSL for full intellisense

---

## Directory Map

```
~/projects/Project-Automaton/  (WSL2) or C:\...\Black_Projects\Project-Automaton\ (Windows)
├── SESSION_HANDOFF.md          ← THIS FILE
├── Current-Plan.md             ← Detailed 100-hour plan (revised 2026-03-21, GPT-5.4 Pro)
├── README.md
├── LICENSE
├── WSL2-Automaton.url          ← (Windows only) shortcut to WSL2 copy
│
├── SO-101/                     ← Physical robot project
│   ├── lerobot/                ← HuggingFace LeRobot framework (v0.4.3)
│   │   ├── src/lerobot/        ← Main source (robots/, policies/, datasets/, rl/)
│   │   ├── pyproject.toml      ← Dependencies
│   │   └── docs/               ← Includes LeIsaac integration guide
│   ├── lerobot-venv/           ← Python virtual environment
│   └── Print Files/            ← 3D print STLs for custom SO-101 end-effectors
│
├── Lychee-AI/                  ← Isaac Lab tutorial work
│   ├── 2026-02-28/Tutorial_1/  ← create_empty.py (basic scene)
│   ├── 2026-03-01/
│   │   ├── Tutorial_2/         ← spawn_prims.py (objects, meshes, lights)
│   │   └── Tutorial_3/         ← run_rigid_object.py, run_articulation.py
│
├── Liberty-Notes/              ← Research & learning notebooks
│   ├── Nvidia-Issac-Lab/       ← Feb-04 through March-04 .ipynb study logs
│   └── PythonRobotics/         ← Reference robotics code
│
├── aic_results/                ← AIC scoring results (gitignored)
│   ├── wavearm_20260320_185331/  ← Per-run timestamped subdirectories
│   │   ├── scoring.yaml          ← Scoring output
│   │   └── bag_trial_*/          ← ROS 2 bag files per trial
│   └── ...
│
├── Intrinsic-AI/               ← AIC competition working directory
│   ├── ros2_graph/             ← ROS 2 computation graph (Graphviz)
│   └── Ideas/                  ← Research notes
│
├── References/
│   ├── Intrinsic AI Notes/     ← Manual notes
│   └── aic/                    ← AIC TOOLKIT REPO (git submodule → intrinsic-dev/aic)
│       ├── pixi.toml           ← Pixi workspace config (robostack-kilted + conda-forge)
│       ├── pixi.lock           ← Locked dependency versions
│       ├── .pixi/              ← (WSL2 only) installed environment
│       ├── aic_model/          ← PARTICIPANT FRAMEWORK (what you subclass)
│       │   └── aic_model/
│       │       ├── aic_model.py    ← ROS 2 LifecycleNode — loads your policy
│       │       └── policy.py       ← Abstract Policy base class — YOU IMPLEMENT THIS
│       ├── aic_example_policies/   ← Reference implementations
│       │   └── aic_example_policies/ros/
│       │       ├── WaveArm.py      ← Minimal example (arm waves)
│       │       ├── CheatCode.py    ← Ground truth policy (optimal insertion)
│       │       ├── RunACT.py       ← Neural network policy (ACT from HuggingFace)
│       │       ├── GentleGiant.py  ← Low-jerk smooth motion
│       │       ├── SpeedDemon.py   ← High-jerk aggressive motion
│       │       ├── WallToucher.py  ← Collision detection test
│       │       └── WallPresser.py  ← Force control demo
│       ├── aic_interfaces/         ← ROS 2 msg/srv/action definitions
│       ├── aic_engine/             ← Trial orchestrator (C++)
│       ├── aic_controller/         ← Low-level robot control (ros2_control, C++)
│       ├── aic_adapter/            ← Sensor fusion node (C++)
│       ├── aic_scoring/            ← Scoring system (C++)
│       ├── aic_gazebo/             ← Gazebo plugins
│       ├── aic_description/        ← URDF/SDF models
│       ├── aic_bringup/            ← Launch files
│       ├── aic_assets/             ← 3D meshes
│       ├── aic_utils/              ← Teleoperation, MuJoCo integration, LeRobot tools
│       └── docker/                 ← Container definitions for submission
│
├── .gitignore
├── .gitmodules                 ← Submodule config (References/aic → intrinsic-dev/aic)
└── LICENSE                     ← Apache 2.0
```

---

## What's Been Done

### Session 1 (2026-03-15) — Deep Analysis
- Read and analyzed every significant file in the AIC toolkit
- Mapped all ROS 2 nodes, topics, services, actions and interconnections
- Generated comprehensive Graphviz visualization at `Intrinsic-AI/aic_ros2_graph.py`
- Understood scoring system (100 pts max per trial)
- Identified two control modes (Cartesian impedance vs Joint-space)
- Isaac Lab Tutorials 1-3 complete
- LeRobot framework setup complete

### Session 2 (2026-03-15) — Environment Setup
- Set up `Shift+Enter` keybinding for newline in Claude Code
- Confirmed WSL2 Ubuntu 24.04 with RTX 5090 (CUDA 12.9, 32GB VRAM)
- Cloned AIC repo on Windows

### Session 3 (2026-03-16) — Full WSL2 Environment Build
- Cloned Project-Automaton into WSL2 `~/projects/`
- Fixed AIC git submodule (added .gitmodules, cloned properly)
- Ran `pixi install` in AIC workspace — ROS 2 Kilted + MuJoCo 3.5.0 + all deps bundled
- Created `~/envs/mujoco` venv with: MuJoCo 3.6.0, MJX, MuJoCo Warp, JAX CUDA 12, Warp
- Verified all: ROS 2 (`ros2 topic list`), MuJoCo, MJX, Warp, JAX (all see RTX 5090)
- Set up bash aliases (automaton, aic, automaton-win, mujoco) in WSL2
- Set up PowerShell aliases (black, automaton, aic, liberty) on Windows
- Created WSL2-Automaton.url shortcut on Windows

### Session 4 (2026-03-20) — Docker Setup + First AIC Run
- **Gazebo Ionic** already installed (v9.5.0) — confirmed working
- Installed **Distrobox** + **NVIDIA Container Toolkit** in WSL2
- Discovered **Docker Desktop's `--network host` is broken on WSL2** — containers run in a separate `docker-desktop` VM, so `--network host` shares that VM's network, NOT WSL2's network. This means the Zenoh router inside the container was unreachable from pixi-run policies outside.
- **Replaced Docker Desktop with Docker Engine CE** installed natively in WSL2 (via systemd). This fixed `--network host` — container ports are now directly accessible from WSL2.
- Created patched AIC eval image with `locales` package (needed for distrobox init, but ultimately not used)
- **Successfully ran WaveArm policy end-to-end** — 3 trials completed with scoring:
  - Trial 1: 31.7 pts (Tier1=1, Tier2=20.8, Tier3=9.9)
  - Trial 2: 40.9 pts (Tier1=1, Tier2=21.3, Tier3=18.6)
  - Trial 3: 1.0 pts (Tier1=1, Tier2=0, Tier3=0)
  - **Total: 73.6 pts** (across 3 trials, not per-trial — WaveArm just waves, doesn't try to insert)
- Results + bag files saved to `~/projects/Project-Automaton/aic_results/` (gitignored)
- Results are now stored in timestamped subdirectories to prevent overwriting (e.g., `WaveArm_20260320_185331/`)
- Discovered GPU-accelerated rendering requires `GALLIUM_DRIVER=d3d12` + `LD_LIBRARY_PATH=/usr/lib/wsl/lib` env vars (without these, Gazebo falls back to llvmpipe CPU rendering)
- Zenoh timestamp errors are cosmetic (WSL2 clock drift) — do not affect functionality
- Created `wsl-rshared.service` systemd unit for `mount --make-rshared /` (needed for distrobox/Docker)

---

## What's Left To Do

> **Full plan:** See `Current-Plan.md` in the project root for the detailed 100-hour plan (revised 2026-03-21, generated by GPT-5.4 Pro). The plan uses a three-lane model: Gazebo (truth/eval), MuJoCo (controller sweeps), Isaac Lab (data/RL training).

### Currently Working On (Hours 5-15)
1. **CheatCode with ground_truth:=true** — IN PROGRESS (user running now)
2. **Run remaining example policies** — GentleGiant, SpeedDemon, WallToucher, WallPresser
3. **Build `run_gazebo_eval.sh`** — One-command launcher
4. **Build `collect_scores.py`** — Parse all scoring.yaml into CSV

### Next Up (Hours 15-25): MuJoCo Mirror
5. Set up official AIC MuJoCo integration (`aic_utils/aic_mujoco/`)
6. Export Gazebo world → convert SDF to MJCF → run WaveArm in MuJoCo

### Then (Hours 25-35): Isaac Lab Lane
7. Clone IsaacLab, use AIC Isaac task (`AIC-Task-v0`)
8. Teleop, record demos, find max stable `num_envs`

### Remaining Pipeline (Hours 35-105)
- Custom policy skeleton + dataset logger (35-45)
- Cross-simulator data factory: GT demos + human teleop + Isaac demos (45-55)
- First non-GT controller + MuJoCo gain sweep (55-65) ← **KEY MILESTONE: Tier 3 > 0 without GT**
- Perception repos: HANDLOOM, TrackDLO (65-75)
- Learner sprint 1: RunACT, LeRobot (75-85)
- Learner sprint 2: ACT++, Diffusion Policy, CableRouting, IndustReal (85-95)
- Bake-off, freeze mainline, package winner (95-105)

### Other Projects
- **SO-101 Lego Assembly** — LeRobot setup done, need Isaac Sim integration
- **Interceptor Drone** — ArduPilot/ROS, not started

---

## First Results — WaveArm Baseline (2026-03-20)

WaveArm just waves the arm — it doesn't attempt insertion. This is the floor baseline.

| Trial | Tier 1 (model) | Tier 2 (trajectory) | Tier 3 (insertion) | Total |
|-------|----------------|--------------------|--------------------|-------|
| 1 | 1 | 20.8 | 9.9 (0.09m from port) | 31.7 |
| 2 | 1 | 21.3 | 18.6 (0.06m from port) | 40.9 |
| 3 | 1 | 0 | 0 (0.24m from port) | 1.0 |
| **Sum** | | | | **73.6** |

Key observations:
- Tier 1 = 1 means model loaded successfully
- Tier 2 varies because WaveArm accidentally gets close to the port on some trials (proximity-based scoring)
- Tier 3 proximity score can be up to 25 pts just for getting close, even without insertion
- Full insertion = 75 pts (Tier 3), which CheatCode should achieve

---

## 100-Hour Development Plan (Revised 2026-03-21)

> **Full plan:** `Current-Plan.md` — three-lane model (Gazebo/MuJoCo/Isaac Lab), generated by GPT-5.4 Pro.

| Hours | Goal | Status |
|-------|------|--------|
| 0-5 | Environment setup, WaveArm baseline | **DONE** (Session 4) |
| 5-15 | Run all example policies, build harness scripts | **IN PROGRESS** — CheatCode running |
| 15-25 | Official MuJoCo mirror setup (same ROS 2 interface) | Not started |
| 25-35 | Official Isaac Lab setup (teleop, recording, RL) | Not started |
| 35-45 | Custom policy package + dataset logger | Not started |
| 45-55 | Cross-simulator data factory (Gazebo GT + teleop + Isaac) | Not started |
| 55-65 | First non-GT controller + MuJoCo gain sweep | Not started |
| 65-75 | Perception repos: HANDLOOM, TrackDLO | Not started |
| 75-85 | Learner sprint 1: RunACT, LeRobot ACT training | Not started |
| 85-95 | Learner sprint 2: ACT++, Diffusion, CableRouting, IndustReal | Not started |
| 95-105 | Gazebo bake-off, freeze mainline, package winner | Not started |

**Key milestone:** First non-GT policy that earns Tier 3 > 0 in Gazebo AIC.

**Three-lane model:**
- **Gazebo/Kilted** = truth lane (all scoring happens here)
- **MuJoCo** = controller lane (same ROS 2 interface, fast gain sweeps)
- **Isaac Lab** = data/learning lane (parallel RL, synthetic data, teleop demos)

---

## Key Technical Details

### The Core Contract — What You Implement

```python
from aic_model.policy import Policy

class MyPolicy(Policy):
    def insert_cable(self, task, get_observation, move_robot, send_feedback):
        # task: Task msg — what cable, what port, time limit
        # get_observation(): returns Observation msg (3 cameras + joints + wrench + ctrl_state)
        # move_robot(motion_update=...) or move_robot(joint_motion_update=...)
        # send_feedback("progress message")
        # return True if success, False if failure
        ...
```

### Control Modes

**Cartesian Impedance (MotionUpdate):**
- `pose`: Target TCP position + quaternion orientation
- `velocity`: Target TCP twist (for MODE_VELOCITY)
- `target_stiffness`: 6x6 matrix as flat 36 floats — `np.diag([Kx,Ky,Kz,Krx,Kry,Krz]).flatten()`
- `target_damping`: Same format
- `feedforward_wrench_at_tip`: Constant force/torque to apply
- `wrench_feedback_gains_at_tip`: [0-0.95] compliance gains
- `trajectory_generation_mode`: MODE_POSITION or MODE_VELOCITY

**Joint-Space (JointMotionUpdate):**
- `target_state.positions`: 6 joint angles in radians
- `target_stiffness`: 6 floats (per-joint)
- `target_damping`: 6 floats (per-joint)

**Stiffness/Damping Trade-offs:**
- Low stiffness (50) + high damping (40) = smooth, slow, low jerk (GentleGiant)
- High stiffness (500) + low damping (5) = aggressive, fast, high jerk (SpeedDemon)
- Default: stiffness [90,90,90,50,50,50], damping [50,50,50,20,20,20]

### Scoring (100 pts max per trial)

| Tier | What | Points |
|------|------|--------|
| Tier 1 | Model loads and responds | 1 |
| Tier 2 | Trajectory smoothness (jerk) | 0-6 |
| Tier 2 | Task duration (5s=12, 60s=0) | 0-12 |
| Tier 2 | Path efficiency | 0-6 |
| Tier 2 | Force penalty (>20N for >1s) | 0 to -12 |
| Tier 2 | Off-limit contact | 0 to -24 |
| Tier 3 | Full correct insertion | 75 |
| Tier 3 | Wrong port | -12 |
| Tier 3 | Partial insertion | 38-50 |
| Tier 3 | Proximity to port | 0-25 |

### Robot Setup
- **Arm:** Universal Robots UR5e (6 DOF)
- **Gripper:** Robotiq Hand-E
- **Cameras:** 3x Basler (left, center, right wrist mounts)
- **F/T Sensor:** Axia80 M20 (6-axis)
- **Joints:** shoulder_pan, shoulder_lift, elbow, wrist_1, wrist_2, wrist_3 + gripper
- **Home position:** [-0.1597, -1.3542, -1.6648, -1.6933, 1.5710, 1.4110]

### ROS 2 Data Flow (Critical Path)
```
Gazebo → ros_gz_bridge → camera/sensor topics → aic_adapter (sync @ 20Hz)
    → /observations → aic_model (YOUR POLICY)
    → /aic_controller/pose_commands OR /joint_commands
    → aic_controller → back to Gazebo physics
```

### CheatCode Strategy (The Gold Standard to Beat)
1. **Phase 1 — Approach (5s):** Interpolate (100 steps x 50ms) from current pose to 20cm above target port, align plug via quaternion slerp
2. **Phase 2 — Descent/Insertion:** Lower 0.5mm per 50ms (10mm/s) with PI controller on XY. Continue until 15mm past port surface.
3. **Hold 5 seconds** to stabilize.
4. Uses ground truth TF frames (FORBIDDEN in eval — must replace with camera-based perception)

### RunACT Strategy (Neural Network Reference)
- Pre-trained ACT model from HuggingFace (`grkw/aic_act_policy`)
- 26-dim state: TCP pose(7) + TCP vel(6) + TCP error(6) + joint positions(7)
- 3 camera images resized to 0.25x, normalized per-camera mean/std
- 7-dim action: 6 velocity + gripper
- ~4Hz (250ms/inference), 30 seconds, MODE_VELOCITY

### Key Competition Rules
- Ground truth TF data ONLY for training, FORBIDDEN in evaluation
- No Gazebo namespace access (/gazebo, /gz_server, /scoring)
- No hardcoded sensor data
- 1 submission per day (team-wide)
- Container images audited
- Zenoh ACL enforced

---

## Quick Start Commands

### WSL2 Navigation
```bash
automaton          # cd to ~/projects/Project-Automaton
aic                # cd to AIC workspace
automaton-win      # cd to Windows copy via /mnt/c/
mujoco             # activate MuJoCo venv (MJX, Warp, JAX)
```

### AIC Simulation (Two Terminals)
```bash
# Terminal 1: Start eval environment (Docker)
# Set POLICY_NAME and GT before running (used for timestamped results dir)
POLICY_NAME=WaveArm   # or CheatCode, GentleGiant, etc.
GT=false              # true for CheatCode training, false for eval
RUN_DIR=~/projects/Project-Automaton/aic_results/${POLICY_NAME}_$(date +%Y%m%d_%H%M%S)
mkdir -p "$RUN_DIR"

docker run -it --rm \
  --name aic_eval \
  --network host \
  --gpus all \
  -e DISPLAY=:0 \
  -e WAYLAND_DISPLAY=wayland-0 \
  -e XDG_RUNTIME_DIR=/mnt/wslg/runtime-dir \
  -e PULSE_SERVER=/mnt/wslg/PulseServer \
  -e GALLIUM_DRIVER=d3d12 \
  -e LD_LIBRARY_PATH=/usr/lib/wsl/lib \
  -e AIC_RESULTS_DIR=/aic_results \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v /mnt/wslg:/mnt/wslg \
  -v /usr/lib/wsl:/usr/lib/wsl \
  -v "$RUN_DIR":/aic_results \
  --device /dev/dxg \
  ghcr.io/intrinsic-dev/aic/aic_eval:latest \
  ground_truth:=$GT start_aic_engine:=true

# Terminal 2: Run a policy (pixi, from WSL2 directly)
# Wait for "No node with name 'aic_model' found. Retrying..." then run:
cd ~/projects/Project-Automaton/References/aic
pixi run ros2 run aic_model aic_model \
    --ros-args -p use_sim_time:=true \
    -p policy:=aic_example_policies.ros.$POLICY_NAME
```

### Quick-Run Examples
```bash
# WaveArm (no GT needed)
POLICY_NAME=WaveArm GT=false

# CheatCode (NEEDS GT)
POLICY_NAME=CheatCode GT=true

# GentleGiant / SpeedDemon / WallToucher / WallPresser (no GT needed)
POLICY_NAME=GentleGiant GT=false
```

### Key Docker Flags Explained
- `--network host` — REQUIRES Docker Engine CE (Docker Desktop breaks this on WSL2)
- `GALLIUM_DRIVER=d3d12` + `LD_LIBRARY_PATH=/usr/lib/wsl/lib` — GPU-accelerated rendering via Mesa d3d12
- `--device /dev/dxg` + WSLg mounts — GPU + display passthrough
- `AIC_RESULTS_DIR=/aic_results` + `-v ~/projects/Project-Automaton/aic_results:/aic_results` — persist results outside container
- `ground_truth:=true` — enables GT TF frames (for training/debugging ONLY, forbidden in eval)

### MuJoCo Viewer
```bash
mujoco                          # activate venv
python3 -m mujoco.viewer        # open interactive 3D viewer
```

### Docker Submission
```bash
aic
docker compose -f docker/docker-compose.yaml build model
docker compose -f docker/docker-compose.yaml up   # test locally
```

### VS Code (from WSL2)
```bash
automaton
code .              # opens VS Code Remote-WSL with full intellisense
```

---

## Key URLs
- **Portal/Leaderboard:** https://aiforindustrychallenge.ai
- **Event Page:** https://www.intrinsic.ai/events/ai-for-industry-challenge
- **GitHub Repo:** https://github.com/intrinsic-dev/aic
- **Our Repo:** https://github.com/Ice-Citron/Project-Automaton
- **Community Forum:** https://discourse.openrobotics.org/c/competitions/ai-for-industry-challenge/

## Competition Timeline

| Phase | Dates | Status |
|-------|-------|--------|
| Qualification | Mar 2 - May 27, 2026 | ACTIVE |
| Phase 1 | May 28 - Jul 22, 2026 | Upcoming |
| Phase 2 | Jul 27 - Sep 8, 2026 | Upcoming |

---

## Known Issues / Gotchas

1. **WSL2 sudo from Claude Code** — `sudo` prompts for password interactively, Claude Code can't see the prompt. Run sudo commands manually in your own WSL2 terminal.
2. **Windows PATH leaks into WSL2** — `Program Files (x86)` parentheses break bash commands. Use `--noprofile --norc` or clean PATH when running WSL commands from Windows.
3. **AIC pixi.toml is linux-64 only** — `pixi install` will fail on Windows. Use WSL2 for all AIC work.
4. **ROS 2 Zenoh warnings** — "Unable to connect to a Zenoh router" is normal when no router is running. Not an error.
5. **Two MuJoCo versions** — 3.5.0 in pixi (AIC workspace), 3.6.0 in `~/envs/mujoco` venv. Both work. Use pixi's for AIC-specific work, venv for standalone MJX/Warp experiments.
6. **Docker Desktop `--network host` is BROKEN on WSL2** — Docker Desktop runs `dockerd` in a separate `docker-desktop` VM, so `--network host` shares that VM's network, not WSL2's. This makes Zenoh router unreachable from pixi policies. **Fix: Use Docker Engine CE installed natively in WSL2** (already done in Session 4).
7. **Zenoh timestamp errors** — Constant `ERROR zenoh::net::routing::dispatcher::pubsub: Error treating timestamp` spam in both terminals during AIC runs. This is **cosmetic** — caused by WSL2 clock drift between Zenoh nodes. Does NOT affect trial execution or scoring. Just makes logs hard to read.
8. **Gazebo falls back to CPU rendering (llvmpipe) by default** — Without `GALLIUM_DRIVER=d3d12` and `LD_LIBRARY_PATH=/usr/lib/wsl/lib`, Gazebo uses software rendering in Docker. Very laggy. The working docker run command in Quick Start already includes these.
9. **WSL2 mount propagation** — `distrobox create` fails with "path / is mounted on / but it is not a shared mount". Fix: `sudo mount --make-rshared /` or use the `wsl-rshared.service` systemd unit (created in Session 4).
10. **AIC eval container needs `locales` package** — Distrobox init fails without it. We patched the image: `ghcr.io/intrinsic-dev/aic/aic_eval:patched` (local only). Not needed if running Docker directly instead of distrobox.
