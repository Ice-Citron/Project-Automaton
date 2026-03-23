# Isaac Lab Component Placement Blocker — 2026-03-23

## Status
All USD assets converted and loading with correct textures. But **component positions on the task board are wrong** — same problem the MuJoCo instance hit.

## What Works
- GLB→USD conversion: 5/5 succeeded (LC Mount, LC Plug, SFP Module, SFP Mount, SC Mount)
- All component meshes render with correct PBR textures in Isaac Sim
- The base AIC-Task-v0 env works perfectly (RL training, 128 envs, etc.)
- The env's built-in 1 NIC + 2 SC ports are placed correctly by the original env config

## What's Wrong
When I manually add extra components using the XACRO rail positions, they end up in wrong locations. The screenshot shows components floating near but not on the task board.

### Root Cause
The XACRO rail positions are relative to `task_board_base_link`, but:
1. The task board in Isaac Lab is at world position `(0.2837, 0.229, 0.0)` — from `aic_task_env_cfg.py`
2. The board has some orientation (the YAML config says `yaw=3.1415` i.e. 180° rotated)
3. The original env config applies its OWN offsets for the 1 NIC and 2 SC ports that DO work:
   - SC port 1: `(0.2904, 0.1928, 0.005)` — hardcoded world position
   - SC port 2: `(0.2913, 0.1507, 0.005)` — hardcoded world position
   - NIC card: `(0.25135, 0.25229, 0.0743)` — hardcoded world position
4. These hardcoded positions DON'T match a simple `board_pos + xacro_offset` calculation

### The Transform Chain Problem
To place a component correctly, you need:
```
world_pos = board_world_pos + board_rotation * (rail_base_pos + translation_offset) + component_local_offset
```
Where:
- `board_world_pos` = from env config init_state
- `board_rotation` = unknown/complex (the board USD itself may have internal transforms)
- `rail_base_pos` = from XACRO
- `translation_offset` = random within rail limits
- `component_local_offset` = the offset from rail origin to where the component mesh sits (UNKNOWN — this is what aic_engine computes at runtime)

## Two Possible Approaches

### Approach A: URDF→USD Import (Recommended)
Import the full task board XACRO as a single USD, which would bring all mount frames with correct transforms:
```
C:/IsaacLab/aic/aic_description/urdf/task_board.urdf.xacro
```
Isaac Sim has `omni.isaac.urdf` for this. The URDF importer handles axis conventions and parent-child transforms automatically.

Challenges:
- Need to process XACRO→URDF first (requires `xacro` tool, usually Linux)
- The XACRO uses `$(arg)` parameters for translations — need to resolve these
- May need to be done in WSL2 then import the generated URDF

### Approach B: Reverse-Engineer from Working Positions
The env config has 3 working positions (1 NIC, 2 SC ports). By comparing these world positions to the XACRO rail definitions, we can compute the actual board transform and apply it to all other rails.

Working positions from `aic_task_env_cfg.py`:
```python
# Task board
task_board.init_state.pos = (0.2837, 0.229, 0.0)

# SC port 1 (which rail is this?)
sc_port.init_state.pos = (0.2904, 0.1928, 0.005)

# SC port 2
sc_port_2.init_state.pos = (0.2913, 0.1507, 0.005)

# NIC card (which rail is this?)
nic_card.init_state.pos = (0.25135, 0.25229, 0.0743)
```

XACRO rail positions (relative to board frame):
```
sc_rail_0: (-0.075 + trans, 0.0295, 0.0165)
sc_rail_1: (-0.075 + trans, 0.0705, 0.0165)
nic_rail_0: (-0.081418 + trans, -0.1745, 0.012)
```

The domain randomization code gives additional clues:
```python
"parts": [
    {"scene_name": "sc_port",   "offset": (0.0067, -0.0362, 0.005)},
    {"scene_name": "sc_port_2", "offset": (0.0076, -0.0783, 0.005)},
    {"scene_name": "nic_card",  "offset": (-0.03235, 0.02329, 0.0743)},
]
```
These offsets are RELATIVE TO THE BOARD'S world position and applied during domain randomization.

### Approach C: Interactive Placement in Isaac Sim GUI
Load the env, then manually drag components in the GUI to find correct positions. Save the transforms. Tedious but reliable.

## Files
- Converted USD assets: `C:/IsaacLab/.../Intrinsic_assets/assets/{LC Mount, LC Plug, SFP Module, SFP Mount, SC Mount}/`
- Env config: `C:/IsaacLab/.../aic_task_env_cfg.py`
- XACRO: `C:/IsaacLab/aic/aic_description/urdf/task_board.urdf.xacro`
- Domain randomization: `aic_task_env_cfg.py` lines 332-358
- Test scripts: `C:/IsaacLab/test_showcase_*.py`
