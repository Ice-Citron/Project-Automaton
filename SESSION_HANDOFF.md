# Project Automaton — Session Handoff & Continuation Guide

> **Last updated:** March 2026
> **Purpose:** Drop this file into a new Claude Code chat to seamlessly continue where we left off.

---

## What This Project Is

**Project Automaton** is a multi-target robotics + AI initiative hitting 3 goals with 1 codebase:

1. **Intrinsic AI Challenge (AIC)** — Training a UR5e robot to autonomously insert fiber optic cables (SFP, LC, SC connectors) into electronics assembly workstations. Competition runs Mar 2 - Sep 8, 2026. Qualification phase is active now.
2. **Revel x NVIDIA Hackathon** — Training a modified SO-101 robot arm to assemble Lego sets using Isaac Sim + LeRobot.
3. **Interceptor Drone** — ArduPilot/ROS integration for an autonomous drone project.

---

## Directory Map

```
/Users/administrator/Black_Projects/Project-Automaton/
├── SESSION_HANDOFF.md          ← THIS FILE
├── README.md
├── LICENSE
│
├── SO-101/                     ← Physical robot project
│   ├── lerobot/                ← HuggingFace LeRobot framework (v0.4.3)
│   │   ├── src/lerobot/        ← Main source (robots/, policies/, datasets/, rl/)
│   │   ├── pyproject.toml      ← Dependencies
│   │   └── docs/               ← Includes LeIsaac integration guide
│   ├── lerobot-venv/           ← Python virtual environment
│   └── Print Files/            ← 3D print STLs for custom SO-101 end-effectors
│       ├── Ender_Follower_SO101.stl
│       ├── Ender_Leader_SO101.stl
│       └── Gauge_*.STL
│
├── Lychee-AI/                  ← Isaac Lab tutorial work
│   ├── 2026-02-28/Tutorial_1/  ← create_empty.py (basic scene)
│   ├── 2026-03-01/
│   │   ├── Tutorial_2/         ← spawn_prims.py (objects, meshes, lights)
│   │   └── Tutorial_3/         ← run_rigid_object.py, run_articulation.py,
│   │                              run_deformable_object.py
│
├── Liberty-Notes/              ← Research & learning notebooks
│   ├── Nvidia-Issac-Lab/       ← Feb-04 through March-04 .ipynb study logs
│   └── PythonRobotics/         ← Reference robotics code
│
├── Intrinsic-AI/               ← AIC competition working directory
│   ├── aic_ros2_graph.py       ← ROS 2 computation graph generator (Graphviz)
│   ├── aic_ros2_graph.png      ← Rendered graph (raster)
│   ├── aic_ros2_graph.pdf      ← Rendered graph (vector — use this for zoom)
│   └── aic_ros2_graph.gv       ← Raw DOT source
│
├── References/
│   ├── Intrinsic AI Notes/     ← Manual notes
│   └── aic/                    ← FULL AIC TOOLKIT REPO (cloned from intrinsic-dev/aic)
│       ├── README.md
│       ├── pixi.toml           ← Pixi package manager config
│       ├── aic.repos           ← VCS dependency manifest
│       ├── docs/               ← 12+ comprehensive guides (scoring, rules, submission, etc.)
│       │
│       ├── aic_model/          ← PARTICIPANT FRAMEWORK (what you subclass)
│       │   └── aic_model/
│       │       ├── aic_model.py    ← ROS 2 LifecycleNode (335 lines) — loads your policy
│       │       └── policy.py       ← Abstract Policy base class (146 lines) — YOU IMPLEMENT THIS
│       │
│       ├── aic_example_policies/   ← Reference implementations
│       │   └── aic_example_policies/ros/
│       │       ├── WaveArm.py      ← Minimal example (85 lines) — arm waves side-to-side
│       │       ├── CheatCode.py    ← Ground truth policy (259 lines) — optimal insertion strategy
│       │       ├── RunACT.py       ← Neural network policy (321 lines) — ACT from HuggingFace
│       │       ├── GentleGiant.py  ← Low-jerk smooth motion (joint-space control)
│       │       ├── SpeedDemon.py   ← High-jerk aggressive motion (comparison)
│       │       ├── WallToucher.py  ← Collision detection test
│       │       └── WallPresser.py  ← Force control demo
│       │
│       ├── aic_interfaces/         ← ROS 2 message/service/action definitions
│       │   ├── aic_model_interfaces/msg/Observation.msg     ← 3 cameras + joints + wrench + ctrl
│       │   ├── aic_control_interfaces/msg/MotionUpdate.msg  ← Cartesian impedance commands
│       │   ├── aic_control_interfaces/msg/JointMotionUpdate.msg  ← Joint-space commands
│       │   ├── aic_control_interfaces/msg/ControllerState.msg    ← TCP pose/vel/error
│       │   ├── aic_control_interfaces/msg/TargetMode.msg         ← Cartesian vs Joint enum
│       │   ├── aic_control_interfaces/msg/TrajectoryGenerationMode.msg ← Position vs Velocity
│       │   ├── aic_control_interfaces/srv/ChangeTargetMode.srv
│       │   ├── aic_task_interfaces/msg/Task.msg              ← Cable/plug/port/module info
│       │   ├── aic_task_interfaces/action/InsertCable.action ← Main task trigger
│       │   └── aic_engine_interfaces/srv/ResetJoints.srv
│       │
│       ├── aic_engine/             ← Trial orchestrator (C++)
│       │   └── config/sample_config.yaml  ← 3 sample trials with board layouts
│       ├── aic_controller/         ← Low-level robot control (ros2_control, C++)
│       ├── aic_adapter/            ← Sensor fusion node (C++) — composites to Observation @ 20Hz
│       ├── aic_scoring/            ← Scoring system (C++) — Tier 1/2/3
│       │   └── config/tier1.yaml, tier2.yaml
│       ├── aic_gazebo/             ← Gazebo plugins (ScoringPlugin, CablePlugin, OffLimitContacts)
│       ├── aic_description/        ← URDF/SDF models
│       │   ├── urdf/ur_gz.urdf.xacro       ← UR5e + cameras + gripper + F/T sensor
│       │   ├── urdf/task_board.urdf.xacro   ← Modular task board (randomizable)
│       │   ├── urdf/cable.sdf.xacro         ← Cable models (sfp_sc, sfp_sc_reversed)
│       │   └── world/aic.sdf               ← Full simulation world
│       ├── aic_bringup/
│       │   └── launch/aic_gz_bringup.launch.py  ← Main launch file
│       ├── aic_assets/             ← 3D meshes (Robotiq, Basler, NIC cards, cables, etc.)
│       ├── aic_utils/              ← Teleoperation, MuJoCo integration, LeRobot dataset tools
│       └── docker/                 ← Container definitions for submission
│           ├── docker-compose.yaml
│           └── aic_model/Dockerfile + entrypoint (inline)
│
├── .gitignore
└── LICENSE                     ← Apache 2.0
```

