#!/usr/bin/env python3
"""
Settle & bake v2: Uses REAL XACRO collision geometry for mount cradles.

Converts XACRO collision specs → MuJoCo XML, drops plugs, bakes poses.
"""

import mujoco
import numpy as np
import os
import json
import math

MJCF_DIR = os.path.expanduser(
    "~/projects/Project-Automaton/References/aic/aic_utils/aic_mujoco/mjcf"
)


def rpy_to_quat(r, p, y):
    """Convert XACRO rpy (radians) to MuJoCo quat (w,x,y,z)."""
    cr, sr = math.cos(r / 2), math.sin(r / 2)
    cp, sp = math.cos(p / 2), math.sin(p / 2)
    cy, sy = math.cos(y / 2), math.sin(y / 2)
    w = cr * cp * cy + sr * sp * sy
    x = sr * cp * cy - cr * sp * sy
    yy = cr * sp * cy + sr * cp * sy
    z = cr * cp * sy - sr * sp * cy
    return f"{w:.6f} {x:.6f} {yy:.6f} {z:.6f}"


def xacro_box_to_mj(name, xyz, rpy, full_size):
    """Convert XACRO collision box to MuJoCo geom string."""
    hx = full_size[0] / 2
    hy = full_size[1] / 2
    hz = full_size[2] / 2
    q = rpy_to_quat(*rpy)
    identity = q == "1.000000 0.000000 0.000000 0.000000"
    qattr = "" if identity else f' quat="{q}"'
    return (
        f'      <geom name="{name}" type="box" '
        f'size="{hx:.6f} {hy:.6f} {hz:.6f}" '
        f'pos="{xyz[0]:.6f} {xyz[1]:.6f} {xyz[2]:.6f}"{qattr} '
        f'rgba="0.4 0.4 0.4 0.5" group="3"/>'
    )


# ===== XACRO collision definitions =====

SFP_MOUNT_COLLISIONS = [
    ("sfp_base",     (0.033272, 0, 0.0025),    (0, 0, 0),           (0.029457, 0.01775, 0.005)),
    ("sfp_wall_01",  (0.016366, 0, 0.017144),  (0, -0.785398, 0),   (0.038533, 0.01775, 0.001728)),
    ("sfp_wall_02",  (0.028636, 0, 0.012684),  (0, -0.785398, 0),   (0.027485, 0.01775, 0.003688)),
    ("sfp_side_L",   (0.021242, 0.007723, 0.013979), (0, -0.785398, 0), (0.036111, 0.002305, 0.010956)),
    ("sfp_side_R",   (0.021003, -0.007938, 0.014217), (0, -0.785398, 0), (0.036111, 0.001875, 0.01163)),
    ("sfp_edge_01",  (0.010017, 0, 0.003231),  (0, -0.785398, 0),   (0.005064, 0.01775, 0.01163)),
    ("sfp_base_02",  (0.0042, 0, 0.0025),      (0, 0, 0),           (0.014371, 0.01775, 0.005)),
    ("sfp_top",      (0.036553, 0, 0.011771),  (0, 0, 0),           (0.004893, 0.01775, 0.016755)),
]

SC_MOUNT_COLLISIONS = [
    ("sc_base",      (0.039002, 0, 0.0025),    (0, 0, 0),           (0.017747, 0.014, 0.005)),
    ("sc_wall_L",    (0.022568, -0.0054, 0.013451), (0, 0.785398, 0), (0.025812, 0.0032, 0.013799)),
    ("sc_wall_R",    (0.022568, 0.00585, 0.013451), (0, 0.785398, 0), (0.025812, 0.0023, 0.013799)),
    ("sc_edge_01",   (0.01415, 0, 0.02187),    (0, 0.785398, 0),    (0.002, 0.014, 0.013799)),
    ("sc_edge_02",   (0.031064, 0, 0.004956),  (0, 0.785398, 0),    (0.001842, 0.014, 0.013799)),
    ("sc_base_02",   (0.009506, 0, 0.0025),    (0, 0, 0),           (0.024957, 0.014, 0.005)),
    ("sc_mid",       (0.017774, 0, 0.008656),  (0, 0.785398, 0),    (0.025812, 0.014, 0.001239)),
    ("sc_top",       (0.035389, 0, 0.004624),  (0, 0, 0),           (0.002221, 0.014, 0.009249)),
    ("sc_side",      (0.009545, 0, 0.008711),  (0, 0, 0),           (0.00209, 0.014, 0.017422)),
]

