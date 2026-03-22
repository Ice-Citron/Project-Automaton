# AWS Setup — SDF, Scripts, Tools, ROS Nodes & IPC
**Date:** 22 March 2026
**Author:** Evan
**Topic:** AWS cloud dev environment — everything explained

---

## Overall Goal

The 4 scripts set up a **cloud Ubuntu instance** (AWS) so you can develop and test AIC policies without your local Windows machine. The pipeline:

```
AWS Ubuntu (L4 GPU)
├── Nice DCV          → remote desktop (enable_dcv.sh)
├── Claude Code       → AI coding assistant in terminal (set_up_dev_tools.sh)
└── Three sim lanes   → (setup_sim_environments.sh + install_and_run_aic.sh)
    ├── Lane 1: Gazebo/Kilted (truth, scoring)
    ├── Lane 2: MuJoCo (fast controller tuning)
    └── Lane 3: Isaac Lab (RL training)
```

---

## The 4 Scripts

### `enable_dcv.sh` — Remote Desktop
Sets up **Nice DCV** (AWS's remote desktop protocol, like RDP but GPU-accelerated):
1. Installs `ubuntu-desktop` (full GNOME GUI)
2. Downloads/installs Nice DCV server + web viewer
3. Starts `dcvserver` as a systemd service
4. You connect via browser or DCV client to get a full desktop with GPU acceleration — this is how you see Gazebo's 3D viewer from your Windows machine

### `set_up_dev_tools.sh` — Claude Code
Installs Node.js → npm → `@anthropic-ai/claude-code`. Minimal utility script.

### `install_and_run_aic.sh` — Repo Bootstrap
```bash
git clone https://github.com/Ice-Citron/Project-Automaton
git submodule update --init --recursive
```
Pulls down the repo including the `aic` reference submodule. Nothing else — just the entry point.

### `setup_sim_environments.sh` — The Main Script
~570 lines. Five phases:

| Phase | What |
|-------|------|
| 1a | APT packages (gcc-14, distrobox, tmux…) |
| 1b | NVIDIA Container Toolkit (GPU access in Docker) |
| 1c | Pixi (conda-like env manager) |
| 1d | `~/ws_aic` workspace + `pixi install` |
| 1e | `aic_eval` distrobox container (Gazebo lane) |
| 1f | ROS 2 Kilted host install + sdformat bindings |
| 1g | MuJoCo colcon build |
| 1h | IsaacLab Docker clone + build |
| 1i | Shell aliases |
| Phase 2 | **Test**: Gazebo + CheatCode (checks `scoring.yaml`) |
| Phase 3 | SDF export → MJCF conversion |
| Phase 4 | **Test**: MuJoCo + CheatCode |
| Phase 5 | **Test**: Isaac Lab `list_envs` smoke test |

---

## What Is an SDF?

**SDF = Simulation Description Format** — XML file that fully describes a robot simulation world. It's the native format for Gazebo.

```xml
<sdf version="1.9">
  <world name="aic_world">
    <model name="ur5e">
      <link name="base_link">
        <visual>
          <geometry>
            <mesh><uri>model://ur5e/base.dae</uri></mesh>
          </geometry>
        </visual>
        <collision>
          <geometry><box><size>0.1 0.1 0.1</size></box></geometry>
        </collision>
        <inertial>
          <mass>4.0</mass>
          <inertia>...</inertia>
        </inertial>
      </link>
      <joint name="shoulder_joint" type="revolute">
        <parent>base_link</parent>
        <child>shoulder_link</child>
        <axis><xyz>0 0 1</xyz></axis>
        <limit><lower>-6.28</lower><upper>6.28</upper></limit>
      </joint>
    </model>
    <model name="task_board">...</model>
    <light name="sun" type="directional">...</light>
    <physics type="ode">
      <max_step_size>0.001</max_step_size>
    </physics>
  </world>
</sdf>
```

**Key SDF concepts:**
- `<model>` — a robot or object (UR5e arm, task board, cable)
- `<link>` — a rigid body with visual + collision + inertial
- `<joint>` — connects two links (revolute = rotates, fixed = rigid, prismatic = slides)
- `<visual>` — mesh for rendering (GLB, DAE, STL)
- `<collision>` — simplified shape for physics
- `<plugin>` — C++ shared library that adds behavior (ros2_control, sensors)
- `<sensor>` — cameras, IMU, force-torque
- `model://` URI scheme — looks up models in `GZ_SIM_RESOURCE_PATH`

**In this project**, Gazebo exports the live scene as `/tmp/aic.sdf` which is then converted to MJCF (MuJoCo's XML format) for the MuJoCo lane. The URI corruption bugs the script fixes (`<urdf-string>`, broken `file:///` paths) happen because Gazebo's SDF exporter writes Docker-internal paths and malformed URIs that need to be rewritten for host use.

---

## Distrobox

Distrobox is a wrapper around Docker/Podman that makes containers feel like native Linux. Key difference from raw Docker: **your home directory, X11 display, GPU, and network are all shared** with the host automatically.

```
Host Ubuntu (AWS)
└── distrobox aic_eval
    └── Docker: ghcr.io/intrinsic-dev/aic/aic_eval:latest
        ├── ROS 2 Kilted (pre-installed)
        ├── Gazebo Harmonic (pre-installed)
        ├── aic packages (pre-built)
        └── /entrypoint.sh  ← starts everything
```

**Why distrobox instead of raw Docker?**
- Container sees `$HOME` on host → `scoring.yaml` written inside container appears on host at `~/aic_results/`
- `$DISPLAY` is shared → Gazebo's OpenGL window appears on your DCV desktop
- `--nvidia` flag passes GPU through to Gazebo for rendering
- No volume mount headaches

**Why the eval image?** The organizers pre-baked the exact Kilted + Gazebo + AIC packages into `ghcr.io/intrinsic-dev/aic/aic_eval:latest`. This is the **identical** environment used on the competition scoring server. Running your policy against it gives you ground truth on your score.

---

## GCC 14

The script does:
```bash
sudo apt-get install -y g++-14 gcc-14
export CC=/usr/bin/gcc-14 CXX=/usr/bin/g++-14
colcon build --cmake-args -DCMAKE_CXX_COMPILER=/usr/bin/g++-14 ...
```

**Why GCC 14 specifically?**

`aic_adapter` uses **C++20 `<format>`** — the `std::format()` library (like Python f-strings but typed):
```cpp
#include <format>
std::string msg = std::format("Joint {} position: {:.3f}", name, value);
```

- Ubuntu 22.04's default GCC is **11** — no `<format>`
- Ubuntu 24.04 ships GCC 13 — partial support
- GCC 14 = full C++20 + C++23 support including `<format>`

Without it you get:
```
fatal error: format: No such file or directory
```
or:
```
error: 'std::format' was not declared in this scope
```

Ubuntu's toolchain PPAs let you install multiple GCC versions side by side. The `CC`/`CXX` env vars + CMake flags tell the build system to use 14 specifically without changing the system default.

---

## `ws_aic` — The Workspace

`~/ws_aic` is a **colcon workspace** (ROS 2's build system workspace). Structure:

```
~/ws_aic/
├── src/
│   ├── aic/               ← symlink to your repo's References/aic
│   │   ├── aic_model/     ← ROS package: runs policies
│   │   ├── aic_adapter/   ← ROS package: bridges sim ↔ policy
│   │   ├── aic_controller/← ROS package: ros2_control interface
│   │   ├── aic_mujoco/    ← ROS package: MuJoCo bringup
│   │   └── aic_utils/     ← MuJoCo repos, Isaac utils
│   ├── mujoco_vendor/     ← imported by vcs from mujoco.repos
│   ├── mujoco_ros2_control/
│   └── sdformat_mjcf/     ← SDF→MJCF converter (Python package)
├── build/                 ← CMake build artifacts
├── install/               ← merged install tree (--merge-install)
│   ├── setup.bash         ← sources all packages into shell
│   ├── lib/               ← executables, shared libs
│   └── share/             ← URDF, meshes, launch files, params
└── log/                   ← colcon build logs
```

`source ~/ws_aic/install/setup.bash` is the critical step that makes all ROS packages findable. Without it, `ros2 run aic_model aic_model` fails with "package not found".

---

## ROS 2 Kilted

**ROS 2** (Robot Operating System 2) is a middleware framework. It's not really an OS — it's a publish/subscribe message bus + package ecosystem + build system.

**Kilted** is the distro codename (like Ubuntu's "Noble"). The competition requires **Kilted** specifically because that's what the eval server runs.

**Core ROS 2 concepts used here:**

| Concept | What |
|---------|------|
| Node | A process that communicates via ROS |
| Topic | Named pub/sub channel (like a Kafka topic) |
| Service | Request/response RPC |
| Action | Long-running goal with feedback |
| Parameter | Named config value per-node |
| Package | Unit of distribution (CMake or Python) |
| Launch file | Python script that starts multiple nodes with config |
| RMW | "ROS Middleware" — the DDS transport layer underneath |

---

## CMake + colcon

**CMake** is the build system generator. For each ROS C++ package it:
1. Reads `CMakeLists.txt`
2. Finds dependencies (`find_package(rclcpp REQUIRED)`)
3. Generates Makefiles / Ninja files
4. Invokes the compiler

**colcon** is a meta-build tool that orchestrates CMake across many packages:
```bash
colcon build \
    --cmake-args -DCMAKE_BUILD_TYPE=Release \   # optimization level
                 -DCMAKE_CXX_COMPILER=/usr/bin/g++-14 \
    --merge-install \    # all outputs go to one install/ tree
    --symlink-install \  # Python files: symlink not copy (instant changes)
    --packages-ignore lerobot_robot_aic aic_gazebo aic_scoring aic_engine
#   ^^^^ skip these — they only exist inside the distrobox container
```

**Build types:**
- `Debug` — no optimization, full symbols, 5-10x slower
- `Release` — `-O3`, stripped, what you use for sim

**Common colcon errors:**

| Error | Cause | Fix |
|-------|-------|-----|
| `Could not find package: rclcpp` | ROS not sourced | `source /opt/ros/kilted/setup.bash` first |
| `fatal error: format: No such file or directory` | GCC < 14 | Set `CC/CXX` to gcc-14/g++-14 |
| `README.md: No such file or directory` | sdformat_mjcf out-of-tree build | Script's `ln -sf` workaround |
| `vcstool: command not found` | Ubuntu's `vcstool` conflicts | Script removes Ubuntu's, installs `python3-vcstool` |
| `MUJOCO_PATH conflicts with mujoco_vendor` | Old env var from previous install | Remove from `.bashrc`, `source` it |
| `gz-cmake3 not found` | Skip it — it's Gazebo-only | `--skip-keys "gz-cmake3 DART ..."` |

---

## Zenoh — The IPC Transport

This project uses **Zenoh** instead of the default DDS (cyclonedds/fastdds):
```bash
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
export ZENOH_CONFIG_OVERRIDE="transport/shared_memory/enabled=true"
ros2 run rmw_zenoh_cpp rmw_zenohd   # the router daemon
```

**Why Zenoh?**
- Shared memory transport → zero-copy for large camera images (3x wrist cams at 20Hz = a lot of data)
- Works cleanly across distrobox container ↔ host (DDS multicast can break across namespaces)
- The competition's `aic_eval` container is pre-configured for Zenoh

**IPC architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│  distrobox aic_eval (Docker container)                          │
│                                                                 │
│  /entrypoint.sh starts:                                         │
│  ├── Gazebo Harmonic (physics sim + rendering)                  │
│  │   └── publishes SDF world, clock                             │
│  ├── aic_engine node                                            │
│  │   ├── spawns task board + cable (randomized each trial)      │
│  │   ├── subscribes to /joint_states, /wrench                   │
│  │   ├── publishes /ground_truth/... (TF of plug + port)        │
│  │   └── writes scoring.yaml when 3 trials complete             │
│  ├── ros2_control (controller manager)                          │
│  │   ├── loads JointTrajectoryController                        │
│  │   └── loads ForceTorqueSensorBroadcaster                     │
│  └── aic_adapter node                                           │
│      ├── bridges Gazebo topics → policy-facing topics           │
│      ├── pub: /wrist_camera_{left,right,bottom}/image_raw       │
│      ├── pub: /joint_states                                     │
│      ├── pub: /wrench (wrist F/T sensor)                        │
│      ├── pub: /controller_state                                 │
│      └── sub: /aic_controller/joint_trajectory                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
              │ Zenoh shared-memory transport (same host)
              │ (rmw_zenohd router bridges namespaces)
              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Host Ubuntu (pixi environment)                                 │
│                                                                 │
│  aic_model node (ros2 run aic_model aic_model)                  │
│  ├── sub: /wrist_camera_*/image_raw  (3x RGB @ 20Hz)           │
│  ├── sub: /joint_states              (6 joint positions/vels)   │
│  ├── sub: /wrench                    (Fx,Fy,Fz,Tx,Ty,Tz)       │
│  ├── sub: /controller_state          (mode, stiffness)          │
│  ├── [CheatCode only] sub: /ground_truth/plug_tip_pose          │
│  ├── [CheatCode only] sub: /ground_truth/port_pose              │
│  └── pub: /aic_controller/joint_trajectory  → arm moves         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## The ROS Nodes In Detail

### `aic_engine`
- Orchestrates trials (resets the scene 3 times)
- Scores each trial: did the plug approach? align? insert?
- Has access to ground truth TF (only if `ground_truth:=true`)
- Writes `scoring.yaml` on completion

### `aic_adapter`
- The **translation layer** — converts Gazebo's internal topics to the clean policy API
- Handles clock sync (`use_sim_time:=true` → uses `/clock` topic so sim time not wall time)
- Published topics match exactly what `docs/policy.md` specifies (so your policy is sim-agnostic)

### `aic_model` (the policy runner)
- Generic node that loads any Python class as a policy via the `policy` parameter
- Calls `policy.step(obs)` at 20 Hz
- `obs` = dict of all subscribed topics as numpy arrays
- Returns `joint_trajectory` command
- `CheatCode` uses ground truth TF → computes analytical IK → perfect insertion
- `RunACT` loads a trained checkpoint → runs inference → attempts insertion

### ros2_control (controller manager)
- **Not a node you write** — it's the hardware abstraction layer
- In Gazebo: talks to Gazebo's joint actuators via the `gz_ros2_control` plugin in the SDF
- In MuJoCo: talks to `mujoco_ros2_control` which wraps the MuJoCo C API
- Exposes `/joint_trajectory_controller/follow_joint_trajectory` action
- `aic_adapter` wraps this into the simpler `/aic_controller/joint_trajectory` topic

### `rmw_zenohd` (Zenoh router daemon)
- Not a ROS node — it's the transport router
- Must start **first** before any other node
- Bridges the distrobox network namespace and host
- Enables shared memory for zero-copy image transfer

---

## MuJoCo Lane Specifics

```
Terminal 1: rmw_zenohd           ← router (must be first)
Terminal 2: aic_mujoco_bringup   ← MuJoCo physics + ros2_control
Terminal 3: aic_model            ← your policy
```

MuJoCo lane uses the **same `aic_model` node and same topic API** as Gazebo. The difference is the physics engine underneath. This is the point: you tune gains/impedance in MuJoCo at 1000Hz, then those gains should work in Gazebo at 1000Hz physics / 20Hz policy.

The SDF → MJCF conversion (`sdf2mjcf`) is what makes the scenes match. The script:
1. Launches Gazebo just long enough to export the world as SDF
2. Copies it out of the container
3. Fixes URI corruption
4. Runs `sdf2mjcf` → `aic_world.xml`
5. Runs `add_cable_plugin.py` → splits into `scene.xml` + `aic_robot.xml` + adds MuJoCo cable plugin

---

## Pixi

Pixi is a **conda-compatible package manager** that resolves the entire ROS 2 Kilted + Python dependency tree without needing to install ROS system-wide. The `pixi.toml` in the AIC repo pins exact versions. `pixi run ros2 run ...` activates the environment and runs the command inside it — no `conda activate` needed.

**Why pixi for the policy but colcon for MuJoCo?**
- Policy (`aic_model`) = pure Python, no native compilation needed → pixi is fast
- MuJoCo lane = C++ (mujoco_vendor, aic_adapter, mujoco_ros2_control) → needs colcon + CMake to compile

---

## Error Taxonomy

### Installation errors

| Error | Root cause | Fix |
|-------|-----------|-----|
| `vcstool` conflicts | Ubuntu ships a Python 2 `vcstool`; ROS needs `python3-vcstool` | Script removes the old one automatically |
| `docker: permission denied` | User not in `docker` group | `sudo usermod -aG docker $USER && newgrp docker` |
| `pixi not found` | PATH not updated | `export PATH="$HOME/.pixi/bin:$PATH"` |

### Build errors

| Error | Root cause | Fix |
|-------|-----------|-----|
| `format: No such file or directory` | GCC < 14 | Check `CC/CXX` env vars |
| `sdformat_mjcf README.md missing` | Out-of-tree build bug | Fixed by the `ln -sf` in script |
| `gz-cmake3 not found` | Gazebo CMake package only in distrobox | Use `--skip-keys` |
| `mujoco_vendor download failed` | Network issues pulling MuJoCo binary | Retry or set `MUJOCO_PATH` manually |

### Runtime errors

| Error | Root cause | Fix |
|-------|-----------|-----|
| `scoring.yaml not found in 300s` | Gazebo crashed on launch | Usually missing GPU or DISPLAY |
| `aic_model: package not found` | Workspace not sourced | `source ~/ws_aic/install/setup.bash` |
| `Connection refused (Zenoh)` | `rmw_zenohd` not running | Start it first |
| `DISPLAY :1 unavailable` | X server not running | Need `Xvfb :1` or DCV session active |
| `MUJOCO_* env var conflict` | Old MuJoCo install interfering with `mujoco_vendor` | Remove from `.bashrc` |
| `No module named 'sdformat'` | `python3-sdformat16` not installed | Run step 1f+ of script |

---

## How It All Connects (End-to-End)

```
1. enable_dcv.sh
   → GPU-accelerated remote desktop on AWS

2. install_and_run_aic.sh
   → repo + submodules on disk

3. setup_sim_environments.sh Phase 1
   → GCC 14 (C++20 <format>)
   → NVIDIA Container Toolkit (GPU in Docker)
   → Pixi (Python policy env)
   → distrobox aic_eval (identical to scoring server)
   → ROS 2 Kilted host (needed by colcon for MuJoCo)
   → colcon build with GCC 14 (compiles aic_adapter, mujoco_vendor...)
   → IsaacLab Docker (RL training)

4. Phase 3: SDF export
   Gazebo inside Docker → /tmp/aic.sdf
   sed fixes (URI corruption) → sdf2mjcf → MJCF XML
   add_cable_plugin.py → scene.xml (MuJoCo ready)

5. Runtime (your development loop):
   aic-eval-gt          → distrobox Gazebo + aic_engine + aic_adapter
   aic-zenoh            → Zenoh router (bridges container ↔ host)
   aic-mujoco           → MuJoCo physics server (same interface as Gazebo)
   aic-policy CheatCode → oracle policy (needs ground_truth:=true)
   aic-policy RunACT    → your trained ACT student policy

6. Scoring:
   aic_engine detects plug position at 20Hz
   Tier 1 (approach) → Tier 2 (alignment) → Tier 3 (insertion) → 75pt full insert
   writes scoring.yaml → you read it
```

The entire setup exists so that **one `aic-policy RunACT` command** running on the host (with GPU access for ACT inference) can communicate over Zenoh with Gazebo inside the distrobox container, move the UR5e arm, and get scored — all identically to how the competition server will evaluate your submission.
