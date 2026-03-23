# Isaac Lab Session 2 — Full Handoff Document
**Date:** 2026-03-23
**Instance:** Claude Code (Isaac Lab / Windows native)
**Project:** Project Automaton — AIC (AI for Industry Challenge) competition

---

## What This Project Is About

Project Automaton is a 100-hour development plan for the **AIC (AI for Industry Challenge)** — a robotics competition where a UR5e robot arm must perform fiber optic cable insertion into networking equipment (NIC cards with SFP ports, SC optical ports) on a standardized task board.

**Three-lane simulator strategy:**
- **Gazebo** (truth/eval lane) — runs in WSL2 Docker, used for official scoring
- **MuJoCo** (controller sweeps) — runs in WSL2, handled by separate Claude Code instance
- **Isaac Lab** (data/learning lane) — runs on Windows native, THIS instance's task

Isaac Lab is used for: teleop demo recording (HDF5), RL training (PPO), and policy development. Outputs (trained checkpoints) get loaded into Gazebo for evaluation.

---

## What Has Been Accomplished (This Session)

### Three Bugs Fixed

**Bug 1: Vulkan crash (`access violation` in `rtx.scenedb.plugin.dll`)**
- NVIDIA driver 595.79 (R590 branch) was unvalidated for Omniverse on Blackwell (RTX 5090)
- **Fix:** User downgraded to driver **581.42** (R580 Production Branch)
- **Workaround discovered** (if ever needed): Force D3D12 via sys.argv:
  ```python
  import sys
  sys.argv.append('--/app/vulkan=false')
  sys.argv.append('--/renderer/active_graphics_api=Direct3D12')
  ```

**Bug 2: DLL load failure (`0xc0000139` in `h5py._errors`)**
- h5py 3.16.0 had incompatible native DLLs
- **Fix:** `pip install h5py==3.12.1`

**Bug 3: RL training `KeyError: 'actor'`**
- rsl-rl-lib 5.0.1 changed its config API; Isaac Lab expects 3.1.2
- **Fix:** `pip install rsl-rl-lib==3.1.2`
- Confirmed: our Isaac Lab is the AIC-tested v2.3.2 stack, `handle_deprecated_rsl_rl_cfg` shim does NOT exist, so 3.1.2 is correct

### Packages Installed/Fixed
| Package | Change | Reason |
|---------|--------|--------|
| h5py | 3.16.0 → 3.12.1 | DLL load failure |
| rsl-rl-lib | 5.0.1 → 3.1.2 | API mismatch with Isaac Lab v2.3.2 |
| isaaclab_contrib | installed (editable from source) | Missing module |
| isaaclab_rl | installed (editable from source) | Required by training |
| warp-lang | uninstalled (session 1) | Conflicted with bundled warp 1.8.2 |

### RL Training Verified
- **Official AIC train.py works:**
  ```bash
  cd C:/IsaacLab/aic/aic_utils/aic_isaac/aic_isaaclab/scripts/rsl_rl/
  C:/IsaacLab/_isaac_sim/python.bat train.py --task AIC-Task-v0 --headless --enable_cameras --num_envs 16 --max_iterations 2
  ```
- 2 iterations completed in 7.44s, no errors
- GUI mode also works (`--headless` removed)

### Scaling Results (RTX 5090, 32GB VRAM)
| num_envs | Throughput | GPU Memory | Backend |
|----------|-----------|------------|---------|
| 16 | 114 env-steps/s | ~0.3 GB | Vulkan |
| 128 | ~250 env-steps/s | 0.3 GB | Vulkan |
| 256 | 648 env-steps/s | 6.2 GB | D3D12 |

### GLB→USD Asset Conversion
Converted 5 missing component models from GLB to USD:
- LC Mount → `Intrinsic_assets/assets/LC Mount/lc_mount_visual.usd`
- LC Plug → `Intrinsic_assets/assets/LC Plug/lc_plug_visual.usd`
- SFP Module → `Intrinsic_assets/assets/SFP Module/sfp_module_visual.usd`
- SFP Mount → `Intrinsic_assets/assets/SFP Mount/sfp_mount_visual.usd`
- SC Mount → `Intrinsic_assets/assets/SC Mount/sc_mount_visual.usd`

Conversion script: `C:/IsaacLab/convert_glb_to_usd.py`

---

## Current Blocker: Component Placement on Task Board

### The Problem
All USD assets load with correct textures (NIC cards look great!), but when placed on the task board using XACRO rail positions, **they end up in wrong locations**. Components float near but not on the board rails. This is the SAME problem the MuJoCo instance hit.

### Why It's Hard
The XACRO rail positions are relative to `task_board_base_link`, but:
1. The board in Isaac Lab sits at world pos `(0.2837, 0.229, 0.0)` with unknown internal rotation in its USD
2. The `aic_engine` (Gazebo-only) computes component→mount transforms at runtime — not stored anywhere
3. Simple `board_pos + xacro_offset` doesn't produce correct results

