#!/usr/bin/env python3
"""
Compute per-mesh correction quaternions by comparing vertex data
between trimesh (GLB native) and MuJoCo (after import).

Uses covariance-based principal axis alignment to find the exact rotation.
"""

import mujoco
import trimesh
import numpy as np
from scipy.spatial.transform import Rotation
import os
import json

MJCF_DIR = os.path.expanduser(
    "~/projects/Project-Automaton/References/aic/aic_utils/aic_mujoco/mjcf"
)
GLB_DIR = os.path.expanduser(
    "~/projects/Project-Automaton/References/aic/aic_assets/models"
)

MESHES = {
    "sfp_mount":  "SFP Mount/sfp_mount_visual.glb",
    "sfp_module": "SFP Module/sfp_module_visual.glb",
    "sc_mount":   "SC Mount/sc_mount_visual.glb",
    "sc_plug":    "SC Plug/sc_plug_visual.glb",
    "lc_mount":   "LC Mount/lc_mount_visual.glb",
    "lc_plug":    "LC Plug/lc_plug_visual.glb",
}


def get_glb_data(name):
    path = os.path.join(GLB_DIR, MESHES[name])
    scene = trimesh.load(path)
    if isinstance(scene, trimesh.Scene):
        mesh = trimesh.util.concatenate(scene.dump())
    else:
        mesh = scene
    return mesh.centroid, mesh.vertices


def get_mj_data(mesh_file):
    xml = (
        '<mujoco>\n'
        f'  <compiler meshdir="{MJCF_DIR}"/>\n'
        f'  <asset><mesh name="test" file="{mesh_file}"/></asset>\n'
        '  <worldbody><geom type="mesh" mesh="test"/></worldbody>\n'
        '</mujoco>'
    )
    model = mujoco.MjModel.from_xml_string(xml)
    mesh_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_MESH, "test")
    vert_start = model.mesh_vertadr[mesh_id]
    vert_count = model.mesh_vertnum[mesh_id]
    verts = model.mesh_vert[vert_start : vert_start + vert_count].copy()
    return verts.mean(axis=0), verts


def find_rotation_covariance(glb_verts, mj_verts, glb_centroid, mj_centroid):
    """Find rotation R such that R @ glb = mj, using covariance eigendecomposition."""
    glb_c = glb_verts - glb_centroid
    mj_c = mj_verts - mj_centroid

    C_glb = (glb_c.T @ glb_c) / len(glb_verts)
    C_mj = (mj_c.T @ mj_c) / len(mj_verts)

    eig_glb, V_glb = np.linalg.eigh(C_glb)
    eig_mj, V_mj = np.linalg.eigh(C_mj)

    idx_glb = np.argsort(eig_glb)
    idx_mj = np.argsort(eig_mj)

    V_g = V_glb[:, idx_glb]
    V_m = V_mj[:, idx_mj]

    R = V_m @ V_g.T

    if np.linalg.det(R) < 0:
        V_m[:, 0] *= -1
        R = V_m @ V_g.T

    return R, eig_glb[idx_glb], eig_mj[idx_mj]


def find_rotation_centroid_bruteforce(glb_c, mj_c):
    """
    Try all 24 rotation matrices (axis permutations + sign flips)
    and find the one that maps glb_centroid -> mj_centroid best.
    """
    best_R = None
    best_err = float("inf")

    # All permutations of axes
    perms = [
        [0, 1, 2], [0, 2, 1], [1, 0, 2],
        [1, 2, 0], [2, 0, 1], [2, 1, 0],
    ]
    signs = [
        [1, 1, 1], [1, 1, -1], [1, -1, 1], [1, -1, -1],
        [-1, 1, 1], [-1, 1, -1], [-1, -1, 1], [-1, -1, -1],
    ]

    for perm in perms:
        for sign in signs:
            R = np.zeros((3, 3))
            for i in range(3):
                R[i, perm[i]] = sign[i]
            if np.linalg.det(R) < 0.99:
                continue  # Not a proper rotation
            predicted = R @ glb_c
            err = np.linalg.norm(predicted - mj_c)
            if err < best_err:
                best_err = err
                best_R = R.copy()

    return best_R, best_err


