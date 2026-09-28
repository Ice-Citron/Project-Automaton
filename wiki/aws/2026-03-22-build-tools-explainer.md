# Build Tools — Pixi, CMake, colcon, ament, rosidl, rosdep, vcs
**Date:** 22 March 2026
**Author:** Evan
**Topic:** Every build tool in the AIC stack — what it is, why it exists, how it fits together

---

## The Big Picture

There are two completely separate build paths in this project:

```
Path A — Python-first (policy runtime)
  pixi.toml → pixi install → pixi run ros2 run aic_model aic_model
  Uses: pixi, conda-forge, robostack-kilted, PyPI
  Builds: aic_model, aic_example_policies (Python packages via pixi-build-ros)

Path B — C++-first (sim plumbing, MuJoCo lane)
  package.xml → CMakeLists.txt → colcon build → ~/ws_aic/install/
  Uses: colcon, CMake, ament, rosidl, rosdep, vcs, GCC 14
  Builds: aic_adapter, aic_controller, mujoco_vendor, mujoco_ros2_control
```

They produce the same ROS 2 interface (topics/services/actions) but are built completely differently. Path A is for running policies. Path B is for compiling the C++ sim bridge and MuJoCo physics backend.

---

## Pixi

### What it is

Pixi is a **cross-platform package manager** built on top of the conda ecosystem. Think of it as `cargo` (Rust) or `poetry` (Python) but for both native binaries and Python packages at the same time. Built by prefix.dev in Rust. Very fast.

Key properties:
- **Lockfile-first** — `pixi.lock` pins every transitive dependency to an exact hash
- **Per-project environments** — stored in `.pixi/` next to `pixi.toml`, never global
- **Conda + PyPI in one file** — `[dependencies]` = conda, `[pypi-dependencies]` = pip
- **No activation step** — `pixi run <cmd>` drops straight into the env without `conda activate`

### Why not just pip / conda directly?

| Tool | Problem |
|------|---------|
| pip alone | Can't install native libs (ROS 2, OpenCV, Qt) |
| conda alone | Old, slow solver; no PyPI support; activation ceremony |
| apt install ros-kilted-* | Installs system-wide; fights with other ROS distros |
| pixi | Installs per-project, pins everything, works on Linux + macOS |

### The `pixi.toml` in this project

Root: `References/aic/pixi.toml`

```toml
[workspace]
name = "aic"
channels = ["robostack-kilted", "conda-forge"]   # search order
platforms = ["linux-64", "osx-arm64"]

[dependencies]                                    # conda packages
ros-kilted-rclpy = "*"
ros-kilted-rmw-zenoh-cpp = "*"
ros-kilted-ros-core = "*"
ros-kilted-aic-model = { path = "aic_model" }     # local pixi package
opencv = "<4.13.0"

[pypi-dependencies]                               # pip packages
lerobot = "==0.4.3"
mujoco = "==3.5.0"
huggingface-hub = { version = "==0.35.3", extras = ["hf-transfer", "cli"] }
lerobot_robot_ros = { git = "https://github.com/...", rev = "b4a635f..." }

[activation]
scripts = ["pixi_env_setup.sh"]                   # runs on every pixi run
```

### Channels explained

**`robostack-kilted`** — a conda channel maintained by the ROS community that repackages ROS 2 Kilted packages as conda packages. Every `ros-kilted-*` dependency in `pixi.toml` comes from here. This is what makes `pixi install` give you a full working ROS 2 without touching `/opt/ros/`.

**`conda-forge`** — the community-maintained conda channel for everything else (OpenCV, numpy, PyTorch, cmake, gcc…). More up-to-date than the default Anaconda channel.

**Search order matters**: pixi tries `robostack-kilted` first, then `conda-forge`. ROS packages shadow conda-forge versions of the same lib.

### `pixi.lock`

The lockfile records the exact URL + SHA256 hash of every package for every platform. First 60 lines show entries like:

```yaml
- conda: https://conda.anaconda.org/conda-forge/linux-64/cmake-4.2.3-hc85cc9f_0.conda
- conda: https://conda.anaconda.org/robostack-kilted/linux-64/ros-kilted-rclpy-...conda
- conda: https://conda.anaconda.org/conda-forge/linux-64/mujoco-3.5.0-...conda
```

This means everyone on the team (and the CI server) gets identical binary artifacts. No "works on my machine" from package version drift.

### pixi-build-ros

Each ROS package (`aic_model`, `aic_example_policies`, `aic_control_interfaces`) has its own `pixi.toml` with:

