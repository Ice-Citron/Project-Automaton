# Task 5: Isaac Lab Setup — Session Compact Notes (2026-03-22/23)

> **Purpose:** Hand this file to the next Claude Code session so it can continue exactly where we left off.
> **Last updated:** 2026-03-23 ~01:45 AM

---

## What This Task Is

**Hours 25-35 of the 100-hour AIC plan:** Set up the Isaac Lab integration for the AI for Industry Challenge (AIC). Isaac Lab is the "data/learning lane" — used for teleop, demo recording (HDF5), and RL training via `rsl-rl`. It does NOT communicate with Gazebo over ROS 2. It outputs datasets and checkpoints that get loaded into a separate Kilted/Gazebo policy for evaluation.

The AIC Isaac Lab integration lives at:
```
References/aic/aic_utils/aic_isaac/aic_isaaclab/
```

---

## Current State (Where We Left Off)

### What's Installed on Windows

| Component | Location | Version | Status |
|-----------|----------|---------|--------|
| Isaac Sim | `C:/isaac-sim/` | 5.1.0-rc.19 | Installed, compatibility checker PASSED |
| IsaacLab | `C:/IsaacLab/` | 2.3.2 | Cloned, junction `_isaac_sim -> C:/isaac-sim/` works |
| AIC repo | `C:/IsaacLab/aic/` | Latest main | Cloned inside IsaacLab |
| NVIDIA assets | `C:/IsaacLab/aic/.../Intrinsic_assets/` | Downloaded | Extracted to correct path (see below) |
| NVIDIA driver | System | 595.79 | Updated from 576.88, compatibility checker PASSED |
| isaaclab (pip) | Isaac Sim Python | 0.54.3 | Installed via `_isaac_sim/python.bat -m pip install -e source/isaaclab` |
| isaaclab_tasks (pip) | Isaac Sim Python | 0.11.13 | Installed |
| aic_task (pip) | Isaac Sim Python | 0.1.0 | Installed |
| h5py (pip) | Isaac Sim Python | installed | Was missing, added |
| rsl-rl-lib (pip) | Isaac Sim Python | 5.0.1 | Was missing, added |
| hydra-core (pip) | Isaac Sim Python | installed | Was missing, added |

### NVIDIA Assets Location
```
C:/IsaacLab/aic/aic_utils/aic_isaac/aic_isaaclab/source/aic_task/aic_task/tasks/manager_based/aic_task/Intrinsic_assets/
├── aic_unified_robot_cable_sdf.usd
├── assets/
│   ├── NIC Card/ (nic_card.usd + textures)
│   ├── NIC Card Mount/
│   ├── SC Plug/ (sc_plug_visual.usd + textures)
│   ├── SC Port/ (sc_port.usd + textures)
│   └── Task Board Base/ (task_board_rigid.usd, base_visual.usd)
├── scene/
│   └── aic.usd
└── scene.usd
```

### What's Confirmed Working
- `AIC-Task-v0` environment **registers correctly** in gymnasium
- Isaac Sim starts on Windows with **Vulkan** graphics API (no errors)
- Compatibility checker: **PASSED** (driver 595.79, RTX 5090, 34GB VRAM)
- Isaac Sim's Python (`C:/IsaacLab/_isaac_sim/python.bat`) works and imports isaaclab, isaacsim, aic_task

### Current Blocker: DLL Crash

When running the RL training script, Isaac Sim crashes with:
```
Windows fatal exception: access violation (0xc0000139 = DLL entry point not found)
```

**Root cause:** I (Claude) pip-installed `warp-lang==1.12.0` into Isaac Sim's Python, but Isaac Sim bundles its own `warp 1.8.2` as an extension (`omni.warp.core-1.8.2`). The version mismatch caused native DLL conflicts.

**Fixes tried (ALL STILL CRASH):**
- Uninstalled `warp-lang` from pip so Isaac Sim's bundled version takes over — STILL CRASHES
- Restored `starlette==0.49.1` — STILL CRASHES
- Downgraded `lxml==4.9.4` — STILL CRASHES

