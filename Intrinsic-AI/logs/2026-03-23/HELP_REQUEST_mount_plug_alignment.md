# URGENT HELP REQUEST: Mount ↔ Plug Alignment in MuJoCo Task Board

## TL;DR
We need to place SFP modules, SC plugs, and LC plugs **inside their mount fixtures** on a MuJoCo task board. We've tried 10+ approaches over several hours and nothing works. The core issue is that **MuJoCo's OBJ importer scrambles mesh coordinate axes in an unpredictable way**, making it impossible to compute correct relative transforms between mount and plug meshes. We need someone to either (a) figure out the correct pos/quat values, or (b) suggest a completely different approach to this problem.

---

## Project Context

### What Is This?
**Project Automaton** — an entry for the Intrinsic AI Challenge (AIC). A UR5e robot arm inserts fiber optic cables into a task board. The competition evaluates in Gazebo, but we're building a MuJoCo training environment as a parallel sim.

### What's the Task Board?
A physical board with 4 zones:
- **Zone 1** (top): Up to 5 NIC (Network Interface Card) cards on rails — **WORKING PERFECTLY**
- **Zone 2** (middle): Up to 2 SC (Subscriber Connector) optical ports — **WORKING PERFECTLY**
- **Zones 3-4** (bottom rows): Mount fixtures on 6 rails that hold cable endpoints (SFP modules, SC plugs, LC plugs) — **BROKEN, THIS IS THE PROBLEM**

### What Are the Mount Fixtures?
V-shaped metal cradles screwed to rails on the task board. Three types:
- **SFP mount** — holds an SFP transceiver module (a silver rectangular box, ~56mm long, plugs into NIC card SFP ports)
- **SC mount** — holds an SC fiber optic plug (a blue connector with fiber ferrules, ~57mm long)
- **LC mount** — holds an LC fiber optic plug (a smaller connector, ~59mm long)

Each mount type goes on its designated rail row:
- Row 1 (closest to board edge): `lc_mount_rail_0` and `lc_mount_rail_1` — LC mounts ONLY
- Row 2 (middle): `sfp_mount_rail_0` and `sfp_mount_rail_1` — SFP mounts ONLY
- Row 3 (furthest from edge): `sc_mount_rail_0` and `sc_mount_rail_1` — SC mounts ONLY

### Why Are the Plugs in Mounts?
In the actual competition, fiber optic cables have plugs on each end. When the cable isn't being manipulated by the robot, the plug endpoints rest in mount cradles on the task board. The robot picks up a cable from a mount, routes it, and inserts the plug into a port.

### How Does Gazebo Handle This?
In Gazebo, `aic_engine` (the trial orchestrator) spawns the task board XACRO with mount parameters, then spawns cables separately. The cable endpoints (which include the SFP module, SC plug, LC plug) are physics objects attached to the cable. They naturally fall into the mount cradles due to gravity. **The engine does NOT compute or store mount→plug transforms** — the plugs physically settle into the cradles.

This means there is NO authoritative source for the exact relative transform between a mount fixture and the plug that sits inside it. It's an emergent result of physics simulation.

---

## The Technical Problem

### What We're Trying to Do
Place static (non-physics) plug/module meshes inside mount fixture meshes in MuJoCo. Both meshes are loaded as OBJ files converted from GLB (GLTF Binary) format. We need the correct `pos` (position offset) and `quat` (orientation quaternion) for each plug geom relative to its parent mount body.

### Why It's Hard: MuJoCo's OBJ Axis Scramble

**MuJoCo rotates mesh vertices when importing OBJ files.** We confirmed this experimentally:

#### Controlled Test
1. Created a box with known dimensions: X=100mm (long), Y=20mm (short), Z=50mm (medium)
2. Wrote raw OBJ file with explicit vertex `v 0.1 0.0 0.0` (100mm along X)
3. Loaded in MuJoCo via `<mesh file="test.obj"/>`
4. Read back vertex data from `MjModel.mesh_vert`

