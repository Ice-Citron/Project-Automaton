#!/usr/bin/env python3
"""
Standalone MuJoCo policy runner for AIC scene.

Runs WaveArm and CheatCode-like policies directly in MuJoCo
without ROS 2 — purely MuJoCo Python API.

Usage (from AIC workspace):
  cd ~/projects/Project-Automaton/References/aic
  pixi run python3 ~/projects/Project-Automaton/Intrinsic-AI/tools/mujoco/mujoco_policies.py --policy wavearm
  pixi run python3 ~/projects/Project-Automaton/Intrinsic-AI/tools/mujoco/mujoco_policies.py --policy cheatcode
  pixi run python3 ~/projects/Project-Automaton/Intrinsic-AI/tools/mujoco/mujoco_policies.py --policy interactive
"""

import argparse
import time
import numpy as np
import mujoco
import mujoco.viewer


def get_scene_path():
    import os
    candidates = [
        os.path.expanduser("~/projects/Project-Automaton/References/aic/aic_utils/aic_mujoco/mjcf/scene.xml"),
        "aic_utils/aic_mujoco/mjcf/scene.xml",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    raise FileNotFoundError("Could not find scene.xml")


# AIC home position for UR5e
HOME_QPOS = np.array([-0.1597, -1.3542, -1.6648, -1.6933, 1.5710, 1.4110])

# Joint indices for the 6 UR5e arm joints (set during init)
ARM_JOINT_NAMES = [
    "shoulder_pan_joint", "shoulder_lift_joint", "elbow_joint",
    "wrist_1_joint", "wrist_2_joint", "wrist_3_joint",
]


def get_joint_info(model):
    """Get joint IDs and qpos/qvel addresses for UR5e arm."""
    info = {}
    for name in ARM_JOINT_NAMES:
        jid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
        if jid >= 0:
            info[name] = {
                "id": jid,
                "qpos_addr": model.jnt_qposadr[jid],
                "qvel_addr": model.jnt_dofadr[jid],
            }
    return info


def get_arm_qpos(model, data, joint_info):
    """Get current arm joint positions as array."""
    return np.array([data.qpos[joint_info[n]["qpos_addr"]] for n in ARM_JOINT_NAMES])


def set_arm_qpos(model, data, joint_info, qpos):
    """Set arm joint positions directly (for initialization)."""
    for i, name in enumerate(ARM_JOINT_NAMES):
        data.qpos[joint_info[name]["qpos_addr"]] = qpos[i]


def get_tcp_pos(model, data):
    """Get TCP position."""
    sid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "gripper_tcp")
    if sid >= 0:
        return data.site_xpos[sid].copy()
    return np.zeros(3)


def get_tcp_mat(model, data):
    """Get TCP rotation matrix (3x3)."""
    sid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "gripper_tcp")
    if sid >= 0:
        return data.site_xmat[sid].reshape(3, 3).copy()
    return np.eye(3)


def setup_joint_dynamics(model):
    """Add armature and damping to joints for realistic UR5e behavior.

    Without these, the robot is infinitely stiff and unstable.
    Real UR5e motors have significant rotor inertia and friction.
    """
    armature_vals = [5.0, 5.0, 3.0, 1.0, 1.0, 0.5]  # kg*m^2 rotor inertia
    damping_vals = [10.0, 10.0, 5.0, 2.0, 2.0, 1.0]   # Nm*s/rad viscous friction

    for i, name in enumerate(ARM_JOINT_NAMES):
        jid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
        if jid >= 0:
            dof = model.jnt_dofadr[jid]
            model.dof_armature[dof] = armature_vals[i]
            model.dof_damping[dof] = damping_vals[i]


def pd_control(data, joint_info, targets, kp=300.0, kd=30.0, gravity_comp=None):
    """PD joint-space control with gravity compensation.

    The UR5e shoulder_lift needs ~17Nm and elbow needs ~27Nm just to
    counteract gravity. We add qfrc_bias as feedforward.
    """
    for i, name in enumerate(ARM_JOINT_NAMES):
        ji = joint_info[name]
        err = targets[i] - data.qpos[ji["qpos_addr"]]
        vel = data.qvel[ji["qvel_addr"]]
        # PD torque
        torque = kp * err - kd * vel
        # Add gravity compensation (feedforward)
        if gravity_comp is not None:
            torque += gravity_comp[i]
        data.ctrl[i] = torque


