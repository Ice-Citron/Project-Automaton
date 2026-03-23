# Handoff to Isaac Lab Instance: Findings from MuJoCo Work

## Context
The MuJoCo Claude Code instance (me) has been working on the same task board component placement problem you're facing. This document shares everything we learned so you don't repeat our mistakes, plus actionable data for your Isaac Lab work.

## The Shared Root Problem
Both MuJoCo and Isaac Lab face the same fundamental issue: **task board components (SFP modules, SC plugs, LC plugs, NIC cards) are dynamically spawned by `aic_engine` in Gazebo at runtime.** They are NOT part of the static URDF/SDF/XACRO scene files. The `aic_engine` uses Gazebo-specific services to spawn entities and attach them to mount fixtures on the task board.

Since neither MuJoCo nor Isaac Lab runs `aic_engine`, these components must be manually placed. The challenge is figuring out the correct position and orientation for each component relative to its mount fixture.

## What the MuJoCo Instance Successfully Built

### Fully Working
1. **Textured NIC cards (Zone 1)**: 3D NIC card meshes with PBR textures render perfectly on the task board. The sdf2mjcf converter extracts textures from GLB files. Key fix: the converter's material `rgba` was set to `(0,0,0,1)` which multiplied textures to black — changing to `(1,1,1,1)` fixed it.

2. **SC optical ports (Zone 2)**: Blue SC port connectors on sc_rail_0 and sc_rail_1, with textured meshes from the converter.

3. **Mount fixtures on rails (Zones 3-4)**: LC mount, SC mount, SFP mount cradle fixtures sit correctly on their designated rails. Converted from GLB→OBJ using trimesh.

4. **Glass walls and lighting**: Enclosure glass panels (transparent alpha=0.25), ceiling light panel, proper ambient/diffuse lighting.

5. **Randomized board generator** (`randomize_board.py`): Python script that generates random task board layouts within the AIC config constraints. Randomizes NIC card count (1-5), SC port count (1-2), and mount placements on rails. Outputs a new `aic_world_rand.xml` that MuJoCo can load.

6. **Full ROS 2 pipeline**: Zenoh + mujoco_ros2_control + aic_controller + aic_adapter + aic_model. WaveArm policy runs end-to-end with `Result: success=True`.

### Broken (Where We're Stuck)
1. **Plug/module alignment inside mounts**: We can place plug meshes near mount fixtures, but the position and orientation are wrong. The plugs float near the cradle instead of sitting inside it.

2. **MuJoCo OBJ import axis rotation**: MuJoCo applies a `(Y,Z,X)` cyclic permutation when importing OBJ files. This scrambles the mesh axes, making it hard to compute correct offsets. Pre-rotating OBJ vertices didn't work (MuJoCo's rotation appears data-dependent). Applying a correcting `quat` on the geom also failed.

3. **Yellow fiber optic cables**: Not implemented. Would require physics composite bodies (ball joints + cylinders) similar to the existing sfp_sc_cable in the scene.

## GLB Model Locations (Complete Set)
All component models with their visual GLB files. These are the source-of-truth for geometry:

```
~/projects/Project-Automaton/References/aic/aic_assets/models/

Components that sit ON the board (need manual placement):
  NIC Card/nic_card_visual.glb            ← Green PCB with SFP port cages (33K vertices, ~12x14.5x5.8cm)
  NIC Card Mount/nic_card_mount_visual.glb ← Rail mount that holds NIC card
  SC Port/sc_port_visual.glb              ← Blue fiber optic connector port (33K vertices)
  SC Mount/sc_mount_visual.glb            ← Grey V-cradle fixture for SC plugs
  SC Plug/sc_plug_visual.glb              ← Blue SC connector plug (~57mm long)
  SFP Module/sfp_module_visual.glb        ← Silver SFP transceiver module (~56mm long)
  SFP Mount/sfp_mount_visual.glb          ← Grey V-cradle fixture for SFP modules
  LC Mount/lc_mount_visual.glb            ← Grey V-cradle fixture for LC plugs
  LC Plug/lc_plug_visual.glb              ← LC connector plug (~59mm long)

Static scene elements (already in scene):
  Task Board Base/task_board_base_visual.glb
  Enclosure/enclosure_visual.glb
  Floor/floor_visual.glb
  Walls/walls_visual.glb
  Camera Mount/camera_mount_visual.glb

Cables (physics objects):
  sfp_sc_cable/model.sdf          ← SFP-to-SC cable with composite body physics
  sfp_sc_cable_reversed/model.sdf ← Reversed version
  lc_cable/model.sdf
  lc_sc_cable/model.sdf
  sc_cable/model.sdf
```