**Result:** MuJoCo reported the box as X=20mm, Y=50mm, Z=100mm. The axes were cyclically permuted.

**Vertex-level confirmation:**
- File vertex (centered): `(0.05, -0.01, -0.025)` → MuJoCo vertex: `(-0.01, -0.025, 0.05)`
- Mapping: `MuJoCo(X,Y,Z) = file(Y, Z, X)`

#### Why Pre-Rotation Doesn't Work
We tried pre-rotating OBJ vertices before export so MuJoCo's rotation would undo itself:
- Applied `(x,y,z) → (z,x,y)` to all vertices before writing OBJ
- Expected MuJoCo's `(Y,Z,X)` to give back the original

**Result:** MuJoCo still showed the WRONG axis assignment. The pre-rotated file had sizes `(0.05, 0.10, 0.02)` and MuJoCo showed `(0.02, 0.05, 0.10)` — which is `(Y,Z,X)` of the ORIGINAL, as if the pre-rotation never happened.

**Hypothesis:** MuJoCo's rotation may be data-dependent (possibly related to mesh inertia computation, convex hull analysis, or vertex ordering), not a fixed transform on file coordinates. Different meshes may get different rotations.

#### Why Geom Quat Doesn't Work
We tried applying correcting quaternions on the geom element in MJCF:
- `quat="0.5 0.5 0.5 0.5"` (120° around (1,1,1)/√3 — the inverse of a cyclic permutation)
- `quat="0.707 0 0.707 0"` (90° around Y)
- `quat="0.707 0 -0.707 0"` (-90° around Y)

**Result:** Each made things worse in different ways. Mounts went flat, plugs pitched 90°, components scattered. The quat correction assumes a known, fixed rotation to undo, but MuJoCo's rotation isn't consistent across meshes.

---

## All Source Files and Their Locations

### GLB Visual Models (Original CAD, Known Good Geometry)
```
Base path: ~/projects/Project-Automaton/References/aic/aic_assets/models/

SFP Mount/sfp_mount_visual.glb       — Grey V-cradle fixture (51×18×36mm, long axis X)
SFP Module/sfp_module_visual.glb     — Silver SFP transceiver (15×56×12mm, long axis Y)
SC Mount/sc_mount_visual.glb         — Grey V-cradle fixture (51×14×32mm, long axis X)
SC Plug/sc_plug_visual.glb           — Blue SC connector (57×25×10mm, long axis X)
LC Mount/lc_mount_visual.glb         — Grey V-cradle fixture (51×15×25mm, long axis X)
LC Plug/lc_plug_visual.glb           — LC connector (12×59×11mm, long axis Y)
```

### OBJ Mesh Files (Converted from GLB via trimesh, in MuJoCo mjcf/ directory)
```
Base path: ~/projects/Project-Automaton/References/aic/aic_utils/aic_mujoco/mjcf/

manual_sfp_mount.obj      — SFP mount (multiple export attempts, axis varies)
manual_sfp_module.obj     — SFP module
manual_sc_mount_fixed.obj — SC mount
manual_sc_plug.obj        — SC plug
manual_lc_mount_fixed.obj — LC mount
manual_lc_plug.obj        — LC plug
```

### XACRO Files (Define mount collision geometry)
```
aic_assets/models/SFP Mount/sfp_mount_macro.xacro
aic_assets/models/SC Mount/sc_mount_macro.xacro
aic_assets/models/LC Mount/lc_mount_macro.xacro
```

### MuJoCo Test Scene (For Quick Iteration)
```
aic_utils/aic_mujoco/mjcf/test_mounts.xml
```
View with: `pixi run python3 -m mujoco.viewer --mjcf=aic_utils/aic_mujoco/mjcf/test_mounts.xml`
Press **Backspace** in viewer to hot-reload after XML edits.

