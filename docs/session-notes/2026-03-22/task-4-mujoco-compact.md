# Task 4: MuJoCo Mirror Setup — Session Compact (2026-03-23)

> **Purpose:** Drop this into a new Claude Code chat to resume MuJoCo work exactly where we left off.
> **Read alongside:** `SESSION_HANDOFF.md` (full project context) and `Current-Plan.md` (100-hour plan)

---

## What This Project Is

**Project Automaton** — AIC (AI for Industry Challenge) competition. Training a UR5e robot to insert fiber optic cables (SFP, SC connectors) into a task board. Competition uses Gazebo for evaluation, but officially supports MuJoCo and Isaac Lab as training environments.

---

## What Task 4 Is

Setting up the **MuJoCo mirror environment** so policies can train/test in MuJoCo with the same ROS 2 interface as Gazebo. The AIC toolkit includes `aic_utils/aic_mujoco/` with official integration.

---

## What's Been Done (COMPLETED)

### Environment
- Full source build: 112 packages via `colcon` in `~/ws_aic/` (ROS 2 Kilted system install + mujoco_vendor + mujoco_ros2_control + gz-mujoco)
- MuJoCo scene converted from Gazebo SDF → MJCF via `sdf2mjcf` (patched to extract textures)
- Scene files at: `~/projects/Project-Automaton/References/aic/aic_utils/aic_mujoco/mjcf/`
- Generated mesh OBJs + texture PNGs stored there alongside the XML files
- Backup of conversion outputs at: `~/aic_mujoco_world/`