---

## What We've Done So Far

### 1. Deep AIC Repository Analysis (COMPLETE)
- Read and analyzed every significant file in the AIC toolkit
- Documented all 10 critical files with line-by-line explanations
- Mapped all ROS 2 nodes, topics, services, actions, and their interconnections
- Understood the scoring system (100 pts max = 1 Tier1 + 30 Tier2 + 75 Tier3 - penalties)
- Identified the two control modes (Cartesian impedance vs Joint-space) and their trade-offs

### 2. ROS 2 Computation Graph (COMPLETE)
- Generated comprehensive Graphviz visualization at `Intrinsic-AI/aic_ros2_graph.py`
- Shows all nodes, topics, services, actions with color coding
- Outputs PNG, PDF (vector), and raw DOT source
- "Project Liberty 2025" watermark in bottom-right

### 3. Isaac Lab Tutorials 1-3 (COMPLETE)
- Tutorial 1: Basic scene creation
- Tutorial 2: Spawning primitives (ground, lights, meshes)
- Tutorial 3: Rigid bodies, articulations (CartPole), deformable objects

### 4. LeRobot Framework Setup (COMPLETE)
- Installed and configured for SO-100/SO-101 arm control
- Version 0.4.3 with all dependencies

### 5. Portal Access Issue (UNRESOLVED)
- Registered for AIC competition, received confirmation email
- Cannot log into https://aiforindustrychallenge.ai portal
- Likely waiting for separate "onboarding email" with AWS credentials + portal access
- Should check spam folder or post on discourse: https://discourse.openrobotics.org/c/competitions/ai-for-industry-challenge/

---

## What's Left To Do

