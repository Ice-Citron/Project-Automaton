# Help Request: Isaac Lab Mount Fixture Positions for AIC Task Board

## The Problem

I'm working on the **AI for Industry Challenge (AIC)** — a robotics competition where a UR5e robot inserts fiber optic cables into a task board. I'm using the official `aic_utils/aic_isaac` Isaac Lab integration provided by Intrinsic/NVIDIA.

The existing `aic_task_env_cfg.py` has 3 components correctly positioned on the task board:
- Task board base
- 2x SC ports
- 1x NIC card

I need to add **3 more component types** (LC mount, SFP mount, SC mount) to the scene. The USD assets already exist in `Intrinsic_assets/assets/` (converted from GLB by the other Claude Code instance). The problem is: **I don't know the correct position offsets for these mounts relative to the task board.**

## What I Know

### Existing known-good positions (from NVIDIA's env config)

```python
# Task board base
task_board.init_state.pos = (0.2837, 0.229, 0.0)

# SC port (offset from board: +0.0067, -0.0362, +0.005)
sc_port.init_state.pos = (0.2904, 0.1928, 0.005)
sc_port.init_state.rot = (0.73136, 0.0, 0.0, -0.682)

# SC port 2 (offset from board: +0.0076, -0.0783, +0.005)
sc_port_2.init_state.pos = (0.2913, 0.1507, 0.005)
sc_port_2.init_state.rot = (0.73136, 0.0, 0.0, -0.682)

# NIC card (offset from board: -0.03235, +0.02329, +0.0743)
nic_card.init_state.pos = (0.25135, 0.25229, 0.0743)
nic_card.init_state.rot = (1.0, 0.0, 0.0, 0.0)  # identity
```

### XACRO mount rail positions (relative to task_board_base_link)

From `task_board.urdf.xacro`, the mount rails are at:
```
lc_mount_rail_0:   x=0.01,   y=-0.10625, z=0.012
sfp_mount_rail_0:  x=0.055,  y=-0.10625, z=0.01
sc_mount_rail_0:   x=0.1,    y=-0.10625, z=0.012
lc_mount_rail_1:   x=0.01,   y=+0.10625, z=0.012
sfp_mount_rail_1:  x=0.055,  y=+0.10625, z=0.01
sc_mount_rail_1:   x=0.0985, y=+0.10625, z=0.01
```

### The coordinate system mismatch

The Isaac Lab positions do NOT follow a simple rigid-body transform from the XACRO positions. I verified this mathematically:

- XACRO SC port position: `(-0.075, 0.0295, 0.0165)` relative to board
- Isaac Lab SC port offset: `(0.0067, -0.0362, 0.005)` relative to board

These are NOT related by any simple rotation (90°, 180°) or axis swap. The NVIDIA team appears to have manually positioned the USD assets in their scene editor.

