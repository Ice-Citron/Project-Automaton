# Session 6 Handoff — MuJoCo Pipeline Fix + Codebase Exploration (2026-03-28)

## Key Breakthrough

**The mount-plug alignment problem was a non-issue.** After reading the official AIC docs (`sample_config.yaml`, `scene_description.md`, `aic_bringup/README.md`), we discovered:

1. **Plugs DON'T start inside mounts** — they're cable endpoints held by the gripper
2. **Mounts start EMPTY** — the robot's task is to INSERT plugs into mounts
3. **The official pipeline** is: Gazebo (randomized params) → export SDF → convert to MuJoCo/Isaac
4. **MuJoCo's mesh normalization** (principal inertia axis alignment) was confirmed by GPT-5.4 — NOT a bug, it's intentional. `mesh_pos`/`mesh_quat` in `mjModel` store the applied transform.

## What Was Done This Session

### 1. Diagnostic Tools Created
- `diagnose_mesh_axes.py` — Compares GLB vs MuJoCo vertex extents for OBJ and STL
- `compute_correction_quats.py` — Brute-force + covariance rotation detection
- `verify_refquat.py` — Tests if MuJoCo `refquat` attribute corrects orientation
- `settle_and_bake.py` / `settle_and_bake_v2.py` — Physics settle approach (GPT-5.4's idea)

**Findings:**
- STL gets SAME axis permutation as OBJ (Gemini was wrong about STL bypass)
- `refquat` doesn't modify `mesh_vert` — MuJoCo normalizes AFTER refquat
- Different meshes get different permutations (principal axis alignment, not format-dependent)
- Physics settle partially worked but cradle collision geometry was insufficient

### 2. Codebase Exploration (Parts 1-2 of 5)
- **Part 1: `sample_config.yaml`** — Master config defining trials, scenes, tasks, scoring topics
- **Part 2: `scene_description.md` + `aic_bringup/README.md`** — Official pipeline docs
- **Parts 3-5 still pending:** aic_mujoco/, aic_isaac/, other docs

### 3. randomize_board.py Fixed
- **Removed all plug-nesting code** (lines 284-352 replaced)
- Mounts are now placed as empty fixtures, matching the actual competition
- SFP mounts use official converter meshes; LC/SC use manual OBJ exports
- Successfully generates randomized boards (tested with --seed 42)

### 4. File Organization
Moved all custom files from `References/aic/` into `Intrinsic-AI/`:
- `meshes/mujoco/` — 16 mesh exports (OBJ + STL)
- `scenes/mujoco/` — 5 test scenes
- `data/mujoco/` — 2 JSON data files
- `tools/mujoco/` — 10 scripts
- Symlinked meshes back into mjcf/ so MuJoCo can find them

### 5. Gazebo Launch Attempted
- Gazebo server works standalone (`gz sim -s -r aic.sdf`)
- Full ROS 2 launch fails — Gazebo transport can't connect spawners to server in WSL2
- AIC eval container (distrobox) not set up yet — would fix this
- **Not a blocker** — MuJoCo pipeline works independently

## Current State of Files

### Key paths (WSL2)
```
~/projects/Project-Automaton/References/aic/aic_utils/aic_mujoco/mjcf/
  aic_world.xml          ← Edited base world (material fixes from session 5)
  aic_world_rand.xml     ← Generated randomized layout
  scene.xml              ← Base scene (robot + world)
  scene_rand.xml         ← Randomized scene
  manual_*.obj/stl       ← Symlinks to Intrinsic-AI/meshes/mujoco/

~/projects/Project-Automaton/Intrinsic-AI/
  tools/mujoco/          ← 10 scripts
  meshes/mujoco/         ← 16 mesh exports
  scenes/mujoco/         ← 5 test scenes
  data/mujoco/           ← JSON data
  logs/2026-03-28/       ← This handoff + shell commands
```

## How to Run Things

### Generate + view randomized board
```bash
cd ~/projects/Project-Automaton/References/aic
export PATH=$HOME/.pixi/bin:$PATH
pixi run python3 ~/projects/Project-Automaton/Intrinsic-AI/tools/mujoco/randomize_board.py --seed 42
pixi run python3 -m mujoco.viewer --mjcf=aic_utils/aic_mujoco/mjcf/scene_rand.xml
```

### View base (non-randomized) scene
```bash
pixi run python3 -m mujoco.viewer --mjcf=aic_utils/aic_mujoco/mjcf/scene.xml
```

### Run CheatCode policy
```bash
pixi run python3 ~/projects/Project-Automaton/Intrinsic-AI/tools/mujoco/mujoco_policies.py
```

### Launch Gazebo (needs interactive terminal, may fail in WSL2)
```bash
source ~/ws_aic/install/setup.bash
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
export ZENOH_CONFIG_OVERRIDE='transport/shared_memory/enabled=true;transport/shared_memory/transport_optimization/pool_size=536870912'
ros2 run rmw_zenoh_cpp rmw_zenohd & sleep 5
ros2 launch aic_bringup aic_gz_bringup.launch.py \
  gazebo_gui:=false spawn_task_board:=true ground_truth:=true start_aic_engine:=false
```

## What To Do Next

### Priority 1: Isaac Lab/Sim Conversion
- Read `aic_utils/aic_isaac/README.md` for the official Isaac Lab integration
- The Isaac Lab instance (separate Claude Code) has been making progress
- Share findings about official pipeline with that instance

### Priority 2: Codebase Exploration (Parts 3-5)
- Part 3: aic_mujoco/ (README, launch, scripts)
- Part 4: aic_isaac/ (task env, observations, rewards, events)
- Part 5: Other docs (controller, policy, scoring, interfaces)

### Priority 3: Camera Rate Fix
- Raise `camera_publish_rate` in MuJoCo ros2_control config (currently ~1Hz, needs 20Hz)

### Priority 4: CheatCode Policy in MuJoCo
- With `ground_truth:=true`, Gazebo publishes GT TF frames
- MuJoCo standalone can access body positions directly via `data.xpos`
- `mujoco_policies.py` already has direct body position access

### Priority 5: Eval Container Setup
- Install AIC eval container via distrobox for proper Gazebo operation
- This would enable the full Gazebo → SDF export → convert pipeline
