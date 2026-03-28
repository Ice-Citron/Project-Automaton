#!/usr/bin/env python3
"""
Extract body positions from MuJoCo and auto-generate Isaac Lab env config.

v2: Uses both position AND rotation from known correspondences.
Also accounts for the fact that the Isaac Lab board is at z=0 (ground level)
while MuJoCo board is at z=1.14 (on a table).

The key insight: Isaac Lab's scene has:
- aic_scene (enclosure) at pos=(0, 0, -1.15)
- task_board at pos=(0.2837, 0.229, 0.0)
- Components placed relative to the board in Isaac Lab world frame

MuJoCo's scene has:
- Everything at absolute world positions (board at 0.15, -0.2, 1.14)

The transform is: IL_pos = R @ (MJ_pos - MJ_board_pos) + IL_board_pos
i.e., positions are RELATIVE to the board, with a rotation between frames.
"""

import mujoco
import numpy as np
import json
import os

SCENE_XML = os.path.expanduser(
    "~/projects/Project-Automaton/References/aic/aic_utils/aic_mujoco/mjcf/scene.xml"
)

# Known Isaac Lab positions (from NVIDIA env config)
IL_BOARD_POS = np.array([0.2837, 0.229, 0.0])
IL_SC_PORT_POS = np.array([0.2904, 0.1928, 0.005])
IL_SC_PORT_ROT = np.array([0.73136, 0.0, 0.0, -0.682])  # (w,x,y,z)
IL_NIC_POS = np.array([0.25135, 0.25229, 0.0743])

# Offsets from board in Isaac Lab
IL_SC_OFFSET = IL_SC_PORT_POS - IL_BOARD_POS  # (0.0067, -0.0362, 0.005)
IL_NIC_OFFSET = IL_NIC_POS - IL_BOARD_POS     # (-0.03235, 0.02329, 0.0743)


def quat_to_mat(q):
    w, x, y, z = q / np.linalg.norm(q)
    return np.array([
        [1 - 2*(y*y + z*z), 2*(x*y - z*w), 2*(x*z + y*w)],
        [2*(x*y + z*w), 1 - 2*(x*x + z*z), 2*(y*z - x*w)],
        [2*(x*z - y*w), 2*(y*z + x*w), 1 - 2*(x*x + y*y)],
    ])


def mat_to_quat(R):
    tr = R[0, 0] + R[1, 1] + R[2, 2]
    if tr > 0:
        s = 0.5 / np.sqrt(tr + 1.0)
        w = 0.25 / s
        x = (R[2, 1] - R[1, 2]) * s
        y = (R[0, 2] - R[2, 0]) * s
        z = (R[1, 0] - R[0, 1]) * s
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = 2.0 * np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2])
        w = (R[2, 1] - R[1, 2]) / s
        x = 0.25 * s
        y = (R[0, 1] + R[1, 0]) / s
        z = (R[0, 2] + R[2, 0]) / s
    elif R[1, 1] > R[2, 2]:
        s = 2.0 * np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2])
        w = (R[0, 2] - R[2, 0]) / s
        x = (R[0, 1] + R[1, 0]) / s
        y = 0.25 * s
        z = (R[1, 2] + R[2, 1]) / s
    else:
        s = 2.0 * np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1])
        w = (R[1, 0] - R[0, 1]) / s
        x = (R[0, 2] + R[2, 0]) / s
        y = (R[1, 2] + R[2, 1]) / s
        z = 0.25 * s
    q = np.array([w, x, y, z])
    if q[0] < 0:
        q = -q
    return q / np.linalg.norm(q)


def quat_mul(q1, q2):
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    return np.array([
        w1*w2 - x1*x2 - y1*y2 - z1*z2,
        w1*x2 + x1*w2 + y1*z2 - z1*y2,
        w1*y2 - x1*z2 + y1*w2 + z1*x2,
        w1*z2 + x1*y2 - y1*x2 + z1*w2,
    ])