### Engine Source (Confirms plugs are cable endpoints, not separately spawned)
```
aic_engine/src/aic_engine.cpp — Lines 1170-1248 show only task_board + cables are spawned
```

---

## Detailed Measurements

### GLB Bounding Boxes (Native Frame = XACRO/ROS Frame, Z-up)
```
Component        Bounds Min               Bounds Max               Size (mm)         Long Axis   Center
─────────────────────────────────────────────────────────────────────────────────────────────────────────
SFP Mount:       (−3, −9, −5)             (48, 9, 31)              (51, 18, 36)      X           (22.5, 0, 12.8)
SFP Module:      (−7, −24, −6)            (7, 33, 6)               (15, 56, 12)      Y           (0, 4.6, 0.1)
SC Mount:        (−3, −7, −5)             (48, 7, 27)              (51, 14, 32)      X           (22.5, 0, 10.9)
SC Plug:         (−46, −13, −5)           (12, 13, 5)              (57, 25, 10)      X           (−17.1, 0, 0)
LC Mount:        (−3, −7, −5)             (48, 7, 20)              (51, 15, 25)      X           (22.5, 0, 7.5)
LC Plug:         (−6, −38, −3)            (6, 21, 7)               (12, 59, 11)      Y           (0, −8.5, 1.9)
```

### MuJoCo Bounding Boxes (After OBJ Import — Axes Scrambled)
These were measured from `MjModel.mesh_vert` after MuJoCo loaded the OBJ files:
```
Component        Size in MuJoCo (mm)      Long Axis in MuJoCo
──────────────────────────────────────────────────────────────
SFP mount:       (18, 39, 50)             Z
SFP module:      (12, 15, 57)             Z
SC mount:        (14, 32, 51)             Z
SC plug:         (25, 10, 57)             Z
LC mount:        (15, 26, 51)             Z
LC plug:         (11, 12, 59)             Z
```

Note: ALL meshes end up with their long axis on MuJoCo Z after import. But the OTHER two axes are scrambled differently per mesh (compare SFP mount 18,39 vs SFP module 12,15 — the non-long axes have different orderings relative to the GLB frame).

### Mount Collision Geometry (From XACRO, All in Mount Link Frame)

**SFP Mount — 8 collision boxes forming V-cradle:**
```
1. Platform:    pos=(33.3, 0, 2.5)mm     size=(29.5, 17.8, 5.0)mm    rpy=(0, 0, 0)
2. V-wall:      pos=(16.4, 0, 17.1)mm    size=(38.5, 17.8, 1.7)mm    rpy=(0, −45°, 0)
3. V-wall:      pos=(28.6, 0, 12.7)mm    size=(27.5, 17.8, 3.7)mm    rpy=(0, −45°, 0)
4. V-wall left:  pos=(21.2, 7.7, 14.0)mm  size=(36.1, 2.3, 11.0)mm   rpy=(0, −45°, 0)
5. V-wall right: pos=(21.0, −7.9, 14.2)mm size=(36.1, 1.9, 11.6)mm   rpy=(0, −45°, 0)
6. Base angle:  pos=(10.0, 0, 3.2)mm     size=(5.1, 17.8, 11.6)mm    rpy=(0, −45°, 0)
7. Base flat:   pos=(4.2, 0, 2.5)mm      size=(14.4, 17.8, 5.0)mm    rpy=(0, 0, 0)
8. Back wall:   pos=(36.6, 0, 11.8)mm    size=(4.9, 17.8, 16.8)mm    rpy=(0, 0, 0)
```
**Cradle center (where plug should rest): approximately (X=22, Y=0, Z=8-10)mm in XACRO frame.**

