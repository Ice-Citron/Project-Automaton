"""
AutomatonV0 — First custom policy for Project Automaton.

This policy does NOT use ground truth TF. It reads camera images,
joint states, and wrist wrench from the observation, and executes
a simple approach-then-hold strategy based on hardcoded workspace
knowledge (NOT hardcoded sensor data — just rough workspace geometry).

The goal is to prove the full pipeline works with custom code:
  1. Receive task info (cable type, target port, time limit)
  2. Read observations (cameras, joints, wrench)
  3. Send motion commands (Cartesian impedance)
  4. Send feedback messages
  5. Return success/failure

Run with:
  pixi run ros2 run aic_model aic_model --ros-args \
    -p use_sim_time:=true \
    -p policy:=aic_example_policies.ros.AutomatonV0
"""

import numpy as np

from aic_model.policy import (
    GetObservationCallback,
    MoveRobotCallback,
    Policy,
    SendFeedbackCallback,
)
from aic_control_interfaces.msg import MotionUpdate, TrajectoryGenerationMode
from aic_model_interfaces.msg import Observation
from aic_task_interfaces.msg import Task
from geometry_msgs.msg import Point, Pose, Quaternion, Vector3, Wrench
from rclpy.duration import Duration
from std_msgs.msg import Header


class AutomatonV0(Policy):
    def __init__(self, parent_node):
        super().__init__(parent_node)
        self.get_logger().info("AutomatonV0 initialized.")

    def insert_cable(
        self,
        task: Task,
        get_observation: GetObservationCallback,
        move_robot: MoveRobotCallback,
        send_feedback: SendFeedbackCallback,
    ) -> bool:
        self.get_logger().info(
            f"AutomatonV0.insert_cable() — "
            f"cable={task.cable_name}, plug={task.plug_name}, "
            f"target={task.target_module_name}/{task.port_name}, "
            f"time_limit={task.time_limit}s"
        )

        # ── Phase 1: Read initial observation and log what we see ──
        send_feedback("Phase 1: Reading sensors")
        obs = get_observation()
        if obs is None:
            self.get_logger().error("No observation received!")
            return False

        self._log_observation(obs)

        # ── Phase 2: Move to a safe hover position above the task board ──
        send_feedback("Phase 2: Moving to hover position")
        hover_pose = Pose(
            position=Point(x=-0.4, y=0.0, z=0.35),
            orientation=Quaternion(x=1.0, y=0.0, z=0.0, w=0.0),
        )
        self._move_smoothly(move_robot, get_observation, hover_pose, steps=60, dt=0.05)

        # ── Phase 3: Lower toward the task board area ──
        send_feedback("Phase 3: Descending toward task board")
        approach_pose = Pose(
            position=Point(x=-0.4, y=0.0, z=0.20),
            orientation=Quaternion(x=1.0, y=0.0, z=0.0, w=0.0),
        )
        self._move_smoothly(move_robot, get_observation, approach_pose, steps=40, dt=0.05)

        # ── Phase 4: Hold position and monitor forces ──
        send_feedback("Phase 4: Holding and monitoring forces")
        start_time = self.time_now()
        hold_duration = Duration(seconds=5.0)

        while (self.time_now() - start_time) < hold_duration:
            obs = get_observation()
            if obs is not None:
                fx = obs.wrist_wrench.wrench.force.x
                fy = obs.wrist_wrench.wrench.force.y
                fz = obs.wrist_wrench.wrench.force.z
                force_mag = np.sqrt(fx**2 + fy**2 + fz**2)

                if force_mag > 15.0:
                    self.get_logger().warn(
                        f"High force detected: {force_mag:.1f}N "
                        f"(fx={fx:.1f}, fy={fy:.1f}, fz={fz:.1f})"
                    )

            self.set_pose_target(move_robot=move_robot, pose=approach_pose)
            self.sleep_for(0.1)

        # ── Phase 5: Return to hover ──
        send_feedback("Phase 5: Returning to hover")
        self._move_smoothly(move_robot, get_observation, hover_pose, steps=40, dt=0.05)

        self.get_logger().info("AutomatonV0.insert_cable() complete.")
        send_feedback("Done")
        return True

    def _log_observation(self, obs: Observation) -> None:
        """Log a summary of the current observation."""
        # Joint positions
        joint_names = list(obs.joint_states.name)
        joint_positions = list(obs.joint_states.position)
        self.get_logger().info(f"Joints: {dict(zip(joint_names, [f'{p:.3f}' for p in joint_positions]))}")

        # Wrist wrench
        f = obs.wrist_wrench.wrench.force
        t = obs.wrist_wrench.wrench.torque
        force_mag = np.sqrt(f.x**2 + f.y**2 + f.z**2)
        self.get_logger().info(
            f"Wrench: force=({f.x:.2f}, {f.y:.2f}, {f.z:.2f}) |F|={force_mag:.2f}N, "
            f"torque=({t.x:.2f}, {t.y:.2f}, {t.z:.2f})"
        )

        # Camera image sizes
        self.get_logger().info(
            f"Cameras: left={obs.left_image.width}x{obs.left_image.height}, "
            f"center={obs.center_image.width}x{obs.center_image.height}, "
            f"right={obs.right_image.width}x{obs.right_image.height}"
        )

        # Controller state
        cs = obs.controller_state
        self.get_logger().info(
            f"TCP pose: ({cs.tcp_pose.position.x:.3f}, "
            f"{cs.tcp_pose.position.y:.3f}, {cs.tcp_pose.position.z:.3f})"
        )

    def _move_smoothly(
        self,
        move_robot: MoveRobotCallback,
        get_observation: GetObservationCallback,
        target_pose: Pose,
        steps: int = 50,
        dt: float = 0.05,
    ) -> None:
        """Move toward target_pose over `steps` iterations, reading observations along the way."""
        obs = get_observation()
        if obs is None:
            for _ in range(steps):
                self.set_pose_target(move_robot=move_robot, pose=target_pose)
                self.sleep_for(dt)
            return

        # Get current TCP pose from controller state
        current = obs.controller_state.tcp_pose

        for i in range(steps):
            frac = (i + 1) / steps

            # Linear interpolation of position
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