### What Works
- **MuJoCo viewer opens** with robot, task board base, cable, enclosure, glass walls, ceiling light
- **Full ROS 2 pipeline works:** Zenoh + mujoco_ros2_control + aic_controller + aic_adapter + aic_model
- **WaveArm policy runs in MuJoCo** — confirmed with observation logs and `Result: success=True`
- **Trigger script** (`Intrinsic-AI/tools/mujoco/trigger_policy.py`) bypasses `aic_engine` to run policies
- **Run script** (`Intrinsic-AI/tools/mujoco/run_mujoco.sh WaveArm`) launches everything with one command
- **Textures extracted** from GLB files (patched `sdf2mjcf` converter's `geometry.py` to not overwrite per-submesh materials)

### How to Run MuJoCo Pipeline
```bash
# One command (launches Zenoh + MuJoCo + policy + trigger):
bash ~/projects/Project-Automaton/Intrinsic-AI/tools/mujoco/run_mujoco.sh WaveArm

# Or manually (4 terminals):
# T1: source ~/ws_aic/install/setup.bash && export RMW_IMPLEMENTATION=rmw_zenoh_cpp && ros2 run rmw_zenoh_cpp rmw_zenohd
# T2: source ~/ws_aic/install/setup.bash && export RMW_IMPLEMENTATION=rmw_zenoh_cpp && ros2 launch aic_mujoco aic_mujoco_bringup.launch.py
# T3: source ~/ws_aic/install/setup.bash && export RMW_IMPLEMENTATION=rmw_zenoh_cpp && ros2 run aic_model aic_model --ros-args -p use_sim_time:=true -p policy:=aic_example_policies.ros.WaveArm
# T4: source ~/ws_aic/install/setup.bash && export RMW_IMPLEMENTATION=rmw_zenoh_cpp && export ZENOH_ROUTER_CHECK_ATTEMPTS=10 && python3 ~/projects/Project-Automaton/Intrinsic-AI/tools/mujoco/trigger_policy.py
```

---

## What's NOT Working (CURRENT BLOCKERS)

### 1. NIC Card / SC Port / SFP Components Not Visible on Task Board

**Root cause:** These components are dynamically spawned by `aic_engine` in Gazebo — they're NOT part of the static task board model. The engine reads `sample_config.yaml` and places NIC cards on rails, SC ports on rails, etc. The MuJoCo bringup doesn't have an engine, so they never appear.

**What we've tried:**
- Re-exported SDF from Gazebo with spawn flags (`nic_card_mount_0_present:=true` etc.) — only exports mount rails, not actual NIC cards
- The sdf2mjcf converter DID create mesh/material/texture/geom entries for NIC cards in `aic_world.xml` — but they don't render in the full scene
- Standalone test (`test_nic.xml`) with JUST the NIC card OBJ mesh DOES render correctly (green NIC card visible)
- Injected `manual_nic_card.obj` mesh into `aic_world.xml` inside the `nic_card_link` body — status unknown (hasn't been tested yet)
- Manually placed box geoms in `scene.xml` — didn't appear (likely worldbody conflict with includes)

**Key finding:** The OBJ mesh file works in isolation. The problem is in how it's assembled into the full scene. Most likely cause: the `aic_world.xml` has existing visual geoms for NIC card that reference the sdf2mjcf-converted meshes, but something (possibly the `class="world_default"` or asset partitioning by `add_cable_plugin.py`) prevents them from rendering.

**Files involved:**
- `manual_nic_card.obj` — NIC card mesh (33K vertices, converted from GLB, confirmed working standalone)
- `manual_sc_port.obj` — SC port mesh (33K vertices, needs scale 0.001 — GLB was in millimeters)
- `test_nic.xml` — Standalone test scene that proves the mesh renders
- `aic_world.xml` — Has injected `manual_nic_geom` inside `nic_card_link` body (UNTESTED)

**Next step to try:** Run the full scene after the injection and see if the green NIC card appears. If not, try removing `class="world_default"` from the NIC card geoms, or add the mesh reference directly inside scene.xml's worldbody (but after the includes, not before).

### 2. aic_engine Doesn't Work With MuJoCo

**Root cause:** `aic_engine` calls Gazebo-specific services (`ResetJoints`, model spawning) that MuJoCo doesn't provide.

**Workaround (WORKING):** `trigger_policy.py` bypasses the engine entirely:
1. Connects to `aic_model`'s lifecycle services
2. Transitions: unconfigured → configure → activate
3. Sends `InsertCable` action goal directly
4. Policy runs and returns result

**Known issue:** After a successful run, `aic_model` may enter `finalized` state (terminal). Must restart `aic_model` process between runs. Per GPT 5.4 Pro analysis, a normal successful goal should NOT finalize the node — something else may be triggering shutdown.

### 3. Camera Rate ~1Hz (Should Be 20Hz)

**Root cause:** `aic_adapter` requires all 3 camera image timestamps within 1ms of each other. MuJoCo cameras publish at ~5Hz by default, but sync issues collapse effective rate to ~1Hz.

**Fix (NOT YET APPLIED):** Raise `camera_publish_rate` parameter in MuJoCo ros2_control hardware config. Or bypass cameras for controller-only testing by publishing directly to `/aic_controller/pose_commands`.

### 4. Zenoh Timestamp Errors (COSMETIC — IGNORE)

Constant `ERROR zenoh::net::routing::dispatcher::pubsub: Error treating timestamp` spam. Does NOT affect functionality. Caused by WSL2 clock drift.

---

## Key File Locations

```
WSL2:
  ~/ws_aic/                                    ← Full source-built ROS 2 workspace (112 packages)
  ~/ws_aic/install/setup.bash                  ← Source this before any ros2 command
  ~/ws_aic/src/aic/                            ← Symlink to ~/projects/Project-Automaton/References/aic/
  ~/aic_mujoco_world/                          ← Backup of SDF→MJCF conversion outputs
  ~/projects/Project-Automaton/References/aic/aic_utils/aic_mujoco/mjcf/  ← Active MJCF scene files

Tools we wrote:
  ~/projects/Project-Automaton/Intrinsic-AI/tools/mujoco/
    trigger_policy.py     ← Bypass aic_engine, send InsertCable goals directly
    run_mujoco.sh         ← One-command full pipeline launcher
    mujoco_policies.py    ← Standalone MuJoCo viewer + basic PD control (no ROS 2)
    patch_mujoco_materials.py  ← Extract GLB colors → patch MJCF materials

Handoff docs:
  ~/projects/Project-Automaton/Intrinsic-AI/logs/2026-03-22/
    forum_post_mujoco_textures.md   ← Forum post about texture conversion issue
    forum_post_mujoco_engine.md     ← Forum post about aic_engine not working with MuJoCo
  ~/projects/Project-Automaton/Intrinsic-AI/logs/2026-03-23/
    handoff_gemini_mujoco_components.md  ← Detailed handoff for NIC card rendering issue
```

---

## Patches Applied to sdf2mjcf Converter

The `gz-mujoco` converter at `/tmp/gz-mujoco/` (cloned from `aic` branch) was patched:

**File:** `/tmp/gz-mujoco/sdformat_mjcf/src/sdformat_mjcf/sdformat_to_mjcf/converters/geometry.py`

**Change:** In `add_visual()` function (~line 334), changed unconditional SDF material override to fallback-only:
```python
# BEFORE: Always overwrites per-submesh materials
if vis.material() is not None:
    mjcf_mat = add_material(geom.root, vis.material())
    for geom in geoms:
        geom.material = mjcf_mat

# AFTER: Only uses SDF material as fallback
if vis.material() is not None:
    mjcf_mat = add_material(geom.root, vis.material())
    for geom in geoms:
        if getattr(geom, "material", None) is None:
            geom.material = mjcf_mat
```

This fix makes the converter extract textures from GLB files instead of always falling back to flat grey.

---

## GPT 5.4 Pro Advice (Key Points)

1. `aic_model` lifecycle: successful goal should NOT finalize — if it does, restart process
2. `mujoco_ros2_control` has `reset_world` service for between-trial resets
3. Camera bottleneck: `aic_adapter` needs 3 cameras within 1ms sync — raise `camera_publish_rate`
4. NIC card invisible: likely `add_cable_plugin.py` asset split issue, not MuJoCo group visibility
5. Direct `ros2 action send_goal` works after lifecycle configure+activate

---

## What To Do Next

1. **Test the NIC card injection** — run full scene, check if green NIC card appears on task board
2. **If NIC card still invisible** — try Approach 3 from handoff doc: remove `class="world_default"` from the geom, or add mesh directly to a new body in `aic_world.xml` worldbody (not inside existing body hierarchy)
3. **Fix camera rate** — add `camera_publish_rate` parameter
4. **Then move to Task 5 (Isaac Lab)** and **Task 6 (Dataset Logger)**
5. **CheatCode in MuJoCo** — once NIC card is visible and camera rate is fixed, CheatCode needs ground truth TF frames which MuJoCo doesn't publish. Either add a GT TF publisher node, or use the standalone `mujoco_policies.py` approach with direct body position access.

---

## Competition Timeline

- Qualification ends: ~May 27, 2026 (internal) / ~June 30 (public outer bound)
- Current date: March 23, 2026
- Hours spent: ~15-20 of 100-hour plan
- Key milestone not yet hit: **Non-GT policy that earns Tier 3 > 0 in Gazebo**