## CRITICAL: Axis Rotation Warning for MuJoCo OBJ Import

When converting GLB→OBJ (using trimesh's `concatenate(scene.dump())`) and loading in MuJoCo, **the coordinate axes get permuted**:

**MuJoCo OBJ import applies: `MuJoCo(X,Y,Z) = file(Y,Z,X)` to vertex data.**

This was confirmed with a controlled experiment:
- Created a box with explicit vertices: X=0.10m (long), Y=0.02m, Z=0.05m
- Wrote raw OBJ file with vertex `v 0.1 0 0`
- MuJoCo loaded the mesh as: X=0.02m, Y=0.05m, Z=0.10m (axes cyclically permuted)
- Checked actual vertex data: `(0.05, -0.01, -0.025)` in file appeared as `(-0.01, -0.025, 0.05)` in MuJoCo

**For Isaac Lab (USD format):** You likely do NOT have this problem. USD uses Y-up convention by default. Isaac Sim's URDF→USD importer (`omni.isaac.urdf`) handles axis conventions automatically. If you import the task board XACRO via the URDF importer, positions should be correct.

However, if you're manually placing components (not using URDF import), you should test with a simple known-geometry object first to confirm your axis conventions.

## Rail Positions from XACRO (Exact Values, Verified)
Source: `aic_description/urdf/task_board.urdf.xacro`

All positions are relative to `task_board_base_link`. The task board itself is at `pos=(0.15, -0.2, 1.14)` with `yaw=3.1415` (180° rotated) in the world frame.

### Zone 1 — NIC Card Rails
5 rails for NIC cards. Each NIC card slides along the rail (X-axis translation).
```
Rail            Base Position (X, Y, Z)                Translation Range
nic_rail_0      (-0.081418 + trans, -0.1745, 0.012)    [-0.0215, 0.0234] along X
nic_rail_1      (-0.081418 + trans, -0.1345, 0.012)    [-0.0215, 0.0234] along X
nic_rail_2      (-0.081418 + trans, -0.0945, 0.012)    [-0.0215, 0.0234] along X
nic_rail_3      (-0.081418 + trans, -0.0545, 0.012)    [-0.0215, 0.0234] along X
nic_rail_4      (-0.081418 + trans, -0.0145, 0.012)    [-0.0215, 0.0234] along X
```
NIC card orientation range: yaw ±10° (±0.1745 rad)

### Zone 2 — SC Port Rails
2 rails for SC optical ports. Each SC port slides along the rail (X-axis translation).
```
Rail            Base Position (X, Y, Z)                Translation Range
sc_rail_0       (-0.075 + trans, 0.0295, 0.0165)       [-0.06, 0.055] along X
sc_rail_1       (-0.075 + trans, 0.0705, 0.0165)       [-0.06, 0.055] along X
```
SC ports have a base rotation of RPY=(1.57, 0, 1.57) relative to the task board.

### Zones 3-4 — Mount Rails (Pick Locations)
6 rails organized as 3 types × 2 sides (left Y=-0.10625, right Y=0.10625).
Mounts slide along the Y-axis (translation applied to Y coordinate).
```
Rail                Base Position (X, Y, Z)                   Translation Range
lc_mount_rail_0     (0.01, -0.10625 + trans, 0.012)          [-0.09425, 0.09425] along Y
sfp_mount_rail_0    (0.055, -0.10625 + trans, 0.01)          [-0.09425, 0.09425] along Y
sc_mount_rail_0     (0.1, -0.10625 + trans, 0.012)           [-0.09425, 0.09425] along Y
lc_mount_rail_1     (0.01, 0.10625 + trans, 0.012)           [-0.09425, 0.09425] along Y
sfp_mount_rail_1    (0.055, 0.10625 + trans, 0.01)           [-0.09425, 0.09425] along Y
sc_mount_rail_1     (0.0985, 0.10625 + trans, 0.01)          [-0.09425, 0.09425] along Y
```
Note: SFP mount Z is 0.01 (not 0.012 like LC and SC mounts). This is from the XACRO.
Mount orientation range: yaw ±60° (±1.0472 rad) per config, but user confirmed mounts are screwed down → effectively 0° yaw.

**IMPORTANT: Component-to-rail mapping is strict:**
- `lc_mount_rail_*` → LC mounts ONLY
- `sfp_mount_rail_*` → SFP mounts ONLY
- `sc_mount_rail_*` → SC mounts ONLY

### NIC Card Mount Positions (Zone 1 — from XACRO)
These are the base positions for the NIC card mount rails:
```
nic_card_mount_0:  pos=(-0.081418 + trans, -0.1745, 0.012)
nic_card_mount_1:  pos=(-0.081418 + trans, -0.1345, 0.012)
nic_card_mount_2:  pos=(-0.081418 + trans, -0.0945, 0.012)
nic_card_mount_3:  pos=(-0.081418 + trans, -0.0545, 0.012)
nic_card_mount_4:  pos=(-0.081418 + trans, -0.0145, 0.012)
```

## Mount XACRO Details (No Plug Attachment Defined)
We read all three mount XACRO macros (`sfp_mount_macro.xacro`, `sc_mount_macro.xacro`, `lc_mount_macro.xacro`). Key finding: they define ONLY the mount fixture geometry (visual mesh + collision boxes). They do NOT define:
- Child links for plugs/modules
- Joints connecting mount to plug
- Any reference to what component sits in the mount

In Gazebo, `aic_engine` handles the attachment at runtime by:
1. Reading `sample_config.yaml` for which rails have components
2. Spawning the component models (SFP module, SC plug, etc.) as separate Gazebo entities
3. Attaching them to the mount fixtures via Gazebo joints

The **relative transform between mount and plug is computed by `aic_engine`**, not stored in any XACRO/SDF file. This is the core blocker for both MuJoCo and Isaac Lab.

## Cable Assembly Structure (from sfp_sc_cable/model.sdf)
The cable model defines how plugs connect to each other via the cable. These are NOT mount-to-plug transforms, but they give clues about plug orientations:

```
Kinematic chain:
cable_connection_0 (base)
  → lc_plug_link:      pos=(-0.041, 0, 0), rpy=(0, 0, π/2)
    → sfp_module_link: pos=(0, 0.0384, 0), rpy=(0, π, π)
      → sfp_tip_link:  pos=(0, -0.02365, 0), rpy=(π/2, 0, 0)
  → link_1 → link_2 → ... → link_20 (cable segments, ball joints)
    → cable_connection_1
      → sc_plug_link:  pos=(0.052, 0, 0), rpy=(0, 0, 0)
        → sc_tip_link: pos=(0.01165, 0, 0), rpy=(-π/2, 0, -π/2)
```

Key insight: The SFP module's long axis (56mm) is along Y in the GLB frame. The SC plug's long axis (57mm) is along X. The LC plug's long axis (59mm) is along Y. These different orientations mean each plug type needs a different rotation to sit correctly in its mount.

## Randomizer Script Details
Location: `~/projects/Project-Automaton/Intrinsic-AI/tools/mujoco/randomize_board.py`

Usage:
```bash
python3 randomize_board.py --seed 42 --nic 3 --sc 2
```

What it does:
1. Loads `aic_world.xml` (the base MuJoCo world file)
2. Randomly selects which NIC rails to populate (e.g., rails 0, 2, 4 for 3 cards)
3. Randomly selects which SC rails to populate
4. Randomly selects mount rail occupancy for zones 3-4
5. Generates random translation offsets within the config limits
6. Deep-copies existing NIC card / SC port body hierarchies for new rails
7. Strips collision geoms from cloned bodies (to avoid visual clutter)
8. Creates mount bodies with visual-only geoms for zones 3-4
9. Writes `aic_world_rand.xml`

The function `make_mount_body()` (around line 100) is where plug/module geoms are nested inside mount bodies. Once we have the correct pos/quat values, they go here:
```python
# Currently geoms are placed at (0,0,0) — WRONG
# Needs correct offset per mount type
geom = ET.SubElement(body, "geom")
geom.set("pos", "X Y Z")  # <-- correct values needed
geom.set("quat", "W X Y Z")  # <-- correct values needed
```

You could adapt the randomization logic for Isaac Lab's `EventTerm` domain randomization system.

## Suggestions for Isaac Lab Specifically

### 1. Use Isaac Sim's URDF Importer
The task board XACRO at `aic_description/urdf/task_board.urdf.xacro` defines the full board with all mount positions. Isaac Sim can import URDF directly via `omni.isaac.urdf`. This should handle axis conventions correctly and give you the mount bodies at the right positions.

```python
from omni.isaac.urdf import _urdf
urdf_interface = _urdf.acquire_urdf_interface()
# Process the XACRO first: xacro task_board.urdf.xacro > task_board.urdf
result = urdf_interface.parse_urdf("path/to/task_board.urdf", import_config)
```

### 2. Convert Missing Assets (GLB → USD)
Isaac Lab is missing USD assets for LC plugs, SFP modules, and some other components. You can convert from GLB using Isaac Sim's asset converter:

```python
import omni.kit.asset_converter as converter
task_manager = converter.get_instance()
task_manager.create_converter_task(
    input_asset_path="path/to/lc_plug_visual.glb",
    output_asset_path="path/to/lc_plug_visual.usd"
)
```

Or use the URDF→USD pipeline which handles this automatically.

### 3. Per-Env Randomization Strategy
Isaac Lab's `EventTerm` randomizes object POSITIONS but doesn't easily support per-env OBJECT COUNT variation. Two approaches:
- **Spawn max components, hide extras**: Spawn 5 NIC cards, 2 SC ports, all mounts. On reset, randomly teleport unwanted components to an offscreen location `(0, 0, -10)`.
- **Modify scene config**: Create multiple scene configurations and load different ones per env index.

### 4. Glass Wall Transparency
In MuJoCo we fixed this by setting wall materials to `rgba="0.85 0.9 0.95 0.25"` (transparent). In Isaac Lab/USD, you'll need to modify the material's opacity in the USD scene. The wall meshes are `walls_visual_Curve.001`, `walls_visual_merged_1`, `walls_visual_Plane.003_1`, `walls_visual_Plane.002`.

## Key Files Reference
```
Source of truth (Gazebo/URDF):
  aic_description/urdf/task_board.urdf.xacro    ← All rail positions, component macros
  aic_assets/models/*/model.sdf                  ← Individual component SDF models
  aic_assets/models/*/*.glb                      ← Visual meshes (known good geometry)
  aic_engine/config/sample_config.yaml           ← Trial configs with component placements

MuJoCo scene (what we built):
  aic_utils/aic_mujoco/mjcf/scene.xml            ← Top-level (robot + world)
  aic_utils/aic_mujoco/mjcf/aic_world.xml        ← Base world (task board, enclosure, cable)
  aic_utils/aic_mujoco/mjcf/aic_world_rand.xml   ← Generated randomized version
  aic_utils/aic_mujoco/mjcf/scene_rand.xml        ← Scene pointing to randomized world
  aic_utils/aic_mujoco/mjcf/test_mounts.xml       ← Standalone mount+plug test scene

Tools we built:
  Intrinsic-AI/tools/mujoco/randomize_board.py    ← Board randomizer
  Intrinsic-AI/tools/mujoco/trigger_policy.py     ← Bypass aic_engine for policy execution
  Intrinsic-AI/tools/mujoco/run_mujoco.sh         ← One-command full pipeline launcher
  Intrinsic-AI/tools/mujoco/patch_mujoco_materials.py ← Extract GLB colors → patch MJCF

Handoff docs:
  Intrinsic-AI/logs/2026-03-23/handoff_component_placement.md     ← Detailed problem statement
  Intrinsic-AI/logs/2026-03-23/handoff_gemini_gpt_component_alignment.md ← For external help
```

## Competition Timeline
- Qualification deadline: ~May 27, 2026 (internal) / ~June 30, 2026 (public)
- Current date: March 23, 2026
- Hours spent: ~20 of 100-hour plan
- Key milestone not yet hit: Non-GT policy that earns Tier 3 > 0 in Gazebo