**SC Mount — 9 collision boxes forming V-cradle:**
```
1. Platform:    pos=(39.0, 0, 2.5)mm     size=(17.7, 14.0, 5.0)mm    rpy=(0, 0, 0)
2. V-wall left:  pos=(22.6, −5.4, 13.5)mm size=(25.8, 3.2, 13.8)mm   rpy=(0, +45°, 0)
3. V-wall right: pos=(22.6, 5.9, 13.5)mm  size=(25.8, 2.3, 13.8)mm   rpy=(0, +45°, 0)
4. Cradle tip:  pos=(14.2, 0, 21.9)mm    size=(2.0, 14.0, 13.8)mm    rpy=(0, +45°, 0)
5. Cradle base: pos=(31.1, 0, 5.0)mm     size=(1.8, 14.0, 13.8)mm    rpy=(0, +45°, 0)
6. Base flat:   pos=(9.5, 0, 2.5)mm      size=(25.0, 14.0, 5.0)mm    rpy=(0, 0, 0)
7. Cradle mid:  pos=(17.8, 0, 8.7)mm     size=(25.8, 14.0, 1.2)mm    rpy=(0, +45°, 0)
8. Back wall:   pos=(35.4, 0, 4.6)mm     size=(2.2, 14.0, 9.2)mm     rpy=(0, 0, 0)
9. Front wall:  pos=(9.5, 0, 8.7)mm      size=(2.1, 14.0, 17.4)mm    rpy=(0, 0, 0)
```
**Cradle center: approximately (X=22-25, Y=0, Z=8-10)mm.**

**LC Mount — 8 collision boxes forming V-cradle:**
```
1. Platform:    pos=(39.5, 0, 2.5)mm     size=(17.0, 6.0, 5.0)mm     rpy=(0, 0, 0)
2. Base flat:   pos=(6.3, 0, 2.5)mm      size=(18.6, 6.0, 5.0)mm     rpy=(0, 0, 0)
3. V-wall:      pos=(16.9, 0, 14.2)mm    size=(14.3, 14.8, 3.1)mm    rpy=(0, −45°, 0)
4. V-wall:      pos=(29.2, 0, 3.4)mm     size=(12.1, 14.8, 8.0)mm    rpy=(0, −45°, 0)
5. V-wall:      pos=(13.5, 0, 3.1)mm     size=(6.3, 14.8, 13.8)mm    rpy=(0, −45°, 0)
6. V-wall left:  pos=(22.2, 5.8, 8.8)mm   size=(14.3, 3.3, 15.6)mm   rpy=(0, −45°, 0)
7. V-wall right: pos=(22.3, −4.5, 8.8)mm  size=(14.3, 5.7, 15.3)mm   rpy=(0, −45°, 0)
8. Back:        pos=(32.7, 0, 10.2)mm    size=(9.0, 6.5, 1.8)mm      rpy=(0, −45°, 0)
```
**Cradle center: approximately (X=20-22, Y=0, Z=5-8)mm.**

### Cable Assembly Kinematic Chain (from sfp_sc_cable/model.sdf)
Shows how plugs connect in the cable, NOT how they sit in mounts:
```
cable_connection_0 (cable start)
  → lc_plug_link:       pos=(−41, 0, 0)mm,  rpy=(0, 0, 90°)
    → sfp_module_link:  pos=(0, 38.4, 0)mm, rpy=(0, 180°, 180°)
      → sfp_tip_link:   pos=(0, −23.7, 0)mm, rpy=(90°, 0, 0)

cable_connection_1 (cable end)
  → sc_plug_link:       pos=(52, 0, 0)mm,   rpy=(0, 0, 0)
    → sc_tip_link:      pos=(11.7, 0, 0)mm, rpy=(−90°, 0, −90°)
```

---

## Complete List of Failed Attempts (With Screenshots/Results)

### Attempt 1: Plug at mount origin (0,0,0), no rotation
- **What:** `<geom type="mesh" mesh="sfp_mod" pos="0 0 0"/>` inside mount body
- **Result:** Plug appeared but completely offset from cradle, wrong orientation. Plug mesh origin is NOT at the cradle center.

