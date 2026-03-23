# Isaac Lab Docker on WSL2: Vulkan Initialization Failure Blocks Camera Rendering

## Environment

| Component | Version |
|-----------|---------|
| **Host OS** | Windows 11 Pro 10.0.26200 |
| **WSL2 Distro** | Ubuntu 24.04 (Noble) |
| **GPU** | NVIDIA RTX 5090 (Blackwell, 32GB VRAM) |
| **Windows NVIDIA Driver** | 576.88 |
| **CUDA (inside WSL2)** | 12.9 |
| **Docker Engine** | Docker Engine CE 29.x (native WSL2 install, NOT Docker Desktop) |
| **NVIDIA Container Toolkit** | 1.19.0 |
| **Isaac Sim (in container)** | 5.1.0 (from `nvcr.io/nvidia/isaac-sim:5.1.0`) |
| **IsaacLab** | 2.3.2 (as recommended by AIC README) |
| **AIC Toolkit** | Latest main branch from `intrinsic-dev/aic` |

## What We're Trying To Do

We are participating in the **AI for Industry Challenge (AIC)** by Intrinsic. The AIC toolkit provides an Isaac Lab integration (`aic_utils/aic_isaac/`) that enables:

- Teleoperation of a UR5e robot in Isaac Lab
- Recording/replaying demos for imitation learning (HDF5)
- Reinforcement learning training with `rsl-rl`

The AIC Isaac README instructs participants to:

1. Clone IsaacLab, clone AIC inside it
2. Build the Docker container: `./docker/container.py build base`
3. Start the container, install `aic_task`, run scripts like `isaaclab -p scripts/teleop.py`

We followed these steps exactly on WSL2 Ubuntu 24.04.

## The Problem

**Every Isaac Sim script crashes during Vulkan initialization inside the Docker container on WSL2**, even in headless mode. The error is:

```
[Error] [carb.graphics-vulkan.plugin] VkResult: ERROR_INCOMPATIBLE_DRIVER
[Error] [carb.graphics-vulkan.plugin] vkCreateInstance failed. Vulkan 1.1 is not supported, or your driver requires an update.
[Error] [gpu.foundation.plugin] carb::graphics::createInstance failed.
```

This blocks **all camera-based functionality**, which the AIC task requires. The `AIC-Task-v0` environment config (`aic_task_env_cfg.py`) includes 3 TiledCamera sensors (center, left, right) with ResNet18 feature extraction as observations. Without Vulkan, cameras cannot render, and the environment cannot be created with `--enable_cameras`.

## What Works

- `nvidia-smi` works inside the container (RTX 5090 visible, CUDA 12.9)
- `docker run --gpus all nvidia/cuda:12.6.3-base-ubuntu24.04 nvidia-smi` works perfectly
- Isaac Sim starts with `SimulationApp({"headless": True, "vulkan": False})` — physics runs (falls back to CPU PhysX)
- The `AIC-Task-v0` environment registers correctly and the scene loads (UR5e robot, task board, SC ports, NIC card all found from the NVIDIA asset pack)
- RL training starts and reaches `sim.reset()` before crashing because cameras require rendering

## What We've Tried

### Attempt 1: Default Docker container (no modifications)

```bash
cd ~/IsaacLab
echo 'n' | python3 docker/container.py build base   # decline X11
echo 'n' | python3 docker/container.py start base
docker exec isaac-lab-base bash -c 'isaaclab -p aic/.../scripts/list_envs.py'
```

**Result:** `VkResult: ERROR_INCOMPATIBLE_DRIVER` — crash. The container's built-in NVIDIA libs are version **580.126.09** (from the `nvcr.io/nvidia/isaac-sim:5.1.0` base image), but the WSL2 host kernel driver is **576.88** (from Windows). This version mismatch causes `vkCreateInstance` to fail.

### Attempt 2: Enable X11 forwarding + WSLg mounts

Started the container with WSLg display passthrough:

```bash
docker run -d --name isaac-lab-base \
  --gpus all --network host \
  -e DISPLAY=:0 \
  -e WAYLAND_DISPLAY=wayland-0 \
  -e XDG_RUNTIME_DIR=/mnt/wslg/runtime-dir \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v /mnt/wslg:/mnt/wslg \
  -v /usr/lib/wsl:/usr/lib/wsl \
  --device /dev/dxg \
  isaac-lab-base:latest bash -c 'sleep infinity'
```

**Result:** WSLg mounts appeared inside the container, but `/usr/lib/wsl/lib/` does not contain Vulkan libraries (`libvulkan.so` or `nvidia_icd.json`). The WSL2 driver in `/usr/lib/wsl/lib/` only provides CUDA/compute libraries (libcuda.so, libd3d12.so, libdxcore.so, libnvwgf2umx.so, etc.) — no Vulkan ICD. Error changed to `ERROR_INITIALIZATION_FAILED` / `vkEnumeratePhysicalDevices failed. No physical device is found.`

