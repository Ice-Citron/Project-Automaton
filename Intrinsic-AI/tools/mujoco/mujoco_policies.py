#!/usr/bin/env python3
"""
Standalone MuJoCo policy runner for AIC scene.

Runs WaveArm and CheatCode-like policies directly in MuJoCo
without ROS 2 — purely MuJoCo Python API.

Usage (from AIC workspace):
  cd ~/projects/Project-Automaton/References/aic
  pixi run python3 ~/projects/Project-Automaton/Intrinsic-AI/mujoco_policies.py --policy wavearm
  pixi run python3 ~/projects/Project-Automaton/Intrinsic-AI/mujoco_policies.py --policy cheatcode
  pixi run python3 ~/projects/Project-Automaton/Intrinsic-AI/mujoco_policies.py --policy interactive
"""

import argparse
import time
import numpy as np
import mujoco
import mujoco.viewer


SCENE_PATH = None  # Set dynamically


def get_scene_path():
    """Find the scene.xml relative to AIC workspace."""
    import os
    candidates = [
        os.path.expanduser("~/projects/Project-Automaton/References/aic/aic_utils/aic_mujoco/mjcf/scene.xml"),
        "aic_utils/aic_mujoco/mjcf/scene.xml",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    raise FileNotFoundError("Could not find scene.xml")


def get_joint_ids(model):
    """Get joint IDs for UR5e arm joints."""
    joint_names = [
        "shoulder_pan_joint",
        "shoulder_lift_joint",
        "elbow_joint",
        "wrist_1_joint",
        "wrist_2_joint",
        "wrist_3_joint",
    ]
    ids = []
    for name in joint_names:
        jid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
        if jid == -1:
            print(f"Warning: joint '{name}' not found")
        ids.append(jid)
    return joint_names, ids


def get_actuator_ids(model):
    """Get actuator IDs for UR5e arm."""
    act_names = []
    act_ids = []
    for i in range(model.nu):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i)
        if name:
            act_names.append(name)
            act_ids.append(i)
    return act_names, act_ids


def get_tcp_pos(model, data):
    """Get the TCP (tool center point) position."""
    # Try to find the TCP site
    tcp_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "gripper_tcp")
    if tcp_id == -1:
        tcp_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "tcp")
    if tcp_id == -1:
        # Fallback: look for any site with "tcp" in the name
        for i in range(model.nsite):
            name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_SITE, i)
            if name and "tcp" in name.lower():
                tcp_id = i
                break
    if tcp_id >= 0:
        return data.site_xpos[tcp_id].copy()
    return np.zeros(3)


def get_body_pos(model, data, body_name):
    """Get a body's position."""
    bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, body_name)
    if bid >= 0:
        return data.xpos[bid].copy()
    return None


def print_scene_info(model, data):
    """Print useful scene information."""
    print(f"\n{'='*60}")
    print(f"MUJOCO SCENE INFO")
    print(f"{'='*60}")
    print(f"Bodies: {model.nbody}")
    print(f"Joints: {model.njnt}")
    print(f"Actuators: {model.nu}")
    print(f"DOFs: {model.nv}")
    print(f"Timestep: {model.opt.timestep}s")

    joint_names, joint_ids = get_joint_ids(model)
    print(f"\nUR5e Joint Positions:")
    for name, jid in zip(joint_names, joint_ids):
        if jid >= 0:
            qpos_addr = model.jnt_qposadr[jid]
            print(f"  {name}: {data.qpos[qpos_addr]:.4f} rad ({np.degrees(data.qpos[qpos_addr]):.1f} deg)")

    act_names, act_ids = get_actuator_ids(model)
    print(f"\nActuators:")
    for name, aid in zip(act_names, act_ids):
        print(f"  [{aid}] {name}: ctrl={data.ctrl[aid]:.4f}")

    tcp_pos = get_tcp_pos(model, data)
    print(f"\nTCP position: ({tcp_pos[0]:.4f}, {tcp_pos[1]:.4f}, {tcp_pos[2]:.4f})")

    # Find port bodies
    print(f"\nLooking for port/plug bodies:")
    for i in range(model.nbody):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i)
        if name and any(k in name.lower() for k in ["port", "plug", "sc_", "sfp", "nic", "board"]):
            pos = data.xpos[i]
            print(f"  {name}: ({pos[0]:.4f}, {pos[1]:.4f}, {pos[2]:.4f})")

    print(f"{'='*60}\n")