```toml
[package.build.backend]
name = "pixi-build-ros"
version = "==0.3.3.20260113.c8b6a54"
channels = ["https://prefix.dev/pixi-build-backends", "robostack-kilted", "conda-forge"]
```

`pixi-build-ros` is a build backend that knows how to take a ROS package (with a `package.xml`) and make it installable as a conda package. It wraps CMake/ament internally. When the root `pixi.toml` does:

```toml
ros-kilted-aic-model = { path = "aic_model" }
```

pixi calls `pixi-build-ros` on the `aic_model/` directory, which:
1. Reads `aic_model/package.xml` for dependencies
2. Runs cmake/ament to build it
3. Packages the result as a conda artifact
4. Installs it into `.pixi/envs/default/`

This is how Python-only ROS packages get into the pixi environment without colcon.

### Common pixi commands

```bash
pixi install                     # solve lockfile + download + install everything
pixi run ros2 run aic_model aic_model  # run command inside the env
pixi run python scripts/foo.py   # any command
pixi shell                       # drop into a shell with env activated
pixi list                        # show installed packages + versions
pixi update                      # re-solve + update pixi.lock
pixi add numpy                   # add a dependency
```

---

## CMake

### What it is

CMake is a **build system generator**. It doesn't compile code directly — it generates the files that actually compile code (Makefiles, Ninja build files, Visual Studio projects).

```
CMakeLists.txt  →  cmake  →  Makefile / build.ninja  →  make/ninja  →  .so / executable
```

### Why a generator instead of just Make?

Because the same `CMakeLists.txt` can target Linux (Ninja), macOS (Xcode), or Windows (MSVC) without changes. ROS 2 uses Ninja by default for speed.

### Anatomy of a CMakeLists.txt (from `aic_adapter`)

```cmake
cmake_minimum_required(VERSION 3.20)       # minimum CMake version
project(aic_adapter)                       # package name

# Compiler warnings — -Wall -Wextra -Wpedantic
if(CMAKE_COMPILER_IS_GNUCXX ...)
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

set(CMAKE_CXX_STANDARD 20)                 # require C++20

# find_package = locate an installed library and load its CMake config
find_package(rclcpp REQUIRED)              # ROS 2 C++ client library
find_package(tf2_ros REQUIRED)             # transform library
find_package(aic_control_interfaces REQUIRED) # our custom messages

# add_executable = declare what to compile
add_executable(aic_adapter src/aic_adapter.cpp)

# target_link_libraries = what to link against
target_link_libraries(aic_adapter PUBLIC
  rclcpp::rclcpp                           # modern CMake target (not -lrclcpp)
  tf2_ros::tf2_ros
  ${aic_control_interfaces_TARGETS})       # generated message targets

# install = where to put the binary in the install tree
install(TARGETS aic_adapter
  DESTINATION lib/${PROJECT_NAME})         # → install/lib/aic_adapter/aic_adapter

ament_package()                            # ROS 2 ament macro (see below)
```

### CMake targets vs variables

Old CMake: `target_link_libraries(foo ${RCLCPP_LIBRARIES})` — error-prone string manipulation.

Modern CMake (what ROS 2 uses): `target_link_libraries(foo rclcpp::rclcpp)` — typed target objects that carry include paths, compile flags, transitive deps automatically. The `::` syntax is the modern target name convention.

### `find_package` mechanics

When you call `find_package(rclcpp REQUIRED)`, CMake looks for `rclcppConfig.cmake` or `rclcpp-config.cmake` in:
- `CMAKE_PREFIX_PATH` — which includes `~/ws_aic/install/` after sourcing `setup.bash`
- `/opt/ros/kilted/` — the system ROS install

This is why **sourcing setup.bash before colcon build is mandatory** — without it, `find_package(rclcpp)` fails because CMake can't find the config files.

### Build types

Set via `-DCMAKE_BUILD_TYPE=`:

| Type | Flags | Use |
|------|-------|-----|
| `Debug` | `-O0 -g` | Debugger, valgrind |
| `RelWithDebInfo` | `-O2 -g` | Profile with symbols |
| `Release` | `-O3 -DNDEBUG` | Normal sim use |
| `MinSizeRel` | `-Os` | Embedded, not used here |

The script always uses `Release` for the MuJoCo build. Debug builds of MuJoCo run 5-10x slower.

---

## colcon

### What it is

colcon (**col**lective **con**struction) is a **meta-build tool** that runs CMake (or Python setuptools) across a workspace of many packages in the correct dependency order.

It answers: "given 20 packages that depend on each other, in what order do I build them, and how?"

### Why not just run cmake manually?

With 20+ packages you'd have to manually figure out the build order, run cmake + make in each directory, then set up the install paths so each package can find the others. colcon does all of this.