### Immediate Next Steps
1. **Get Portal Access Sorted** — Need the onboarding email with AWS keys + ECR URI to submit
2. **Get Isaac Sim Running with UR5e** — Port the AIC robot description into Isaac Lab USD format
3. **Set Up ROS 2 Bridge** — Connect Isaac Sim to the AIC controller stack via the same topics
4. **Test WaveArm Policy** — Verify full pipeline works end-to-end in sim

### Training Pipeline
5. **Collect Demonstrations** — Run CheatCode with `ground_truth:=true` to record trajectories via LeRobot
6. **Train ACT Policy** — Use LeRobot to train an Action Chunking with Transformers model on the demo data
7. **Camera-Based Perception** — Replace ground truth TF lookups with a vision model (fine-tuned on sim images)
8. **Domain Randomization** — Randomize task board layouts, lighting, cable poses in Isaac Sim for robust training

### Submission Pipeline
9. **Containerize Policy** — Build Docker image based on `docker/aic_model/Dockerfile` template
10. **Local Verification** — `docker compose -f docker/docker-compose.yaml up`
11. **Push to ECR** — Tag + push to `973918476471.dkr.ecr.us-east-1.amazonaws.com/aic-team/<team_name>:v1`
12. **Register on Portal** — Paste OCI Image URI at aiforindustrychallenge.ai

---

## Key Technical Details

### The Core Contract — What You Implement

Your entire submission is a Python class that subclasses `Policy` and implements `insert_cable()`:

```python
from aic_model.policy import Policy

class MyPolicy(Policy):
    def insert_cable(self, task, get_observation, move_robot, send_feedback):
        # task: Task msg — what cable, what port, time limit
        # get_observation(): returns Observation msg (3 cameras + joints + wrench + ctrl_state)
        # move_robot(motion_update=...) or move_robot(joint_motion_update=...)
        # send_feedback("progress message")
        # return True if success, False if failure
        ...
```

### Control Modes

**Cartesian Impedance (MotionUpdate):**
- `pose`: Target TCP position + quaternion orientation
- `velocity`: Target TCP twist (for MODE_VELOCITY)
- `target_stiffness`: 6x6 matrix as flat 36 floats — `np.diag([Kx,Ky,Kz,Krx,Kry,Krz]).flatten()`
- `target_damping`: Same format
- `feedforward_wrench_at_tip`: Constant force/torque to apply
- `wrench_feedback_gains_at_tip`: [0-0.95] compliance gains
- `trajectory_generation_mode`: MODE_POSITION or MODE_VELOCITY

**Joint-Space (JointMotionUpdate):**
- `target_state.positions`: 6 joint angles in radians
- `target_stiffness`: 6 floats (per-joint)
- `target_damping`: 6 floats (per-joint)

**Stiffness/Damping Trade-offs:**
- Low stiffness (50) + high damping (40) = smooth, slow, low jerk (GentleGiant)
- High stiffness (500) + low damping (5) = aggressive, fast, high jerk (SpeedDemon)
- Default: stiffness [90,90,90,50,50,50], damping [50,50,50,20,20,20]

### Scoring (100 pts max per trial)

| Tier | What | Points |
|------|------|--------|
| Tier 1 | Model loads and responds | 1 |
| Tier 2 | Trajectory smoothness (jerk) | 0-6 |
| Tier 2 | Task duration (5s=12, 60s=0) | 0-12 |
| Tier 2 | Path efficiency | 0-6 |
| Tier 2 | Force penalty (>20N for >1s) | 0 to -12 |
| Tier 2 | Off-limit contact | 0 to -24 |
| Tier 3 | Full correct insertion | 75 |
| Tier 3 | Wrong port | -12 |
| Tier 3 | Partial insertion | 38-50 |
| Tier 3 | Proximity to port | 0-25 |

### Robot Setup
- **Arm:** Universal Robots UR5e (6 DOF)
- **Gripper:** Robotiq Hand-E
- **Cameras:** 3x Basler (left, center, right wrist mounts)
- **F/T Sensor:** Axia80 M20 (6-axis)
- **Joints:** shoulder_pan, shoulder_lift, elbow, wrist_1, wrist_2, wrist_3 + gripper
- **Home position:** [-0.1597, -1.3542, -1.6648, -1.6933, 1.5710, 1.4110]

### ROS 2 Data Flow (Critical Path)
```
Gazebo → ros_gz_bridge → camera/sensor topics → aic_adapter (sync @ 20Hz)
    → /observations → aic_model (YOUR POLICY)
    → /aic_controller/pose_commands OR /joint_commands
    → aic_controller → back to Gazebo physics
```