# ============================================================
# POLICIES
# ============================================================

HOME_QPOS = np.array([-0.1597, -1.3542, -1.6648, -1.6933, 1.5710, 1.4110])


def set_joint_targets(data, joint_ids, model, targets, kp=200.0, kd=20.0):
    """PD control to drive joints to target positions.

    Uses per-joint gains scaled by typical UR5e torque requirements:
    shoulder/elbow joints need more torque than wrist joints.
    """
    # Per-joint gain multipliers (shoulder > elbow > wrist)
    joint_scales = [1.5, 2.0, 1.5, 0.5, 0.5, 0.3]
    max_torque = [150.0, 150.0, 150.0, 28.0, 28.0, 28.0]

    for i, jid in enumerate(joint_ids):
        if jid < 0 or i >= len(targets):
            continue
        qpos_addr = model.jnt_qposadr[jid]
        qvel_addr = model.jnt_dofadr[jid]
        pos_error = targets[i] - data.qpos[qpos_addr]
        vel = data.qvel[qvel_addr]
        scale = joint_scales[i] if i < len(joint_scales) else 1.0
        torque = scale * kp * pos_error - scale * kd * vel
        # Clamp torque
        limit = max_torque[i] if i < len(max_torque) else 87.0
        torque = np.clip(torque, -limit, limit)
        if i < model.nu:
            data.ctrl[i] = torque


def policy_wavearm(model, data, joint_names, joint_ids, t):
    """WaveArm: wave the arm back and forth."""
    loop_seconds = 5.0
    loop_fraction = (t % loop_seconds) / loop_seconds
    wave = np.sin(2 * np.pi * loop_fraction)

    targets = HOME_QPOS.copy()
    targets[0] += 0.5 * wave       # shoulder_pan: wave left/right
    targets[1] += 0.2 * wave       # shoulder_lift: slight nod

    set_joint_targets(data, joint_ids, model, targets, kp=100.0, kd=10.0)


def policy_cheatcode(model, data, joint_names, joint_ids, t, state):
    """
    CheatCode-like: approach a target body, descend, and hold.

    Uses MuJoCo's internal body positions (equivalent to ground truth TF).
    This is the MuJoCo equivalent of CheatCode's GT-based insertion.
    """
    # Find the SC port or any insertion target
    if "target_pos" not in state:
        for i in range(model.nbody):
            name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i)
            if name and "sc_port" in name.lower():
                state["target_pos"] = data.xpos[i].copy()
                print(f"CheatCode: targeting '{name}' at {state['target_pos']}")
                break
        if "target_pos" not in state:
            # Fallback: look for any port-like body
            for i in range(model.nbody):
                name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i)
                if name and "port" in name.lower():
                    state["target_pos"] = data.xpos[i].copy()
                    print(f"CheatCode: targeting '{name}' at {state['target_pos']}")
                    break

        if "target_pos" not in state:
            print("CheatCode: no port found, using default position")
            state["target_pos"] = np.array([-0.4, 0.0, 1.3])

        state["phase"] = "approach"
        state["phase_start"] = t

    # Simple joint-space PD control
    # Phase 1 (0-5s): Move to pre-approach
    # Phase 2 (5-15s): Hold above target
    # Phase 3 (15-25s): Slowly descend
    phase_time = t - state["phase_start"]

    if state["phase"] == "approach" and phase_time < 5.0:
        # Move to a safe position above home
        approach_targets = HOME_QPOS.copy()
        approach_targets[1] = -1.2  # lift shoulder slightly
        frac = min(1.0, phase_time / 3.0)
        targets = HOME_QPOS + frac * (approach_targets - HOME_QPOS)
        set_joint_targets(data, joint_ids, model, targets, kp=100.0, kd=10.0)

    elif state["phase"] == "approach" and phase_time >= 5.0:
        state["phase"] = "hover"
        state["phase_start"] = t
        print(f"CheatCode: phase -> hover (t={t:.1f}s)")

    elif state["phase"] == "hover" and phase_time < 5.0:
        # Hold steady
        hover_targets = HOME_QPOS.copy()
        hover_targets[1] = -1.2
        set_joint_targets(data, joint_ids, model, hover_targets, kp=150.0, kd=15.0)

    elif state["phase"] == "hover" and phase_time >= 5.0:
        state["phase"] = "descend"
        state["phase_start"] = t
        state["descend_offset"] = 0.0
        print(f"CheatCode: phase -> descend (t={t:.1f}s)")

    elif state["phase"] == "descend":
        # Slowly lower the arm
        state["descend_offset"] = min(0.3, state["descend_offset"] + 0.001)
        descend_targets = HOME_QPOS.copy()
        descend_targets[1] = -1.2 + state["descend_offset"]
        descend_targets[3] = HOME_QPOS[3] - state["descend_offset"] * 0.5
        set_joint_targets(data, joint_ids, model, descend_targets, kp=80.0, kd=10.0)

        # Monitor forces
        tcp_pos = get_tcp_pos(model, data)
        if phase_time > 10.0:
            state["phase"] = "hold"
            state["phase_start"] = t
            print(f"CheatCode: phase -> hold (t={t:.1f}s), TCP at {tcp_pos}")

    elif state["phase"] == "hold":
        # Hold position for 5 seconds
        hold_targets = HOME_QPOS.copy()
        hold_targets[1] = -1.2 + state.get("descend_offset", 0)
        hold_targets[3] = HOME_QPOS[3] - state.get("descend_offset", 0) * 0.5
        set_joint_targets(data, joint_ids, model, hold_targets, kp=150.0, kd=15.0)

        if phase_time > 5.0:
            print(f"CheatCode: complete (t={t:.1f}s)")
            state["phase"] = "done"


