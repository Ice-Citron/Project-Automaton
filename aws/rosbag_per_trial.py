#!/usr/bin/env python3
"""Record one ros2 bag per InsertCable action (trial), aligned with aic_engine goals.

Subscribes to the action server status topic and starts ``ros2 bag record`` when a goal
enters EXECUTING, then stops the recorder when that goal reaches a terminal state.

Run from the AIC pixi workspace (same Zenoh/RMW as your stack)::

    cd ~/ws_aic/src/aic
    pixi run python /path/to/Project-Automaton/aws/rosbag_per_trial.py --output-dir ~/bags/run1

This is raw ROS 2 data — not LeRobot/ACT format. ACT training in-tree expects
``lerobot-record`` datasets; bags are for analysis, custom converters, or non-ACT
pipelines. Isaac Lab ``record_demos.py`` instead writes HDF5 episodes with explicit
success/reset handling inside the sim loop.

Requires: ``ros-kilted-ros2bag`` and ``ros-kilted-rosbag2-storage-default-plugins``
in pixi (see References/aic/pixi.toml).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from uuid import UUID

import rclpy
from action_msgs.msg import GoalStatus, GoalStatusArray
from rclpy.node import Node
from rclpy.qos import QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy


def _goal_uuid(gs: GoalStatus) -> str:
    return str(UUID(bytes=bytes(gs.goal_info.goal_id.uuid)))


class BagPerTrialNode(Node):
    TERMINAL = {
        GoalStatus.STATUS_SUCCEEDED,
        GoalStatus.STATUS_ABORTED,
        GoalStatus.STATUS_CANCELED,
    }

    def __init__(
        self,
        *,
        output_dir: Path,
        topics: list[str],
        status_topic: str,
        ros2_bin: str,
        manifest_name: str,
    ) -> None:
        super().__init__("rosbag_per_trial_recorder")
        self._output_dir = output_dir
        self._topics = topics
        self._ros2_bin = ros2_bin
        self._manifest_path = output_dir / manifest_name
        self._trial_idx = 0
        self._proc: subprocess.Popen[Any] | None = None
        self._recording_goal: str | None = None

        output_dir.mkdir(parents=True, exist_ok=True)
        manifest: dict[str, Any] = {"trials": []}
        if self._manifest_path.is_file():
            try:
                manifest = json.loads(self._manifest_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self.get_logger().warn(
                    f"Could not parse existing manifest {self._manifest_path}; overwriting list"
                )
        self._manifest = manifest
        if "trials" not in self._manifest:
            self._manifest["trials"] = []

        qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=50,
        )
        self.create_subscription(
            GoalStatusArray, status_topic, self._on_status, qos
        )
        self.get_logger().info(
            f"Listening on {status_topic}; bags -> {output_dir}. Ctrl+C to stop."
        )

    def _stop_bag(self) -> None:
        if self._proc is None:
            return
        self.get_logger().info("Stopping ros2 bag record …")
        self._proc.terminate()
        try:
            self._proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self._proc.kill()
        self._proc = None
        self._recording_goal = None

    def _start_bag(self, goal_uuid: str) -> None:
        if self._proc is not None:
            self.get_logger().warn("Recorder already running; stopping previous bag.")
            self._stop_bag()

        stamp = time.strftime("%Y%m%d_%H%M%S")
        self._trial_idx += 1
        bag_path = self._output_dir / f"trial_{self._trial_idx:04d}_{stamp}"
        bag_path.mkdir(parents=True, exist_ok=True)

        cmd = [
            self._ros2_bin,
            "bag",
            "record",
            "-o",
            str(bag_path),
            *self._topics,
        ]
        self.get_logger().info(f"Starting: {' '.join(cmd)}")
        self._proc = subprocess.Popen(
            cmd,
            env=os.environ.copy(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._recording_goal = goal_uuid

        entry = {
            "index": self._trial_idx,
            "goal_id": goal_uuid,
            "bag_directory": str(bag_path),
            "started_monotonic": time.monotonic(),
        }
        self._manifest["trials"].append(entry)
        self._save_manifest()

    def _save_manifest(self) -> None:
        self._manifest_path.write_text(
            json.dumps(self._manifest, indent=2), encoding="utf-8"
        )

    def _on_status(self, msg: GoalStatusArray) -> None:
        # Terminal first so we close the current bag before handling a new EXECUTING
        # in the same or next message.
        uid_rec = self._recording_goal
        if uid_rec is not None:
            for gs in msg.status_list:
                if _goal_uuid(gs) != uid_rec:
                    continue
                if gs.status not in self.TERMINAL:
                    continue
                name = {
                    GoalStatus.STATUS_SUCCEEDED: "SUCCEEDED",
                    GoalStatus.STATUS_ABORTED: "ABORTED",
                    GoalStatus.STATUS_CANCELED: "CANCELED",
                }.get(gs.status, str(gs.status))
                self.get_logger().info(f"Goal {uid_rec[:8]}… {name}; closing bag.")
                self._stop_bag()
                if self._manifest["trials"]:
                    self._manifest["trials"][-1]["finished_monotonic"] = time.monotonic()
                    self._manifest["trials"][-1]["terminal_status"] = name
                    self._save_manifest()
                return

        for gs in msg.status_list:
            if gs.status != GoalStatus.STATUS_EXECUTING:
                continue
            uid = _goal_uuid(gs)
            if uid != self._recording_goal:
                self._start_bag(uid)
            return

    def destroy_node(self) -> bool:
        self._stop_bag()
        return super().destroy_node()


def _find_ros2() -> str:
    env_path = os.environ.get("PATH", "")
    for d in env_path.split(os.pathsep):
        candidate = Path(d) / "ros2"
        if candidate.is_file():
            return str(candidate)
    return "ros2"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Record one ros2 bag per InsertCable (insert_cable action) trial."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory for trial_NNNN_* bag folders + manifest JSON.",
    )
    parser.add_argument(
        "--status-topic",
        default="/insert_cable/_action/status",
        help="GoalStatusArray topic for the insert_cable action server.",
    )
    parser.add_argument(
        "--topics",
        nargs="+",
        default=[
            "/observations",
            "/aic_controller/pose_commands",
            "/joint_states",
        ],
        help="Topics to pass to ros2 bag record.",
    )
    parser.add_argument(
        "--manifest",
        default="trials_manifest.json",
        help="Manifest filename inside output-dir.",
    )
    parser.add_argument(
        "--ros2",
        default=None,
        help="Path to ros2 executable (default: first ros2 on PATH).",
    )
    args = parser.parse_args()

    ros2_bin = args.ros2 or _find_ros2()

    rclpy.init()
    node: BagPerTrialNode | None = None
    try:
        node = BagPerTrialNode(
            output_dir=args.output_dir.resolve(),
            topics=args.topics,
            status_topic=args.status_topic,
            ros2_bin=ros2_bin,
            manifest_name=args.manifest,
        )
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
