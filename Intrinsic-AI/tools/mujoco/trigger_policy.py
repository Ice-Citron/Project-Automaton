#!/usr/bin/env python3
"""
Trigger the insert_cable action on aic_model without aic_engine.

This script:
1. Configures the aic_model lifecycle node
2. Activates it
3. Sends an InsertCable action goal
4. Prints feedback and result

Usage:
  source ~/ws_aic/install/setup.bash
  export RMW_IMPLEMENTATION=rmw_zenoh_cpp
  export ZENOH_ROUTER_CHECK_ATTEMPTS=10
  python3 ~/projects/Project-Automaton/Intrinsic-AI/tools/mujoco/trigger_policy.py
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

        # Lifecycle client for aic_model
        self.configure_client = self.create_client(
            ChangeState, "/aic_model/change_state"
        )
        self.get_state_client = self.create_client(
            GetState, "/aic_model/get_state"
        )

        # Action client for insert_cable
        self.action_client = ActionClient(
            self, InsertCable, "/insert_cable"
        )

    def wait_for_services(self, timeout=30.0):
        self.get_logger().info("Waiting for aic_model services...")
        if not self.configure_client.wait_for_service(timeout_sec=timeout):
            self.get_logger().error("aic_model change_state service not available")
            return False
        self.get_logger().info("Services found!")
        return True

    def get_lifecycle_state(self):
        req = GetState.Request()
        future = self.get_state_client.call_async(req)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)
        if future.result() is not None:
            state = future.result().current_state
            self.get_logger().info(f"Current state: {state.label} (id={state.id})")
            return state.id
        return -1

    def configure_node(self):
        self.get_logger().info("Configuring aic_model...")
        req = ChangeState.Request()
        req.transition = Transition()
        req.transition.id = Transition.TRANSITION_CONFIGURE
        future = self.configure_client.call_async(req)
        rclpy.spin_until_future_complete(self, future, timeout_sec=10.0)
        if future.result() and future.result().success:
            self.get_logger().info("Configured!")
            return True
        self.get_logger().error("Failed to configure")
        return False

    def activate_node(self):
        self.get_logger().info("Activating aic_model...")
        req = ChangeState.Request()
        req.transition = Transition()
        req.transition.id = Transition.TRANSITION_ACTIVATE
        future = self.configure_client.call_async(req)
        rclpy.spin_until_future_complete(self, future, timeout_sec=10.0)
        if future.result() and future.result().success:
            self.get_logger().info("Activated!")
            return True
        self.get_logger().error("Failed to activate")
        return False

    def send_insert_cable_goal(self):
        self.get_logger().info("Waiting for insert_cable action server...")
        if not self.action_client.wait_for_server(timeout_sec=10.0):
            self.get_logger().error("Action server not available")
            return

        goal = InsertCable.Goal()
        goal.task = Task()
        goal.task.id = "mujoco_test_1"
        goal.task.cable_type = "sfp_sc_cable"
        goal.task.cable_name = "sfp_sc"
        goal.task.plug_type = "sfp"
        goal.task.plug_name = "sfp_module"
        goal.task.port_type = "sfp"
        goal.task.port_name = "sfp_port_0"
        goal.task.target_module_name = "nic_card_0"
        goal.task.time_limit = 60

        self.get_logger().info(f"Sending InsertCable goal: {goal.task.plug_name} → {goal.task.port_name}")

        future = self.action_client.send_goal_async(
            goal, feedback_callback=self.feedback_callback
        )
        rclpy.spin_until_future_complete(self, future, timeout_sec=10.0)

        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error("Goal was rejected!")
            return

        self.get_logger().info("Goal accepted! Waiting for result...")
        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future, timeout_sec=120.0)

        if result_future.result() is not None:
            result = result_future.result().result
            self.get_logger().info(f"Result: success={result.success}, message={result.message}")
        else:
            self.get_logger().warn("No result received (timeout?)")

    def feedback_callback(self, feedback_msg):
        self.get_logger().info(f"Feedback: {feedback_msg.feedback.message}")

    def run(self):
        if not self.wait_for_services():
            return

        # Check current state
        state = self.get_lifecycle_state()

        # Configure if unconfigured (state 1 = unconfigured)
        if state == 1:
            if not self.configure_node():
                return
            time.sleep(1)

        # Activate if inactive (state 2 = inactive)
        state = self.get_lifecycle_state()
        if state == 2:
            if not self.activate_node():
                return
            time.sleep(1)

        # Send the goal
        self.send_insert_cable_goal()


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