def main():
    parser = argparse.ArgumentParser(description="MuJoCo AIC Policy Runner")
    parser.add_argument("--policy", choices=["wavearm", "cheatcode", "interactive", "info"],
                        default="info", help="Policy to run")
    parser.add_argument("--duration", type=float, default=30.0, help="Duration in seconds")
    parser.add_argument("--scene", type=str, default=None, help="Path to scene.xml")
    args = parser.parse_args()

    scene_path = args.scene or get_scene_path()
    print(f"Loading scene: {scene_path}")

    model = mujoco.MjModel.from_xml_path(scene_path)
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)

    joint_names, joint_ids = get_joint_ids(model)
    print_scene_info(model, data)

    # Initialize robot at home position (not all-zeros)
    print("Setting initial joint positions to AIC home...")
    for i, jid in enumerate(joint_ids):
        if jid >= 0 and i < len(HOME_QPOS):
            qpos_addr = model.jnt_qposadr[jid]
            data.qpos[qpos_addr] = HOME_QPOS[i]

    # Let the robot settle with gravity compensation before starting
    print("Settling for 1 second...")
    for _ in range(500):
        set_joint_targets(data, joint_ids, model, HOME_QPOS, kp=200.0, kd=20.0)
        mujoco.mj_step(model, data)
    mujoco.mj_forward(model, data)

    tcp = get_tcp_pos(model, data)
    print(f"After settling — TCP: ({tcp[0]:.3f}, {tcp[1]:.3f}, {tcp[2]:.3f})")

    if args.policy == "info":
        print("Use --policy wavearm|cheatcode|interactive to run a policy")
        return

    if args.policy == "interactive":
        print("Launching interactive viewer (no policy). Use mouse/keyboard to explore.")
        print("  Spacebar = play/pause, Backspace = reset")
        mujoco.viewer.launch(model, data)
        return

    # Run policy with viewer
    cheatcode_state = {}
    step_count = 0

    with mujoco.viewer.launch_passive(model, data) as viewer:
        start = time.time()
        while viewer.is_running() and (time.time() - start) < args.duration:
            t = time.time() - start

            if args.policy == "wavearm":
                policy_wavearm(model, data, joint_names, joint_ids, t)
            elif args.policy == "cheatcode":
                policy_cheatcode(model, data, joint_names, joint_ids, t, cheatcode_state)

            mujoco.mj_step(model, data)
            step_count += 1

            # Sync viewer at ~60Hz (every ~33 physics steps at 0.002s timestep)
            if step_count % 33 == 0:
                viewer.sync()

            # Print status every 5 seconds
            if step_count % 2500 == 0:
                tcp = get_tcp_pos(model, data)
                print(f"  t={t:.1f}s  TCP=({tcp[0]:.3f}, {tcp[1]:.3f}, {tcp[2]:.3f})")

    print(f"\nPolicy '{args.policy}' finished after {time.time() - start:.1f}s")


if __name__ == "__main__":
    main()
