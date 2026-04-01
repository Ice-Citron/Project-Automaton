#!/usr/bin/env python3
# Copyright 2026 Project-Automaton contributors. SPDX-License-Identifier: Apache-2.0
"""Convert AIC ros2 bags (per-trial folders) into a LeRobot v3 dataset for ACT / lerobot-train.

Maps the same observation layout as ``lerobot_robot_aic`` / ``RunACT``:
  - ``observation.images.{left,center,right}_camera`` (resized like training, default 0.25 scale)
  - ``observation.state`` float32 (26,) — TCP pose/vel/error + 7 joint positions
  - ``action`` float32 (7,) — Cartesian twist (6) + trailing zero (matches 7-D ACT checkpoint IO)

Episode boundaries mirror Isaac Lab ``record_demos.py`` conceptually (one episode ≈ one bag / one
InsertCable run), but storage is **LeRobot v3** (parquet + videos), not Isaac HDF5.

Dependencies (AIC pixi env):
  - ``lerobot``, ``opencv``, message packages (``ros-kilted-aic-*`` interfaces)
  - ``rosbag2_py`` — install if missing: ``pixi add ros-kilted-rosbag2-py`` (robostack-kilted)

Usage:
  cd ~/ws_aic/src/aic
  pixi run python /path/to/Project-Automaton/aws/rosbag_to_lerobot_aic.py \\
    --session-dir ~/bags/my_session \\
    --output-dir ~/datasets/aic_act_from_bags \\
    --repo-id local/aic_bag_export

See also: ``aws/bag_record_per_trial.sh`` for recording one bag per InsertCable trial.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import yaml

from aic_control_interfaces.msg import MotionUpdate
from aic_model_interfaces.msg import Observation
from lerobot.datasets.lerobot_dataset import LeRobotDataset
from lerobot.datasets.video_utils import get_safe_default_codec

try:
    from rclpy.serialization import deserialize_message
    from rosbag2_py import ConverterOptions, SequentialReader, StorageOptions
except ImportError as e:
    raise ImportError(
        "rosbag2_py / rclpy serialization required. In the AIC pixi env try:\n"
        "  pixi add ros-kilted-rosbag2-py\n"
        "or install rosbag2 Python bindings for your ROS distro."
    ) from e

LOG = logging.getLogger(__name__)

CAM_KEYS = ("left_camera", "center_camera", "right_camera")
LR_IMAGE_KEYS = tuple(f"observation.images.{k}" for k in CAM_KEYS)

# Native AIC camera resolution (see lerobot_robot_aic/aic_robot.py)
CAM_H, CAM_W = 1024, 1152


def _lerobot_image_feature(h: int, w: int, fps: int) -> dict[str, Any]:
    codec = get_safe_default_codec()
    return {
        "dtype": "video",
        "shape": (h, w, 3),
        "names": ["height", "width", "channels"],
        "video.fps": fps,
        "video.codec": codec,
        "video.pix_fmt": "yuv420p",
        "video.is_depth_map": False,
        "has_audio": False,
    }


def aic_act_feature_dict(*, img_h: int, img_w: int, fps: int) -> dict[str, Any]:
    cam = _lerobot_image_feature(img_h, img_w, fps)
    return {
        "observation.state": {"dtype": "float32", "shape": (26,)},
        "action": {"dtype": "float32", "shape": (7,)},
        LR_IMAGE_KEYS[0]: {**cam},
        LR_IMAGE_KEYS[1]: {**cam},
        LR_IMAGE_KEYS[2]: {**cam},
    }


def ros_image_to_hwc(msg) -> np.ndarray:
    """sensor_msgs/Image -> HWC uint8 RGB."""
    arr = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, -1)
    if arr.shape[2] == 4:
        arr = arr[:, :, :3]
    return np.ascontiguousarray(arr)


def resize_hwc(img: np.ndarray, scale: float) -> np.ndarray:
    if scale == 1.0:
        return img
    new_w = int(img.shape[1] * scale)
    new_h = int(img.shape[0] * scale)
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)


def observation_to_state(obs: Observation) -> np.ndarray:
    """Same 26-D order as RunACT.prepare_observations."""
    tcp_pose = obs.controller_state.tcp_pose
    tcp_vel = obs.controller_state.tcp_velocity
    return np.array(
        [
            tcp_pose.position.x,
            tcp_pose.position.y,
            tcp_pose.position.z,
            tcp_pose.orientation.x,
            tcp_pose.orientation.y,
            tcp_pose.orientation.z,
            tcp_pose.orientation.w,
            tcp_vel.linear.x,
            tcp_vel.linear.y,
            tcp_vel.linear.z,
            tcp_vel.angular.x,
            tcp_vel.angular.y,
            tcp_vel.angular.z,
            *obs.controller_state.tcp_error,
            *obs.joint_states.position[:7],
        ],
        dtype=np.float32,
    )


def motion_to_action7(msg: MotionUpdate) -> np.ndarray:
    v = msg.velocity
    return np.array(
        [
            float(v.linear.x),
            float(v.linear.y),
            float(v.linear.z),
            float(v.angular.x),
            float(v.angular.y),
            float(v.angular.z),
            0.0,
        ],
        dtype=np.float32,
    )


def _ros_time_to_ns(stamp) -> int:
    if stamp is None:
        return 0
    return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)


def _parse_read_next(raw: Any) -> tuple[str, Any]:
    """Handle rosbag2_py ``read_next()`` tuple or SerializedBagMessage-style object."""
    if isinstance(raw, tuple):
        if len(raw) < 2:
            raise ValueError(f"Unexpected read_next tuple: {raw!r}")
        return str(raw[0]), raw[1]
    topic = getattr(raw, "topic_name", None)
    data = getattr(raw, "serialized_data", None)
    if topic is None or data is None:
        raise ValueError(f"Unexpected read_next return type: {type(raw)!r}")
    return str(topic), data


def _storage_options_for_bag(bag_dir: Path) -> StorageOptions:
    meta_path = bag_dir / "metadata.yaml"
    storage_id = ""
    if meta_path.is_file():
        meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
        info = meta.get("rosbag2_bagfile_information") or {}
        storage_id = info.get("storage_identifier") or ""
    uri = str(bag_dir.resolve())
    return StorageOptions(uri=uri, storage_id=storage_id)


def read_bag_messages(bag_dir: Path):
    reader = SequentialReader()
    reader.open(
        _storage_options_for_bag(bag_dir),
        ConverterOptions(
            input_serialization_format="cdr",
            output_serialization_format="cdr",
        ),
    )
    topic_types = {t.name: t.type for t in reader.get_all_topics_and_types()}

    seq = 0
    while reader.has_next():
        topic, data = _parse_read_next(reader.read_next())
        seq += 1
        if topic not in topic_types:
            continue
        ttype = topic_types[topic]
        if topic == "/observations" and "Observation" in ttype:
            obs = deserialize_message(data, Observation)
            t_ns = _ros_time_to_ns(obs.controller_state.header.stamp) or seq
            yield t_ns, topic, obs
        elif topic == "/aic_controller/pose_commands" and "MotionUpdate" in ttype:
            cmd = deserialize_message(data, MotionUpdate)
            t_ns = _ros_time_to_ns(cmd.header.stamp) or seq
            yield t_ns, topic, cmd


def build_frames_for_bag(
    bag_dir: Path, max_action_lag_ns: int
) -> list[tuple[Observation, np.ndarray, int]]:
    """Return list of (observation_msg, action7, obs_time_ns) aligned to last command ≤ obs time."""
    observations: list[tuple[int, Observation]] = []
    commands: list[tuple[int, MotionUpdate]] = []

    for t_ns, topic, msg in read_bag_messages(bag_dir):
        if topic == "/observations":
            observations.append((t_ns, msg))
        elif topic == "/aic_controller/pose_commands":
            commands.append((t_ns, msg))

    observations.sort(key=lambda x: x[0])
    commands.sort(key=lambda x: x[0])

    if not observations or not commands:
        return []

    out: list[tuple[Observation, np.ndarray, int]] = []
    j = 0
    last_act: MotionUpdate | None = None
    last_t: int | None = None

    for t_ns, obs in observations:
        while j < len(commands) and commands[j][0] <= t_ns:
            last_t, last_act = commands[j]
            j += 1
        if last_act is None or last_t is None:
            continue
        if t_ns - last_t > max_action_lag_ns:
            continue
        out.append((obs, motion_to_action7(last_act), t_ns))

    return out


def discover_bag_dirs(session_dir: Path) -> list[Path]:
    manifest = session_dir / "trials_manifest.json"
    dirs: list[Path] = []
    if manifest.is_file():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        for trial in data.get("trials", []):
            p = Path(trial["bag_directory"])
            if (p / "metadata.yaml").is_file():
                dirs.append(p)
    if dirs:
        return sorted(dirs, key=lambda p: p.name)

    if (session_dir / "metadata.yaml").is_file():
        return [session_dir]

    for child in sorted(session_dir.iterdir()):
        if child.is_dir() and (child / "metadata.yaml").is_file():
            dirs.append(child)
    return sorted(dirs, key=lambda p: p.name)


def write_conversion_meta(
    output_dir: Path,
    *,
    session_dir: Path,
    bag_dirs: list[Path],
    repo_id: str,
    fps: int,
    task: str,
    image_scale: float,
    episodes_written: int,
    skipped: list[str],
) -> None:
    meta = {
        "converter": "rosbag_to_lerobot_aic.py",
        "format": "LeRobot dataset v3 (Hugging Face lerobot)",
        "analogous_to": (
            "Isaac Lab aic_isaaclab/scripts/record_demos.py semantics: "
            "one episode per demonstration / trial, tabular + images; "
            "here Isaac uses HDF5 + recorder manager, we use rosbag2 → LeRobot v3."
        ),
        "source_session": str(session_dir),
        "bag_directories": [str(p) for p in bag_dirs],
        "repo_id": repo_id,
        "fps": fps,
        "task": task,
        "image_scale": image_scale,
        "episodes_written": episodes_written,
        "skipped_bags": skipped,
        "notes": [
            "action[6] is padded 0.0 to match 7-D ACT I/O used by RunACT / grkw/aic_act_policy.",
            "Success filtering (Isaac EXPORT_SUCCEEDED_ONLY) is not applied; filter by trials_manifest terminal_status if needed.",
        ],
    }
    (output_dir / "conversion_meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(
        description="Convert AIC ros2 bags to LeRobot v3 dataset (ACT-compatible layout)."
    )
    parser.add_argument(
        "--session-dir",
        type=Path,
        required=True,
        help="Directory containing per-trial bags (or a single bag), optionally trials_manifest.json.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="New LeRobot dataset root (must not exist, or use --overwrite).",
    )
    parser.add_argument(
        "--repo-id",
        type=str,
        default="local/aic_rosbag_export",
        help="Dataset repo_id metadata (local id is fine).",
    )
    parser.add_argument("--fps", type=int, default=20, help="Dataset FPS metadata (nominal).")
    parser.add_argument(
        "--task",
        type=str,
        default="insert_cable",
        help="Task string stored per frame (like --dataset.single_task in lerobot-record).",
    )
    parser.add_argument(
        "--image-scale",
        type=float,
        default=0.25,
        help="Resize factor vs 1024x1152 (match AICRobotAICController default).",
    )
    parser.add_argument(
        "--max-action-lag-ms",
        type=float,
        default=80.0,
        max=500.0,
        help="Drop observation if no pose_commands at or before this time within lag (ms).",
    )
    parser.add_argument(
        "--min-frames",
        type=int,
        default=5,
        help="Skip bags with fewer aligned frames.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Delete output-dir if it exists.",
    )
    args = parser.parse_args()
    if args.max_action_lag_ms < 0:
        parser.error("--max-action-lag-ms must be >= 0")

    session_dir = args.session_dir.resolve()
    out_root = args.output_dir.resolve()
    if out_root.exists():
        if not args.overwrite:
            LOG.error("Output exists; pass --overwrite to replace.")
            return 1
        import shutil

        shutil.rmtree(out_root)

    img_h = int(CAM_H * args.image_scale)
    img_w = int(CAM_W * args.image_scale)
    features = aic_act_feature_dict(img_h=img_h, img_w=img_w, fps=args.fps)
    max_lag_ns = int(args.max_action_lag_ms * 1e6)

    bag_dirs = discover_bag_dirs(session_dir)
    if not bag_dirs:
        LOG.error("No ros2 bags found under %s", session_dir)
        return 1

    LOG.info("Creating LeRobot dataset at %s (%d bag(s))", out_root, len(bag_dirs))
    dataset = LeRobotDataset.create(
        repo_id=args.repo_id,
        fps=args.fps,
        features=features,
        root=out_root,
        robot_type="ur5e_aic",
        use_videos=True,
        image_writer_threads=4,
        batch_encoding_size=1,
    )

    skipped: list[str] = []
    written = 0

    for bag in bag_dirs:
        rows = build_frames_for_bag(bag, max_action_lag_ns=max_lag_ns)
        if len(rows) < args.min_frames:
            skipped.append(f"{bag.name}: only {len(rows)} aligned frames")
            continue

        for obs, action7, t_ns in rows:
            left = resize_hwc(ros_image_to_hwc(obs.left_image), args.image_scale)
            center = resize_hwc(ros_image_to_hwc(obs.center_image), args.image_scale)
            right = resize_hwc(ros_image_to_hwc(obs.right_image), args.image_scale)
            state = observation_to_state(obs)
            frame = {
                "observation.state": state,
                "action": action7,
                LR_IMAGE_KEYS[0]: left,
                LR_IMAGE_KEYS[1]: center,
                LR_IMAGE_KEYS[2]: right,
                "task": args.task,
                "timestamp": t_ns / 1e9,
            }
            dataset.add_frame(frame)

        dataset.save_episode(parallel_encoding=True)
        written += 1
        LOG.info("Episode %d from %s (%d frames)", written - 1, bag.name, len(rows))

    dataset.finalize()
    LOG.info("Done: %d episode(s) written to %s", written, out_root)

    write_conversion_meta(
        out_root,
        session_dir=session_dir,
        bag_dirs=bag_dirs,
        repo_id=args.repo_id,
        fps=args.fps,
        task=args.task,
        image_scale=args.image_scale,
        episodes_written=written,
        skipped=skipped,
    )
    if skipped:
        for s in skipped:
            LOG.warning("Skipped: %s", s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