def get_gravity_comp(model, data, joint_info):
    """Get gravity compensation torques for arm joints."""
    return np.array([data.qfrc_bias[joint_info[n]["qvel_addr"]] for n in ARM_JOINT_NAMES])


def ik_step(model, data, joint_info, target_pos, target_quat=None, step_size=0.5):
    """One step of Jacobian-based IK toward target position.

    Returns joint position targets that move TCP toward target_pos.
    """
    tcp_sid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "gripper_tcp")
    if tcp_sid < 0:
        return get_arm_qpos(model, data, joint_info)

    current_pos = data.site_xpos[tcp_sid].copy()
    pos_error = target_pos - current_pos

    # Clamp step size
    err_norm = np.linalg.norm(pos_error)
    if err_norm > 0.05:
        pos_error = pos_error / err_norm * 0.05

    # Compute Jacobian for the TCP site
    jacp = np.zeros((3, model.nv))
    jacr = np.zeros((3, model.nv))
    mujoco.mj_jacSite(model, data, jacp, jacr, tcp_sid)

    # Extract columns for arm joints only
    arm_dof_ids = [joint_info[n]["qvel_addr"] for n in ARM_JOINT_NAMES]
    J = jacp[:, arm_dof_ids]  # 3x6 Jacobian

    # Damped least squares IK
    lam = 0.1
    JtJ = J.T @ J + lam * np.eye(6)
    dq = np.linalg.solve(JtJ, J.T @ pos_error) * step_size

    current_q = get_arm_qpos(model, data, joint_info)
    return current_q + dq


def find_target_body(model, data, keywords):
    """Find a body by keyword search."""
    for kw in keywords:
        for i in range(model.nbody):
            name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i)
            if name and kw in name.lower():
                return name, data.xpos[i].copy()
    return None, None


def print_scene_info(model, data, joint_info):
    """Print scene summary."""
    print(f"\n{'='*60}")
    print(f"MUJOCO SCENE INFO")
    print(f"{'='*60}")
    print(f"Bodies: {model.nbody}  Joints: {model.njnt}  Actuators: {model.nu}  DOFs: {model.nv}")

    q = get_arm_qpos(model, data, joint_info)
    print(f"\nArm joints: [{', '.join(f'{v:.3f}' for v in q)}]")
    print(f"TCP position: {get_tcp_pos(model, data)}")

    print(f"\nKey bodies:")
    for i in range(model.nbody):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i)
        if name and any(k in name.lower() for k in ["port", "plug", "sc_", "sfp", "nic", "board", "cable"]):
            print(f"  {name}: {data.xpos[i]}")
    print(f"{'='*60}\n")


# ============================================================
# POLICIES
# ============================================================

def policy_wavearm(model, data, joint_info, t):
    """WaveArm: oscillate shoulder joints."""
    wave = np.sin(2 * np.pi * t / 5.0)
    targets = HOME_QPOS.copy()
    targets[0] += 0.5 * wave
    targets[1] += 0.2 * wave
    gc = get_gravity_comp(model, data, joint_info)
    pd_control(data, joint_info, targets, gravity_comp=gc)


