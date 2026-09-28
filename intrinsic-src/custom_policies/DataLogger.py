"""DataLogger — AIC policy that executes CheatCode-like GT insertion while
saving complete observation data per trial for offline training datasets.

Run with ground_truth:=true so the TF frames are available for the
CheatCode approach logic AND so the demos represent successful insertions.

Output structure:
    <dataset_root>/<run_timestamp>/
        metadata.json
        trial_<N>/
            frame_<NNNNN>/
                left.png, center.png, right.png
                joint_states.json, wrist_wrench.json
                controller_state.json, timestamp.json
            scoring.yaml   (copied from AIC results if available)
"""

import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from aic_model.policy import (
    GetObservationCallback,
    MoveRobotCallback,
    Policy,
    SendFeedbackCallback,
)
from aic_model_interfaces.msg import Observation
from aic_task_interfaces.msg import Task
from geometry_msgs.msg import Point, Pose, Quaternion, Transform
from rclpy.duration import Duration
from rclpy.time import Time
from tf2_ros import TransformException
from transforms3d._gohlketransforms import quaternion_multiply, quaternion_slerp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ros_image_to_bgr(img_msg) -> np.ndarray:
    """Convert a sensor_msgs/Image to a BGR numpy array for cv2."""
    raw = np.frombuffer(img_msg.data, dtype=np.uint8).reshape(
        img_msg.height, img_msg.width, -1
    )
    enc = img_msg.encoding.lower()
    if enc in ("rgb8",):
        return cv2.cvtColor(raw, cv2.COLOR_RGB2BGR)
    if enc in ("bgr8",):
        return raw.copy()
    if enc in ("rgba8",):
        return cv2.cvtColor(raw, cv2.COLOR_RGBA2BGR)
    if enc in ("bgra8",):
        return cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)
    # fallback: assume rgb8-ish 3-channel
    if raw.shape[2] == 3:
        return cv2.cvtColor(raw, cv2.COLOR_RGB2BGR)
    return raw[:, :, :3].copy()


def _camera_info_to_dict(info) -> dict:
    """Extract the useful fields from sensor_msgs/CameraInfo."""
    return {
        "height": info.height,
        "width": info.width,
        "distortion_model": info.distortion_model,
        "d": list(info.d),
        "k": list(info.k),
        "r": list(info.r),
        "p": list(info.p),
    }


def _pose_to_dict(pose) -> dict:
    return {
        "position": {"x": pose.position.x, "y": pose.position.y, "z": pose.position.z},
        "orientation": {
            "x": pose.orientation.x,
            "y": pose.orientation.y,
            "z": pose.orientation.z,
            "w": pose.orientation.w,
        },
    }


def _twist_to_dict(twist) -> dict:
    return {
        "linear": {"x": twist.linear.x, "y": twist.linear.y, "z": twist.linear.z},
        "angular": {"x": twist.angular.x, "y": twist.angular.y, "z": twist.angular.z},
    }


# ---------------------------------------------------------------------------
# DataLogger Policy
# ---------------------------------------------------------------------------

