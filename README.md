# Project Automaton

Robot simulation tools, cable-insertion policy prototypes, and robotics
study material. The code uses MuJoCo, Gazebo, ROS 2, and NVIDIA Isaac Lab.
The repository also contains SO-101 print files and a LeRobot submodule.

## Simulation and control

[Intrinsic-AI](Intrinsic-AI/) contains the main experiment code:

- **Policy prototypes:** `AutomatonV0` sends approach-and-hold commands.
  `AutomatonV1` captures wrist-camera images and detects port candidates
  with OpenCV. Its position estimate uses an assumed depth.
- **Observation capture:** `DataLogger` combines a ground-truth-guided
  controller with camera, joint-state, wrench, and controller-state logs.
- **MuJoCo scenes:** MJCF files and connector meshes support task-board
  experiments. Tools randomise component placement with a fixed seed.
- **Mesh and pose tools:** Scripts inspect mesh axes, calculate correction
  quaternions, settle components, and export poses for Isaac Lab.
- **Material conversion:** Tools extract colours and textures from GLB
  assets and prepare MJCF files for simulator imports.
- **ROS 2 tools:** A launcher and action client support policy experiments.
  A bag reader extracts joint-state and force-torque data from trial logs.

[Policy source](Intrinsic-AI/custom_policies/) ·
[MuJoCo tools](Intrinsic-AI/tools/mujoco/) ·
[Scenes](Intrinsic-AI/scenes/mujoco/)

## ROS 2 interface diagram

![AIC ROS 2 interface diagram](docs/ros2-graph/aic_ros2_graph.png)

[Open the PDF](docs/ros2-graph/aic_ros2_graph.pdf) ·
[Diagram source](docs/ros2-graph/aic_ros2_graph.py)

## Study material and hardware

- [Robotics notebooks](study/robotics-notebooks/) cover simulator setup,
  ROS 2 interfaces, teleoperation, ACT, datasets, and experiment notes.
- [Isaac Lab tutorials](study/isaac-lab-tutorials/) include empty scenes,
  object creation, rigid bodies, deformable objects, and articulations.
- [PythonRobotics examples](study/python-robotics/) cover quadrotor
  trajectories and rocket landing with successive convexification.
- [NVIDIA webinar notes](study/nvidia-webinars/) cover physical AI,
  synthetic data, simulation, and robotics hardware.
- [SO-101 print files](SO-101/print-files/) contain leader and follower
  STL files, plus fit gauges.

## Directory structure

```text
Project-Automaton/
├── Intrinsic-AI/
│   ├── custom_policies/       # ROS 2 policy prototypes
│   ├── data/mujoco/           # Component poses and mesh corrections
│   ├── meshes/mujoco/         # Connector and mount meshes
│   ├── scenes/mujoco/         # MJCF scenes
│   └── tools/                # MuJoCo and Gazebo utilities
├── SO-101/
│   ├── print-files/          # STL files
│   └── lerobot/              # Git submodule
├── References/
│   └── aic/                  # Git submodule
├── study/
│   ├── robotics-notebooks/
│   ├── isaac-lab-tutorials/
│   ├── python-robotics/
│   └── nvidia-webinars/
├── docs/                     # Diagrams, plans, notes, and run configs
├── LICENSE
└── README.md
```

## Setup

Clone the repository:

```bash
git clone https://github.com/Ice-Citron/Project-Automaton.git
cd Project-Automaton
```

Install Git LFS before you fetch LeRobot assets. Then fetch the submodules:

```bash
git submodule update --init --recursive
```

The AIC and LeRobot submodules contain their own setup instructions.
The simulator scripts require their respective simulator environments.

Several scripts use fixed paths under `~/projects/Project-Automaton/`.
The ROS 2 launcher also expects `~/ws_aic/install/setup.bash`.
Check these paths and the required assets before you run an experiment.
Custom ROS 2 policies must be available to the AIC policy loader.

[Setup records](docs/session-notes/) contain environment details and
simulator issue reports. The policy code is experimental.

## Licence and sources

See [LICENSE](LICENSE) for the repository's MIT licence.
Tutorial and reference code includes material from Isaac Lab and
PythonRobotics. The AIC and LeRobot dependencies remain separate submodules.
Third-party code and assets retain their respective licences and credits.