I attempted:
1. **SVD-based Procrustes alignment** using the 3 known points — errors of 4-11cm (unusable)
2. **MuJoCo position extraction** (since sdf2mjcf preserves correct positions) — same transform doesn't work because MuJoCo and Isaac Lab have completely different coordinate frames
3. **Isaac Sim MJCF importer** — crashes on the complex sdf2mjcf mesh filenames (`invalid char filename argument`)
4. **Isaac Sim URDF importer** — runs but produces a 3KB file with no visual meshes (can't resolve `package://` URIs even after replacing with absolute paths; GLB format not supported by the importer)

## What I Need

The **Isaac Lab world-frame positions and orientations** (pos + quaternion) for:
1. **SFP mount** fixture (USD: `Intrinsic_assets/assets/SFP Mount/sfp_mount_visual.usd`)
2. **LC mount** fixture (USD: `Intrinsic_assets/assets/LC Mount/lc_mount_visual.usd`)
3. **SC mount** fixture (USD: `Intrinsic_assets/assets/SC Mount/sc_mount_visual.usd`)

These should be positioned ON the task board rails, matching where Gazebo would place them.

## The Ideal Answer

The ideal answer is one of:
1. **The actual offsets** (like the SC port's `(0.0067, -0.0362, 0.005)`) that I can plug into `aic_task_env_cfg.py`
2. **The coordinate transform** from XACRO board-relative frame to Isaac Lab world frame, so I can compute any component's position
3. **A working automated pipeline** (SDF→USD, URDF→USD, or MJCF→USD) that preserves positions — so I never have to manually calibrate

## Context & Constraints

- **Isaac Sim version:** 5.1.0 (Python 5.1.0)
- **Isaac Lab version:** 2.3.2
- **GPU:** NVIDIA RTX 5090, driver 581.42
- **The scene USD** (`Intrinsic_assets/scene/aic.usd`) contains the enclosure at pos=(0, 0, -1.15)
- **The robot USD** (`aic_unified_robot_cable_sdf.usd`) is at pos=(-0.18, -0.122, 0)
- **All existing components use `kinematic_enabled=True`** (static, no physics)
- **The randomization event** (`randomize_board_and_parts`) moves parts as board_pos + fixed_offset + random_noise
- **The task board XACRO** uses `package://aic_assets/...` URIs for mesh references
- **Competition deadline:** ~May 27, 2026

## What I've Already Tried

| Approach | Result |
|----------|--------|
| Manual position guessing | Components floating off the board (see screenshot) |
| 3-point Procrustes (MJ→IL) | 4-11cm errors, unusable |
| Isaac Sim MJCF importer | Crashes — `invalid char filename argument` on hash-named OBJ files |
| Isaac Sim URDF importer | 3KB empty USD — GLB meshes not supported |
| Physics settle in MuJoCo | Plugs bounce off collision geometry, don't settle into cradles |
| STL format instead of OBJ | Same MuJoCo normalization applied — no improvement |

## Files Referenced

```
aic_task_env_cfg.py    — Scene + MDP config (needs mount positions added)
events.py              — randomize_board_and_parts function
task_board.urdf.xacro  — Source of truth for rail positions
sample_config.yaml     — Competition trial configs with rail translation limits
```

## NEW: Positions extracted from NVIDIA's scene.usd

We read the actual `scene.usd` provided by NVIDIA (9.4MB file). It contains ONLY 4 positioned components:

```
/base_visual           → translate = (0.2194, 0.2838, 1.1284)   ← task board
/nic_card_mount_visual → translate = (0.0513, 0.2601, 1.1311)   ← NIC card mount bracket
/nic_card_visual       → translate = (0.0333, 0.2623, 1.2190)   ← NIC card itself
/sc_port_visual        → translate = (0.3015, 0.2474, 1.1319)   ← SC port
```

**Mount fixtures (LC/SFP/SC) do NOT exist in scene.usd.** NVIDIA never placed them.

Note: these scene.usd positions are at Z≈1.13 (table height). The aic_task_env_cfg.py positions are at Z≈0.0 because the env config subtracts the table offset. The `aic_scene` asset is placed at z=-1.15 to compensate.

So the Isaac Lab env config board position (0.2837, 0.229, 0.0) corresponds to scene.usd board position (0.2194, 0.2838, 1.1284) after the scene transform.

We now have 4 reference points between scene.usd absolute positions and env config positions. This should be enough to compute the transform.

## Specific Questions

1. How did NVIDIA determine the positions `(0.2904, 0.1928, 0.005)` for the SC port in Isaac Lab? Was this done in the Isaac Sim GUI scene editor?

2. Is there a way to extract the world-frame positions from the `scene/aic.usd` file programmatically? (The enclosure USD might contain reference positions)

3. The `aic_unified_robot_cable_sdf.usd` was clearly converted from the Gazebo SDF. How was this conversion done — is there a tool that preserves positions? If so, can the same tool convert the task board?

4. Is there a known mapping between the XACRO coordinate frame and the Isaac Lab world frame? Even just the rotation matrix would let me compute all positions.

5. Alternatively: can I import the task board XACRO via Isaac Lab's `sim_utils.UrdfFileCfg` spawner (not the standalone URDF importer) and have it resolve `package://` URIs automatically?