**The warp uninstall alone was not enough.** Other pip packages likely overwrote Isaac Sim's bundled native DLLs. The command running is:
```bat
C:\IsaacLab\_isaac_sim\python.bat C:\IsaacLab\aic\aic_utils\aic_isaac\aic_isaaclab\scripts\rsl_rl\train.py --task AIC-Task-v0 --num_envs 1 --headless --enable_cameras
```

**It still crashes. The REQUIRED next step** is a clean reinstall:
1. Uninstall all pip packages I added from Isaac Sim's Python
2. Reinstall only what's needed using `isaaclab.bat --install` from a native Windows cmd.exe (NOT from bash — bash picks up miniconda Python from PATH)
3. Then `pip install -e aic_task` and the missing deps (h5py, rsl-rl-lib, hydra-core)

### Known Issue: `isaaclab.bat` Uses Wrong Python

When `isaaclab.bat` is run from bash (Git Bash / WSL), it finds `C:\Users\StarForge-SF\miniconda3\python.exe` from PATH instead of `C:\IsaacLab\_isaac_sim\kit\python\kit.exe`. This causes packages to install into miniconda instead of Isaac Sim.

**Workaround:** Always use Isaac Sim's Python directly:
```bat
C:\IsaacLab\_isaac_sim\python.bat -m pip install ...
```
Or run `isaaclab.bat --install` from a native Windows Command Prompt (cmd.exe) where miniconda isn't on PATH.

---

## What Was Tried and Failed (WSL2 Docker Path)

We spent significant time trying to run Isaac Lab inside a Docker container on WSL2. **This is officially unsupported by NVIDIA.**

### Key Findings
- Isaac Sim's Docker container (`nvcr.io/nvidia/isaac-sim:5.1.0`) does NOT support WSL2 for rendering/cameras
- `nvidia-smi` works inside the container (CUDA works) but Vulkan does NOT
- The container's NVIDIA libs (v580) don't match the WSL2 kernel driver (Windows side)
- WSL2's `/usr/lib/wsl/lib/` has no Vulkan ICD — only CUDA/compute libs
- NVIDIA forum confirmed: Isaac Sim container is Linux-only for graphics
- `SimulationApp({"headless": True, "vulkan": False})` lets physics run but cameras can't render
- The AIC task requires 3 cameras (center, left, right) with ResNet18 features as observations

### WSL2 Docker Artifacts (can be cleaned up)
- `~/IsaacLab/` — may still exist with root-owned pyc files (needs `sudo rm -rf`)
- Docker image `isaac-lab-base:latest` — was deleted
- `docker-compose.wsl2.yaml` — created but unused

### What IS Installed in WSL2 (from this session, useful for MuJoCo)
- ROS 2 Kilted system-wide (`/opt/ros/kilted/setup.bash`)
- `ros-dev-tools` (colcon, vcs, rosdep)
- `python3-sdformat16`, `python3-gz-math9`, `libsdformat16` (for MuJoCo SDF→MJCF conversion)
- `libnvidia-gl-575` — **SHOULD BE REMOVED** (conflicts with WSL2 driver model per NVIDIA docs)

---

## What Still Needs To Be Done

### Immediate (fix the crash)
1. Check if the warp uninstall fixed the DLL crash
2. If not, clean reinstall: uninstall all pip packages from Isaac Sim Python, use `isaaclab.bat --install` from native cmd.exe
3. Get `train.py --task AIC-Task-v0 --num_envs 1 --headless --enable_cameras` to run at least 1 iteration

### Success Criteria (Hours 25-35)
1. `AIC-Task-v0` environment runs and renders ✓ (registered, scene loads)
2. Keyboard teleop works (robot moves with arrow keys/WASD) — NOT TESTED YET
3. At least 10 demos recorded to HDF5 — NOT TESTED YET
4. Demos can be replayed — NOT TESTED YET
5. RL training starts without crashing (even 1 iteration = success) — BLOCKED BY DLL CRASH
6. Find max stable num_envs for the RTX 5090 — NOT TESTED YET