### The workspace layout

```
~/ws_aic/
├── src/            ← your source packages (colcon scans this)
│   ├── aic/        ← the AIC repo (symlinked)
│   ├── mujoco_vendor/
│   └── sdformat_mjcf/
├── build/          ← per-package build dirs (CMake runs here)
│   ├── aic_adapter/
│   ├── aic_controller/
│   └── ...
├── install/        ← merged install tree (all outputs here)
│   ├── setup.bash  ← sources everything into your shell
│   ├── lib/        ← executables + shared libs
│   └── share/      ← URDF, launch files, meshes, params
└── log/            ← build logs (check here on failure)
```

### Key flags

```bash
colcon build \
  --cmake-args -DCMAKE_BUILD_TYPE=Release \
               -DCMAKE_CXX_COMPILER=/usr/bin/g++-14 \
  --merge-install \      # single install/ tree instead of per-package
  --symlink-install \    # Python/launch files: symlink → edit without rebuild
  --packages-ignore aic_gazebo aic_scoring aic_engine \  # skip these
  --packages-select aic_mujoco \   # only build this one
  --parallel-workers 4             # build N packages in parallel
```

**`--merge-install`**: by default colcon makes `install/aic_adapter/`, `install/aic_controller/` etc. `--merge-install` puts everything into one `install/` — simpler PATH/LD_LIBRARY_PATH.

**`--symlink-install`**: for Python packages, instead of copying `.py` files to `install/`, it symlinks them. This means you can edit a Python file and the change is live immediately without rebuilding. For C++ it makes no difference (you still need to recompile).

**`--packages-ignore`**: the four ignored packages (`aic_gazebo`, `aic_scoring`, `aic_engine`, `lerobot_robot_aic`) only exist pre-compiled inside the `aic_eval` Docker image. Their source depends on Gazebo Harmonic libraries which are not installed on the host. If you try to build them on the host, cmake fails with missing Gazebo headers.

### Dependency resolution

colcon reads each package's `package.xml` to find `<depend>` tags, builds a DAG, then builds leaves first. Example order for this project:

```
1. aic_control_interfaces    (no deps on aic packages)
2. aic_model_interfaces
3. aic_task_interfaces
4. aic_adapter               (depends on aic_control_interfaces, aic_model_interfaces)
5. aic_controller            (depends on aic_control_interfaces, hardware_interface...)
6. aic_mujoco                (depends on aic_adapter install outputs)
```

### Reading build logs

On failure:
```bash
cat ~/ws_aic/log/latest_build/aic_adapter/stdout_stderr.log
```

colcon shows `--- stderr: aic_adapter ---` in terminal but the full CMake/compiler output is in `log/`.

---

## ament

### What it is

**ament** is ROS 2's CMake extension layer. Every ROS 2 C++ package ends with `ament_package()` in its `CMakeLists.txt`. ament provides:

- `find_package(ament_cmake REQUIRED)` — the base ament CMake macros
- `ament_package()` — registers the package into the install tree (generates the `*Config.cmake` files that let other packages `find_package()` it)
- `ament_export_dependencies()` — propagates transitive deps to consumers
- `ament_export_targets()` — exports CMake targets so `target_link_libraries(foo bar::bar)` works from other packages

Without ament, you'd have to manually write CMake config files for every package. ament generates them automatically.

### ament_python

`aic_model` is a Python package:

```xml
<!-- package.xml -->
<export>
  <build_type>ament_python</build_type>
</export>
```

For Python packages, colcon uses `ament_python` instead of `ament_cmake`. This wraps `pip install -e .` / `setup.py` and registers the Python package into `install/lib/python3.x/site-packages/` (or via symlinks with `--symlink-install`).

### The two package types side by side

| | `aic_adapter` (C++) | `aic_model` (Python) |
|---|---|---|
| Build type | `ament_cmake` | `ament_python` |
| `CMakeLists.txt` | Yes, required | No (or minimal) |
| `package.xml` | Yes | Yes |
| Output | `.so` + binary in `install/lib/` | `.py` files in site-packages |
| Rebuild needed after edit? | Yes (recompile) | No (with `--symlink-install`) |

---

## rosidl — Message/Service/Action Code Generation

### What it is

`rosidl` is the **ROS Interface Definition Language** — the system that takes `.msg`, `.srv`, `.action` files and generates C++ headers + Python classes from them.

### From `aic_control_interfaces/CMakeLists.txt`