### Attempt 2: Various Z offsets for mount bodies
- **What:** Tried Z=0.01, 0.012, 0.015, 0.02, 0.025 for mount body position relative to task board
- **Result:** Could get mounts at correct height on board, but plug-inside-mount alignment unchanged. This only adjusts mount-to-board, not plug-to-mount.

### Attempt 3: Cable-end plug meshes directly on rails (no mounts)
- **What:** Placed converter's plug meshes (sfp_module_visual, sc_plug_visual, lc_plug_visual) directly on mount rail positions
- **Result:** Plugs showed cable ferrules/strain-relief sticking out. Wrong visual for a static board display. Also still misoriented.

### Attempt 4: Converted mount GLBs → OBJ via trimesh
- **What:** Used `trimesh.load(glb) → concatenate(scene.dump()) → export(obj)` for LC mount and SC mount
- **Result:** Mount fixtures rendered correctly on the task board! This was a breakthrough for the mounts themselves. But plugs inside mounts were still wrong.

### Attempt 5: Nested plug meshes inside mount bodies
- **What:** Added converter plug meshes as child geoms of mount bodies, at mount center offset `pos="0.02 0 0.005"`
- **Result:** Plugs appeared but at wrong position and orientation. The converter meshes have their own coordinate origins that don't align with the mount frame.

### Attempt 6: Pre-rotate OBJ vertices to compensate for MuJoCo axis swap
- **What:** Identified MuJoCo's `(Y,Z,X)` permutation. Applied inverse `(x,y,z)→(z,x,y)` to trimesh vertices before OBJ export using `new_verts = mesh.vertices @ M` with rotation matrix.
- **Result:** FAILED. MuJoCo showed the same axis ordering regardless. Tried two different rotation matrices (`[[0,1,0],[0,0,1],[1,0,0]]` and `[[0,0,1],[1,0,0],[0,1,0]]`). Neither worked. Even tested with raw OBJ (bypassing trimesh) — same result. MuJoCo's rotation appears to happen AFTER any vertex transform, not on raw file data.

### Attempt 7: Apply correcting quat on mesh geoms
- **What:** Added `quat="0.5 0.5 0.5 0.5"` (120° around (1,1,1)/√3) to every mesh geom to undo the cyclic permutation.
- **Result:** FAILED. Mounts lay flat on the board. Plugs pitched 90° forward. Components completely misaligned. Screenshot shows mounts and plugs separated and at wrong angles.

### Attempt 8: Read XACRO/SDF for mount→plug transforms
- **What:** Read all mount XACROs, plug SDFs, cable SDF. Extracted every joint, link, and pose.
- **Result:** Mount XACROs only define fixture geometry (no child links for plugs). Cable SDF gives plug-to-cable transforms, not plug-to-mount transforms. Engine source (`aic_engine.cpp`) confirms plugs are NOT separately spawned — they're cable endpoints that physically fall into cradles.

### Attempt 9: Compute offsets in MuJoCo's scrambled frame
- **What:** Since both mount and plug go through the same MuJoCo axis scramble, computed offset in scrambled frame: XACRO `(x,y,z)` → MuJoCo `(y,z,x)`. Applied `pos="0 0.008 0.022"` and `quat="0.707 0 0.707 0"` (90° around MuJoCo Y for plug rotation).
- **Result:** FAILED BADLY. Plugs and mounts completely scattered, wrong orientations, worst result yet. The screenshot shows components wildly separated with red collision wireframes. The "same scramble" assumption was wrong — different meshes get different scrambles.

### Attempt 10: Re-export OBJs with corrected axes
- **What:** Re-exported all GLBs to OBJ with pre-rotation matrix applied to create new Trimesh objects: `new_mesh = trimesh.Trimesh(vertices=new_verts, faces=mesh.faces)`.
- **Result:** The exported OBJ files had correct sizes in trimesh (matching GLB), but MuJoCo still loaded them with scrambled axes. The rotation survives the new mesh creation but MuJoCo still applies its own.

---

## What We Think Is Happening

