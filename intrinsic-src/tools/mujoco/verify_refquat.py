#!/usr/bin/env python3
"""Verify that refquat corrections restore GLB-native orientation in MuJoCo."""

import mujoco
import trimesh
import numpy as np
import os
import json

MJCF_DIR = os.path.expanduser(
    "~/projects/Project-Automaton/References/aic/aic_utils/aic_mujoco/mjcf"
)
GLB_DIR = os.path.expanduser(
    "~/projects/Project-Automaton/References/aic/aic_assets/models"
)

MESHES = {
    "sfp_mount":  ("SFP Mount/sfp_mount_visual.glb",  "-0.707107 0 0 0.707107"),
    "sfp_module": ("SFP Module/sfp_module_visual.glb", "-0.500000 0.500000 0.500000 0.500000"),
    "sc_mount":   ("SC Mount/sc_mount_visual.glb",     "0.707107 0 0 0.707107"),
    "sc_plug":    ("SC Plug/sc_plug_visual.glb",       "-0.500000 0.500000 0.500000 -0.500000"),
    "lc_mount":   ("LC Mount/lc_mount_visual.glb",     "0.707107 0 0 0.707107"),
    "lc_plug":    ("LC Plug/lc_plug_visual.glb",       "-0.500000 0.500000 0.500000 0.500000"),
}


def load_glb(path):
    scene = trimesh.load(path)
    if isinstance(scene, trimesh.Scene):
        mesh = trimesh.util.concatenate(scene.dump())
    else:
        mesh = scene
    return mesh.centroid, mesh.bounds[1] - mesh.bounds[0]


def load_mj(mesh_file, refquat=None):
    rq = f' refquat="{refquat}"' if refquat else ""
    xml = (
        "<mujoco>\n"
        f'  <compiler meshdir="{MJCF_DIR}"/>\n'
        f'  <asset><mesh name="test" file="{mesh_file}"{rq}/></asset>\n'
        '  <worldbody><geom type="mesh" mesh="test"/></worldbody>\n'
        "</mujoco>"
    )
    model = mujoco.MjModel.from_xml_string(xml)
    mid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_MESH, "test")
    vs = model.mesh_vert[model.mesh_vertadr[mid]:model.mesh_vertadr[mid] + model.mesh_vertnum[mid]]
    centroid = vs.mean(axis=0)
    extent = vs.max(axis=0) - vs.min(axis=0)
    return centroid, extent


print("=" * 75)
print("RefQuat Verification: Does it restore GLB orientation?")
print("=" * 75)

for name, (glb_path, refquat) in MESHES.items():
    glb_c, glb_e = load_glb(os.path.join(GLB_DIR, glb_path))
    mj_c_raw, mj_e_raw = load_mj(f"manual_{name}.obj")
    mj_c_fix, mj_e_fix = load_mj(f"manual_{name}.obj", refquat)

    print(f"\n--- {name} ---")
    print(f"  GLB extent:      X={glb_e[0]:.5f}  Y={glb_e[1]:.5f}  Z={glb_e[2]:.5f}")
    print(f"  MJ raw extent:   X={mj_e_raw[0]:.5f}  Y={mj_e_raw[1]:.5f}  Z={mj_e_raw[2]:.5f}")
    print(f"  MJ fixed extent: X={mj_e_fix[0]:.5f}  Y={mj_e_fix[1]:.5f}  Z={mj_e_fix[2]:.5f}")

    extent_err = np.abs(glb_e - mj_e_fix)
    print(f"  Extent error:    X={extent_err[0]:.5f}  Y={extent_err[1]:.5f}  Z={extent_err[2]:.5f}")
    match = all(e < 0.005 for e in extent_err)
    print(f"  EXTENT MATCH: {'YES' if match else 'NO'}")

    print(f"  GLB centroid:    ({glb_c[0]:.5f}, {glb_c[1]:.5f}, {glb_c[2]:.5f})")
    print(f"  MJ raw centroid: ({mj_c_raw[0]:.5f}, {mj_c_raw[1]:.5f}, {mj_c_raw[2]:.5f})")
    print(f"  MJ fix centroid: ({mj_c_fix[0]:.5f}, {mj_c_fix[1]:.5f}, {mj_c_fix[2]:.5f})")

    centroid_err = np.linalg.norm(glb_c - mj_c_fix)
    print(f"  Centroid error:  {centroid_err:.5f}")