```cmake
set(msg_files
  "msg/ControllerState.msg"
  "msg/JointMotionUpdate.msg"
  "msg/MotionUpdate.msg"
  "msg/TargetMode.msg"
  "msg/TrajectoryGenerationMode.msg"
)
set(srv_files
  "srv/ChangeTargetMode.srv"
)

rosidl_generate_interfaces(${PROJECT_NAME}
  ${msg_files}
  ${srv_files}
  DEPENDENCIES builtin_interfaces geometry_msgs std_msgs trajectory_msgs
)
```

This single macro call generates:
- **C++ headers**: `install/include/aic_control_interfaces/msg/controller_state.hpp` — usable as `#include <aic_control_interfaces/msg/controller_state.hpp>`
- **Python module**: `aic_control_interfaces.msg.ControllerState` — importable directly
- **Serialization code**: DDS/Zenoh wire format (IDL → C bindings)
- **TypeSupport libraries**: `.so` files loaded at runtime by the RMW layer

### A `.msg` file

```
# ControllerState.msg
string controller_name
float64 stiffness_translational
float64 stiffness_rotational
int32 mode
```

Simple key: value format. rosidl turns this into strongly-typed structs in C++ and Python dataclasses. This is what flows over Zenoh between `aic_adapter` and `aic_model`.

### Why this matters

When `aic_adapter` publishes `ControllerState` and `aic_model` subscribes to it, they both use the same generated types. The serialization is automatic — you just set fields and publish.

---

## rosdep

### What it is

`rosdep` is a **system dependency installer**. It maps ROS package names to OS packages (apt, brew, etc.).

```bash
rosdep install --from-paths src --ignore-src --rosdistro kilted -yr
```

This scans every `package.xml` in `src/`, looks up each `<depend>` in the rosdep database, and installs any system packages not already present. For example:

- `eigen3` in `package.xml` → `libeigen3-dev` via apt
- `python3-numpy` → `python3-numpy` via apt
- `rclcpp` → already in ROS repo, skipped (`--ignore-src`)

**`--skip-keys "gz-cmake3 DART libogre-dev libogre-next-2.3-dev"`** — these are Gazebo-specific deps that only exist in the `aic_eval` container. Skipping them prevents rosdep from failing on the host.

---

## vcs (vcstool)

### What it is

`vcs` is a **multi-repo source control tool** — like `repo` (Android) but simpler. It reads a `.repos` YAML file and clones/updates each repository at a specific commit.

### From the script

```bash
vcs import --skip-existing < aic/aic_utils/aic_mujoco/mujoco.repos
```

`mujoco.repos` looks like:

```yaml
repositories:
  gazebo/gz-mujoco:
    type: git
    url: https://github.com/gazebosim/gz-mujoco
    version: main
  mujoco_ros2_control:
    type: git
    url: https://github.com/taDachs/mujoco_ros2_control
    version: some-sha
```

`vcs import` clones each repo into `src/`. This is how the MuJoCo workspace gets populated — there's no single monorepo, just a manifest of what to pull.

