# go back into aic eval and check again (ROS lives here)
distrobox enter -r aic_eval

# (Ros) vcs (Version Control System tool) is a ROS utility that lets you manage multiple git repos at once using a single .repos file.
cd ~/ws_aic/src
vcs import < aic/aic_utils/aic_mujoco/mujoco.repos

# MISSING DEPENDENCY FROM GUIDE
sudo apt install -y libsdformat16

# Add the OSRF Gazebo stable apt repository (if not already added)
sudo wget https://packages.osrfoundation.org/gazebo.gpg -O /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" \
  | sudo tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null
sudo apt update

# Install required Python bindings
sudo apt install -y python3-sdformat16 python3-gz-math9

# refresh terminal (safety)
source ~/ws_aic/install/setup.bash

# test bindings
# python3 -c "import sdformat16; print('sdformat OK')"  ### ...16 NOT FOUND! NOTE
# python3 -c "from gz.math9 import Vector3d; print('gz.math OK')" ## ...9 NOT FOUND! NOTE

# test bindings
python3 -c "import sdformat; print('sdformat OK')"
python3 -c "from gz.math import Vector3d; print('gz.math OK')"

# build sdformat_mjcf
cd ~/ws_aic
source /opt/ros/kilted/setup.bash
colcon build --packages-select sdformat_mjcf
source install/setup.bash
