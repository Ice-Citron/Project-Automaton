# Handoff: MuJoCo Component Placement — What's Stuck

## The Problem

We need to correctly position SFP modules, SC plugs, and LC plugs **inside their respective mounts** on the MuJoCo task board (zones 3-4). Currently the plug/module meshes are placed at the mount body origin (0,0,0 relative to mount), but they appear misaligned because:

1. Each mesh has its **own coordinate origin** from the original CAD/GLB model
2. I don't know the **relative transform** between the mount frame and the plug frame
3. I've been guessing positions instead of reading the actual Gazebo/URDF definitions

## What Works

- **Zone 1 (NIC cards)**: Perfect — 3 NIC cards with textures on nic_rails, properly randomized
- **Zone 2 (SC ports)**: Perfect — 2 SC ports on sc_rails with textured meshes
- **Mount fixtures on rails**: LC mount, SC mount, SFP mount meshes all appear correctly on their rails
- **Randomizer script**: `randomize_board.py` generates valid randomized layouts
- **Scene loads cleanly**: No XML errors, all meshes parse

## What Doesn't Work

- **SFP module position in SFP mount**: The silver SFP transceiver module mesh appears offset/misaligned relative to the SFP mount. It should slot into the mount like a card into a reader.
- **SC plug position in SC mount**: The SC plug (blue connector) is misaligned in the SC mount
- **LC plug position in LC mount**: Same issue
- **No fiber cables**: The yellow optical fiber cables (connecting SFP module to SC/LC plug) are not present

## Root Cause

The plug/module meshes (`sfp_module_visual`, `sc_plug_visual`, `lc_plug_visual`) come from the **cable assembly** in the sdf2mjcf conversion. Their coordinate origins are relative to the cable body hierarchy, NOT relative to the mount fixtures. When I nest them at `pos="0 0 0"` inside a mount body, they don't line up because the mesh origin is at an arbitrary point.

### What I Need

The **exact relative transform** (pos + quat) between:
- `sfp_mount_link` frame → `sfp_module_link` frame (how the SFP module sits in the mount)
- `sc_mount_link` frame → `sc_plug_link` frame (how the SC plug sits in the mount)
- `lc_mount_link` frame → `lc_plug_link` frame (how the LC plug sits in the mount)

These transforms are defined in the **URDF/XACRO** files or can be observed from a **running Gazebo instance**.

## Where to Find the Transforms

### Option A: Read the XACRO/URDF directly
```
~/projects/Project-Automaton/References/aic/aic_assets/models/SFP Mount/sfp_mount_macro.xacro
~/projects/Project-Automaton/References/aic/aic_assets/models/SC Mount/sc_mount_macro.xacro
~/projects/Project-Automaton/References/aic/aic_assets/models/LC Mount/lc_mount_macro.xacro
~/projects/Project-Automaton/References/aic/aic_assets/models/SFP Module/sfp_module_macro.xacro
~/projects/Project-Automaton/References/aic/aic_assets/models/SC Plug/sc_plug_macro.xacro
~/projects/Project-Automaton/References/aic/aic_assets/models/LC Plug/lc_plug_macro.xacro
```
Look for `<joint>` elements that define the parent→child transforms. The mount is the parent, the plug/module is the child.

### Option B: Read the SDF model files
```
~/projects/Project-Automaton/References/aic/aic_assets/models/SFP Mount/model.sdf
~/projects/Project-Automaton/References/aic/aic_assets/models/SC Mount/model.sdf
~/projects/Project-Automaton/References/aic/aic_assets/models/LC Mount/model.sdf
```
Look for `<link>` and `<joint>` elements with `<pose>` values.

### Option C: Spin up Gazebo and observe
Run the eval container with max components and use `gz model` or TF to read the actual transforms:
```bash
# In the eval container:
ros2 topic echo /tf_static --once
# Or:
gz model -m sc_mount_0 --pose
gz model -m sc_plug_0 --pose
```

### Option D: Read the cable model SDF
The cable models define how plugs connect to modules:
```
~/projects/Project-Automaton/References/aic/aic_assets/models/sfp_sc_cable/model.sdf
```
This has the full kinematic chain: `sfp_module_link` → cable_links → `sc_plug_link`

## Files Involved

### Randomizer Script
```
~/projects/Project-Automaton/Intrinsic-AI/tools/mujoco/randomize_board.py
```
The `make_mount_body()` function creates mount bodies and nests plug/module geoms inside. The geoms are placed at `pos="0 0 0"` which is wrong — they need the correct offset.