**`--skip-existing`** means if the directory already exists, skip it (don't overwrite local changes).

**Why not git submodules?** vcs allows pinning to branches or tags without the overhead of submodule tracking. It also handles heterogeneous repo types (git, mercurial, svn) though in practice only git is used here.

---

## How All These Tools Interact

### Path A: pixi (policy development)

```
pixi.toml
  ↓ pixi install
  ├── conda solver resolves full dep graph
  ├── downloads conda packages from robostack-kilted + conda-forge
  ├── downloads PyPI packages (lerobot, mujoco, huggingface-hub)
  ├── for local packages { path = "aic_model" }:
  │     calls pixi-build-ros backend
  │       which runs cmake + ament internally
  │       packages result as conda artifact
  │       installs into .pixi/envs/default/
  └── writes resolved state to pixi.lock

pixi run ros2 run aic_model aic_model
  ↓ activates .pixi/envs/default/
  ├── runs pixi_env_setup.sh (activation script)
  ├── ROS 2 Kilted is available (from robostack-kilted conda packages)
  ├── rmw_zenoh_cpp is available (from robostack-kilted)
  └── aic_model node starts, subscribes/publishes over Zenoh
```

### Path B: colcon (MuJoCo C++ build)

```
mujoco.repos
  ↓ vcs import
  src/mujoco_vendor/, src/mujoco_ros2_control/, src/sdformat_mjcf/

package.xml (per package)
  ↓ rosdep install
  apt installs: libeigen3-dev, libsophus-dev, python3-vcstool, ...

CMakeLists.txt (per package)
  ↓ colcon build (runs cmake + ninja/make per package in dep order)
  ├── cmake configures: find_package() locates deps via CMAKE_PREFIX_PATH
  ├── rosidl_generate_interfaces() generates msg/srv C++ + Python code
  ├── GCC 14 compiles .cpp → .o → links → .so / binary
  └── ament_package() generates *Config.cmake for downstream find_package()

install/setup.bash
  ↓ source
  sets: CMAKE_PREFIX_PATH, AMENT_PREFIX_PATH, LD_LIBRARY_PATH, PYTHONPATH
  result: ros2 run aic_mujoco ... works
```

### The dependency graph across tools

```
pixi.lock (pins exact versions)
    └── conda: ros-kilted-rclpy, ros-kilted-rmw-zenoh-cpp, opencv, mujoco...
    └── pypi: lerobot, huggingface-hub

package.xml (declares ROS deps by name)
    └── rosdep maps names → apt packages
    └── colcon reads for build order

CMakeLists.txt (CMake build logic)
    └── find_package() uses CMAKE_PREFIX_PATH set by setup.bash
    └── ament_package() generates config for downstream packages
    └── rosidl generates C++/Python from .msg/.srv

colcon (orchestrates CMake across all packages)
    └── reads package.xml for dep ordering
    └── runs cmake + compiler per package
    └── writes merged install/ tree
```

---

## Error Reference

### Pixi errors

| Error | Cause | Fix |
|-------|-------|-----|
| `pixi: command not found` | PATH not set | `export PATH="$HOME/.pixi/bin:$PATH"` |
| `error: package not found: ros-kilted-rclpy` | robostack-kilted not in channels | Check `channels` in `pixi.toml` |
| `lock file is out of date` | `pixi.toml` changed, lock not updated | `pixi install` or `pixi update` |
| `failed to build local package aic_model` | pixi-build-ros failure | Check cmake output: `pixi run --verbose` |
| `PyPI package lerobot not compatible` | Version conflict with conda packages | Pin specific version in `[pypi-dependencies]` |

### CMake errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Could not find package: rclcpp` | ROS not on `CMAKE_PREFIX_PATH` | `source /opt/ros/kilted/setup.bash` |
| `Could not find package: aic_control_interfaces` | ws not sourced | `source ~/ws_aic/install/setup.bash` |
| `fatal error: format: No such file or directory` | GCC < 14, no `<format>` | `export CXX=/usr/bin/g++-14` |
| `target_link_libraries called with wrong signature` | Old CMake | `cmake_minimum_required(VERSION 3.20)` |
| `undefined reference to rclcpp::...` | Linked against wrong rclcpp | Check `CMAKE_PREFIX_PATH` order |

### colcon errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Package 'X' not found` | Build order wrong or dep not installed | Run `rosdep install` first |
| `[1/1 packages failed]` | Check `log/latest_build/X/stdout_stderr.log` | See `cat ~/ws_aic/log/latest_build/*/stderr.log` |
| `sdformat_mjcf README.md not found` | Out-of-tree build reads README | Script's `ln -sf` fix |
| `[0.0s] Package 'X' skipped` | In `--packages-ignore` | Intentional |
| `vcstool not found` | Ubuntu's broken `vcstool` installed | `sudo apt install python3-vcstool` |

### rosidl errors

| Error | Cause | Fix |
|-------|-------|-----|
| `No module named 'aic_control_interfaces'` | Python path not set | `source ~/ws_aic/install/setup.bash` |
| `rosidl_generate_interfaces: DEPENDENCIES missing` | Interface deps not listed | Add to `DEPENDENCIES` in `CMakeLists.txt` |
| `TypeSupport not found for rmw_zenoh_cpp` | Zenoh typesupport not built | Ensure `ros-kilted-rmw-zenoh-cpp` installed |

---

## Quick Reference: Which Tool For What

| Task | Tool | Command |
|------|------|---------|
| Add a Python dep to policy env | pixi | `pixi add numpy` in `aic/` |
| Run the policy node | pixi | `pixi run ros2 run aic_model aic_model` |
| Compile aic_adapter (C++) | colcon | `colcon build --packages-select aic_adapter` |
| Add a system dep (apt) | rosdep | Add to `package.xml`, run `rosdep install` |
| Pull a new C++ repo into ws | vcs | Add to `mujoco.repos`, run `vcs import` |
| Add a new ROS message | rosidl | Create `.msg` file, add to `CMakeLists.txt` |
| Debug a build failure | colcon logs | `cat ~/ws_aic/log/latest_build/PKG/stdout_stderr.log` |
| Freeze all dep versions | pixi | `pixi update` (rewrites `pixi.lock`) |
| Check what's installed in pixi env | pixi | `pixi list` |
| Check what colcon built | colcon | `colcon list` (in `~/ws_aic/`) |