LC_MOUNT_COLLISIONS = [
    ("lc_base",      (0.039468, 0, 0.0025),    (0, 0, 0),           (0.017033, 0.006, 0.005)),
    ("lc_base_02",   (0.006285, 0, 0.0025),    (0, 0, 0),           (0.018569, 0.006, 0.005)),
    ("lc_wall_01",   (0.016889, 0, 0.014186),  (0, -0.785398, 0),   (0.014269, 0.01475, 0.003054)),
    ("lc_wall_02",   (0.029227, 0, 0.003364),  (0, -0.785398, 0),   (0.012103, 0.01475, 0.007998)),
    ("lc_wall_03",   (0.013496, 0, 0.003079),  (0, -0.785398, 0),   (0.006255, 0.01475, 0.013841)),
    ("lc_side_R",    (0.022239, 0.00575, 0.008836), (0, -0.785398, 0), (0.014269, 0.00325, 0.015602)),
    ("lc_side_L",    (0.02227, -0.004513, 0.008805), (0, -0.785398, 0), (0.014269, 0.005725, 0.015265)),
    ("lc_top",       (0.032739, 0, 0.010179),  (0, -0.785398, 0),   (0.009041, 0.0065, 0.001804)),
]


def build_mount_geoms(collisions):
    return "\n".join(xacro_box_to_mj(*c) for c in collisions)


def quat_normalize(q):
    q = np.asarray(q, dtype=float)
    return q / np.linalg.norm(q)


def quat_conj(q):
    return np.array([q[0], -q[1], -q[2], -q[3]])


def quat_mul(q1, q2):
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    return np.array([
        w1*w2 - x1*x2 - y1*y2 - z1*z2,
        w1*x2 + x1*w2 + y1*z2 - z1*y2,
        w1*y2 - x1*z2 + y1*w2 + z1*x2,
        w1*z2 + x1*y2 - y1*x2 + z1*w2,
    ])


def quat_to_mat(q):
    w, x, y, z = quat_normalize(q)
    return np.array([
        [1 - 2*(y*y + z*z), 2*(x*y - z*w),     2*(x*z + y*w)],
        [2*(x*y + z*w),     1 - 2*(x*x + z*z), 2*(y*z - x*w)],
        [2*(x*z - y*w),     2*(y*z + x*w),     1 - 2*(x*x + y*y)],
    ])


def relative_pose(parent_p, parent_q, child_p, child_q):
    R_parent = quat_to_mat(parent_q)
    p_rel = R_parent.T @ (np.asarray(child_p) - np.asarray(parent_p))
    q_rel = quat_mul(quat_conj(parent_q), child_q)
    if q_rel[0] < 0:
        q_rel = -q_rel
    return p_rel, quat_normalize(q_rel)


