# Handoff: MuJoCo Scene Missing NIC Card + SC Port Components

## Problem

The MuJoCo mirror of the AIC Gazebo scene is missing the NIC card, SC port, and other components that sit ON the task board. The task board base (with rails and screw holes) renders correctly, but the components that slot into those rails are absent.

## Root Cause

In Gazebo, these components are **spawned dynamically** by `aic_engine` during trial setup. They are NOT part of the static task board model. The engine reads `sample_config.yaml`, then calls Gazebo-specific spawning services to place NIC cards on rails, SC ports on rails, etc.

The MuJoCo bringup (`aic_mujoco_bringup.launch.py`) does NOT include `aic_engine` and has no spawning mechanism. So these components never appear.

## What We Need To Do

Convert the individual component GLB models from `aic_assets/models/` into MuJoCo-compatible format (OBJ meshes) and inject them into the MuJoCo MJCF scene at the correct positions from `sample_config.yaml`.

## Files Involved

### Source GLB Models (in `References/aic/aic_assets/models/`)
```
NIC Card/nic_card_visual.glb        ← Green PCB with SFP port cages (33K vertices)
SC Port/sc_port_visual.glb          ← Blue fiber optic connector port (33K vertices)
SFP Module/sfp_module_visual.glb    ← SFP transceiver module (the plug)
NIC Card Mount/nic_card_mount_visual.glb  ← Rail that holds NIC card
SC Mount/sc_mount_visual.glb        ← Mount for SC port
SFP Mount/sfp_mount_visual.glb      ← Mount for SFP cage
```

### Already Converted OBJ Files (in `References/aic/aic_utils/aic_mujoco/mjcf/`)
```
manual_nic_card.obj    ← Just converted, 33K vertices, bounds ~12cm x 14.5cm x 5.8cm
manual_sc_port.obj     ← Just converted, 33K vertices, BUT bounds are in MILLIMETERS (needs scale 0.001)
```

### MuJoCo Scene Files (in `References/aic/aic_utils/aic_mujoco/mjcf/`)
```
scene.xml       ← Top-level scene (includes robot + world)
aic_robot.xml   ← Robot definition (UR5e + gripper + cameras)
aic_world.xml   ← World definition (task board base, enclosure, floor, cable, lights)
```

### Config File
```
~/ws_aic/install/aic_engine/share/aic_engine/config/sample_config.yaml
```

## Positions From Config (Trial 1)

Task board base: `pos=(0.15, -0.2, 1.14)`, `yaw=3.1415` (180° rotated)

Components on task board:
- **NIC card on nic_rail_0**: `entity_name="nic_card_0"`, `translation=0.036`
- **SC port on sc_rail_0**: `entity_name="sc_mount_0"`, `translation=0.042`, `yaw=0.1`
- **SFP mount on sfp_mount_rail_0**: `entity_name="sfp_mount_0"`, `translation=0.03`
- **SC mount on sc_mount_rail_0**: `entity_name="sc_mount_0"`, `translation=-0.02`

## What Already Works

- MuJoCo scene loads correctly with robot, task board base, cable, enclosure, glass walls
- WaveArm policy runs via `trigger_policy.py` (lifecycle configure → activate → send InsertCable goal)
- Full ROS 2 pipeline: Zenoh + mujoco_ros2_control + aic_controller + aic_adapter + aic_model
- Source build of 112 packages completed

## What We've Already Tried That Failed

1. **Exporting SDF from Gazebo with spawn flags** — Only exports mount rails, not actual NIC/SC/SFP models (those are spawned dynamically by the engine)
2. **The sdf2mjcf converter** — Converts geometry but the resulting visual geoms don't render (the converter's `add_cable_plugin.py` post-processing may be stripping assets)
3. **Manually placing box/cylinder geoms in scene.xml** — They don't appear either (possibly a MuJoCo worldbody ordering issue with includes)
4. **Patching material colors** — Confirmed the issue is NOT just "too dark" — the geoms are genuinely not rendering

## Likely Issue With Manual Placement

When we added bodies to `scene.xml` before the `<include>` tags, they might be getting overridden or ignored because MuJoCo processes includes in a specific order. The `<worldbody>` in scene.xml might conflict with the `<worldbody>` defined in the included files.

## What Gemini Should Try

### Approach 1: Add components directly to aic_world.xml (not scene.xml)
Instead of scene.xml, inject the NIC card and SC port meshes+geoms directly into `aic_world.xml`, inside the `task_board_base_link` body hierarchy where the mount rails already exist.

The NIC card mount body already exists at:
```xml
<body name="nic_card_mount_0::nic_card_mount_link" pos="-0.081418 -0.1745 0.012">
```

Add a child body inside it with the NIC card OBJ mesh.

### Approach 2: Use the already-converted mesh assets from the sdf2mjcf conversion
The MJCF already has mesh/material/texture definitions for NIC card and SC port:
```
mesh name="ef964132...nic_card_visual_merged_0" file="ef964132...obj"
texture name="texture_ef964132...nic_card_visual_merged_0" file="ef964132...45ced356...png"
```
And visual geoms exist:
```
<geom name="nic_card_visual" type="mesh" ... mesh="ef964132...nic_card_visual_merged_0"/>
```

These geoms are present in the XML but NOT rendering. Debug why:
- Check if the `class="world_default"` is setting visibility to hidden
- Check if MuJoCo is actually loading the mesh (look for XML parse errors on load)
- Try removing `class="world_default"` from one NIC card geom

### Approach 3: Standalone test
Create a minimal scene.xml that ONLY loads one mesh to verify it works:
```xml
<mujoco>
  <asset>
    <mesh name="test_nic" file="manual_nic_card.obj"/>
    <material name="test_green" rgba="0 1 0 1"/>
  </asset>
  <worldbody>
    <body pos="0 0 1">
      <geom type="mesh" mesh="test_nic" material="test_green"/>
    </body>
  </worldbody>
</mujoco>
```
Run with: `pixi run python3 -m mujoco.viewer --mjcf=test.xml`
If this works, the mesh is fine and the issue is in the scene assembly.

## Environment

- WSL2 Ubuntu 24.04, ROS 2 Kilted
- MuJoCo 3.5.0 (pixi) / 3.6.0 (standalone)
- All work in: `~/projects/Project-Automaton/References/aic/aic_utils/aic_mujoco/mjcf/`
- Run MuJoCo viewer: `cd ~/projects/Project-Automaton/References/aic && pixi run python3 -m mujoco.viewer --mjcf=aic_utils/aic_mujoco/mjcf/scene.xml`
- Run full pipeline: `bash ~/projects/Project-Automaton/Intrinsic-AI/tools/mujoco/run_mujoco.sh WaveArm`

## Key Command to Verify

After any change, quick visual test:
```bash
cd ~/projects/Project-Automaton/References/aic
pixi run python3 aic_utils/aic_mujoco/scripts/view_scene.py aic_utils/aic_mujoco/mjcf/scene.xml
```