### Attempt 3: Install matching NVIDIA GL libraries on host

```bash
sudo apt install -y libnvidia-gl-575
```

This installed `libGLX_nvidia.so.0` (version 575.64.03) on the WSL2 host, which the NVIDIA Container Toolkit could mount into the container.

**Result:** Error changed to `vkEnumeratePhysicalDevices failed. No physical device is found.` — the Vulkan loader now finds the ICD but the userspace libs (575.64.03) still don't match the kernel driver (576.88 from Windows).

### Attempt 4: Use `--runtime=nvidia` with `NVIDIA_DRIVER_CAPABILITIES=all`

```bash
docker run -d --name isaac-lab-base \
  --runtime=nvidia --gpus all \
  -e NVIDIA_DRIVER_CAPABILITIES=all \
  ...
```

**Result:** The NVIDIA Container Toolkit stripped the container's built-in NVIDIA libs (580.126.09) and tried to inject the host's, but the host (WSL2) doesn't have the standard NVIDIA Vulkan/GLX libraries — only the WSL2-specific stubs in `/usr/lib/wsl/lib/`. `libGLX_nvidia.so.0` disappeared entirely from the container.

### Attempt 5: Software renderer fallback

Tried forcing Mesa software rendering:

```bash
docker exec -e GALLIUM_DRIVER=llvmpipe -e MESA_GL_VERSION_OVERRIDE=4.6 ...
```

**Result:** Isaac Sim's Vulkan plugin doesn't use Mesa/Gallium — it specifically requires the NVIDIA Vulkan driver. Same `ERROR_INCOMPATIBLE_DRIVER`.

### Attempt 6: Disable Vulkan entirely (`vulkan=False`)

```python
from isaacsim import SimulationApp
simulation_app = SimulationApp({"headless": True, "vulkan": False})
```

**Result:** Isaac Sim starts! Extensions load, scene loads, `AIC-Task-v0` environment registers. However:
- PhysX falls back to CPU: `PhysX warning: GPU solver pipeline failed, switching to software`
- No rendering pipeline available, so `TiledCamera` sensors cannot initialize
- RL training crashes at `sim.reset()` → `render()` with: `RuntimeError: A camera was spawned without the --enable_cameras flag`
- Even with `--enable_cameras`, camera init fails because there's no GPU renderer

### Attempt 7: `OMNI_KIT_ALLOW_NO_DISPLAY=1`

```bash
docker exec -e OMNI_KIT_ALLOW_NO_DISPLAY=1 isaac-lab-base ...
```

**Result:** No effect on the Vulkan error. This flag allows Kit to start without a display connection but does not bypass the Vulkan driver requirement.

## Key Files

### Container's Vulkan ICD (`/etc/vulkan/icd.d/nvidia_icd.json` inside container):
```json
{
    "file_format_version" : "1.0.0",
    "ICD" : {
        "library_path" : "libGLX_nvidia.so.0",
        "api_version" : "1.3.194"
    }
}
```

### NVIDIA libs inside the container (from base image):
```
/usr/lib/x86_64-linux-gnu/libGLX_nvidia.so.0 -> libGLX_nvidia.so.580.126.09
/usr/lib/x86_64-linux-gnu/libnvidia-glcore.so.580.126.09
/usr/lib/x86_64-linux-gnu/libnvidia-glsi.so.580.126.09
/usr/lib/x86_64-linux-gnu/libnvidia-glvkspirv.so.580.126.09
```

### WSL2 host `/usr/lib/wsl/lib/` contents (NO Vulkan):
```
libcuda.so, libcuda.so.1, libcuda.so.1.1
libd3d12.so, libd3d12core.so, libdxcore.so
libnvwgf2umx.so
libnvidia-ml.so.1
libnvidia-encode.so, libnvidia-encode.so.1
libnvcuvid.so, libnvcuvid.so.1
libnvoptix.so.1, libnvoptix_loader.so.1
libnvidia-ngx.so.1
libnvidia-opticalflow.so, libnvidia-opticalflow.so.1
libnvdxdlkernels.so
```

Note: **No `libvulkan.so`, no `libGLX_nvidia.so`, no `nvidia_icd.json`** in the WSL2 driver library path.

### WSL2 host Vulkan packages:
```
libvulkan1:amd64      1.3.275.0-1build1
mesa-vulkan-drivers    25.2.8-0ubuntu0.24.04.1  (provides d3d12, lvp, etc.)
```

But no `nvidia_icd.json` on the host — only Mesa ICDs (asahi, gfxstream, intel, lvp, nouveau, radeon, virtio).