def main():
    print("Loading MuJoCo scene...")
    model = mujoco.MjModel.from_xml_path(SCENE_XML)
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)

    # Get MuJoCo positions
    mj = {}
    for i in range(model.nbody):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i)
        if name:
            mj[name] = {
                "pos": data.xpos[i].copy(),
                "quat": data.xquat[i].copy(),
            }

    # MuJoCo board position
    mj_board_pos = mj["task_board_base_link"]["pos"]
    mj_board_quat = mj["task_board_base_link"]["quat"]
    mj_sc_pos = mj["sc_port_0::sc_port_link"]["pos"]
    mj_sc_quat = mj["sc_port_0::sc_port_link"]["quat"]
    mj_nic_pos = mj["nic_card_mount_0::nic_card_mount_link"]["pos"]

    print(f"MJ board: pos={mj_board_pos}")
    print(f"MJ SC:    pos={mj_sc_pos}")
    print(f"MJ NIC:   pos={mj_nic_pos}")

    # Compute board-relative positions in MuJoCo
    R_mj_board = quat_to_mat(mj_board_quat)
    mj_sc_offset = R_mj_board.T @ (mj_sc_pos - mj_board_pos)
    mj_nic_offset = R_mj_board.T @ (mj_nic_pos - mj_board_pos)

    print(f"\nMJ board-relative SC offset:  {mj_sc_offset}")
    print(f"MJ board-relative NIC offset: {mj_nic_offset}")
    print(f"IL board-relative SC offset:  {IL_SC_OFFSET}")
    print(f"IL board-relative NIC offset: {IL_NIC_OFFSET}")

    # Now find the rotation R that maps MJ board-relative offsets to IL board-relative offsets
    # IL_offset = R @ MJ_offset
    # Use SVD on the two offset pairs
    mj_offsets = np.array([mj_sc_offset, mj_nic_offset])
    il_offsets = np.array([IL_SC_OFFSET, IL_NIC_OFFSET])

    # Procrustes with 2 points — constrain to proper rotation
    H = mj_offsets.T @ il_offsets
    U, S, Vt = np.linalg.svd(H)
    d = np.linalg.det(Vt.T @ U.T)
    R_board = Vt.T @ np.diag([1, 1, d]) @ U.T

    print(f"\nBoard-frame rotation R:")
    print(R_board)

    # Verify
    for name, mj_off, il_off in [("SC", mj_sc_offset, IL_SC_OFFSET),
                                   ("NIC", mj_nic_offset, IL_NIC_OFFSET)]:
        predicted = R_board @ mj_off
        err = np.linalg.norm(predicted - il_off)
        print(f"  {name}: predicted={predicted}, actual={il_off}, error={err:.6f}m")

    # Also compute the board rotation mapping (MJ board quat → IL board quat)
    # IL has board at identity rotation (rot not specified, defaults to (1,0,0,0))
    # MJ has board at mj_board_quat
    # The full transform for any body:
    #   1. Get body pos/quat in MuJoCo world
    #   2. Convert to board-relative: offset = R_mj_board.T @ (pos - board_pos)
    #   3. Transform to IL board-relative: il_offset = R_board @ offset
    #   4. Convert to IL world: il_pos = IL_board_pos + il_offset

    # For rotations:
    #   1. Get body quat relative to board: q_rel = conj(board_quat) * body_quat
    #   2. Transform: il_q_rel = R_board_quat * q_rel
    #   3. Convert to IL world: il_quat = il_board_quat * il_q_rel
    # Since IL board quat ≈ identity: il_quat ≈ R_board_quat * q_rel

    R_board_quat = mat_to_quat(R_board)
    print(f"\nR_board as quat: {R_board_quat}")

    # Verify SC port rotation
    mj_sc_q_rel = quat_mul(
        np.array([mj_board_quat[0], -mj_board_quat[1], -mj_board_quat[2], -mj_board_quat[3]]),
        mj_sc_quat
    )
    il_sc_q_predicted = quat_mul(R_board_quat, mj_sc_q_rel)
    # Normalize sign
    if il_sc_q_predicted[0] < 0:
        il_sc_q_predicted = -il_sc_q_predicted
    il_sc_q_actual = IL_SC_PORT_ROT / np.linalg.norm(IL_SC_PORT_ROT)
    if il_sc_q_actual[0] < 0:
        il_sc_q_actual = -il_sc_q_actual
    print(f"\nSC port rotation check:")
    print(f"  Predicted: {il_sc_q_predicted}")
    print(f"  Actual:    {il_sc_q_actual}")
    print(f"  Error:     {np.linalg.norm(il_sc_q_predicted - il_sc_q_actual):.6f}")

    # Now transform ALL components
    print(f"\n{'='*70}")
    print(f"AUTO-GENERATED ISAAC LAB POSITIONS")
    print(f"{'='*70}")

    results = {}
    board_children = []
    for name in sorted(mj.keys()):
        if not any(kw in name for kw in [
            "task_board", "sc_port", "nic_card", "sfp_mount",
            "lc_mount", "sc_mount", "cable", "plug", "sfp_module",
            "sc_tip", "sfp_tip", "lc_plug", "sc_plug",
        ]):
            continue

        body = mj[name]
        mj_pos = body["pos"]
        mj_quat = body["quat"]

        # Board-relative offset in MuJoCo frame
        mj_offset = R_mj_board.T @ (mj_pos - mj_board_pos)
        # Transform to IL frame
        il_offset = R_board @ mj_offset
        # IL world position
        il_pos = IL_BOARD_POS + il_offset

        # Rotation
        mj_q_rel = quat_mul(
            np.array([mj_board_quat[0], -mj_board_quat[1], -mj_board_quat[2], -mj_board_quat[3]]),
            mj_quat
        )
        il_quat = quat_mul(R_board_quat, mj_q_rel)
        if il_quat[0] < 0:
            il_quat = -il_quat

        pos_str = f"({il_pos[0]:.5f}, {il_pos[1]:.5f}, {il_pos[2]:.5f})"
        rot_str = f"({il_quat[0]:.5f}, {il_quat[1]:.5f}, {il_quat[2]:.5f}, {il_quat[3]:.5f})"

        print(f"  {name}:")
        print(f"    pos={pos_str}, rot={rot_str}")

        results[name] = {
            "pos": [round(x, 5) for x in il_pos.tolist()],
            "rot": [round(x, 5) for x in il_quat.tolist()],
            "mj_board_offset": [round(x, 5) for x in mj_offset.tolist()],
        }

    # Save
    out_path = os.path.expanduser(
        "~/projects/Project-Automaton/Intrinsic-AI/data/mujoco/isaac_lab_positions.json"
    )
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to {out_path}")

    # Generate Python code snippet for env config
    print(f"\n{'='*70}")
    print("PYTHON CODE FOR aic_task_env_cfg.py:")
    print(f"{'='*70}")
    for name, data in results.items():
        if "mount_rail" in name or "sfp_mount" in name or "lc_mount" in name or "sc_mount" in name:
            # Skip rails, we care about the actual components
            continue
        safe_name = name.replace("::", "__").replace("-", "_")
        p = data["pos"]
        r = data["rot"]
        if "task_board" in name:
            continue  # Already defined
        print(f"""
    # {name}
    # {safe_name} = RigidObjectCfg(
    #     prim_path="{{ENV_REGEX_NS}}/{safe_name}",
    #     spawn=sim_utils.UsdFileCfg(
    #         usd_path=os.path.join(AIC_PARTS_DIR, "...", "....usd"),
    #         rigid_props=sim_utils.RigidBodyPropertiesCfg(kinematic_enabled=True),
    #     ),
    #     init_state=RigidObjectCfg.InitialStateCfg(
    #         pos=({p[0]}, {p[1]}, {p[2]}),
    #         rot=({r[0]}, {r[1]}, {r[2]}, {r[3]}),
    #     ),
    # )""")


if __name__ == "__main__":
    main()
