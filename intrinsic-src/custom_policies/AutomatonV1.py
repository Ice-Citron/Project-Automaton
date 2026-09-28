"""
AutomatonV1 — Camera-based perception prototype.

This policy:
  1. Saves camera frames from all 3 wrist cameras
  2. Attempts to detect the target port using classical CV (color/contour analysis)
  3. Estimates 3D port position from camera intrinsics
  4. Moves toward the detected port

Run with:
  pixi run ros2 run aic_model aic_model --ros-args \
    -p use_sim_time:=true \
    -p policy:=aic_example_policies.ros.AutomatonV1
"""

import os
import numpy as np

from aic_model.policy import (
    GetObservationCallback,
    MoveRobotCallback,
    Policy,
    SendFeedbackCallback,
)
from aic_model_interfaces.msg import Observation
from aic_task_interfaces.msg import Task
from geometry_msgs.msg import Point, Pose, Quaternion
from rclpy.duration import Duration
from sensor_msgs.msg import Image, CameraInfo

# We'll try to import CV2 for image processing
try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


class AutomatonV1(Policy):
    def __init__(self, parent_node):
        super().__init__(parent_node)
        self._frame_count = 0
        self._save_dir = os.path.expanduser(
            "~/projects/Project-Automaton/aic_results/camera_frames"
        )
        os.makedirs(self._save_dir, exist_ok=True)
        self.get_logger().info(f"AutomatonV1 initialized. HAS_CV2={HAS_CV2}")

    def _ros_image_to_numpy(self, img: Image) -> np.ndarray:
        """Convert a ROS sensor_msgs/Image to a numpy array (HxWxC, BGR)."""
        # ROS images can be rgb8, bgr8, rgba8, etc.
        if img.encoding == "rgb8":
            arr = np.frombuffer(img.data, dtype=np.uint8).reshape(
                img.height, img.width, 3
            )
            return arr[:, :, ::-1]  # RGB -> BGR for OpenCV
        elif img.encoding == "bgr8":
            return np.frombuffer(img.data, dtype=np.uint8).reshape(
                img.height, img.width, 3
            )
        elif img.encoding == "rgba8":
            arr = np.frombuffer(img.data, dtype=np.uint8).reshape(
                img.height, img.width, 4
            )
            return arr[:, :, :3][:, :, ::-1]  # RGBA -> BGR
        elif img.encoding == "bgra8":
            arr = np.frombuffer(img.data, dtype=np.uint8).reshape(
                img.height, img.width, 4
            )
            return arr[:, :, :3]  # BGRA -> BGR
        else:
            # Fallback: try to reshape as 3-channel
            self.get_logger().warn(f"Unknown encoding: {img.encoding}, trying raw reshape")
            return np.frombuffer(img.data, dtype=np.uint8).reshape(
                img.height, img.width, -1
            )[:, :, :3]

    def _save_frame(self, obs: Observation, label: str = "") -> None:
        """Save all 3 camera images to disk for inspection."""
        if not HAS_CV2:
            self.get_logger().warn("cv2 not available, skipping frame save")
            return

        self._frame_count += 1
        prefix = f"frame_{self._frame_count:04d}"
        if label:
            prefix = f"{prefix}_{label}"

        for cam_name, img in [
            ("left", obs.left_image),
            ("center", obs.center_image),
            ("right", obs.right_image),
        ]:
            arr = self._ros_image_to_numpy(img)
            path = os.path.join(self._save_dir, f"{prefix}_{cam_name}.png")
            cv2.imwrite(path, arr)

        self.get_logger().info(
            f"Saved frame {prefix} to {self._save_dir} "
            f"({obs.center_image.width}x{obs.center_image.height})"
        )

    def _detect_port_in_image(self, img_bgr: np.ndarray) -> tuple:
        """
        Attempt to detect the target port in a BGR image.

        Strategy: The task board has distinctive colors and geometry.
        We look for rectangular dark regions (ports/slots) against
        the lighter board surface.

        Returns (found, center_x, center_y, bbox) or (False, 0, 0, None).
        """
        if not HAS_CV2:
            return False, 0, 0, None

        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        # Apply adaptive thresholding to find dark regions (ports are dark slots)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 11, 2
        )

        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Filter for rectangular contours of reasonable size
        # Ports are small rectangular openings
        candidates = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            # Filter by area: not too small (noise), not too large (background)
            if area < 100 or area > (h * w * 0.3):
                continue

            # Check rectangularity
            rect = cv2.minAreaRect(cnt)
            box = cv2.boxPoints(rect)
            rect_area = rect[1][0] * rect[1][1]
            if rect_area == 0:
                continue
            rectangularity = area / rect_area

            if rectangularity > 0.6:  # Roughly rectangular
                cx, cy = int(rect[0][0]), int(rect[0][1])
                candidates.append((area, cx, cy, rect))

        if not candidates:
            return False, 0, 0, None

        # Pick the candidate closest to center of image (heuristic: port is likely
        # near the middle since the robot is roughly aimed at the board)
        img_cx, img_cy = w // 2, h // 2
        candidates.sort(key=lambda c: (c[1] - img_cx)**2 + (c[2] - img_cy)**2)

        best = candidates[0]
        return True, best[1], best[2], best[3]

    def _pixel_to_3d_estimate(
        self, px: int, py: int, camera_info: CameraInfo, depth_estimate: float = 0.25
    ) -> tuple:
        """
        Rough 3D position estimate from a pixel coordinate + assumed depth.

        Uses the pinhole camera model:
          X = (px - cx) * Z / fx
          Y = (py - cy) * Z / fy
          Z = depth_estimate

        Returns (x, y, z) in camera frame.
        """
        fx = camera_info.k[0]  # K matrix: [fx, 0, cx, 0, fy, cy, 0, 0, 1]
        fy = camera_info.k[4]
        cx = camera_info.k[2]
        cy = camera_info.k[5]

        if fx == 0 or fy == 0:
            return 0.0, 0.0, depth_estimate

        x = (px - cx) * depth_estimate / fx
        y = (py - cy) * depth_estimate / fy
        z = depth_estimate

        return x, y, z

    def insert_cable(
        self,
        task: Task,
        get_observation: GetObservationCallback,
        move_robot: MoveRobotCallback,
        send_feedback: SendFeedbackCallback,
    ) -> bool:
        self.get_logger().info(
            f"AutomatonV1 — cable={task.cable_name}, "
            f"target={task.target_module_name}/{task.port_name}"
        )

        # ── Phase 1: Move to hover and save initial frames ──
        send_feedback("Phase 1: Moving to hover + saving camera frames")
        hover_pose = Pose(
            position=Point(x=-0.4, y=0.0, z=0.35),
            orientation=Quaternion(x=1.0, y=0.0, z=0.0, w=0.0),
        )
        self._move_smoothly(move_robot, get_observation, hover_pose, steps=60, dt=0.05)

        obs = get_observation()
        if obs is None:
            return False
        self._save_frame(obs, "hover")

        # ── Phase 2: Try to detect port in center camera ──
        send_feedback("Phase 2: Attempting port detection")

        if HAS_CV2:
            center_bgr = self._ros_image_to_numpy(obs.center_image)
            found, px, py, rect = self._detect_port_in_image(center_bgr)

            if found:
                self.get_logger().info(f"Port candidate detected at pixel ({px}, {py})")

                # Estimate 3D offset from camera
                cam_x, cam_y, cam_z = self._pixel_to_3d_estimate(
                    px, py, obs.center_camera_info, depth_estimate=0.20
                )
                self.get_logger().info(
                    f"Estimated camera-frame offset: ({cam_x:.3f}, {cam_y:.3f}, {cam_z:.3f})"
                )

                # Draw detection on image and save
                annotated = center_bgr.copy()
                cv2.circle(annotated, (px, py), 10, (0, 255, 0), 2)
                cv2.putText(
                    annotated, f"Port? ({px},{py})",
                    (px + 15, py), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1
                )
                det_path = os.path.join(self._save_dir, f"frame_{self._frame_count:04d}_detection.png")
                cv2.imwrite(det_path, annotated)
                self.get_logger().info(f"Detection visualization saved to {det_path}")

                # Adjust target pose based on detection
                # The camera offset gives us a rough correction from hover
                tcp = obs.controller_state.tcp_pose
                target_pose = Pose(
                    position=Point(
                        x=tcp.position.x + cam_y,   # camera Y ≈ robot X (forward)
                        y=tcp.position.y - cam_x,   # camera X ≈ robot -Y (left/right)
                        z=tcp.position.z - 0.15,     # descend toward board
                    ),
                    orientation=Quaternion(x=1.0, y=0.0, z=0.0, w=0.0),
                )
            else:
                self.get_logger().warn("No port candidate found — using default position")
                target_pose = Pose(
                    position=Point(x=-0.4, y=0.0, z=0.20),
                    orientation=Quaternion(x=1.0, y=0.0, z=0.0, w=0.0),
                )
        else:
            self.get_logger().warn("OpenCV not available — using default position")
            target_pose = Pose(
                position=Point(x=-0.4, y=0.0, z=0.20),
                orientation=Quaternion(x=1.0, y=0.0, z=0.0, w=0.0),
            )

        # ── Phase 3: Approach detected/default position ──
        send_feedback("Phase 3: Approaching target")
        self._move_smoothly(move_robot, get_observation, target_pose, steps=60, dt=0.05)

        # Save frame at approach position
        obs = get_observation()
        if obs is not None:
            self._save_frame(obs, "approach")

        # ── Phase 4: Hold and monitor ──
        send_feedback("Phase 4: Holding position")
        start_time = self.time_now()
        hold_duration = Duration(seconds=5.0)
        while (self.time_now() - start_time) < hold_duration:
            obs = get_observation()
            if obs is not None and self._frame_count < 10:
                self._save_frame(obs, "hold")
            self.set_pose_target(move_robot=move_robot, pose=target_pose)
            self.sleep_for(0.5)

        # ── Phase 5: Return to hover ──
        send_feedback("Phase 5: Returning to hover")
        self._move_smoothly(move_robot, get_observation, hover_pose, steps=40, dt=0.05)

        self.get_logger().info("AutomatonV1 complete.")
        return True

    def _move_smoothly(self, move_robot, get_observation, target_pose, steps=50, dt=0.05):
        """Linearly interpolate from current TCP pose to target."""
        obs = get_observation()
        if obs is None:
            for _ in range(steps):
                self.set_pose_target(move_robot=move_robot, pose=target_pose)
                self.sleep_for(dt)
            return

        current = obs.controller_state.tcp_pose
        for i in range(steps):
            frac = (i + 1) / steps
            interp_pose = Pose(
                position=Point(
                    x=current.position.x + frac * (target_pose.position.x - current.position.x),
                    y=current.position.y + frac * (target_pose.position.y - current.position.y),
                    z=current.position.z + frac * (target_pose.position.z - current.position.z),
                ),
                orientation=target_pose.orientation,
            )
            self.set_pose_target(move_robot=move_robot, pose=interp_pose)
            self.sleep_for(dt)