### Known-Good Positions (from env config)
These 3 components ARE placed correctly by the original env config:
```python
task_board.init_state.pos = (0.2837, 0.229, 0.0)
sc_port.init_state.pos = (0.2904, 0.1928, 0.005)     # + randomization offset (0.0067, -0.0362, 0.005)
sc_port_2.init_state.pos = (0.2913, 0.1507, 0.005)    # + randomization offset (0.0076, -0.0783, 0.005)
nic_card.init_state.pos = (0.25135, 0.25229, 0.0743)  # + randomization offset (-0.03235, 0.02329, 0.0743)
```

### Suggested Approaches
1. **Reverse-engineer the board transform** from the 3 known-good positions vs XACRO rail positions
2. **URDF→USD import** of full task board XACRO (handles all transforms automatically)
3. **Interactive placement** in Isaac Sim GUI (tedious but reliable)

### Detailed handoff docs for this problem:
- `Intrinsic-AI/logs/2026-03-23/isaac-lab-component-placement-blocker.md`
- `Intrinsic-AI/logs/2026-03-23/isaac-lab-showcase-todo.md`
- MuJoCo handoff: `Intrinsic-AI/logs/2026-03-23/handoff_component_placement.md`

---

## What Still Needs To Be Done

### Priority 1: Component Placement (Current Blocker)
Fix the position math so extra NICs, SC/LC mounts, SFP modules sit correctly on the task board rails. Once this works, the full showcase (randomized layouts per env) becomes trivial.

### Priority 2: Remaining Isaac Lab Smoke Tests
- [ ] Teleop recording (HDF5 demos) — uses `record_demos.py` script
- [ ] Demo replay — uses `replay_demos.py` script
- [ ] Find max stable num_envs with Vulkan backend
- [ ] Run full 1500-iteration training

### Priority 3: Showcase
- [ ] Run 16-64 envs with GUI showing full board (all zones populated)
- [ ] Randomized NIC count (0-5), mount placements, cable layouts per env
- [ ] User wants to record video for a friend

### Priority 4: Policy Export
- [ ] Export trained policy checkpoint for Gazebo evaluation
- [ ] Verify policy works in the Kilted/Gazebo evaluation pipeline

---

## Key File Locations

```
Isaac Sim installation:     C:/isaac-sim/  (v5.1.0-rc.19)
Isaac Lab:                  C:/IsaacLab/
Isaac Lab ↔ Isaac Sim link: C:/IsaacLab/_isaac_sim  (junction → C:/isaac-sim/)

AIC task source:            C:/IsaacLab/aic/aic_utils/aic_isaac/aic_isaaclab/source/aic_task/
Env config:                 .../aic_task/tasks/manager_based/aic_task/aic_task_env_cfg.py
PPO config:                 .../aic_task/tasks/manager_based/aic_task/agents/rsl_rl_ppo_cfg.py
Domain randomization:       .../aic_task/tasks/manager_based/aic_task/mdp/events.py

Training script:            C:/IsaacLab/aic/aic_utils/aic_isaac/aic_isaaclab/scripts/rsl_rl/train.py
Play script:                C:/IsaacLab/aic/aic_utils/aic_isaac/aic_isaaclab/scripts/rsl_rl/play.py

USD assets (existing):      .../Intrinsic_assets/assets/{NIC Card, SC Port, SC Plug, Task Board Base}/
USD assets (new converts):  .../Intrinsic_assets/assets/{LC Mount, LC Plug, SFP Module, SFP Mount, SC Mount}/
Scene USD:                  .../Intrinsic_assets/scene/aic.usd

Test scripts:               C:/IsaacLab/test_*.py
Training logs:              C:/IsaacLab/logs/rsl_rl/
GLB source models:          C:/IsaacLab/aic/aic_assets/models/*/
Task board XACRO:           C:/IsaacLab/aic/aic_description/urdf/task_board.urdf.xacro
Sample trial config:        C:/IsaacLab/aic/aic_engine/config/sample_config.yaml

Handoff docs:               Intrinsic-AI/logs/2026-03-23/
Progress log:               Intrinsic-AI/logs/2026-03-23/isaac-lab-session2-progress.md
```

## System Configuration
- **GPU:** NVIDIA GeForce RTX 5090 (32GB VRAM, Blackwell)
- **Driver:** 581.42 (R580 Production Branch — NVIDIA validated for Omniverse)
- **OS:** Windows 11 Pro 10.0.26200
- **CPU:** Intel Core i9-14900K (24 cores)
- **RAM:** 64GB
- **Isaac Sim:** 5.1.0-rc.19, Vulkan graphics API
- **Python:** 3.11 (bundled with Isaac Sim at `_isaac_sim/kit/python/`)
- **Key packages:** torch 2.7.0+cu128, rsl-rl-lib 3.1.2, h5py 3.12.1, gymnasium 1.2.1

## Critical Rules
- **Never install Linux NVIDIA drivers in WSL2** — Windows driver is the only driver needed
- **Never pip install `warp-lang`** into Isaac Sim's Python — it bundles warp 1.8.2 internally
- **Always use `--enable_cameras`** flag when running AIC training (TiledCamera sensors need it)
- **rsl-rl-lib must be 3.1.2** — not 5.0.1 (our Isaac Lab is v2.3.2 stack, no compatibility shim)
- **Driver must be 581.42** (or R580 branch) for Blackwell + Omniverse Vulkan
- **Run from `_isaac_sim/python.bat`** not `isaaclab.bat` from bash (bash picks up miniconda Python)