def main():
    print("=" * 75)
    print("Per-Mesh Correction Quaternion Calculator")
    print("=" * 75)

    corrections = {}

    for name in MESHES:
        glb_c, glb_v = get_glb_data(name)
        mj_c, mj_v = get_mj_data(f"manual_{name}.obj")

        print(f"\n--- {name} ---")
        print(f"  GLB centroid: ({glb_c[0]:.6f}, {glb_c[1]:.6f}, {glb_c[2]:.6f})")
        print(f"  MJ  centroid: ({mj_c[0]:.6f}, {mj_c[1]:.6f}, {mj_c[2]:.6f})")

        # Method 1: Brute-force over 24 proper rotations (permutations + signs)
        R_bf, err_bf = find_rotation_centroid_bruteforce(glb_c, mj_c)
        pred_bf = R_bf @ glb_c
        print(f"  Brute-force R @ GLB_c = ({pred_bf[0]:.6f}, {pred_bf[1]:.6f}, {pred_bf[2]:.6f})")
        print(f"  Brute-force error: {err_bf:.8f}")
        print(f"  Brute-force R:")
        for row in R_bf:
            entries = "  ".join(f"{v:6.1f}" for v in row)
            print(f"    [{entries}]")

        # Method 2: Covariance eigendecomposition
        R_cov, eig_glb, eig_mj = find_rotation_covariance(glb_v, mj_v, glb_c, mj_c)
        pred_cov = R_cov @ glb_c
        err_cov = np.linalg.norm(pred_cov - mj_c)
        print(f"  Covariance R @ GLB_c = ({pred_cov[0]:.6f}, {pred_cov[1]:.6f}, {pred_cov[2]:.6f})")
        print(f"  Covariance error: {err_cov:.8f}")

        # Use the better one
        if err_bf < err_cov * 1.1:  # Prefer brute-force (clean rotation)
            R_best = R_bf
            method = "brute-force"
        else:
            R_best = R_cov
            method = "covariance"

        print(f"  Using: {method}")

        # Verify: does R @ several test points work?
        # Sample a few GLB vertices and check if R maps them near MJ vertices
        if len(glb_v) == len(mj_v):
            # Same vertex count — check if R @ glb_v[i] ≈ mj_v[i] for first 10
            errs = np.linalg.norm((R_best @ glb_v[:10].T).T - mj_v[:10], axis=1)
            print(f"  Vertex check (first 10): mean_err={errs.mean():.6f}, max={errs.max():.6f}")
        else:
            print(f"  Vertex count mismatch: GLB={len(glb_v)}, MJ={len(mj_v)} (MuJoCo may deduplicate)")

        # Compute correction quat (inverse of the detected rotation)
        R_corr = R_best.T
        rot = Rotation.from_matrix(R_corr)
        q = rot.as_quat()  # scipy: (x, y, z, w)
        q_mj = f"{q[3]:.6f} {q[0]:.6f} {q[1]:.6f} {q[2]:.6f}"

        # Also express as euler angles for readability
        euler = rot.as_euler("xyz", degrees=True)

        print(f"  Correction quat (w,x,y,z): {q_mj}")
        print(f"  Correction euler (xyz deg): ({euler[0]:.1f}, {euler[1]:.1f}, {euler[2]:.1f})")

        corrections[name] = {
            "refquat": q_mj,
            "R": R_best.tolist(),
            "euler_deg": euler.tolist(),
            "centroid_error": float(min(err_bf, err_cov)),
        }

    # Print summary for copy-paste into XML
    print("\n" + "=" * 75)
    print("COPY-PASTE REFQUATS FOR test_mounts.xml:")
    print("=" * 75)
    for name, data in corrections.items():
        print(f'    <mesh name="{name}" file="manual_{name}.obj" refquat="{data["refquat"]}"/>')

    # Also save to JSON for use by randomize_board.py
    out_path = os.path.join(MJCF_DIR, "mesh_corrections.json")
    with open(out_path, "w") as f:
        json.dump(corrections, f, indent=2)
    print(f"\nSaved corrections to {out_path}")


if __name__ == "__main__":
    main()
