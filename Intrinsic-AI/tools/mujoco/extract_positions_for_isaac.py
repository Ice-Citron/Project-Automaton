#!/usr/bin/env python3
"""
Extract all body positions from MuJoCo scene and output them for Isaac Lab.

MuJoCo's MJCF (from sdf2mjcf) has all components at correct positions.
This script reads those positions and computes the coordinate transform
to Isaac Lab's frame, so we can auto-generate the env config.

Usage:
  cd ~/projects/Project-Automaton/References/aic
  pixi run python3 ~/projects/Project-Automaton/Intrinsic-AI/tools/mujoco/extract_positions_for_isaac.py
"""

import mujoco
import numpy as np
import json
import os

SCENE_XML = os.path.expanduser(
    "~/projects/Project-Automaton/References/aic/aic_utils/aic_mujoco/mjcf/scene.xml"
)

# Known-good Isaac Lab positions (from NVIDIA-prepared env config)
ISAAC_KNOWN = {
    "task_board_base_link": {"pos": (0.2837, 0.229, 0.0), "rot": (1.0, 0.0, 0.0, 0.0)},
    "sc_port_0::sc_port_link": {"pos": (0.2904, 0.1928, 0.005), "rot": (0.73136, 0.0, 0.0, -0.682)},
    "nic_card_mount_0::nic_card_mount_link": {"pos": (0.25135, 0.25229, 0.0743), "rot": (1.0, 0.0, 0.0, 0.0)},
}


def quat_to_mat(q):
    """MuJoCo quat (w,x,y,z) to 3x3 rotation matrix."""
    w, x, y, z = q / np.linalg.norm(q)
    return np.array([
        [1 - 2*(y*y + z*z), 2*(x*y - z*w), 2*(x*z + y*w)],
        [2*(x*y + z*w), 1 - 2*(x*x + z*z), 2*(y*z - x*w)],
        [2*(x*z - y*w), 2*(y*z + x*w), 1 - 2*(x*x + y*y)],
    ])


def mat_to_quat(R):
    """3x3 rotation matrix to quat (w,x,y,z)."""
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


def compute_transform(mj_positions, isaac_positions):
    """
    Compute the affine transform T (rotation + translation) that maps
    MuJoCo world positions to Isaac Lab world positions.

    Uses least-squares fit from known-good correspondences.
    """
    mj_pts = np.array(mj_positions)
    il_pts = np.array(isaac_positions)

    # Compute centroids
    mj_c = mj_pts.mean(axis=0)
    il_c = il_pts.mean(axis=0)

    # Center
    mj_centered = mj_pts - mj_c
    il_centered = il_pts - il_c

    # Compute rotation using SVD (Procrustes)
    H = mj_centered.T @ il_centered
    U, S, Vt = np.linalg.svd(H)
    d = np.linalg.det(Vt.T @ U.T)
    D = np.diag([1, 1, d])  # Ensure proper rotation
    R = Vt.T @ D @ U.T

    # Compute translation
    t = il_c - R @ mj_c

    return R, t


def main():
    print("Loading MuJoCo scene...")
    model = mujoco.MjModel.from_xml_path(SCENE_XML)
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)

    # Extract all body positions from MuJoCo
    print("\n=== MuJoCo Body Positions ===")
    mj_bodies = {}
    for i in range(model.nbody):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i)
        if name:
            pos = data.xpos[i].copy()
            quat = data.xquat[i].copy()
            mj_bodies[name] = {"pos": pos, "quat": quat}

    # Print key bodies
    key_bodies = [
        "task_board_base_link",
        "sc_port_0::sc_port_link",
        "nic_card_mount_0::nic_card_mount_link",
    ]
    for name in key_bodies:
        if name in mj_bodies:
            b = mj_bodies[name]
            print(f"  {name}: pos=({b['pos'][0]:.5f}, {b['pos'][1]:.5f}, {b['pos'][2]:.5f})")

    # Compute MuJoCo → Isaac Lab transform from known correspondences
    mj_pts = []
    il_pts = []
    for name, isaac_data in ISAAC_KNOWN.items():
        if name in mj_bodies:
            mj_pts.append(mj_bodies[name]["pos"])
            il_pts.append(np.array(isaac_data["pos"]))

    if len(mj_pts) < 2:
        print("ERROR: Not enough correspondences to compute transform!")
        return

    R, t = compute_transform(mj_pts, il_pts)

    print(f"\n=== MuJoCo → Isaac Lab Transform ===")
    print(f"Rotation matrix:\n{R}")
    print(f"Translation: {t}")

    # Verify on known points
    print(f"\n=== Verification ===")
    for name, isaac_data in ISAAC_KNOWN.items():
        if name in mj_bodies:
            mj_pos = mj_bodies[name]["pos"]
            predicted = R @ mj_pos + t
            actual = np.array(isaac_data["pos"])
            error = np.linalg.norm(predicted - actual)
            print(f"  {name}:")
            print(f"    MJ:        ({mj_pos[0]:.5f}, {mj_pos[1]:.5f}, {mj_pos[2]:.5f})")
            print(f"    Predicted: ({predicted[0]:.5f}, {predicted[1]:.5f}, {predicted[2]:.5f})")
            print(f"    Actual IL: ({actual[0]:.5f}, {actual[1]:.5f}, {actual[2]:.5f})")
            print(f"    Error:     {error:.6f}m")

    # Now transform ALL task board components to Isaac Lab frame
    print(f"\n=== ALL Components in Isaac Lab Frame ===")
    board_components = [name for name in mj_bodies
                        if any(kw in name for kw in [
                            "task_board", "sc_port", "nic_card",
                            "sfp_mount", "lc_mount", "sc_mount",
                            "cable", "plug", "sfp_module",
                        ])]

    results = {}
    for name in sorted(board_components):
        mj_pos = mj_bodies[name]["pos"]
        mj_quat = mj_bodies[name]["quat"]
        il_pos = R @ mj_pos + t

        # Transform quaternion: R_il = R_transform @ R_mj
        R_mj = quat_to_mat(mj_quat)
        R_il = R @ R_mj
        il_quat = mat_to_quat(R_il)

        print(f"  {name}:")
        print(f"    pos=({il_pos[0]:.5f}, {il_pos[1]:.5f}, {il_pos[2]:.5f})")
        print(f"    rot=({il_quat[0]:.5f}, {il_quat[1]:.5f}, {il_quat[2]:.5f}, {il_quat[3]:.5f})")

        results[name] = {
            "pos": il_pos.tolist(),
            "rot": il_quat.tolist(),
        }

    # Save results
    out_path = os.path.expanduser(
        "~/projects/Project-Automaton/Intrinsic-AI/data/mujoco/isaac_lab_positions.json"
    )
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