MuJoCo's OBJ mesh loader does NOT simply read vertices as-is. It appears to perform one or more of:
1. **Y-up to Z-up conversion** — OBJ format traditionally uses Y-up, MuJoCo uses Z-up
2. **Mesh reorientation based on geometry** — possibly aligning principal axes of inertia with coordinate axes
3. **Data-dependent rotation** — different meshes get different rotations based on their shape

Evidence for data-dependent rotation: the SAME pre-rotation matrix applied to different meshes produces DIFFERENT axis orderings in MuJoCo. A simple box gets a clean `(Y,Z,X)` permutation, but complex meshes get something else.

---

## Suggested Approaches (For External Help)

### Approach A: Open GLBs in Blender (MOST RELIABLE)
1. Install Blender (user has it installed)
2. File → Import → glTF: import `sfp_mount_visual.glb`
3. File → Import → glTF: import `sfp_module_visual.glb` into same scene
4. Manually position and rotate the SFP module so it sits in the mount's V-cradle
5. Read the transform from Blender's properties panel (N key)
6. These are the VALUES IN THE GLB/XACRO FRAME
7. Then we need to figure out how to translate those values into MuJoCo-compatible pos/quat (accounting for the axis scramble)

### Approach B: Use MuJoCo's Native Primitives Instead of Meshes
Instead of fighting with OBJ mesh axes, create the plugs/modules from MuJoCo's native primitive shapes (boxes, cylinders) at the correct positions. This avoids the mesh import rotation entirely. The plugs won't look as realistic but will be positioned correctly.

### Approach C: Use `content_type="model/obj"` with Explicit Orientation
Some MuJoCo mesh loading behaviors depend on the `content_type` attribute. Try adding `content_type="model/obj"` or removing it to see if it changes the axis handling. Also try the `refpos` and `refquat` mesh attributes which offset the mesh in its own frame.

### Approach D: Convert GLB → STL Instead of OBJ
STL format has no axis convention (it's just triangles). MuJoCo might handle STL differently from OBJ. Try exporting from trimesh as `.stl` instead of `.obj` and see if the axis scramble goes away.

### Approach E: Run Gazebo and Observe
Spin up the AIC eval Docker container with all components, let cables settle into mount cradles, then read the final poses:
```bash
# In eval container:
gz model -m sfp_mount_0 --pose
gz model -m cable_0 --pose
# Compute relative transforms from poses
```

### Approach F: Check MuJoCo Source Code
Look at MuJoCo's OBJ/mesh loading code to understand exactly what rotation it applies. The source is at https://github.com/google-deepmind/mujoco. Relevant files would be in `src/engine/` or `src/xml/` — search for OBJ parsing and mesh processing.

---

## Environment
- WSL2 Ubuntu 24.04, ROS 2 Kilted
- MuJoCo 3.5.0 via pixi (Python 3.12)
- trimesh for GLB→OBJ conversion
- Blender installed on Windows (available for manual inspection)
- All work in: `~/projects/Project-Automaton/References/aic/aic_utils/aic_mujoco/mjcf/`
- Test scene: `test_mounts.xml` (press Backspace in viewer to hot-reload)

## Quick Commands
```bash
# View test scene:
cd ~/projects/Project-Automaton/References/aic
pixi run python3 -m mujoco.viewer --mjcf=aic_utils/aic_mujoco/mjcf/test_mounts.xml

# View full randomized board:
pixi run python3 ~/projects/Project-Automaton/Intrinsic-AI/tools/mujoco/randomize_board.py --seed 42 --nic 3 --sc 2
pixi run python3 -m mujoco.viewer --mjcf=aic_utils/aic_mujoco/mjcf/scene_rand.xml

# View base (non-randomized) scene:
pixi run python3 -m mujoco.viewer --mjcf=aic_utils/aic_mujoco/mjcf/scene.xml
```

## Competition Deadline
Qualification: ~May 27, 2026. Current date: March 23, 2026. This blocker is holding up the MuJoCo training pipeline.
