#!/usr/bin/env python3
"""
Trigger insert_cable action on aic_model without aic_engine.

Per GPT 5.4 Pro's analysis:
- aic_model should NOT finalize after a successful goal
- Just configure → activate → send goal
- If stuck in finalized, restart aic_model process

Usage:
  source ~/ws_aic/install/setup.bash
  export RMW_IMPLEMENTATION=rmw_zenoh_cpp
  export ZENOH_ROUTER_CHECK_ATTEMPTS=10
  python3 trigger_policy.py
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from lifecycle_msgs.srv import ChangeState, GetState
from lifecycle_msgs.msg import Transition
from aic_task_interfaces.action import InsertCable
from aic_task_interfaces.msg import Task
import time


class PolicyTrigger(Node):
    def __init__(self):
        super().__init__("policy_trigger")
        self.get_logger().info("PolicyTrigger starting...")

        self.configure_client = self.create_client(
            ChangeState, "/aic_model/change_state"
        )
        self.get_state_client = self.create_client(
            GetState, "/aic_model/get_state"
        )
        self.action_client = ActionClient(
            self, InsertCable, "/insert_cable"
        )

    def get_lifecycle_state(self):
        req = GetState.Request()
        future = self.get_state_client.call_async(req)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)
        if future.result() is not None:
            state = future.result().current_state
            self.get_logger().info(f"aic_model state: {state.label} (id={state.id})")
            return state.id
        return -1

    def transition(self, transition_id, label):
        self.get_logger().info(f"Transitioning: {label}")
        req = ChangeState.Request()
        req.transition = Transition()
        req.transition.id = transition_id
        future = self.configure_client.call_async(req)
        rclpy.spin_until_future_complete(self, future, timeout_sec=10.0)
        if future.result() and future.result().success:
            self.get_logger().info(f"{label} succeeded")
            return True
        self.get_logger().error(f"{label} failed")
        return False

    def ensure_active(self):
        """Get aic_model to active state from whatever state it's in."""
        state = self.get_lifecycle_state()

        # Already active
        if state == 3:
            return True

        # Active → deactivate → cleanup → configure → activate
        if state == 3:
            self.transition(Transition.TRANSITION_DEACTIVATE, "deactivate")
            state = 2

        if state == 2:  # inactive
            self.transition(Transition.TRANSITION_CLEANUP, "cleanup")
            time.sleep(0.5)
            state = 1

        if state == 1:  # unconfigured
            if not self.transition(Transition.TRANSITION_CONFIGURE, "configure"):
                return False
            time.sleep(1)
            if not self.transition(Transition.TRANSITION_ACTIVATE, "activate"):
                return False
            return True

        if state == 4:  # finalized — terminal, must restart
            self.get_logger().error(
                "aic_model is FINALIZED (terminal state). "
                "Restart terminal 3 (ros2 run aic_model aic_model ...)"
            )
            return False

        self.get_logger().error(f"Unknown state: {state}")
        return False

    def send_goal(self):
        self.get_logger().info("Waiting for /insert_cable action server...")
        if not self.action_client.wait_for_server(timeout_sec=10.0):
            self.get_logger().error("Action server not available!")
            return

        goal = InsertCable.Goal()
        goal.task = Task()
        goal.task.id = "mujoco_test"
        goal.task.cable_type = "sfp_sc_cable"
        goal.task.cable_name = "sfp_sc"
        goal.task.plug_type = "sfp"
        goal.task.plug_name = "sfp_module"
        goal.task.port_type = "sfp"
        goal.task.port_name = "sfp_port_0"
        goal.task.target_module_name = "nic_card_mount_0"
        goal.task.time_limit = 60

        self.get_logger().info(
            f"Sending goal: {goal.task.plug_name} → {goal.task.port_name}"
        )

        future = self.action_client.send_goal_async(
            goal, feedback_callback=self.feedback_cb
        )
        rclpy.spin_until_future_complete(self, future, timeout_sec=10.0)

        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error("Goal REJECTED!")
            return

        self.get_logger().info("Goal accepted, waiting for result...")
        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future, timeout_sec=120.0)

        if result_future.result() is not None:
            r = result_future.result().result
            self.get_logger().info(f"Result: success={r.success}, message={r.message}")
        else:
            self.get_logger().warn("No result (timeout)")

    def feedback_cb(self, msg):
        self.get_logger().info(f"Feedback: {msg.feedback.message}")

    def run(self):
        if not self.configure_client.wait_for_service(timeout_sec=30.0):
            self.get_logger().error("aic_model services not found")
            return

        if not self.ensure_active():
            return

        self.send_goal()


def main():
    rclpy.init()
    node = PolicyTrigger()
    try:
        node.run()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
