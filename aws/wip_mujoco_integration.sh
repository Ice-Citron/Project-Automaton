# ============================================================
# STEP 1: Enter eval container (ROS lives here)
# ============================================================
distrobox enter -r aic_eval

# ============================================================
# STEP 2: Import MuJoCo dependencies
# ============================================================
cd ~/ws_aic/src
# vcs = ROS tool to clone multiple git repos from a .repos file
vcs import < aic/aic_utils/aic_mujoco/mujoco.repos

# ============================================================
# STEP 3: Install sdformat dependencies
# NOTE: Guide says to verify with sdformat16/gz.math9 but
#       noble packages are unversioned: sdformat / gz.math
# ============================================================
# Add OSRF Gazebo apt repo (if not already added)
sudo wget https://packages.osrfoundation.org/gazebo.gpg -O /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" \
  | sudo tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null
sudo apt update
sudo apt install -y python3-sdformat16 python3-gz-math9
# MISSING from guide — native C++ lib must be installed separately
sudo apt install -y libsdformat16

# Verify bindings (note: unversioned names, guide is wrong)
python3 -c "import sdformat; print('sdformat OK')"
python3 -c "from gz.math import Vector3d; print('gz.math OK')"

# ============================================================
# STEP 4: Build sdformat_mjcf
# ============================================================
cd ~/ws_aic
source /opt/ros/kilted/setup.bash
colcon build --packages-select sdformat_mjcf
source install/setup.bash

# ============================================================
# STEP 5: Install dm_control and other Python deps for sdf2mjcf
# NOTE: Must use pixi's Python — system Python lacks pip
#       dm_control installed with --no-deps to avoid mujoco
#       version conflict (pixi has 3.6.0, dm_control wants 3.5.0)
# ============================================================
cd ~/ws_aic/src/aic
pixi run python3 -m ensurepip
pixi run python3 -m pip install dm_control dm_env trimesh scipy pycollada absl-py lxml numpy --no-deps

# ============================================================
# STEP 6: Launch Gazebo WITH cable to generate /tmp/aic.sdf
#         Wait for "World saved to /tmp/aic.sdf" then Ctrl+C
# ============================================================
source ~/ws_aic/install/setup.bash
/entrypoint.sh \
  spawn_task_board:=true \
  spawn_cable:=true \
  cable_type:=sfp_sc_cable \
  attach_cable_to_gripper:=true \
  ground_truth:=true
# ... wait for: [WorldSdfGeneratorPlugin] World saved to /tmp/aic.sdf
# then Ctrl+C

# ============================================================
# STEP 7: Fix known SDF export bugs (run every time after export)
# ============================================================
sed -i 's|file://<urdf-string>/model://|model://|g' /tmp/aic.sdf
sed -i 's|file:///lc_plug_visual.glb|model://LC Plug/lc_plug_visual.glb|g' /tmp/aic.sdf
sed -i 's|file:///sc_plug_visual.glb|model://SC Plug/sc_plug_visual.glb|g' /tmp/aic.sdf
sed -i 's|file:///sfp_module_visual.glb|model://SFP Module/sfp_module_visual.glb|g' /tmp/aic.sdf
# Verify cable is present
grep -c "cable" /tmp/aic.sdf  # should be > 0

# ============================================================
# STEP 8: Convert SDF to MJCF
# NOTE: Must use pixi run — sdf2mjcf needs pixi's Python env
# ============================================================
source ~/ws_aic/install/setup.bash
mkdir -p ~/aic_mujoco_world
cd ~/ws_aic/src/aic
pixi run sdf2mjcf /tmp/aic.sdf ~/aic_mujoco_world/aic_world.xml

# ============================================================
# STEP 9: Copy assets and post-process MJCF
# NOTE: Run add_cable_plugin.py via pixi (needs mujoco module)
#       Do NOT source ROS workspace before this step
# ============================================================
cp ~/aic_mujoco_world/* ~/ws_aic/src/aic/aic_utils/aic_mujoco/mjcf/
cd ~/ws_aic/src/aic/aic_utils/aic_mujoco/
pixi run python3 scripts/add_cable_plugin.py \
  --input mjcf/aic_world.xml \
  --output mjcf/aic_world.xml \
  --robot_output mjcf/aic_robot.xml \
  --scene_output mjcf/scene.xml
# Expected: "Attached plugin to 24 bodies" and "Done."

# ============================================================
# STEP 10: Part 1 — View scene in MuJoCo (no ros2_control)
# Press Space to start, Backspace to reset
# ============================================================
cd ~/ws_aic/src/aic
pixi shell
cd ~/ws_aic
python src/aic/aic_utils/aic_mujoco/scripts/view_scene.py \
  src/aic/aic_utils/aic_mujoco/mjcf/scene.xml

# ============================================================
# STEP 11: Part 2 — Full build for ros2_control integration
# NOTE: Must exit pixi shell first!
#       Remove old install/ (was isolated layout, incompatible
#       with --merge-install)
# ============================================================
exit  # exit pixi shell
sudo rosdep init  # may already be done
rosdep update
rosdep install --from-paths src --ignore-src --rosdistro kilted -yr \
  --skip-keys "gz-cmake3 DART libogre-dev libogre-next-2.3-dev"

rm -rf ~/ws_aic/install ~/ws_aic/build ~/ws_aic/log
source /opt/ros/kilted/setup.bash
cd ~/ws_aic
GZ_BUILD_FROM_SOURCE=1 colcon build \
  --cmake-args -DCMAKE_BUILD_TYPE=Release \
  --merge-install \
  --symlink-install \
  --packages-ignore lerobot_robot_aic
# Expected: 20 packages finished

# Verify MuJoCo installation
source ~/ws_aic/install/setup.bash
echo $MUJOCO_DIR         # should be ~/ws_aic/install/opt/mujoco_vendor
echo $MUJOCO_PLUGIN_PATH # should be ~/ws_aic/install/opt/mujoco_vendor/lib
which simulate           # should be ~/ws_aic/install/opt/mujoco_vendor/bin/simulate

# ============================================================
# STEP 12: Part 2 — Launch MuJoCo with ros2_control
# Terminal 1: Zenoh router (skip if port 7447 already in use)
# ============================================================
source ~/ws_aic/install/setup.bash
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
export ZENOH_CONFIG_OVERRIDE='transport/shared_memory/enabled=true'
ros2 run rmw_zenoh_cpp rmw_zenohd

# Terminal 2: MuJoCo simulation
source ~/ws_aic/install/setup.bash
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
export ZENOH_CONFIG_OVERRIDE='transport/shared_memory/enabled=true'
ros2 launch aic_mujoco aic_mujoco_bringup.launch.py