def build_scene():
    sfp_geoms = build_mount_geoms(SFP_MOUNT_COLLISIONS)
    sc_geoms = build_mount_geoms(SC_MOUNT_COLLISIONS)
    lc_geoms = build_mount_geoms(LC_MOUNT_COLLISIONS)

    return f"""<mujoco model="settle_v2">
  <compiler angle="radian" meshdir="{MJCF_DIR}"/>
  <option gravity="0 0 -9.81" timestep="0.0005">
    <flag contact="enable"/>
  </option>
  <default>
    <geom friction="0.8 0.005 0.005" solref="0.002 1" solimp="0.99 0.999 0.001"/>
    <joint damping="0.5"/>
  </default>

  <visual>
    <headlight ambient="0.3 0.3 0.3" diffuse="0.6 0.6 0.6"/>
  </visual>

  <asset>
    <material name="mat_sc_plug" rgba="0.15 0.4 0.85 1" specular="0.4"/>
    <material name="mat_lc_plug" rgba="0.6 0.6 0.6 1" specular="0.4"/>
    <material name="mat_sfp_0" rgba="0.5 0.5 0.5 1" specular="0.3"/>
    <material name="mat_sfp_1" rgba="0.3 0.3 0.35 1" specular="0.3"/>
    <mesh name="sc_plug_mesh" content_type="model/obj" file="3c8f162873ab26f3c28d587135247b1ab9ef1a18a9d490deb9666be4c03443e6_sc_plug_visual_merged_0-67f94accf247f722dd4954d7448d7956402901f2.obj" inertia="shell"/>
    <mesh name="lc_plug_mesh" content_type="model/obj" file="b9fc682e4820b05cce436c98153fe0a21cf8357a9ca103d5872f530c3a9e2114_lc_plug_visual_merged_0-fdaf59710fc3cc118a7df05add4ff4205edda4ef.obj" inertia="shell"/>
    <mesh name="sfp_mesh_0" content_type="model/obj" file="1c33e96b885803ba8f50d0e401fdc0b85ffce960d08fc167466b66b5712840ce_sfp_module_visual_Body.005-f93147e1e403de321fb70c06a4b1e00f20feb9fd.obj" inertia="shell"/>
    <mesh name="sfp_mesh_1" content_type="model/obj" file="1c33e96b885803ba8f50d0e401fdc0b85ffce960d08fc167466b66b5712840ce_sfp_module_visual_Body.005_1-4af964a95522e2593eb6381eca4f09ef239782c7.obj" inertia="shell"/>
  </asset>

  <worldbody>
    <light pos="0 0 0.5" dir="0 0 -1" diffuse="1 1 1"/>
    <geom type="plane" size="1 1 0.01" rgba="0.15 0.15 0.15 1"/>

    <!-- SFP MOUNT (static, real XACRO collision) -->
    <body name="sfp_mount" pos="-0.15 0 0">
{sfp_geoms}
    </body>

    <!-- SFP MODULE (free) — -90deg Z to align module +Y to mount +X -->
    <body name="sfp_plug" pos="-0.127 0 0.018" quat="0.707107 0 0 -0.707107">
      <freejoint name="sfp_free"/>
      <inertial pos="0.00024115 0.00702224 0.000553372" quat="0.510037 0.497012 -0.483415 0.50907" mass="0.02" diaginertia="3.07513e-06 2.81054e-06 5.69919e-07"/>
      <geom size="0.00071 0.000503 0.0064415" pos="-0.00571 0.018813 -0.003546" quat="0.707107 0.707107 0 0" type="box" group="3"/>
      <geom size="0.00071 0.000503 0.0064415" pos="0.00571 0.018813 -0.003546" quat="0.707107 0.707107 0 0" type="box" group="3"/>
      <geom size="0.006875 0.02365 0.0003945" pos="0 0.001 0.00383" type="box" group="3"/>
      <geom size="0.006875 0.02365 8.9e-05" pos="0 0.001 -0.004138" type="box" group="3"/>
      <geom size="0.000287 0.02365 0.004225" pos="-0.006588 0.001 0" type="box" group="3"/>
      <geom size="0.0004055 0.02365 0.004225" pos="0.00647 0.001 0" type="box" group="3"/>
      <geom size="0.00642 0.0038815 0.0058645" pos="0 0.01229 0.000119" quat="0.707107 0.707107 0 0" type="box" group="3"/>
      <geom size="0.00642 0.0002045 0.0008005" pos="0 0.024453 -0.004254" quat="0.707107 0.707107 0 0" type="box" group="3"/>
      <geom size="0.00125 0.000503 0.0064415" pos="0 0.018813 -0.003546" quat="0.707107 0.707107 0 0" type="box" group="3"/>
      <geom type="mesh" mesh="sfp_mesh_0" material="mat_sfp_0" contype="0" conaffinity="0"/>
      <geom type="mesh" mesh="sfp_mesh_1" material="mat_sfp_1" contype="0" conaffinity="0"/>
    </body>

    <!-- SC MOUNT (static, real XACRO collision) -->
    <body name="sc_mount" pos="0 0 0">
{sc_geoms}
    </body>

    <!-- SC PLUG (free) — identity quat, SC long axis is already X -->
    <body name="sc_plug" pos="0.022 0 0.015" quat="1 0 0 0">
      <freejoint name="sc_free"/>
      <inertial pos="-0.00907511 4.9566e-05 8.71699e-06" quat="0.000872542 0.70691 -0.000868656 0.707302" mass="0.04" diaginertia="8.85404e-06 7.17322e-06 2.12253e-06"/>
      <geom size="0.0063605 0.0045 0.00365" pos="0.002038 0.006344 4e-06" type="box" group="3"/>
      <geom size="0.0063605 0.0045 0.00365" pos="0.002038 -0.006344 4e-06" type="box" group="3"/>
      <geom size="0.006861 0.0035 0.00365" pos="0.002539 0.006344 4e-06" type="box" group="3"/>
      <geom size="0.006861 0.0035 0.00365" pos="0.002539 -0.006344 4e-06" type="box" group="3"/>
      <geom size="0.001 0.000705 0.00365" pos="0.008191 0.003056 4e-06" quat="0.92388 0 0 -0.382683" type="box" group="3"/>
      <geom size="0.001 0.000705 0.00365" pos="0.008191 0.009636 4e-06" quat="0.92388 0 0 0.382683" type="box" group="3"/>
      <geom size="0.001 0.000705 0.00365" pos="0.008191 -0.009636 4e-06" quat="0.92388 0 0 -0.382683" type="box" group="3"/>
      <geom size="0.001 0.000705 0.00365" pos="0.008191 -0.003056 4e-06" quat="0.92388 0 0 0.382683" type="box" group="3"/>
      <geom size="0.006275 0.0125 0.00505" pos="-0.010291 0 0" type="box" group="3"/>
      <geom size="0.0029 0.014605" pos="-0.031147 -0.00635 0" quat="0.707107 0 0.707107 0" type="cylinder" group="3"/>
      <geom size="0.0029 0.015799" pos="-0.029953 0.00635 0" quat="0.707107 0 0.707107 0" type="cylinder" group="3"/>
      <geom size="0.00125 0.007" pos="0.00465 -0.00635 0" quat="0.707107 0 0.707107 0" type="cylinder" group="3"/>
      <geom size="0.00125 0.007" pos="0.00465 0.00635 0" quat="0.707107 0 0.707107 0" type="cylinder" group="3"/>
      <geom size="0.002125 0.00081 0.0005" pos="0.00146 -0.00632 0.0042" type="box" group="3"/>
      <geom size="0.002125 0.00081 0.0005" pos="0.00146 0.00632 0.0042" type="box" group="3"/>
      <geom type="mesh" mesh="sc_plug_mesh" material="mat_sc_plug" contype="0" conaffinity="0"/>
    </body>

    <!-- LC MOUNT (static, real XACRO collision) -->
    <body name="lc_mount" pos="0.15 0 0">
{lc_geoms}
    </body>

    <!-- LC PLUG (free) — -90deg Z for ferrule alignment -->
    <body name="lc_plug" pos="0.172 0 0.012" quat="0.707107 0 0 -0.707107">
      <freejoint name="lc_free"/>
      <inertial pos="0 0.0197 0" quat="0 0.707107 0 0.707107" mass="0.01" diaginertia="1.06153e-07 9.96094e-08 8.49658e-09"/>
      <geom size="0.000625 0.001502" pos="0.003125 0.0197 0" quat="0.707107 0.707107 0 0" type="cylinder" group="3"/>
      <geom size="0.000625 0.001502" pos="-0.003125 0.0197 0" quat="0.707107 0.707107 0 0" type="cylinder" group="3"/>
      <geom type="mesh" mesh="lc_plug_mesh" material="mat_lc_plug" contype="0" conaffinity="0"/>
    </body>
  </worldbody>
</mujoco>"""


