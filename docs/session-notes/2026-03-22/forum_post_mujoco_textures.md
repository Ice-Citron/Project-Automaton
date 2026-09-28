# MuJoCo Mirror: Visual assets lose all textures/materials after SDF→MJCF conversion

## Summary

After following the official AIC MuJoCo integration guide (`aic_utils/aic_mujoco/README.md`), the converted MuJoCo scene loads and runs correctly from a physics standpoint — robot joints, cable plugin, actuators, and contact dynamics all work. However, **all visual assets render as flat grey/untextured geometry** because the `sdf2mjcf` converter (from `gz-mujoco`) extracts mesh geometry as `.obj` files but discards all material/texture data from the source `.glb` files.

## What we have

The AIC toolkit ships 23 `.glb` (binary glTF) visual assets in `aic_assets/models/` — these are the source of truth for all visual geometry. In Gazebo, these render beautifully using the Ogre2 PBR pipeline with:
- Embedded PBR `baseColorFactor` (RGBA) per mesh
- Embedded `baseColorTexture` image maps (e.g., the NIC card has a detailed circuit board texture)
- Roughness/metalness values
- The world SDF (`aic_description/world/aic.sdf`) additionally configures Voxel Cone Tracing GI, shadow mapping, and a spotlight

## The conversion pipeline

Following the official MuJoCo README:

1. Launch Gazebo → exports world to `/tmp/aic.sdf`
2. Fix URI paths in the exported SDF (`sed` commands per the README)
3. Run `sdf2mjcf /tmp/aic.sdf output.xml` (from `gz-mujoco` repo, `aic` branch)
4. Run `add_cable_plugin.py` to split into robot/world/scene XML and configure cable physics

At step 3, the converter calls `trimesh` to load each `.glb`, exports each sub-mesh as a standalone `.obj` file, and references those `.obj` files in the output MJCF `<mesh>` elements. The corresponding `<material>` elements get a default `rgba="0.5 0.5 0.5 1"` (flat grey) with `shininess="30"` — **none of the original PBR colors or textures are carried over**.

## What MuJoCo actually supports

MuJoCo's rendering pipeline supports:
- `<material rgba="R G B A" specular="..." shininess="..." reflectance="..."/>` — per-material flat colors
- `<texture type="2d" file="image.png"/>` — PNG/JPG texture maps applied via UV coordinates
- `<texture type="cube"/>` — skybox/environment maps

So MuJoCo *can* display textures and correct colors — the `sdf2mjcf` converter just doesn't extract them.

## What we tried

We wrote a script (`patch_mujoco_materials.py`) that:
1. Loads each `.glb` with `trimesh`
2. Reads `PBRMaterial.baseColorFactor` (RGBA) from each mesh
3. Computes a dominant color per GLB
4. Patches the corresponding `<material>` elements in the MJCF XML

