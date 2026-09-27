# Session 5 Handoff — MuJoCo Mirror Setup (2026-03-23)

> **Purpose:** Drop this into a new Claude Code chat to resume exactly where we left off.
> **Read alongside:** `task-4-mujoco-compact.md` (earlier session state) and `HELP_REQUEST_mount_plug_alignment.md` (the blocker we're stuck on)

---

## What This Project Is

**Project Automaton** — AIC (AI for Industry Challenge) competition entry. A UR5e robot arm inserts fiber optic cables (SFP, SC, LC connectors) into a task board. Competition evaluates in Gazebo, but we're building parallel training environments in MuJoCo (this instance) and Isaac Lab (separate Claude Code instance).

**Three-lane model:**
- **Gazebo** — truth/evaluation (competition eval runs here)
- **MuJoCo** — controller training (this is what we're building)
- **Isaac Lab** — parallel RL/data generation (separate instance, also working)

**Qualification deadline:** ~May 27, 2026. Current date: March 23, 2026.

---

## What This Session Accomplished

### Major Wins (All Working)

1. **NIC card textures fixed** — The sdf2mjcf converter set textured material `rgba` to `(0,0,0,1)` which multiplied textures to black. Changed to `(1,1,1,1)` and now the green PCB NIC cards render with full textures. Also removed redundant `manual_nic_geom` (solid green overlay) since converter geoms now render properly.

2. **SC port materials fixed** — Textured SC port material rgba changed from near-black to `(1,1,1,1)`. Non-textured SC port submeshes set to blue `(0.15, 0.3, 0.7)`.

3. **Task board magenta reverted** — The `base_visual_ISO_4762_-_M3_x_8.019_2` material was originally magenta `rgba=(0.216, 0, 0.216)` in the conversion. A previous session's fix_colors.py had changed it to near-black. User confirmed magenta is correct — reverted it.

4. **Glass walls restored** — Wall materials changed from opaque grey `rgba=(0.263, 0.263, 0.263, 1.0)` to transparent `rgba=(0.85, 0.9, 0.95, 0.25)` with reflectance.

5. **SFP mount and NIC card mount materials brightened** — Near-black screw materials brightened to visible grey.

6. **LC and SC mount OBJs converted** — Converted `lc_mount_visual.glb` and `sc_mount_visual.glb` to OBJ via trimesh for use as mount fixtures.

7. **Randomized board generator** (`randomize_board.py`) — Full Python script that:
   - Reads `aic_world.xml` as base
   - Randomly populates NIC rails (1-5 cards), SC rails (1-2 ports), mount rails
   - Enforces correct rail→component mapping (lc_mount_rail→LC only, sfp_mount_rail→SFP only, sc_mount_rail→SC only)
   - Uses exact rail positions from `task_board.urdf.xacro`
   - Clones body hierarchies with renamed elements and stripped collision geoms
   - Outputs `aic_world_rand.xml`, viewable via `scene_rand.xml`
   - Zero yaw on all components (screwed to rails)

8. **aic_engine source code analysis** — Read `aic_engine.cpp` and confirmed: the engine only spawns the task board XACRO + cables. Plugs/modules are NOT separately spawned — they're cable endpoints that physically settle into mount cradles via gravity. No authoritative mount→plug transform exists anywhere.

9. **Handoff docs for Isaac Lab + Gemini/GPT** — Wrote detailed handoff documents sharing all findings with the Isaac Lab Claude instance and external AI help.

### The One Remaining Blocker

**Plug/module alignment inside mount fixtures (Zones 3-4).**

SFP modules, SC plugs, and LC plugs need to sit inside their V-shaped mount cradles. We cannot get the correct position + orientation because:

- **MuJoCo's OBJ importer scrambles mesh coordinate axes** in a data-dependent way
- Pre-rotating OBJ vertices doesn't work (MuJoCo re-applies its rotation)
- Correcting with geom `quat` doesn't work (different meshes get different scrambles)
- No authoritative mount→plug transform exists (Gazebo uses physics settling, not stored transforms)
- The mount XACROs don't define plug child links

**10 approaches tried and failed** — all documented in `HELP_REQUEST_mount_plug_alignment.md`.

**Status:** Handed off to Gemini Deep Think and GPT-5.4 Pro for help. User also installed Blender for manual GLB inspection. Suggested alternative approaches include: GLB→STL instead of OBJ, MuJoCo native primitives, checking MuJoCo source code, running Gazebo to observe.

---

## Current State of All Files

### MuJoCo Scene Files (WSL2)
```
~/projects/Project-Automaton/References/aic/aic_utils/aic_mujoco/mjcf/
  scene.xml              ← Top-level (includes robot + world)
  scene_rand.xml         ← Top-level (includes robot + randomized world)
  aic_robot.xml          ← Robot definition (UR5e + gripper + cameras)
  aic_world.xml          ← Base world (task board, enclosure, cable, lights) — EDITED THIS SESSION
  aic_world_rand.xml     ← Generated randomized layout (output of randomize_board.py)
  test_mounts.xml        ← Standalone test scene for mount+plug alignment debugging
  test_nic.xml           ← Standalone test proving NIC card mesh renders (confirmed working)
```

### OBJ Mesh Files Added This Session
```
~/projects/Project-Automaton/References/aic/aic_utils/aic_mujoco/mjcf/
  manual_lc_mount.obj          ← LC mount fixture (original export, no axis fix)
  manual_lc_mount_fixed.obj    ← LC mount (attempted axis fix — still has issues)
  manual_sc_mount.obj          ← SC mount fixture (original export)
  manual_sc_mount_fixed.obj    ← SC mount (attempted axis fix)
  manual_sfp_mount.obj         ← SFP mount fixture
  manual_sfp_module.obj        ← SFP transceiver module
  manual_sc_plug.obj           ← SC plug connector
  manual_lc_plug.obj           ← LC plug connector
  manual_nic_card.obj          ← NIC card (confirmed working from prior session)
  manual_sc_port.obj           ← SC port (confirmed working from prior session)
```

### Tools Written
```
~/projects/Project-Automaton/Intrinsic-AI/tools/mujoco/
  randomize_board.py      ← Board randomizer (NEW this session)
  trigger_policy.py       ← Bypass aic_engine for policy execution (prior session)
  run_mujoco.sh           ← One-command full pipeline launcher (prior session)
  mujoco_policies.py      ← Standalone MuJoCo viewer + PD control (prior session)
  patch_mujoco_materials.py ← Extract GLB colors → patch MJCF (prior session)
```

### Handoff/Help Documents
```
~/projects/Project-Automaton/Intrinsic-AI/logs/2026-03-23/
  HELP_REQUEST_mount_plug_alignment.md       ← DETAILED help request for Gemini/GPT (NEW)
  handoff_gemini_gpt_component_alignment.md  ← Earlier version of help request (NEW)
  handoff_isaac_lab_from_mujoco.md           ← Findings shared with Isaac Lab instance (NEW)
  handoff_gemini_mujoco_components.md        ← Earlier session's NIC card handoff
  handoff_component_placement.md             ← Initial component placement problem doc (NEW)
```

---

## Key Edits Made to aic_world.xml This Session

1. **Line 53-54**: NIC card textured materials `rgba` changed from `(0,0,0,1)` to `(1,1,1,1)`
2. **Line 55**: NIC card Plane.029 material brightened from `(0.02,0.08,0.02)` to `(0.08,0.35,0.12)`
3. **Line 56**: NIC card Cube.007 material brightened from `(0.03,0.03,0.03)` to `(0.15,0.15,0.15)`
4. **Line 45**: Task board `_8.019_2` material reverted to magenta `(0.216, 0, 0.216)`
5. **Lines 39-42**: Wall materials changed to transparent glass `rgba=(0.85,0.9,0.95,0.25)`
6. **Lines 48-50**: SC port materials fixed — textured one to `(1,1,1,1)`, others to blue
7. **Lines 46-47**: SFP mount screw materials brightened to `(0.18, 0.18, 0.18)`
8. **Line 90-93**: Added `manual_lc_mount`, `manual_sc_mount`, `nic_green`, `sc_blue`, `mount_grey`, `plug_blue` mesh/material assets
9. **Line 169**: Removed `manual_sc_geom` (converter SC port geoms now render)
10. **Line 189**: Removed `manual_nic_geom` (converter NIC card geoms now render with textures)
11. **Line 223**: Changed `debug_red` back to original NIC card material

---

## How to Run Things

### View base scene (non-randomized)
```bash
cd ~/projects/Project-Automaton/References/aic
~/.pixi/bin/pixi run python3 -m mujoco.viewer --mjcf=aic_utils/aic_mujoco/mjcf/scene.xml
```

### Generate + view randomized board
```bash
cd ~/projects/Project-Automaton/References/aic
~/.pixi/bin/pixi run python3 ~/projects/Project-Automaton/Intrinsic-AI/tools/mujoco/randomize_board.py --seed 42 --nic 3 --sc 2
~/.pixi/bin/pixi run python3 -m mujoco.viewer --mjcf=aic_utils/aic_mujoco/mjcf/scene_rand.xml
```

### Test mount+plug alignment (hot-reload with Backspace)
```bash
cd ~/projects/Project-Automaton/References/aic
~/.pixi/bin/pixi run python3 -m mujoco.viewer --mjcf=aic_utils/aic_mujoco/mjcf/test_mounts.xml
```

### Run full ROS 2 pipeline (WaveArm policy)
```bash
bash ~/projects/Project-Automaton/Intrinsic-AI/tools/mujoco/run_mujoco.sh WaveArm
```

---

## What To Do Next

### Priority 1: Resolve mount→plug alignment (BLOCKED)
Waiting on external help from Gemini/GPT-5.4. Most promising approaches:
- **Try STL format instead of OBJ** — STL has no axis convention, MuJoCo might not scramble axes
- **Use MuJoCo primitives** (boxes/cylinders) instead of mesh geoms for plugs — avoids import rotation entirely
- **Open GLBs in Blender** — manually align mount+plug, read transform, then figure out MuJoCo mapping
- **Check MuJoCo's mesh `refpos`/`refquat` attributes** — these offset the mesh in its own frame before any transform
- **Check if `content_type` attribute affects axis handling**

### Priority 2: Camera rate fix
Raise `camera_publish_rate` in MuJoCo ros2_control hardware config. Currently ~1Hz, needs to be 20Hz. The `aic_adapter` requires 3 camera image timestamps within 1ms sync.

### Priority 3: CheatCode policy in MuJoCo
Needs ground truth TF frames which MuJoCo doesn't publish. Either add a GT TF publisher node, or use standalone `mujoco_policies.py` with direct body position access.

### Priority 4: Dataset logger (Task 6 from 100-hour plan)
User explicitly said NOT to work on this until MuJoCo is fixed.

---

## Git Status
- Committed: `randomize_board.py` + `handoff_component_placement.md`
- NOT committed: All other changes to `aic_world.xml`, new OBJ files, new handoff docs
- Push to remote may be stuck (SSH auth issue in WSL2)
- Workaround: `wsl -e bash -c "cp <file> /mnt/c/..."` to copy files directly to Windows

---

## Key Technical Findings This Session

1. **MuJoCo OBJ import applies (Y,Z,X) axis permutation** — confirmed with controlled test. But rotation appears data-dependent for complex meshes.

2. **aic_engine only spawns task_board XACRO + cables** — plugs are cable endpoints, not separately placed. Mount→plug transform is physics-emergent, not stored anywhere.

3. **trimesh's `concatenate(scene.dump())` preserves GLB native coordinates** — the axis scramble happens in MuJoCo's loader, not in trimesh.

4. **Material rgba multiplies texture colors in MuJoCo** — `rgba=(0,0,0,1)` makes any texture invisible. Must be `(1,1,1,1)` for textures to show.

5. **MuJoCo `class="world_default"` is an empty default** — it does NOT hide geoms or set invisible properties. The rendering issues were purely material-related.

6. **Task board base has 3 visual geoms** — all named after ISO 4762 screws. The main board surface has no dedicated visual mesh (it's collision boxes only).