### Isaac Sim Kit config (`/isaac-sim/apps/isaacsim.exp.base.kit`):
```
vulkan = true  # Enable Vulkan by default for all platforms
```

### AIC task env config (`aic_task_env_cfg.py`) — cameras are integral:
```python
self.center_camera = TiledCameraCfg(
    prim_path="{ENV_REGEX_NS}/Robot/aic_unified_robot/center_camera_optical/center_camera",
    spawn=_cam_spawn,
    height=224, width=224,
    data_types=["rgb"],
)
# + left_camera, right_camera (same config)
```

Observations include:
```python
center_rgb = ObsTerm(func=mdp.image_features, params={"sensor_cfg": SceneEntityCfg("center_camera"), "data_type": "rgb", "model_name": "resnet18"})
left_rgb = ObsTerm(func=mdp.image_features, params={"sensor_cfg": SceneEntityCfg("left_camera"), ...})
right_rgb = ObsTerm(func=mdp.image_features, params={"sensor_cfg": SceneEntityCfg("right_camera"), ...})
```

## The Core Issue

The NVIDIA Vulkan driver inside the Docker container (v580.126.09, baked into `nvcr.io/nvidia/isaac-sim:5.1.0`) **cannot communicate with the WSL2 kernel-mode driver (v576.88)** because:

1. WSL2's GPU driver model is fundamentally different from native Linux — the GPU is accessed through `/dev/dxg` and D3D12 translation, not through the standard `/dev/nvidia*` device files
2. The NVIDIA Container Toolkit on WSL2 only injects CUDA/compute libraries into containers, not Vulkan/GLX/EGL libraries
3. The WSL2 host `/usr/lib/wsl/lib/` does not contain Vulkan libraries or an NVIDIA Vulkan ICD
4. Even installing `libnvidia-gl-575` on the WSL2 host doesn't help because the version doesn't match the kernel driver (576.88 from Windows)

## What We Need

Guidance on **any** of the following:

1. **Is there a way to get Vulkan working inside the Isaac Lab Docker container on WSL2?** Perhaps a specific NVIDIA driver version, container toolkit config, or mount strategy?

2. **Can Isaac Sim's `TiledCamera` render using CUDA-only (no Vulkan)?** Perhaps via a software Vulkan layer (e.g., `lavapipe`) or an alternative rendering backend?

3. **Should we modify the AIC `aic_task_env_cfg.py` to support state-only training (no cameras)?** This would let us train RL policies headless, but we'd lose the camera observations that are central to the challenge.

4. **Is running on a native Ubuntu machine (not WSL2) the only viable path for Isaac Lab with cameras?** NVIDIA's own docs state that Isaac Sim ROS 2 launch is "not supported in WSL2" — does this extend to all Docker-based Isaac Sim workflows?

5. **Is there an alternative headless rendering path** (e.g., EGL, OSMesa, or headless Vulkan via `VK_ICD_FILENAMES` pointing to a software implementation) that could work for camera sensors without a physical display?

## Reproduction Steps

```bash
# On WSL2 Ubuntu 24.04 with NVIDIA Container Toolkit installed:

cd ~
git clone https://github.com/isaac-sim/IsaacLab.git
cd ~/IsaacLab
git clone https://github.com/intrinsic-dev/aic.git

# Build (decline X11 prompt)
echo 'n' | python3 docker/container.py build base

# Start
echo 'n' | python3 docker/container.py start base

# Install aic_task
docker exec isaac-lab-base bash -c \
  '/workspace/isaaclab/_isaac_sim/python.sh -m pip install -e \
  /workspace/isaaclab/aic/aic_utils/aic_isaac/aic_isaaclab/source/aic_task'

# This crashes with Vulkan error:
docker exec isaac-lab-base bash -c \
  '/workspace/isaaclab/isaaclab.sh -p \
  /workspace/isaaclab/aic/aic_utils/aic_isaac/aic_isaaclab/scripts/list_envs.py'

# This works (vulkan=False) but cameras can't render:
docker exec -e ACCEPT_EULA=Y -e OMNI_KIT_ALLOW_NO_DISPLAY=1 isaac-lab-base bash -c \
  '/workspace/isaaclab/_isaac_sim/python.sh -c "
from isaacsim import SimulationApp
simulation_app = SimulationApp({\"headless\": True, \"vulkan\": False})
import gymnasium as gym
import aic_task.tasks.manager_based.aic_task
found = [s.id for s in gym.registry.values() if \"AIC\" in s.id]
import sys; sys.stderr.write(f\"AIC_ENVS={found}\n\")
simulation_app.close()
"'
# Output: AIC_ENVS=['AIC-Task-v0']  ← env registers, but cameras won't work
```

Thank you for any guidance.