### Commands to Test (once crash is fixed)
```bat
REM List environments
C:\IsaacLab\_isaac_sim\python.bat C:\IsaacLab\aic\aic_utils\aic_isaac\aic_isaaclab\scripts\list_envs.py

REM Teleop (opens GUI window)
C:\IsaacLab\_isaac_sim\python.bat C:\IsaacLab\aic\aic_utils\aic_isaac\aic_isaaclab\scripts\teleop.py --task AIC-Task-v0 --num_envs 1 --teleop_device keyboard --enable_cameras

REM Record 10 demos
C:\IsaacLab\_isaac_sim\python.bat C:\IsaacLab\aic\aic_utils\aic_isaac\aic_isaaclab\scripts\record_demos.py --task AIC-Task-v0 --teleop_device keyboard --enable_cameras --dataset_file ./datasets/aic_demo.hdf5 --num_demos 10

REM Replay demos
C:\IsaacLab\_isaac_sim\python.bat C:\IsaacLab\aic\aic_utils\aic_isaac\aic_isaaclab\scripts\replay_demos.py --dataset_file ./datasets/aic_demo.hdf5

REM RL training (start small)
C:\IsaacLab\_isaac_sim\python.bat C:\IsaacLab\aic\aic_utils\aic_isaac\aic_isaaclab\scripts\rsl_rl\train.py --task AIC-Task-v0 --num_envs 1 --headless --enable_cameras

REM Scale up: --num_envs 64, 128, 256 to find max stable
```

### Note on `import_packages` Issue
The `aic_task/tasks/__init__.py` uses `isaaclab_tasks.utils.import_packages` to auto-discover and register the AIC task. This sometimes fails silently (caught by `except: pass`). When it fails, `AIC-Task-v0` doesn't register. The workaround is to directly import:
```python
import aic_task.tasks.manager_based.aic_task  # forces gym.register()
```
The `train.py` script handles this differently (via hydra config), so it may not have this issue.

---

## Project Context

**Project Automaton** is a multi-target robotics + AI initiative:
1. **AIC (AI for Industry Challenge)** — UR5e robot inserting fiber optic cables. Competition qualification ends May 27, 2026.
2. **SO-101 Lego Assembly** — Physical robot arm with LeRobot.
3. **Interceptor Drone** — ArduPilot/ROS.

**Three-lane simulator model:**
- **Gazebo/Kilted** = truth lane (all scoring, evaluation). Works in WSL2 Docker.
- **MuJoCo** = controller lane (gain sweeps). Being set up by another Claude Code instance.
- **Isaac Lab** = data/learning lane (THIS TASK). Runs on Windows natively.

**Key files:**
- `SESSION_HANDOFF.md` — full project state
- `Current-Plan.md` — 100-hour development plan
- `References/aic/` — AIC toolkit (git submodule)
- `Intrinsic-AI/logs/2026-03-22/isaac-lab-vulkan-issue.md` — detailed Vulkan issue report posted to forums

---

## Important Lessons Learned

1. **NEVER install Linux NVIDIA display drivers in WSL2** — Windows driver is the only driver needed
2. **Isaac Sim Docker container does NOT support WSL2** for camera/rendering workloads
3. **Isaac Lab on Windows** is the correct path for camera-based training
4. **Always use `_isaac_sim/python.bat`** for pip installs, not `isaaclab.bat` from bash (picks up miniconda)
5. **Don't pip-install `warp-lang`** into Isaac Sim's Python — it bundles its own version as an extension
6. **Isaac Sim 5.1.0-rc.19** is a release candidate — might have bugs with RTX 5090 (Blackwell)
7. The AIC task's `import_packages` auto-discovery can fail silently — use direct imports as fallback
