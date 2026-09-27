# Shell Commands Reference — Session 6 (2026-03-28)

## MuJoCo Commands

### Generate randomized board
```bash
cd ~/projects/Project-Automaton/References/aic
export PATH=$HOME/.pixi/bin:$PATH
pixi run python3 ~/projects/Project-Automaton/Intrinsic-AI/tools/mujoco/randomize_board.py --seed 42 --nic 3 --sc 2
```

### View randomized scene
```bash
pixi run python3 -m mujoco.viewer --mjcf=aic_utils/aic_mujoco/mjcf/scene_rand.xml
```

### View base scene
```bash
pixi run python3 -m mujoco.viewer --mjcf=aic_utils/aic_mujoco/mjcf/scene.xml
```

### Run CheatCode / standalone MuJoCo policy
```bash
pixi run python3 ~/projects/Project-Automaton/Intrinsic-AI/tools/mujoco/mujoco_policies.py
```

### Run mesh axis diagnostic
```bash
pixi run python3 ~/projects/Project-Automaton/Intrinsic-AI/tools/mujoco/diagnose_mesh_axes.py
```

### Run physics settle (v2 with real XACRO collision)
```bash
pixi run python3 ~/projects/Project-Automaton/Intrinsic-AI/tools/mujoco/settle_and_bake_v2.py
```

### View settle test scene
```bash
pixi run python3 -m mujoco.viewer --mjcf=aic_utils/aic_mujoco/mjcf/test_mounts_settle.xml
```

## Gazebo Commands (need interactive WSL terminal)

### Start Zenoh router (required first)
```bash
source ~/ws_aic/install/setup.bash
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
export ZENOH_CONFIG_OVERRIDE='transport/shared_memory/enabled=true;transport/shared_memory/transport_optimization/pool_size=536870912'
ros2 run rmw_zenoh_cpp rmw_zenohd &
sleep 5
```

### Launch full scene (headless)
```bash
ros2 launch aic_bringup aic_gz_bringup.launch.py \
  gazebo_gui:=false \
  spawn_task_board:=true task_board_yaw:=3.1415 \
  nic_card_mount_0_present:=true sc_port_0_present:=true \
  sfp_mount_rail_0_present:=true lc_mount_rail_0_present:=true sc_mount_rail_0_present:=true \
  spawn_cable:=true cable_type:=sfp_sc_cable attach_cable_to_gripper:=true \
  ground_truth:=true start_aic_engine:=false
```

### Standalone Gazebo server test (this works in WSL2)
```bash
gz sim -s -r ~/ws_aic/src/aic/aic_description/world/aic.sdf --headless-rendering -v 4
```

### Test xacro generation
```bash
source ~/ws_aic/install/setup.bash
xacro $(ros2 pkg prefix aic_description)/share/aic_description/urdf/ur_gz.urdf.xacro ur_type:=ur5e name:=ur > /dev/null && echo "OK"
```

## Cleanup Commands

### Kill all Gazebo/ROS processes
```bash
pkill -f "gz sim"; pkill -f rmw_zenohd; pkill -f component_container; pkill -f robot_state; pkill -f "ros2 launch"
```

## File Sync (WSL ↔ Windows)

### Copy from WSL to Windows
```bash
cp ~/projects/Project-Automaton/Intrinsic-AI/path/to/file /mnt/c/Users/StarForge-SF/Black_Projects/Project-Automaton/Intrinsic-AI/path/to/file
```
