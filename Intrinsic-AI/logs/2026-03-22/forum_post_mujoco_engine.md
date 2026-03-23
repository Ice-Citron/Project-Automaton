# MuJoCo Mirror: aic_engine fails with "ResetJoints service call timed out" — cannot run policies via trial orchestration

## Summary

After building the full AIC evaluation stack from source (112 packages, including `aic_engine`, `aic_controller`, `aic_adapter`, `mujoco_ros2_control`, `mujoco_vendor`), we cannot run ANY policy (WaveArm, CheatCode, etc.) through the MuJoCo mirror using `aic_engine`. The engine fails because it calls services that the MuJoCo bringup doesn't provide.

The MuJoCo README (`aic_utils/aic_mujoco/README.md`) states: *"Any of the policies in `aic_example_policies` can be used to control the robot in MuJoCo."* — but we cannot find any documented way to actually trigger policy execution without `aic_engine`, which doesn't work with MuJoCo.

## Environment

- Ubuntu 24.04 (WSL2, but this is NOT a WSL2-specific issue — the error is a missing ROS 2 service)
- ROS 2 Kilted (system-level `ros-kilted-desktop`)
- Full source build via `colcon` — 112 packages built successfully including:
  - `mujoco_vendor` (AIC branch)
  - `mujoco_ros2_control` (AIC branch)
  - `gz-mujoco` / `sdformat_mjcf` (AIC branch)
  - All `aic_*` packages (engine, controller, adapter, model, scoring, etc.)
- MuJoCo scene loads correctly (robot, task board, cable, actuators all work)
- `aic_mujoco_bringup.launch.py` starts successfully
- RTX 5090, CUDA 12.9

## What we tried

### Setup (4 terminals)

**Terminal 1 — Zenoh router:**
```bash
source ~/ws_aic/install/setup.bash
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
ros2 run rmw_zenoh_cpp rmw_zenohd
```

**Terminal 2 — MuJoCo sim:**
```bash
source ~/ws_aic/install/setup.bash
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
ros2 launch aic_mujoco aic_mujoco_bringup.launch.py
```

**Terminal 3 — Policy (WaveArm):**
```bash
source ~/ws_aic/install/setup.bash
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
ros2 run aic_model aic_model --ros-args -p use_sim_time:=true -p policy:=aic_example_policies.ros.WaveArm
```

**Terminal 4 — AIC Engine:**
```bash
source ~/ws_aic/install/setup.bash
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
ros2 run aic_engine aic_engine --ros-args -p use_sim_time:=true -p config_file_path:=$HOME/ws_aic/install/aic_engine/share/aic_engine/config/sample_config.yaml
```

### Result

All 4 processes start. The MuJoCo viewer opens correctly. The `aic_model` node loads WaveArm successfully (`Using policy: WaveArm`). Then `aic_engine` fails:

```
[ERROR] [aic_engine]: ResetJoints service call timed out requesting for reset!
[ERROR] [aic_engine]: Failed to home robot during simulator reset.
[INFO]  [aic_engine]: Reset after trial completed.
[ERROR] [aic_engine]: ╔════════════════════════════════════════╗
[ERROR] [aic_engine]: ║   ✗ Engine Stopped with Errors         ║
[ERROR] [aic_engine]: ╚════════════════════════════════════════╝

Complete Scoring Results:
total: 0
trial_1:
  tier_1:
    score: 0
    message: Model validation failed.
```

### What we verified is working

- All ROS 2 nodes are running: `aic_adapter_node`, `aic_controller`, `aic_model`, `mujoco_ros2_control_node`, `robot_state_publisher`, `rviz2`
- Topics are active: `/aic_controller/pose_commands`, `/aic_controller/joint_commands`, `/observations`, `/tf`, `/clock`
- Controller state publishes at ~100Hz
- Camera images publish at ~1Hz (slow, but present)
- Observations topic publishes at ~1Hz (bottlenecked by cameras)

### What's NOT working

