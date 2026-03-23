#!/usr/bin/env python3
"""
Diagnose MuJoCo mesh axis transforms.

For each mesh, compares the bounding-box extents in the ORIGINAL GLB/trimesh
coordinate frame vs the LOADED MuJoCo frame. This reveals the exact axis
permutation MuJoCo applies during import, for both OBJ and STL formats.

Usage:
  pixi run python3 ~/projects/Project-Automaton/Intrinsic-AI/tools/mujoco/diagnose_mesh_axes.py
"""

import mujoco
import trimesh
import numpy as np
import tempfile
import os

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

AXIS_NAMES = ["X", "Y", "Z"]


def get_glb_extents(name: str) -> np.ndarray:
    """Load GLB and return bounding box extents in original coordinates."""
    path = os.path.join(GLB_DIR, MESHES[name])
    scene = trimesh.load(path)
    if isinstance(scene, trimesh.Scene):
        mesh = trimesh.util.concatenate(scene.dump())
    else:
        mesh = scene
    return mesh.bounds[1] - mesh.bounds[0]  # (dx, dy, dz)


def get_mujoco_extents(mesh_file: str) -> np.ndarray:
    """Load a single mesh in MuJoCo and return bounding box extents."""
    xml = f"""<mujoco>
  <compiler meshdir="{MJCF_DIR}"/>
  <asset>
    <mesh name="test" file="{mesh_file}"/>
  </asset>
  <worldbody>
    <geom type="mesh" mesh="test"/>
  </worldbody>
</mujoco>"""
    model = mujoco.MjModel.from_xml_string(xml)

    # Get mesh vertex data from model
    mesh_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_MESH, "test")
    vert_start = model.mesh_vertadr[mesh_id]
    vert_count = model.mesh_vertnum[mesh_id]
    verts = model.mesh_vert[vert_start : vert_start + vert_count]

    bb_min = verts.min(axis=0)
    bb_max = verts.max(axis=0)
    return bb_max - bb_min


def find_permutation(original: np.ndarray, loaded: np.ndarray, tol=0.001):
    """
    Given original extents (dx,dy,dz) and loaded extents, find which
    original axis maps to which loaded axis.

    Returns a mapping: loaded_axis -> original_axis
    """
    mapping = {}
    used = set()
    # Match by closest extent value
    for li in range(3):
        best_oi = -1
        best_diff = float("inf")
        for oi in range(3):
            if oi in used:
                continue
            diff = abs(loaded[li] - original[oi])
            if diff < best_diff:
                best_diff = diff
                best_oi = oi
        mapping[li] = best_oi
        used.add(best_oi)

    return mapping