class DataLogger(Policy):
    """Records full observation data while running a CheatCode-style insertion."""

    # Where datasets are stored (overridable via DATALOGGER_ROOT env var)
    DEFAULT_DATASET_ROOT = os.path.expanduser(
        "~/projects/Project-Automaton/aic_results/datasets"
    )
    # Save every Nth observation (20Hz / 4 = 5Hz)
    SAVE_EVERY_N = 4

    def __init__(self, parent_node):
        # CheatCode state
        self._tip_x_error_integrator = 0.0
        self._tip_y_error_integrator = 0.0
        self._max_integrator_windup = 0.05
        self._task = None

        # Dataset state
        self._dataset_root = Path(
            os.environ.get("DATALOGGER_ROOT", self.DEFAULT_DATASET_ROOT)
        )
        self._run_dir = self._dataset_root / datetime.now().strftime("%Y%m%d_%H%M%S")
        self._run_dir.mkdir(parents=True, exist_ok=True)

        self._trial_count = 0
        self._camera_intrinsics_saved = False
        self._camera_intrinsics = {}

        super().__init__(parent_node)
        self.get_logger().info(
            f"DataLogger initialized. Saving to {self._run_dir}"
        )

    # ------------------------------------------------------------------
    # Observation saving
    # ------------------------------------------------------------------

    def _save_frame(self, obs: Observation, trial_dir: Path, frame_idx: int):
        """Save one observation frame (images + structured JSON)."""
        frame_dir = trial_dir / f"frame_{frame_idx:05d}"
        frame_dir.mkdir(parents=True, exist_ok=True)

        # --- Images ---
        for cam_name, img_msg in [
            ("left", obs.left_image),
            ("center", obs.center_image),
            ("right", obs.right_image),
        ]:
            bgr = _ros_image_to_bgr(img_msg)
            cv2.imwrite(str(frame_dir / f"{cam_name}.png"), bgr)

        # --- Joint States ---
        js = obs.joint_states
        joint_data = {
            "names": list(js.name),
            "positions": list(js.position),
            "velocities": list(js.velocity),
            "efforts": list(js.effort),
        }
        with open(frame_dir / "joint_states.json", "w") as f:
            json.dump(joint_data, f, indent=2)

        # --- Wrist Wrench ---
        w = obs.wrist_wrench.wrench
        wrench_data = {
            "force": {"x": w.force.x, "y": w.force.y, "z": w.force.z},
            "torque": {"x": w.torque.x, "y": w.torque.y, "z": w.torque.z},
        }
        with open(frame_dir / "wrist_wrench.json", "w") as f:
            json.dump(wrench_data, f, indent=2)

        # --- Controller State ---
        cs = obs.controller_state
        ctrl_data = {
            "tcp_pose": _pose_to_dict(cs.tcp_pose),
            "tcp_velocity": _twist_to_dict(cs.tcp_velocity),
            "reference_tcp_pose": _pose_to_dict(cs.reference_tcp_pose),
            "tcp_error": list(cs.tcp_error),
        }
        with open(frame_dir / "controller_state.json", "w") as f:
            json.dump(ctrl_data, f, indent=2)

        # --- Timestamp ---
        stamp = obs.center_image.header.stamp
        ts_data = {
            "sec": stamp.sec,
            "nanosec": stamp.nanosec,
            "sim_time": stamp.sec + stamp.nanosec / 1e9,
        }
        with open(frame_dir / "timestamp.json", "w") as f:
            json.dump(ts_data, f, indent=2)

    def _capture_camera_intrinsics(self, obs: Observation):
        """Save camera intrinsics once from the first valid observation."""
        if self._camera_intrinsics_saved:
            return
        self._camera_intrinsics = {
            "left": _camera_info_to_dict(obs.left_camera_info),
            "center": _camera_info_to_dict(obs.center_camera_info),
            "right": _camera_info_to_dict(obs.right_camera_info),
        }
        self._camera_intrinsics_saved = True

    # ------------------------------------------------------------------
    # CheatCode insertion logic (copied from CheatCode.py)
    # ------------------------------------------------------------------

    def _wait_for_tf(
        self, target_frame: str, source_frame: str, timeout_sec: float = 10.0
    ) -> bool:
        start = self.time_now()
        timeout = Duration(seconds=timeout_sec)
        attempt = 0
        while (self.time_now() - start) < timeout:
            try:
                self._parent_node._tf_buffer.lookup_transform(
                    target_frame, source_frame, Time()
                )
                return True
            except TransformException:
                if attempt % 20 == 0:
                    self.get_logger().info(
                        f"Waiting for transform '{source_frame}' -> '{target_frame}'... "
                        "-- are you running eval with ground_truth:=true?"
                    )
                attempt += 1
                self.sleep_for(0.1)
        self.get_logger().error(
            f"Transform '{source_frame}' not available after {timeout_sec}s"
        )
        return False

    def _calc_gripper_pose(
        self,
        port_transform: Transform,
        slerp_fraction: float = 1.0,
        position_fraction: float = 1.0,
        z_offset: float = 0.1,
        reset_xy_integrator: bool = False,
    ) -> Pose:
        q_port = (
            port_transform.rotation.w,
            port_transform.rotation.x,
            port_transform.rotation.y,
            port_transform.rotation.z,
        )
        plug_tf = self._parent_node._tf_buffer.lookup_transform(
            "base_link",
            f"{self._task.cable_name}/{self._task.plug_name}_link",
            Time(),
        )
        q_plug = (
            plug_tf.transform.rotation.w,
            plug_tf.transform.rotation.x,
            plug_tf.transform.rotation.y,
            plug_tf.transform.rotation.z,
        )
        q_plug_inv = (-q_plug[0], q_plug[1], q_plug[2], q_plug[3])
        q_diff = quaternion_multiply(q_port, q_plug_inv)

        gripper_tf = self._parent_node._tf_buffer.lookup_transform(
            "base_link", "gripper/tcp", Time()
        )
        q_gripper = (
            gripper_tf.transform.rotation.w,
            gripper_tf.transform.rotation.x,
            gripper_tf.transform.rotation.y,
            gripper_tf.transform.rotation.z,
        )
        q_gripper_target = quaternion_multiply(q_diff, q_gripper)
        q_gripper_slerp = quaternion_slerp(q_gripper, q_gripper_target, slerp_fraction)

        gripper_xyz = (
            gripper_tf.transform.translation.x,
            gripper_tf.transform.translation.y,
            gripper_tf.transform.translation.z,
        )
        port_xy = (
            port_transform.translation.x,
            port_transform.translation.y,
        )
        plug_xyz = (
            plug_tf.transform.translation.x,
            plug_tf.transform.translation.y,
            plug_tf.transform.translation.z,
        )
        plug_tip_gripper_offset = (
            gripper_xyz[0] - plug_xyz[0],
            gripper_xyz[1] - plug_xyz[1],
            gripper_xyz[2] - plug_xyz[2],
        )

        tip_x_error = port_xy[0] - plug_xyz[0]
        tip_y_error = port_xy[1] - plug_xyz[1]

        if reset_xy_integrator:
            self._tip_x_error_integrator = 0.0
            self._tip_y_error_integrator = 0.0
        else:
            self._tip_x_error_integrator = np.clip(
                self._tip_x_error_integrator + tip_x_error,
                -self._max_integrator_windup,
                self._max_integrator_windup,
            )
            self._tip_y_error_integrator = np.clip(
                self._tip_y_error_integrator + tip_y_error,
                -self._max_integrator_windup,
                self._max_integrator_windup,
            )

        i_gain = 0.15
        target_x = port_xy[0] + i_gain * self._tip_x_error_integrator
        target_y = port_xy[1] + i_gain * self._tip_y_error_integrator
        target_z = port_transform.translation.z + z_offset - plug_tip_gripper_offset[2]

        blend_xyz = (
            position_fraction * target_x + (1.0 - position_fraction) * gripper_xyz[0],
            position_fraction * target_y + (1.0 - position_fraction) * gripper_xyz[1],
            position_fraction * target_z + (1.0 - position_fraction) * gripper_xyz[2],
        )

        return Pose(
            position=Point(x=blend_xyz[0], y=blend_xyz[1], z=blend_xyz[2]),
            orientation=Quaternion(
                w=q_gripper_slerp[0],
                x=q_gripper_slerp[1],
                y=q_gripper_slerp[2],
                z=q_gripper_slerp[3],
            ),
        )

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def insert_cable(
        self,
        task: Task,
        get_observation: GetObservationCallback,
        move_robot: MoveRobotCallback,
        send_feedback: SendFeedbackCallback,
    ) -> bool:
        self._trial_count += 1
        trial_num = self._trial_count
        self._task = task
        self.get_logger().info(
            f"DataLogger.insert_cable() trial {trial_num} — task: {task}"
        )

        # Reset integrators for this trial
        self._tip_x_error_integrator = 0.0
        self._tip_y_error_integrator = 0.0

        trial_dir = self._run_dir / f"trial_{trial_num}"
        trial_dir.mkdir(parents=True, exist_ok=True)

        # ------ Wait for GT TF frames ------
        port_frame = f"task_board/{task.target_module_name}/{task.port_name}_link"
        cable_tip_frame = f"{task.cable_name}/{task.plug_name}_link"

        for frame in [port_frame, cable_tip_frame]:
            if not self._wait_for_tf("base_link", frame):
                self.get_logger().error("GT frames unavailable — aborting trial")
                send_feedback("GT frames unavailable")
                return False

        try:
            port_tf_stamped = self._parent_node._tf_buffer.lookup_transform(
                "base_link", port_frame, Time()
            )
        except TransformException as ex:
            self.get_logger().error(f"Could not look up port transform: {ex}")
            return False
        port_transform = port_tf_stamped.transform

        # ------ Counters for observation saving ------
        obs_count = 0      # total observations polled
        frame_idx = 0       # saved frame counter
        z_offset = 0.2
        trial_start_time = time.time()

        send_feedback(f"Trial {trial_num}: approach phase")

        # ====== Phase 1: Approach (5s, 100 steps x 50ms) ======
        for t in range(100):
            interp_fraction = t / 100.0
            try:
                self.set_pose_target(
                    move_robot=move_robot,
                    pose=self._calc_gripper_pose(
                        port_transform,
                        slerp_fraction=interp_fraction,
                        position_fraction=interp_fraction,
                        z_offset=z_offset,
                        reset_xy_integrator=True,
                    ),
                )
            except TransformException as ex:
                self.get_logger().warn(f"TF failed during approach: {ex}")

            # Save observations at ~5Hz
            obs = get_observation()
            if obs is not None:
                self._capture_camera_intrinsics(obs)
                obs_count += 1
                if obs_count % self.SAVE_EVERY_N == 0:
                    self._save_frame(obs, trial_dir, frame_idx)
                    frame_idx += 1

            self.sleep_for(0.05)

        # ====== Phase 2: Descent / Insertion ======
        send_feedback(f"Trial {trial_num}: insertion phase")
        while z_offset > -0.015:
            z_offset -= 0.0005
            try:
                self.set_pose_target(
                    move_robot=move_robot,
                    pose=self._calc_gripper_pose(port_transform, z_offset=z_offset),
                )
            except TransformException as ex:
                self.get_logger().warn(f"TF failed during insertion: {ex}")

            obs = get_observation()
            if obs is not None:
                self._capture_camera_intrinsics(obs)
                obs_count += 1
                if obs_count % self.SAVE_EVERY_N == 0:
                    self._save_frame(obs, trial_dir, frame_idx)
                    frame_idx += 1

            self.sleep_for(0.05)

        # ====== Phase 3: Hold for stabilization (5s) ======
        send_feedback(f"Trial {trial_num}: stabilizing")
        self.get_logger().info("Waiting for connector to stabilize...")
        hold_steps = int(5.0 / 0.05)  # 100 steps
        for _ in range(hold_steps):
            obs = get_observation()
            if obs is not None:
                obs_count += 1
                if obs_count % self.SAVE_EVERY_N == 0:
                    self._save_frame(obs, trial_dir, frame_idx)
                    frame_idx += 1
            self.sleep_for(0.05)

        trial_duration = time.time() - trial_start_time

        # ------ Save / update metadata ------
        self._save_metadata(task, trial_num, frame_idx, trial_duration)

        # ------ Try to copy scoring.yaml from AIC results ------
        self._copy_scoring(trial_dir, trial_num)

        self.get_logger().info(
            f"DataLogger trial {trial_num} complete — "
            f"{frame_idx} frames saved in {trial_duration:.1f}s"
        )
        send_feedback(
            f"Trial {trial_num} done: {frame_idx} frames, {trial_duration:.1f}s"
        )
        return True

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def _save_metadata(self, task: Task, trial_num: int, frames: int, duration: float):
        meta_path = self._run_dir / "metadata.json"

        # Load existing or start fresh
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
        else:
            meta = {
                "run_timestamp": self._run_dir.name,
                "created": datetime.now().isoformat(),
                "save_hz": 20.0 / self.SAVE_EVERY_N,
                "observation_hz": 20.0,
                "save_every_n": self.SAVE_EVERY_N,
                "camera_intrinsics": self._camera_intrinsics,
                "trials": [],
            }

        meta["trials"].append({
            "trial": trial_num,
            "task": {
                "id": task.id,
                "cable_type": task.cable_type,
                "cable_name": task.cable_name,
                "plug_type": task.plug_type,
                "plug_name": task.plug_name,
                "port_type": task.port_type,
                "port_name": task.port_name,
                "target_module_name": task.target_module_name,
                "time_limit": task.time_limit,
            },
            "frames_saved": frames,
            "duration_sec": round(duration, 2),
            "timestamp": datetime.now().isoformat(),
        })
        meta["last_updated"] = datetime.now().isoformat()

        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

    def _copy_scoring(self, trial_dir: Path, trial_num: int):
        """Try to copy scoring.yaml from the AIC results directory."""
        aic_results = os.environ.get("AIC_RESULTS_DIR")
        if not aic_results:
            return
        # AIC engine writes scoring.yaml at the results root
        scoring_src = Path(aic_results) / "scoring.yaml"
        if scoring_src.exists():
            try:
                shutil.copy2(str(scoring_src), str(trial_dir / "scoring.yaml"))
                self.get_logger().info(f"Copied scoring.yaml to trial_{trial_num}")
            except Exception as ex:
                self.get_logger().warn(f"Could not copy scoring.yaml: {ex}")
