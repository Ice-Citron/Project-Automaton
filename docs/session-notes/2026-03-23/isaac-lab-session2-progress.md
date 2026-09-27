# Isaac Lab Session 2 Progress — 2026-03-23

## Summary
**Isaac Lab AIC-Task-v0 is FULLY WORKING on Windows native with Vulkan rendering + RL training.**

All success criteria met:
- AIC-Task-v0 runs
- RL training completes (10 iterations verified)
- GUI visualization works
- 128+ envs stable

## Root Cause: Three Separate Bugs

### Bug 1: Vulkan crash (access violation in `rtx.scenedb.plugin.dll`)
- **Cause**: NVIDIA driver 595.79 (R590 branch) is unvalidated for Omniverse on Blackwell GPUs
- **Fix**: Downgraded to **driver 581.42** (R580 Production Branch) — the officially supported driver per NVIDIA's Omniverse Technical Requirements page
- **Workaround** (if stuck on 595.79): Force D3D12 via `sys.argv.append('--/app/vulkan=false'); sys.argv.append('--/renderer/active_graphics_api=Direct3D12')` before importing SimulationApp
- **Credit**: Gemini Deep Think identified this as a known driver regression

### Bug 2: DLL load failure (`0xc0000139` in h5py._errors)
- **Cause**: h5py 3.16.0 had incompatible native DLLs in Isaac Sim's Python environment
- **Fix**: Downgraded to h5py 3.12.1: `pip install h5py==3.12.1`

### Bug 3: RL training `KeyError: 'actor'`
- **Cause**: rsl-rl-lib 5.0.1 changed its config API (expects `actor`/`critic` keys), but Isaac Lab expects rsl-rl-lib 3.1.2 (uses `policy` key)
- **Fix**: Downgraded rsl-rl-lib: `pip install rsl-rl-lib==3.1.2`

## Packages Installed/Fixed
| Package | Action | Reason |
|---------|--------|--------|
| h5py | 3.16.0 → 3.12.1 | DLL load failure fix |
| rsl-rl-lib | 5.0.1 → 3.1.2 | API mismatch with Isaac Lab |
| isaaclab_contrib | installed (editable) | Missing module |
| isaaclab_rl | installed (editable) | Required by training script |
| warp-lang | uninstalled (session 1) | Conflicted with bundled warp 1.8.2 |

## Scaling Results (RTX 5090, 32GB VRAM)

### D3D12 Backend (driver 595.79 — workaround)
| num_envs | Throughput (env-steps/s) | GPU Memory | Status |
|----------|------------------------|------------|--------|
| 16 | 78 | 0.6 GB | Clean |
| 128 | 406 | 3.2 GB | Clean |
| 256 | 648 | 6.2 GB | Clean (sweet spot) |
| 512 | 80 | 12.2 GB | D3D12 Map errors at shutdown |

### Vulkan Backend (driver 581.42 — production)
| num_envs | Throughput (env-steps/s) | GPU Memory | Status |
|----------|------------------------|------------|--------|
| 16 | 114 | TBD | Clean |
| 128 (RL train) | ~250 (10 iters in 61.5s) | 0.3 GB | Clean |

## RL Training Results
- **4 envs, GUI, 2 iters**: 8.3s — GUI visualization works
- **128 envs, headless, 10 iters**: 61.5s (~6.2s/iter) — production ready

## What's Working
- [x] Isaac Sim 5.1.0-rc.19 starts cleanly (Vulkan, driver 581.42)
- [x] AIC-Task-v0 environment registers
- [x] Environment creates with configurable num_envs (tested up to 256)
- [x] env.reset() returns observations (shape [N, 3154])
- [x] env.step() runs, rewards compute correctly
- [x] 3 TiledCamera sensors active (center, left, right)
- [x] Physics + rendering stepping works
- [x] PPO RL training (OnPolicyRunner) works
- [x] GUI visualization during training works
- [x] Headless training with 128 envs works

## Remaining TODOs
- [ ] Teleop recording (HDF5 demos)
- [ ] Demo replay
- [ ] Find max stable num_envs with Vulkan (tested 128 so far)
- [ ] Run full 1500-iteration training
- [ ] Export trained policy for Gazebo evaluation

## Key File Locations
- Isaac Sim: `C:/isaac-sim/` (5.1.0-rc.19)
- Isaac Lab: `C:/IsaacLab/`
- AIC task source: `C:/IsaacLab/aic/aic_utils/aic_isaac/aic_isaaclab/source/aic_task/`
- Training script: `C:/IsaacLab/aic/aic_utils/aic_isaac/aic_isaaclab/scripts/rsl_rl/train.py`
- Test scripts: `C:/IsaacLab/test_*.py`
- Training logs: `C:/IsaacLab/logs/rsl_rl/`

## How to Run Training
```bash
# Quick test (GUI, 4 envs, 2 iterations)
C:/IsaacLab/_isaac_sim/python.bat C:/IsaacLab/test_rl_train_gui.py

# Full benchmark (headless, 128 envs, 10 iterations)
C:/IsaacLab/_isaac_sim/python.bat C:/IsaacLab/test_rl_train_full.py

# Official AIC training script (untested — needs cd to scripts dir)
cd C:/IsaacLab/aic/aic_utils/aic_isaac/aic_isaaclab/scripts/rsl_rl/
C:/IsaacLab/_isaac_sim/python.bat train.py --task AIC-Task-v0 --headless --num_envs 128 --max_iterations 10
```

## D3D12 Workaround (for future reference if driver regresses)
```python
import sys
sys.argv.append('--/app/vulkan=false')
sys.argv.append('--/renderer/active_graphics_api=Direct3D12')
# Then import SimulationApp or AppLauncher as usual
```