### MuJoCo Scene Files
```
~/projects/Project-Automaton/References/aic/aic_utils/aic_mujoco/mjcf/aic_world.xml      ← base world
~/projects/Project-Automaton/References/aic/aic_utils/aic_mujoco/mjcf/aic_world_rand.xml  ← randomized output
~/projects/Project-Automaton/References/aic/aic_utils/aic_mujoco/mjcf/scene_rand.xml      ← scene including randomized world
```

### Mesh Assets (all in mjcf/ directory)
- `manual_lc_mount.obj` — LC mount fixture (converted from GLB)
- `manual_sc_mount.obj` — SC mount fixture (converted from GLB)
- `manual_nic_card.obj` — NIC card (confirmed working)
- `manual_sc_port.obj` — SC port (confirmed working)
- SFP mount: uses converter meshes (`7ad515da...sfp_mount_visual_ISO_4762_-_M2_x_8.011*.obj`)
- SFP module: uses converter meshes (`1c33e96b...sfp_module_visual_Body.005*.obj`)
- SC plug: uses converter mesh (`3c8f1628...sc_plug_visual_merged_0*.obj`)
- LC plug: uses converter mesh (`b9fc682e...lc_plug_visual_merged_0*.obj`)

## What Was Already Tried

1. **Nesting at (0,0,0)** — plug meshes appear but at wrong position/orientation relative to mount
2. **Adjusting Z height** — tried z=0.01, 0.025, 0.012 for mount rails. z=0.012 seems closest.
3. **Using cable-end plug meshes directly on rails** — shows ferrules/cables sticking out (wrong mesh for static placement)
4. **Using actual mount OBJ meshes** — mounts look correct, but plugs inside are misaligned

## New Data: Mesh Bounding Boxes

All meshes have their long axis along mesh-Z (~50-60mm), but the XACRO uses X as the long axis. The GLB→OBJ conversion via trimesh rotated the coordinate frames.

```
SFP mount mesh:  X=[-0.009,0.009] Y=[-0.019,0.017] Z=[-0.029,0.021]  size=(0.018, 0.035, 0.050)
SFP module mesh: X=[-0.007,0.006] Y=[-0.007,0.007] Z=[-0.023,0.034]  size=(0.013, 0.015, 0.057)
SC mount mesh:   X=[-0.007,0.007] Y=[-0.018,0.017] Z=[-0.023,0.028]  size=(0.014, 0.035, 0.051)
SC plug mesh:    X=[-0.005,0.005] Y=[-0.013,0.013] Z=[-0.034,0.023]  size=(0.010, 0.025, 0.057)
LC mount mesh:   X=[-0.008,0.007] Y=[-0.012,0.014] Z=[-0.025,0.026]  size=(0.015, 0.026, 0.051)
LC plug mesh:    X=[-0.004,0.006] Y=[-0.006,0.006] Z=[-0.025,0.035]  size=(0.011, 0.012, 0.059)
```

## New Data: XACRO Collision Geometry (SFP Mount)

From `sfp_mount_macro.xacro`, the cradle platform collision is at:
- `x=0.033, y=0, z=0.0025` with size `(0.029, 0.018, 0.005)`
- V-cradle walls at `x≈0.02, z≈0.013` with -45° rotation about Y

But mesh bounding boxes show the long axis on mesh-Z (0.050) while XACRO has it on X (0.029-0.037). **The GLB→OBJ conversion has rotated the mesh axes.**

## Key Problem

The coordinate mapping between mesh space and XACRO space is unknown. The trimesh GLB→OBJ export may have:
1. Swapped axes (XACRO X → mesh Z?)
2. Applied a rotation from the GLB's scene transform
3. Flipped directions

## Test Scene Available

`aic_utils/aic_mujoco/mjcf/test_mounts.xml` has one of each mount+plug combo for quick iteration. Edit the `pos` and `quat` of each plug body to test offsets visually.

Run: `pixi run python3 -m mujoco.viewer --mjcf=aic_utils/aic_mujoco/mjcf/test_mounts.xml`

Press **Backspace** in the MuJoCo viewer to hot-reload after XML edits.

## Suggested Fix

**Option A (quick):** Open `test_mounts.xml` in one terminal, MuJoCo viewer in another. Manually adjust the `pos` and `quat` of each plug body, press Backspace to reload, until it looks right. Copy the working offsets into `randomize_board.py`.

**Option B (proper):** Load the GLB files in Blender, check the export orientation, and determine the axis mapping. Or: re-export the OBJ files from trimesh with a known rotation applied.

**Option C (definitive):** Run Gazebo with all mounts enabled, use `gz model --pose` to get the world positions of each mount+plug pair, compute the relative transform.

Once the relative transforms are known, update `make_mount_body()` in `randomize_board.py` to pass the correct `pos` and `quat` when creating nested plug geoms.