def policy_cheatcode(model, data, joint_info, t, state):
    """
    CheatCode: Jacobian IK approach + descend toward target port.

    Uses MuJoCo body positions as ground truth (equivalent to Gazebo GT TF).
    Phases:
      1. Approach: IK to position above target port
      2. Descend: Slowly lower toward port
      3. Hold: Maintain position for stabilization
    """
    # Initialize target
    if "target_pos" not in state:
        # Try to find SC port or SFP port
        name, pos = find_target_body(model, data, ["sc_port", "sfp_port", "sc_tip", "sfp_tip"])
        if pos is not None:
            state["target_pos"] = pos
            state["target_name"] = name
            print(f"CheatCode: targeting '{name}' at [{pos[0]:.3f}, {pos[1]:.3f}, {pos[2]:.3f}]")
        else:
            # Fallback to task board
            name, pos = find_target_body(model, data, ["task_board"])
            state["target_pos"] = pos if pos is not None else np.array([0.15, -0.2, 1.14])
            state["target_name"] = name or "default"
            print(f"CheatCode: no port found, targeting '{state['target_name']}' at {state['target_pos']}")

        state["phase"] = "approach"
        state["phase_start"] = t
        state["hover_height"] = 0.15  # start 15cm above target

    phase_time = t - state["phase_start"]
    target = state["target_pos"]

    if state["phase"] == "approach":
        # IK toward position above target
        above = target.copy()
        above[2] += state["hover_height"]

        tcp = get_tcp_pos(model, data)
        dist = np.linalg.norm(tcp - above)

        q_target = ik_step(model, data, joint_info, above, step_size=0.8)
        gc = get_gravity_comp(model, data, joint_info)
        pd_control(data, joint_info, q_target, kp=400.0, kd=40.0, gravity_comp=gc)

        if dist < 0.02 or phase_time > 8.0:
            state["phase"] = "descend"
            state["phase_start"] = t
            print(f"CheatCode: → descend (t={t:.1f}s, dist={dist:.3f}m)")

    elif state["phase"] == "descend":
        # Slowly lower toward target
        state["hover_height"] = max(-0.02, 0.15 - phase_time * 0.02)  # ~2cm/s descent
        descend_target = target.copy()
        descend_target[2] += state["hover_height"]

        q_target = ik_step(model, data, joint_info, descend_target, step_size=0.6)
        gc = get_gravity_comp(model, data, joint_info)
        pd_control(data, joint_info, q_target, kp=400.0, kd=40.0, gravity_comp=gc)

        tcp = get_tcp_pos(model, data)
        if state["hover_height"] <= -0.015 or phase_time > 10.0:
            state["phase"] = "hold"
            state["phase_start"] = t
            state["hold_q"] = get_arm_qpos(model, data, joint_info)
            print(f"CheatCode: → hold (t={t:.1f}s, TCP={tcp})")

    elif state["phase"] == "hold":
        # Hold final position
        gc = get_gravity_comp(model, data, joint_info)
        pd_control(data, joint_info, state["hold_q"], kp=500.0, kd=50.0, gravity_comp=gc)

        if phase_time > 5.0 and state.get("done_printed") is None:
            print(f"CheatCode: complete (t={t:.1f}s)")
            state["done_printed"] = True


def main():
    parser = argparse.ArgumentParser(description="MuJoCo AIC Policy Runner")
    parser.add_argument("--policy", choices=["wavearm", "cheatcode", "interactive", "info"],
                        default="info")
    parser.add_argument("--duration", type=float, default=30.0)
    parser.add_argument("--scene", type=str, default=None)
    args = parser.parse_args()

    scene_path = args.scene or get_scene_path()
    print(f"Loading: {scene_path}")

    model = mujoco.MjModel.from_xml_path(scene_path)
    data = mujoco.MjData(model)

    joint_info = get_joint_info(model)

    # Add realistic joint dynamics (armature + damping)
    setup_joint_dynamics(model)

    # Initialize at home position
    set_arm_qpos(model, data, joint_info, HOME_QPOS)
    mujoco.mj_forward(model, data)

    # Settle with high-gain PD + gravity compensation
    print("Settling...")
    for _ in range(1000):
        gc = get_gravity_comp(model, data, joint_info)
        pd_control(data, joint_info, HOME_QPOS, kp=500.0, kd=50.0, gravity_comp=gc)
        mujoco.mj_step(model, data)
    mujoco.mj_forward(model, data)

    print_scene_info(model, data, joint_info)

    if args.policy == "info":
        return

    if args.policy == "interactive":
        print("Interactive mode. Spacebar=play/pause, mouse to orbit.")
        mujoco.viewer.launch(model, data)
        return

    # Run policy
    state = {}
    step = 0

    with mujoco.viewer.launch_passive(model, data) as viewer:
        start = time.time()
        while viewer.is_running() and (time.time() - start) < args.duration:
            t = time.time() - start

            if args.policy == "wavearm":
                policy_wavearm(model, data, joint_info, t)
            elif args.policy == "cheatcode":
                policy_cheatcode(model, data, joint_info, t, state)

            mujoco.mj_step(model, data)
            step += 1

            if step % 33 == 0:
                viewer.sync()

            if step % 2500 == 0:
                tcp = get_tcp_pos(model, data)
                print(f"  t={t:.1f}s  TCP=({tcp[0]:.3f}, {tcp[1]:.3f}, {tcp[2]:.3f})")

    print(f"\nDone ({time.time() - start:.1f}s)")


if __name__ == "__main__":
    main()