1. **`ResetJoints` service** — `aic_engine` calls a service to reset robot joints before each trial. This service exists in the Gazebo bringup but NOT in the MuJoCo bringup. The call times out.

2. **Model spawning** — `aic_engine` dynamically spawns task board components (NIC cards, SC ports, cables) via Gazebo services. The MuJoCo scene has these as static geometry in the MJCF, but the engine doesn't know that.

3. **`insert_cable` action never triggered** — Because the engine fails during setup, it never sends the `InsertCable` action goal to `aic_model`. The policy's `insert_cable()` method is never called. WaveArm loads but sits idle forever.

### Without aic_engine

If we skip `aic_engine` entirely (only Terminals 1-3), the `aic_model` node loads the policy but then just waits indefinitely for an action goal that never comes. There is no documented way to trigger `insert_cable()` without the engine.

## What the nodes look like when running

```
$ ros2 node list
/aic_adapter_node
/aic_controller
/aic_model
/controller_manager
/fts_broadcaster
/joint_state_broadcaster
/mujoco_ros2_control_node
/robot_state_publisher
/rviz2
```

```
$ ros2 topic list
/aic_controller/joint_commands
/aic_controller/pose_commands
/aic_model/transition_event
/clock
/observations
/parameter_events
/rosout
/tf
/tf_static
```

## Services that aic_engine expects but MuJoCo doesn't provide

Based on the error, at minimum:
- `ResetJoints` service (resets robot to home position between trials)
- Likely also: model spawning services (Gazebo-specific for dynamic task board assembly)
- Possibly: ground truth TF frame publisher

## Questions

1. **How are policies supposed to be run in the MuJoCo mirror?** The README says "Any of the policies in `aic_example_policies` can be used to control the robot in MuJoCo" — but without `aic_engine`, there's no way to trigger the `insert_cable()` action. Is there a different launch file or workflow?

2. **Is `aic_engine` supposed to work with MuJoCo?** If so, what services need to be added to `aic_mujoco_bringup.launch.py` to satisfy the engine's requirements (ResetJoints, model spawning, etc.)?

3. **Is there a way to bypass `aic_engine` and directly trigger `insert_cable()` on `aic_model`?** For example, manually sending an action goal via CLI:
   ```bash
   ros2 action send_goal /aic_model/insert_cable aic_task_interfaces/action/InsertCable "{task: {cable_name: 'sfp_sc', plug_name: 'sfp_module', ...}}"
   ```

4. **Is the MuJoCo mirror primarily intended for teleoperation only?** If so, could the README be clarified? Currently it implies full policy compatibility.

5. **Camera rendering at ~1Hz** — Is this expected in MuJoCo? It bottlenecks `aic_adapter` (which synchronizes all inputs) and makes observation delivery very slow (~1Hz vs 20Hz in Gazebo). Is there a configuration to speed this up or disable cameras for controller-only testing?

## Relevant files

```
aic_utils/aic_mujoco/launch/aic_mujoco_bringup.launch.py  — MuJoCo launch (no engine, no spawning)
aic_bringup/launch/aic_gz_bringup.launch.py                — Gazebo launch (includes engine, spawning, GT TF)
aic_engine/config/sample_config.yaml                        — Trial configuration (3 trials)
aic_engine/src/aic_engine.cpp                               — Engine source (calls ResetJoints, spawning services)
```

## What we think the fix might be

Either:
- **Add MuJoCo-compatible versions of the services** that `aic_engine` expects (`ResetJoints` at minimum — set `data.qpos` to home position via a MuJoCo plugin/service)
- **Provide a `aic_mujoco_engine_bringup.launch.py`** that includes both the MuJoCo sim AND engine with appropriate service shims
- **Document the direct action call** to trigger policies without the engine
- **Provide a lightweight "mock engine"** that sends `InsertCable` goals without Gazebo-specific spawning

Thanks for any guidance. The MuJoCo physics mirror is working great — the task board, robot, cable, and controllers all function correctly. The only gap is the trial orchestration layer.