def main():
    print("=" * 75)
    print("MuJoCo Mesh Axis Diagnostic")
    print("=" * 75)

    results = {}

    for name in MESHES:
        print(f"\n--- {name} ---")
        glb_ext = get_glb_extents(name)
        print(f"  GLB native extents:    X={glb_ext[0]:.5f}  Y={glb_ext[1]:.5f}  Z={glb_ext[2]:.5f}")

        for fmt in ["obj", "stl"]:
            mesh_file = f"manual_{name}.{fmt}"
            full_path = os.path.join(MJCF_DIR, mesh_file)
            if not os.path.exists(full_path):
                print(f"  [{fmt.upper()}] File not found: {mesh_file}")
                continue

            try:
                mj_ext = get_mujoco_extents(mesh_file)
                print(f"  [{fmt.upper()}] MuJoCo extents: X={mj_ext[0]:.5f}  Y={mj_ext[1]:.5f}  Z={mj_ext[2]:.5f}")

                perm = find_permutation(glb_ext, mj_ext)
                perm_str = ", ".join(
                    f"MJ_{AXIS_NAMES[li]} ← GLB_{AXIS_NAMES[oi]}"
                    for li, oi in sorted(perm.items())
                )
                print(f"  [{fmt.upper()}] Axis mapping: {perm_str}")

                # Check if OBJ and STL give same permutation
                results.setdefault(name, {})[fmt] = perm

            except Exception as e:
                print(f"  [{fmt.upper()}] ERROR: {e}")

    # Summary
    print("\n" + "=" * 75)
    print("SUMMARY")
    print("=" * 75)

    # Check if STL avoids the permutation
    for name, fmts in results.items():
        obj_perm = fmts.get("obj", {})
        stl_perm = fmts.get("stl", {})

        obj_identity = all(obj_perm.get(i) == i for i in range(3))
        stl_identity = all(stl_perm.get(i) == i for i in range(3))

        print(f"\n  {name}:")
        print(f"    OBJ: {'IDENTITY (no scramble)' if obj_identity else 'PERMUTED'} {dict(obj_perm)}")
        print(f"    STL: {'IDENTITY (no scramble)' if stl_identity else 'PERMUTED'} {dict(stl_perm)}")
        if obj_perm == stl_perm:
            print(f"    → SAME permutation for both formats")
        else:
            print(f"    → DIFFERENT permutation! STL might help!")

    # Check if all meshes get the SAME permutation
    print("\n" + "-" * 40)
    obj_perms = [fmts.get("obj") for fmts in results.values() if "obj" in fmts]
    stl_perms = [fmts.get("stl") for fmts in results.values() if "stl" in fmts]

    if obj_perms and all(p == obj_perms[0] for p in obj_perms):
        print(f"  ALL OBJ meshes have SAME permutation: {dict(obj_perms[0])}")
        print(f"  → Single global correction quat would work for OBJ!")
    else:
        print(f"  OBJ meshes have DIFFERENT permutations (data-dependent scramble confirmed)")

    if stl_perms and all(p == stl_perms[0] for p in stl_perms):
        print(f"  ALL STL meshes have SAME permutation: {dict(stl_perms[0])}")
        if all(stl_perms[0].get(i) == i for i in range(3)):
            print(f"  → STL preserves axes! USE STL FORMAT!")
        else:
            print(f"  → Single global correction quat would work for STL!")
    else:
        print(f"  STL meshes have DIFFERENT permutations (data-dependent scramble for STL too)")

    # If consistent permutation found, compute correction quaternion
    for fmt in ["stl", "obj"]:
        perms = [fmts.get(fmt) for fmts in results.values() if fmt in fmts]
        if perms and all(p == perms[0] for p in perms):
            p = perms[0]
            if not all(p.get(i) == i for i in range(3)):
                # Build the rotation matrix from the permutation
                # MJ_axis[i] came from GLB_axis[p[i]]
                # So to undo: we need R such that R @ glb_vec = mj_vec
                # Actually for geom quat correction, we need the inverse
                R = np.zeros((3, 3))
                for mj_i, glb_i in p.items():
                    R[mj_i, glb_i] = 1.0

                # Convert rotation matrix to quaternion (w, x, y, z)
                from scipy.spatial.transform import Rotation
                rot = Rotation.from_matrix(R)
                q = rot.as_quat()  # scipy returns (x, y, z, w)
                q_mujoco = [q[3], q[0], q[1], q[2]]  # MuJoCo uses (w, x, y, z)

                print(f"\n  Correction quat for {fmt.upper()} (to undo permutation):")
                print(f"    refquat=\"{q_mujoco[0]:.4f} {q_mujoco[1]:.4f} {q_mujoco[2]:.4f} {q_mujoco[3]:.4f}\"")

                # Also compute the inverse (to apply as geom quat)
                q_inv = rot.inv().as_quat()
                q_inv_mj = [q_inv[3], q_inv[0], q_inv[1], q_inv[2]]
                print(f"    geom quat (inverse): \"{q_inv_mj[0]:.4f} {q_inv_mj[1]:.4f} {q_inv_mj[2]:.4f} {q_inv_mj[3]:.4f}\"")


if __name__ == "__main__":
    main()
