# Session 6 Final Handoff (2026-03-28)

## Current Active Task: Isaac Lab Docker Container Build

### Status: BLOCKED on Windows line endings

Building `isaac-lab-base` Docker image from Windows Docker Desktop. Build fails at step 6/13:
```
/usr/bin/env: 'bash\r': No such file or directory
```

**Root cause:** `isaaclab.sh` has Windows line endings (`\r\n`) because the IsaacLab repo was cloned on Windows. The Linux Docker container can't execute it.

**Fix:** Convert line endings before building:
```bash
cd C:\IsaacLab
git config core.autocrlf input
git rm --cached -r .
git reset --hard HEAD
```
Or manually: `dos2unix isaaclab.sh` or `sed -i 's/\r$//' isaaclab.sh`

Then retry: `python docker/container.py build base`

### Docker build config:
- Image: `nvcr.io/nvidia/isaac-sim:5.1.0` (from NVIDIA NGC)
- IsaacLab version: v2.3.2
- Config: `C:\IsaacLab\docker\.env.base`
- Build command: `cd C:\IsaacLab && echo "N" | python docker/container.py build base`

---

## What Was Accomplished This Session

### 1. Codebase Exploration (Parts 1-3 of 5)
- **Part 1:** `sample_config.yaml` — trials, scoring topics, rail limits, cable types
- **Part 2:** `scene_description.md` + `aic_bringup/README.md` — official pipeline, launch params
- **Part 3:** `aic_utils/aic_isaac/` — ALL files explained:
  - `aic_task_env_cfg.py` — scene, MDP, rewards, observations, actions
  - `events.py` — randomize_board_and_parts, randomize_dome_light
  - `rewards.py` — position/orientation tracking with L2/tanh/exp kernels
  - `observations.py` — contact forces, joint state, cameras (ResNet18)
  - `rsl_rl_ppo_cfg.py` — PPO hyperparameters

### 2. Key Discovery: Plugs Don't Go Inside Mounts
- Plugs are cable endpoints held by the gripper
- Mounts start EMPTY on the task board
- The robot's task is to INSERT plugs into mounts
- Updated `randomize_board.py` to remove plug nesting

### 3. MuJoCo Randomizer Fixed
- Removed all plug-inside-mount code
- Mounts placed as empty fixtures matching competition setup
- Tested with `--seed 42`, works correctly
- Symlinked mesh files from `Intrinsic-AI/meshes/mujoco/` back to mjcf/

### 4. File Organization
- Moved custom files from `References/aic/` into `Intrinsic-AI/` subdirectories
- Synced between WSL2 and Windows
- Handoff docs, shell commands reference written

### 5. NVIDIA scene.usd Positions Extracted
Read the NVIDIA-prepared `scene.usd` (9.4MB) and found only 4 positioned components:
```
/base_visual           → (0.2194, 0.2838, 1.1284)
/nic_card_mount_visual → (0.0513, 0.2601, 1.1311)
/nic_card_visual       → (0.0333, 0.2623, 1.2190)
/sc_port_visual        → (0.3015, 0.2474, 1.1319)
```
**Mount fixtures (LC/SFP/SC) are NOT in NVIDIA's scene.** They never placed them.

### 6. Isaac Lab Mount Position Problem
- NVIDIA hardcoded offsets for 3 components (SC ports, NIC card)
- Mount fixture offsets don't exist anywhere
- Coordinate transform between XACRO and Isaac Lab is NOT a simple rotation
- Each USD model has different internal origin → can't reuse one component's correction
- Help request written and sent to Gemini/GPT

### 7. Conversion Attempts (All Failed)
| Approach | Result |
|----------|--------|
| MJCF→USD via Isaac Sim importer | Crashes on complex OBJ mesh filenames |
| MJCF→USD with sanitized filenames | Crashes on mesh→USD conversion step |
| URDF→USD via Isaac Sim importer | 3KB file, no meshes (GLB not supported) |
| Position extraction (Procrustes) | 4-11cm errors, different USD origins |
| Physics settle in MuJoCo | Plugs bounce off cradle collision |