This gets the **flat colors roughly correct** (enclosure is dark grey, gripper is silver, task board is near-black, etc.) but:
- It uses one average color per GLB file, losing per-mesh color variation
- Image textures (e.g., the NIC card's circuit board pattern) are not mapped
- No UV-mapped textures are generated — `.obj` files from `sdf2mjcf` may not even preserve UV coordinates

## What we're asking

1. **Is there a recommended way to get proper visual materials in the MuJoCo mirror environment?** The current `sdf2mjcf` pipeline produces physics-correct but visually flat scenes. Has anyone on the AIC team or at Google DeepMind addressed this?

2. **Does `sdf2mjcf` have an option or branch that preserves textures?** We're using the `aic` branch of `gazebosim/gz-mujoco`. Perhaps there's a newer version or configuration flag we're missing.

3. **Would an alternative conversion approach work better?** For example:
   - Export `.glb` → `.obj` + `.mtl` + texture PNGs using Blender/trimesh, then reference them in MJCF manually
   - Use `obj2mjcf` (the DeepMind tool) which reportedly handles textures better
   - Directly author MuJoCo `<texture>` and `<material>` elements from the GLB PBR data

4. **For Isaac Lab users** — the AIC Isaac integration uses NVIDIA-prepared `.usd` assets (downloaded separately). Are the MuJoCo users expected to use a similar pre-prepared asset pack, or is the SDF conversion the intended path?

## Environment details

- Ubuntu 24.04 (WSL2)
- MuJoCo 3.5.0 (via AIC pixi) / 3.6.0 (standalone)
- `gz-mujoco` `aic` branch (sdformat_mjcf 0.1.2)
- `python3-sdformat15` (sdformat16 has a missing `libsdformat16` dependency on Noble)
- Gazebo Ionic 9.5.0
- RTX 5090, CUDA 12.9

## Relevant file paths in the AIC toolkit

```
aic_assets/models/                          ← 23 GLB files with PBR materials
aic_assets/models/NIC Card/nic_card_visual.glb  ← Has embedded image textures
aic_assets/models/Enclosure/enclosure_visual.glb ← Has PBR baseColorFactor only
aic_description/world/aic.sdf              ← Gazebo world with Ogre2 PBR rendering config
aic_utils/aic_mujoco/README.md             ← Official MuJoCo integration guide
aic_utils/aic_mujoco/mjcf/scene.xml        ← Generated MuJoCo scene (flat grey)
aic_utils/aic_mujoco/scripts/add_cable_plugin.py  ← Post-processing script
```

Thanks for any guidance. The physics side of the MuJoCo mirror is working great — just need help closing the visual gap.







● They're all ROS 2 distributions — essentially versioned releases of the same framework,
  like Ubuntu 22.04 vs 24.04. Same core system, different release dates, different
  supported Ubuntu versions, and different package ecosystems.

  The three distributions

  ┌──────────────┬────────────────────┬────────────────────┬─────────────────────────┐
  │              │       Humble       │       Jazzy        │         Kilted          │
  ├──────────────┼────────────────────┼────────────────────┼─────────────────────────┤
  │ Release date │ May 2022           │ May 2024           │ May 2025                │
  ├──────────────┼────────────────────┼────────────────────┼─────────────────────────┤
  │ End of life  │ Dec 2027           │ Dec 2029           │ Dec 2025                │
  ├──────────────┼────────────────────┼────────────────────┼─────────────────────────┤
  │ Type         │ LTS (5 year        │ LTS (5 year        │ Non-LTS (7 month        │
  │              │ support)           │ support)           │ support)                │
  ├──────────────┼────────────────────┼────────────────────┼─────────────────────────┤
  │ Target       │ 22.04 (Jammy)      │ 24.04 (Noble)      │ 24.04 (Noble)           │
  │ Ubuntu       │                    │                    │                         │
  ├──────────────┼────────────────────┼────────────────────┼─────────────────────────┤
  │ Python       │ 3.10               │ 3.12               │ 3.12                    │
  └──────────────┴────────────────────┴────────────────────┴─────────────────────────┘

  Why multiple versions exist

  Same reason Ubuntu has multiple versions — stability vs bleeding edge. Each ROS 2 distro:
  - Pins specific dependency versions (DDS middleware, build tools, core libraries)
  - Gets tested against a specific Ubuntu release
  - Has its own package repository (ros-humble-*, ros-jazzy-*, ros-kilted-*)

  LTS releases (Humble, Jazzy) get 5 years of support — industry/production use.
  Non-LTS releases (Kilted) get ~7 months — cutting edge features, early adoption.

  Why this matters for AIC

  - AIC evaluation uses Kilted (latest features, Ubuntu 24.04)
  - Isaac Sim only supports LTS distros (Humble/Jazzy) — NVIDIA won't track short-lived
  releases
  - Packages compiled for one distro can't be used with another — ros-humble-nav2 won't
  work with Kilted. Binary incompatibility.
  - ROS 2 nodes from different distros can't reliably communicate over the network — the
  middleware (DDS/Zenoh) versions may differ

  Typical usage

  Humble — Most industrial/production robots today. If you buy a robot in 2024-2025, its
  ROS 2 stack is probably Humble. NVIDIA, MoveIt, Nav2, all major packages support it.

  Jazzy — The new LTS. Companies are migrating to it now. Will be the standard for the next
   few years.

  Kilted — Bleeding edge. The AIC chose it because it's the latest at competition time. Not
   widely adopted in industry yet.

  For our project: we run Kilted in Gazebo (because AIC requires it), and Isaac Lab runs
  its own internal Python stack (no ROS 2 cross-talk needed). The version difference
  doesn't matter because data flows as files (HDF5, checkpoints), not live ROS 2 messages.





pixi run python3 ~/projects/Project-Automaton/Intrinsic-AI/tools/mujoco/mujoco_policies.py --policy interactive  



pixi run python3 ~/projects/Project-Automaton/Intrinsic-AI/tools/mujoco/mujoco_policies.py --policy cheatcode --duration 30




colcon build --packages-select mujoco_vendor sdformat_mjcf mujoco_ros2_control \
  aic_mujoco --cmake-args -DCMAKE_BUILD_TYPE=Release

---


● There they are:
  - Gazebo: References/aic/aic_bringup/launch/aic_gz_bringup.launch.py
  - MuJoCo: References/aic/aic_utils/aic_mujoco/launch/aic_mujoco_bringup.launch.py

  Both are ROS 2 launch files — same structure, different simulator backend.

  To verify your current MuJoCo setup (the visual-only test without ROS 2), yes:

  cd ~/projects/Project-Automaton/References/aic
  pixi run python3
  ~/projects/Project-Automaton/Intrinsic-AI/tools/mujoco/mujoco_policies.py --policy
  cheatcode --duration 30

  This tests that:
  1. Scene loads with textures + glass walls + light panels
  2. Robot arm actually moves (shoulder/elbow, not just wrist)
  3. Arm approaches the SC plug target via IK

  But this is just the visual sanity check. The real MuJoCo pipeline
  (aic_mujoco_bringup.launch.py) needs system ROS 2 Kilted + colcon build to run. That's
  the next blocker if you want the original CheatCode.py running in MuJoCo.




---

  # 2. Install Gazebo apt dependencies
  sudo apt -y install $(sort -u $(find . -iname 'packages-noble.apt' -o -iname \
  'packages.apt' | grep -v '/\.git/') | sed '/gz\|sdf/d' | tr '\n' ' ')

  # 3. Install ROS 2 dependencies
  cd ~/ws_aic
  rosdep install --from-paths src --ignore-src --rosdistro kilted -yr --skip-keys \
  "gz-cmake3 DART libogre-dev libogre-next-2.3-dev rosetta"

  # 4. Install Zenoh middleware
  sudo apt install -y ros-kilted-rmw-zenoh-cpp python3-pynput

  # 5. Build everything (this will take 20-40 minutes)
  source /opt/ros/kilted/setup.bash
  GZ_BUILD_FROM_SOURCE=1 colcon build --cmake-args -DCMAKE_BUILD_TYPE=Release \
  --merge-install --symlink-install --packages-ignore lerobot_robot_aic







---
  rm -rf ~/ws_aic/install ~/ws_aic/build ~/ws_aic/log
  source /opt/ros/kilted/setup.bash
  GZ_BUILD_FROM_SOURCE=1 colcon build --cmake-args -DCMAKE_BUILD_TYPE=Release \
  --merge-install --symlink-install --packages-ignore lerobot_robot_aic








  Terminal 1 — Zenoh router:
  source ~/ws_aic/install/setup.bash
  export RMW_IMPLEMENTATION=rmw_zenoh_cpp
  ros2 run rmw_zenoh_cpp rmw_zenohd

  Terminal 2 — MuJoCo sim:
  source ~/ws_aic/install/setup.bash
  export RMW_IMPLEMENTATION=rmw_zenoh_cpp
  ros2 launch aic_mujoco aic_mujoco_bringup.launch.py

  Terminal 3 — CheatCode policy:
  source ~/ws_aic/install/setup.bash
  export RMW_IMPLEMENTATION=rmw_zenoh_cpp
  ros2 run aic_model aic_model --ros-args -p use_sim_time:=true -p \
  policy:=aic_example_policies.ros.WaveArm

  Terminal 4 - ...
  source ~/ws_aic/install/setup.bash
  export RMW_IMPLEMENTATION=rmw_zenoh_cpp
  ros2 run aic_engine aic_engine --ros-args -p use_sim_time:=true -p config_file_path:= \
  $HOME/ws_aic/install/aic_engine/share/aic_engine/config/sample_config.yaml