### CheatCode Strategy (The Gold Standard to Beat)
1. **Phase 1 — Approach (5 seconds):** Smoothly interpolate (100 steps x 50ms) from current pose to 20cm above the target port, simultaneously aligning plug orientation via quaternion slerp
2. **Phase 2 — Descent/Insertion:** Lower 0.5mm per 50ms (10mm/s) with PI controller on XY to keep plug centered. Continue until 15mm past port surface.
3. **Hold for 5 seconds** to let connector stabilize.
4. Uses ground truth TF frames (FORBIDDEN in eval — must replace with camera-based perception)

### RunACT Strategy (Neural Network Reference)
- Downloads pre-trained ACT model from HuggingFace (`grkw/aic_act_policy`)
- 26-dim state vector: TCP pose(7) + TCP vel(6) + TCP error(6) + joint positions(7)
- 3 camera images resized to 0.25x, normalized per-camera mean/std
- 7-dim action output: 6 velocity components + gripper
- Runs at ~4Hz (250ms per inference step) for 30 seconds
- Uses MODE_VELOCITY (velocity commands, not position)

### Key Competition Rules
- Ground truth TF data ONLY for training, FORBIDDEN in evaluation
- No Gazebo namespace access (/gazebo, /gz_server, /scoring)
- No hardcoded sensor data
- 1 submission per day (team-wide)
- Container images audited
- Zenoh ACL enforced

### Key URLs
- **Portal/Leaderboard:** https://aiforindustrychallenge.ai
- **Event Page:** https://www.intrinsic.ai/events/ai-for-industry-challenge
- **GitHub Repo:** https://github.com/intrinsic-dev/aic
- **Community Forum:** https://discourse.openrobotics.org/c/competitions/ai-for-industry-challenge/
- **Issues:** https://github.com/intrinsic-dev/aic/issues

### Tech Stack
| Component | Technology |
|-----------|-----------|
| Simulation | NVIDIA Isaac Sim + Isaac Lab, Gazebo (AIC default) |
| Robotics | LeRobot (HuggingFace), ROS 2 Kilted |
| ML | PyTorch, ACT, Diffusion Policy, LeRobot |
| Physics | Bullet-Featherstone (Gazebo), PhysX (Isaac) |
| Build | Pixi, colcon, CMake |
| Submission | Docker/OCI, AWS ECR, Zenoh middleware |
| Compute | Local: NVIDIA RTX 5090 (Windows), Cloud: RTX 6000 Pro / L40 (Linux) |

---

## Competition Timeline

| Phase | Dates | Status |
|-------|-------|--------|
| Qualification | Mar 2 - May 27, 2026 | ACTIVE |
| Phase 1 | May 28 - Jul 22, 2026 | Upcoming |
| Phase 2 | Jul 27 - Sep 8, 2026 | Upcoming |

---

## Quick Start Commands

```bash
# Run the AIC simulation locally (from aic/ root)
pixi run ros2 launch aic_bringup aic_gz_bringup.launch.py \
    ground_truth:=true \
    spawn_task_board:=true \
    spawn_cable:=true \
    start_aic_engine:=true

# Run your policy
pixi run ros2 run aic_model aic_model \
    --ros-args -p policy:=my_package.MyPolicy

# Build submission container
docker compose -f docker/docker-compose.yaml build model

# Test locally
docker compose -f docker/docker-compose.yaml up

# Regenerate the ROS 2 graph
cd Intrinsic-AI && python3 aic_ros2_graph.py
```

---

## Notes for Next Session

- The `Intrinsic-AI/` folder has the ROS 2 computation graph (regenerate with `python3 aic_ros2_graph.py`)
- The `References/aic/` folder is the cloned AIC toolkit — don't modify organizer-provided files
- `SO-101/` has the LeRobot setup for the Lego assembly project (separate from AIC but shares techniques)
- Isaac Lab tutorials are in `Lychee-AI/` — Tutorials 1-3 are done, continue from there for Isaac Sim integration
- All 3 projects (AIC cable insertion, SO-101 Lego assembly, drone) share the ROS 2 + Isaac Sim + LeRobot stack
- The old `"Black Projects"` (with space) directory is stale — everything lives under `Black_Projects` (underscore)