def run_settle(xml_string, steps=15000):
    model = mujoco.MjModel.from_xml_string(xml_string)
    data = mujoco.MjData(model)
    for i in range(steps):
        mujoco.mj_step(model, data)
        if i % 3000 == 0:
            max_vel = np.max(np.abs(data.qvel))
            print(f"  Step {i:5d}: max_vel = {max_vel:.8f}")
            if i > 3000 and max_vel < 1e-6:
                print(f"  Settled at step {i}")
                break
    return model, data


def main():
    print("=" * 60)
    print("Mount-Plug Settle & Bake v2 (real XACRO collision)")
    print("=" * 60)

    xml = build_scene()

    # Save scene for visual inspection
    scene_path = os.path.join(MJCF_DIR, "test_mounts_settle.xml")
    with open(scene_path, "w") as f:
        f.write(xml)
    print(f"Saved settle scene to {scene_path}")

    print("\nRunning physics settle...")
    model, data = run_settle(xml)

    results = {}
    for mount_name, plug_name, label in [
        ("sfp_mount", "sfp_plug", "SFP"),
        ("sc_mount",  "sc_plug",  "SC"),
        ("lc_mount",  "lc_plug",  "LC"),
    ]:
        mount_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, mount_name)
        plug_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, plug_name)

        p_rel, q_rel = relative_pose(
            data.xpos[mount_id], data.xquat[mount_id],
            data.xpos[plug_id], data.xquat[plug_id],
        )

        pos_str = f"{p_rel[0]:.6f} {p_rel[1]:.6f} {p_rel[2]:.6f}"
        quat_str = f"{q_rel[0]:.6f} {q_rel[1]:.6f} {q_rel[2]:.6f} {q_rel[3]:.6f}"

        print(f"\n--- {label} ---")
        print(f"  World plug pos:  {data.xpos[plug_id]}")
        print(f"  World plug quat: {data.xquat[plug_id]}")
        print(f"  Mount-relative pos:  [{p_rel[0]:.6f}, {p_rel[1]:.6f}, {p_rel[2]:.6f}]")
        print(f"  Mount-relative quat: [{q_rel[0]:.6f}, {q_rel[1]:.6f}, {q_rel[2]:.6f}, {q_rel[3]:.6f}]")
        print(f'  XML: pos="{pos_str}" quat="{quat_str}"')

        results[label.lower()] = {
            "pos": p_rel.tolist(),
            "quat": q_rel.tolist(),
            "pos_str": pos_str,
            "quat_str": quat_str,
        }

    out_path = os.path.join(MJCF_DIR, "baked_mount_poses.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to {out_path}")
    print(f"\nVisual check: pixi run python3 -m mujoco.viewer --mjcf={scene_path}")


if __name__ == "__main__":
    main()