### 8. Gazebo Launch Attempted
- `gz sim -s` works standalone in WSL2
- Full ROS 2 launch fails (Gazebo transport issue in WSL2)
- Eval container (distrobox) not set up

---

## Pending Help Requests

### 1. Isaac Lab Mount Positions
File: `Intrinsic-AI/logs/2026-03-28/HELP_REQUEST_isaac_lab_mount_positions.md`
Sent to Gemini Deep Think + GPT-5.4 Pro.
Key question: What coordinate transform maps XACRO board-relative positions to Isaac Lab world offsets?

### 2. Mount-Plug Alignment (from Session 5)
File: `Intrinsic-AI/logs/2026-03-23/HELP_REQUEST_mount_plug_alignment.md`
**RESOLVED:** Plugs don't go inside mounts (they're cable endpoints).

---

## Key Files Modified This Session

### Modified:
- `randomize_board.py` — removed plug nesting, mounts are empty fixtures
- `aic_task_env_cfg.py` — added TODO comment for mount fixtures (reverted manual positions)
- `convert_mjcf_to_usd.py` — MJCF→USD script (doesn't work due to importer crash)
- `convert_urdf_to_usd.py` — URDF→USD script (produces empty USD)

### Created:
- `extract_positions_for_isaac.py` — position extraction v1
- `extract_positions_for_isaac_v2.py` — board-relative position extraction
- `sanitize_mjcf_for_isaac.py` — filename sanitizer for MJCF importer
- `session6_handoff.md`, `session6_handoff_final.md` — handoffs
- `shell_commands.md` — command reference
- `handoff_codebase_exploration.md` — parts 1-5 tracking
- `handoff_to_isaac_lab_instance.md` — cross-instance findings
- `HELP_REQUEST_isaac_lab_mount_positions.md` — help request
- `view_task_board_usd.bat`, `run_mjcf_import.bat` — Windows launchers

---

## How to Run Things

### MuJoCo (WSL2)
```bash
cd ~/projects/Project-Automaton/References/aic && export PATH=$HOME/.pixi/bin:$PATH
pixi run python3 ~/projects/Project-Automaton/Intrinsic-AI/tools/mujoco/randomize_board.py --seed 42
pixi run python3 -m mujoco.viewer --mjcf=aic_utils/aic_mujoco/mjcf/scene_rand.xml
```

### Isaac Lab (Windows — native, works)
```bash
cd C:\IsaacLab
_isaac_sim\python.bat aic\aic_utils\aic_isaac\aic_isaaclab\scripts\random_agent.py --task AIC-Task-v0 --num_envs 1 --enable_cameras
```

### Isaac Lab Docker (Windows — IN PROGRESS)
```bash
cd C:\IsaacLab
# Fix line endings first:
git config core.autocrlf input
# Then build:
python docker/container.py build base
python docker/container.py start base
python docker/container.py enter base
# Inside container:
python -m pip install -e aic/aic_utils/aic_isaac/aic_isaaclab/source/aic_task
isaaclab -p aic/aic_utils/aic_isaac/aic_isaaclab/scripts/rsl_rl/train.py --task AIC-Task-v0 --num_envs 16 --enable_cameras
```

---

## What To Do Next

### Priority 1: Fix Docker build (line endings)
Fix `\r\n` → `\n` in the IsaacLab repo, rebuild the container.

### Priority 2: Run Isaac Lab in Docker
Once container works, install aic_task and run training. The official Docker setup should handle everything correctly.

### Priority 3: Mount fixture positions
Wait for Gemini/GPT response on the coordinate transform. Or: place mounts visually in the running Isaac Lab and read positions from the sim.

### Priority 4: CheatCode SLERP policy
User wants to apply SLERP from CheatCode.py to both Gazebo and Isaac Lab. This was the next task before the Isaac Lab rabbit hole.

### Priority 5: Codebase exploration Parts 4-5
- Part 4: Other docs (controller, policy, scoring, interfaces)
- Part 5: Example policies
