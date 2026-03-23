# Isaac Lab Showcase TODO — Task Board Components

## What the User Wants
Run 128 envs with GUI showing the full AIC task board with:
- SC ports (Subscriber Connector) — Zone 2, optical patch panel
- LC ports (Lucent Connector) — Zones 3-4, pick locations
- NIC cards with SFP (Small Form-factor Pluggable) ports — Zone 1
- SFP modules
- Randomized layouts per env (some envs 0 NICs, some 1, some 5, different cable counts, etc.)

## Current State
The AIC-Task-v0 env works (128 envs, RL training, Vulkan). BUT the scene only spawns:
- 1x task_board base
- 2x SC ports (`sc_port`, `sc_port_2`)
- 1x NIC card (`nic_card`)
- 1x UR5e robot with cable

**Missing from the scene:**
- LC plugs/ports (no USD asset for LC plug exists in `Intrinsic_assets/assets/`)
- SFP modules (no standalone USD asset — SFP ports are part of the NIC card USD)
- Additional NIC cards (only 1 is spawned, config supports up to 5 on Zone 1 rails)
- Cable randomization (cables are commented out in `aic_task_env_cfg.py`)
- Per-env NIC count variation (all envs get identical object set)

## Available USD Assets
Located at: `C:/IsaacLab/aic/aic_utils/aic_isaac/aic_isaaclab/source/aic_task/aic_task/tasks/manager_based/aic_task/Intrinsic_assets/assets/`

| Asset | Files | Notes |
|-------|-------|-------|
| NIC Card | `nic_card.usd`, `nic_card_visual.usd` | Has SFP ports built-in |
| NIC Card Mount | exists as directory | Mount/rail for NIC |
| SC Port | `sc_port.usd`, `sc_port_visual.usd` | Subscriber Connector |
| SC Plug | `sc_plug_visual.usd` | Visual only |
| Task Board Base | `task_board_rigid.usd` | The board chassis |

**Not found as standalone USD:**
- LC plug/port (only referenced in YAML config as `lc_mount_0`, `lc_mount_1`)
- SFP module (referenced as `sfp_mount_0` in YAML)
- Cables (referenced as `sfp_sc_cable`, `sfp_sc_cable_reversed`)

## What Needs to Happen
1. **Find or create LC/SFP USD assets** — check if they exist elsewhere in the AIC repo or Gazebo models
2. **Add more NIC cards to the scene** — modify `aic_task_env_cfg.py` to spawn 5 NIC cards on Zone 1 rails
3. **Add LC/SFP assets to the scene** — once found
4. **Randomize per-env component count** — Isaac Lab's `EventTerm` domain randomization currently only randomizes positions, not object visibility/count. Per-env object count variation would require either:
   - Spawning max objects and randomly hiding/teleporting some offscreen on reset
   - Or modifying the scene to use different configs per env (non-trivial in Isaac Lab)

## The MuJoCo Instance Had the Same Issue
The other Claude Code instance working on MuJoCo also struggled with spawning the full set of board components. This is likely a shared problem — the AIC repo's Gazebo-centric assets may not have standalone USD equivalents for all components.

## Where to Look for Missing Assets
- `C:/IsaacLab/aic/aic_assets/models/` — Gazebo model source files (URDF/xacro, not USD)
- `C:/IsaacLab/aic/aic_description/urdf/task_board.urdf.xacro` — Full board URDF with all components
- May need to convert URDF → USD using Isaac Sim's URDF importer

## Key Config Files
- Env config: `C:/IsaacLab/aic/.../aic_task_env_cfg.py` (lines 144-210 define scene objects)
- Domain randomization: same file, lines 332-358 (`randomize_board_and_parts`)
- Sample trial YAML: `C:/IsaacLab/aic/aic_engine/config/sample_config.yaml`
- Task board description: `C:/IsaacLab/aic/docs/task_board_description.md`

## AIC Task Board Zones (from docs)
- **Zone 1** — NIC cards with SFP ports (up to 5 cards, each with 2 SFP ports). Rail translation: [0, 0.062]m, orientation: [-10, +10] deg
- **Zone 2** — SC optical ports (up to 5 ports across 2 rails). Rail translation: [0, 0.115]m
- **Zone 3 & 4** — Pick locations for LC plugs, SC plugs, SFP modules. Translation: [0, 0.188]m, orientation: [-60, +60] deg

## Cable Types
- `sfp_sc_cable` — SFP plug on one end, SC plug on the other
- `sfp_sc_cable_reversed` — same but reversed orientation
