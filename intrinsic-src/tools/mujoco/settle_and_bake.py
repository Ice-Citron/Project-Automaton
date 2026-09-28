#!/usr/bin/env python3
"""
Offline settle scene: drop plugs/modules into mount cradles via physics,
then bake the resulting mount-relative poses for use in randomize_board.py.

Approach from GPT-5.4: use MuJoCo physics to find the correct mount→plug
transform, instead of fighting mesh coordinate scrambles.

Usage:
  cd ~/projects/Project-Automaton/References/aic
  pixi run python3 ~/projects/Project-Automaton/Intrinsic-AI/tools/mujoco/settle_and_bake.py
"""

import mujoco
import numpy as np
import os
import json

MJCF_DIR = os.path.expanduser(
    "~/projects/Project-Automaton/References/aic/aic_utils/aic_mujoco/mjcf"
)


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
    """Compute child pose relative to parent."""
    R_parent = quat_to_mat(parent_q)
    p_rel = R_parent.T @ (np.asarray(child_p) - np.asarray(parent_p))
    q_rel = quat_mul(quat_conj(parent_q), child_q)
    if q_rel[0] < 0:
        q_rel = -q_rel
    return p_rel, quat_normalize(q_rel)


# ---------------------------------------------------------------------------
# Settle scene XML template
# Uses the OFFICIAL converted mesh assets from aic_world.xml (not manual OBJs)
# Mount V-cradle collision from XACRO macro specs
# ---------------------------------------------------------------------------

SETTLE_XML = f"""<mujoco model="settle_test">
  <compiler angle="radian" meshdir="{MJCF_DIR}"/>
  <option gravity="0 0 -9.81" timestep="0.001"/>

  <visual>
    <headlight ambient="0.3 0.3 0.3" diffuse="0.6 0.6 0.6"/>
  </visual>

  <asset>
    <!-- Plain materials (no textures needed for physics settle) -->
    <material name="mat_sc_plug" rgba="0.15 0.4 0.85 1" specular="0.4"/>
    <material name="mat_lc_plug" rgba="0.6 0.6 0.6 1" specular="0.4"/>
    <material name="mat_sfp_0" rgba="0.5 0.5 0.5 1" specular="0.3"/>
    <material name="mat_sfp_1" rgba="0.3 0.3 0.35 1" specular="0.3"/>
    <material name="mat_sfp_mount_0" rgba="0.18 0.18 0.18 1" specular="0.3"/>
    <material name="mat_sfp_mount_1" rgba="0.25 0.25 0.25 1" specular="0.3"/>

    <!-- Official converter OBJ meshes -->
    <mesh name="sc_plug_mesh" content_type="model/obj" file="3c8f162873ab26f3c28d587135247b1ab9ef1a18a9d490deb9666be4c03443e6_sc_plug_visual_merged_0-67f94accf247f722dd4954d7448d7956402901f2.obj" inertia="shell"/>
    <mesh name="lc_plug_mesh" content_type="model/obj" file="b9fc682e4820b05cce436c98153fe0a21cf8357a9ca103d5872f530c3a9e2114_lc_plug_visual_merged_0-fdaf59710fc3cc118a7df05add4ff4205edda4ef.obj" inertia="shell"/>
    <mesh name="sfp_mesh_0" content_type="model/obj" file="1c33e96b885803ba8f50d0e401fdc0b85ffce960d08fc167466b66b5712840ce_sfp_module_visual_Body.005-f93147e1e403de321fb70c06a4b1e00f20feb9fd.obj" inertia="shell"/>
    <mesh name="sfp_mesh_1" content_type="model/obj" file="1c33e96b885803ba8f50d0e401fdc0b85ffce960d08fc167466b66b5712840ce_sfp_module_visual_Body.005_1-4af964a95522e2593eb6381eca4f09ef239782c7.obj" inertia="shell"/>
    <mesh name="sfp_mount_vis_0" content_type="model/obj" file="7ad515da736fc2c58c890d539f7e6b354f74c917d05e12c54574393bcc0acd27_sfp_mount_visual_ISO_4762_-_M2_x_8.011-e79a298280ce559f60558a5df64e118c814f63e4.obj" inertia="shell"/>
    <mesh name="sfp_mount_vis_1" content_type="model/obj" file="7ad515da736fc2c58c890d539f7e6b354f74c917d05e12c54574393bcc0acd27_sfp_mount_visual_ISO_4762_-_M2_x_8.011_1-3a79ef8883f6645921d3fa2c67cf381141e6ea26.obj" inertia="shell"/>
  </asset>

  <worldbody>
    <light pos="0 0 0.5" dir="0 0 -1" diffuse="1 1 1"/>
    <geom type="plane" size="1 1 0.01" rgba="0.15 0.15 0.15 1"/>

    <!-- ============================================================ -->
    <!-- SFP MOUNT (static) at world origin                           -->
    <!-- V-cradle collision from sfp_mount_macro.xacro                -->
    <!-- ============================================================ -->
    <body name="sfp_mount" pos="-0.15 0 0">
      <!-- Base plate -->
      <geom type="box" size="0.0255 0.009 0.002" pos="0.022 0 0.002" rgba="0.4 0.4 0.4 0.5"/>
      <!-- Left wall (45 deg tilt = 0.785 rad around X) -->
      <geom type="box" size="0.0255 0.002 0.006" pos="0.022 -0.006 0.008" quat="0.9239 0.3827 0 0" rgba="0.4 0.4 0.4 0.5"/>
      <!-- Right wall (-45 deg) -->
      <geom type="box" size="0.0255 0.002 0.006" pos="0.022 0.006 0.008" quat="0.9239 -0.3827 0 0" rgba="0.4 0.4 0.4 0.5"/>
      <!-- Official visual meshes -->
      <geom type="mesh" mesh="sfp_mount_vis_0" material="mat_sfp_mount_0" contype="0" conaffinity="0"/>
      <geom type="mesh" mesh="sfp_mount_vis_1" material="mat_sfp_mount_1" contype="0" conaffinity="0"/>
    </body>

    <!-- SFP MODULE (free, starts above cradle) -->
    <body name="sfp_plug" pos="-0.127 0 0.030" quat="0.707107 0 0 0.707107">
      <freejoint name="sfp_free"/>
        <inertial pos="0.00024115 0.00702224 0.000553372" quat="0.510037 0.497012 -0.483415 0.50907" mass="0.02" diaginertia="3.07513e-06 2.81054e-06 5.69919e-07"/>
        <!-- Collision boxes from aic_world.xml sfp_module_link -->
        <geom size="0.00071 0.000503 0.0064415" pos="-0.00571 0.018813 -0.003546" quat="0.707107 0.707107 0 0" type="box" group="3"/>
        <geom size="0.00071 0.000503 0.0064415" pos="0.00571 0.018813 -0.003546" quat="0.707107 0.707107 0 0" type="box" group="3"/>
        <geom size="0.006875 0.02365 0.0003945" pos="0 0.001 0.00383" type="box" group="3"/>
        <geom size="0.006875 0.02365 8.9e-05" pos="0 0.001 -0.004138" type="box" group="3"/>
        <geom size="0.000287 0.02365 0.004225" pos="-0.006588 0.001 0" type="box" group="3"/>
        <geom size="0.0004055 0.02365 0.004225" pos="0.00647 0.001 0" type="box" group="3"/>
        <geom size="0.00642 0.0038815 0.0058645" pos="0 0.01229 0.000119" quat="0.707107 0.707107 0 0" type="box" group="3"/>
        <geom size="0.00642 0.0002045 0.0008005" pos="0 0.024453 -0.004254" quat="0.707107 0.707107 0 0" type="box" group="3"/>
        <geom size="0.00125 0.000503 0.0064415" pos="0 0.018813 -0.003546" quat="0.707107 0.707107 0 0" type="box" group="3"/>
        <!-- Visual -->
      <geom type="mesh" mesh="sfp_mesh_0" material="mat_sfp_0" contype="0" conaffinity="0"/>
      <geom type="mesh" mesh="sfp_mesh_1" material="mat_sfp_1" contype="0" conaffinity="0"/>
    </body>

    <!-- ============================================================ -->
    <!-- SC MOUNT (static)                                            -->
    <!-- V-cradle collision from sc_mount_macro.xacro                 -->
    <!-- ============================================================ -->
    <body name="sc_mount" pos="0 0 0">
      <!-- Base plate -->
      <geom type="box" size="0.0255 0.007 0.003" pos="0.022 0 0.003" rgba="0.4 0.4 0.4 0.5"/>
      <!-- Left wall (45 deg) -->
      <geom type="box" size="0.0255 0.002 0.005" pos="0.022 -0.005 0.007" quat="0.9239 0.3827 0 0" rgba="0.4 0.4 0.4 0.5"/>
      <!-- Right wall (-45 deg) -->
      <geom type="box" size="0.0255 0.002 0.005" pos="0.022 0.005 0.007" quat="0.9239 -0.3827 0 0" rgba="0.4 0.4 0.4 0.5"/>
    </body>

    <!-- SC PLUG (free, starts above cradle) -->
    <body name="sc_plug" pos="0.023 0 0.030" quat="1 0 0 0">
      <freejoint name="sc_free"/>
        <inertial pos="-0.00907511 4.9566e-05 8.71699e-06" quat="0.000872542 0.70691 -0.000868656 0.707302" mass="0.04" diaginertia="8.85404e-06 7.17322e-06 2.12253e-06"/>
        <!-- Collision boxes from aic_world.xml sc_plug_link -->
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
      <!-- Visual -->
      <geom type="mesh" mesh="sc_plug_mesh" material="mat_sc_plug" contype="0" conaffinity="0"/>
    </body>

    <!-- ============================================================ -->
    <!-- LC MOUNT (static)                                            -->
    <!-- V-cradle collision from lc_mount_macro.xacro                 -->
    <!-- ============================================================ -->
    <body name="lc_mount" pos="0.15 0 0">
      <!-- Base plate -->
      <geom type="box" size="0.0255 0.007 0.001" pos="0.022 0 0.001" rgba="0.4 0.4 0.4 0.5"/>
      <!-- Left wall -->
      <geom type="box" size="0.0255 0.002 0.005" pos="0.022 -0.005 0.005" quat="0.9239 0.3827 0 0" rgba="0.4 0.4 0.4 0.5"/>
      <!-- Right wall -->
      <geom type="box" size="0.0255 0.002 0.005" pos="0.022 0.005 0.005" quat="0.9239 -0.3827 0 0" rgba="0.4 0.4 0.4 0.5"/>
    </body>

    <!-- LC PLUG (free, starts above cradle) -->
    <body name="lc_plug" pos="0.172 0 0.030" quat="0.707107 0 0 -0.707107">
      <freejoint name="lc_free"/>
        <inertial pos="0 0.0197 0" quat="0 0.707107 0 0.707107" mass="0.01" diaginertia="1.06153e-07 9.96094e-08 8.49658e-09"/>
      <!-- Collision cylinders from aic_world.xml lc_plug_link -->
      <geom size="0.000625 0.001502" pos="0.003125 0.0197 0" quat="0.707107 0.707107 0 0" type="cylinder" group="3"/>
      <geom size="0.000625 0.001502" pos="-0.003125 0.0197 0" quat="0.707107 0.707107 0 0" type="cylinder" group="3"/>
      <!-- Visual -->
      <geom type="mesh" mesh="lc_plug_mesh" material="mat_lc_plug" contype="0" conaffinity="0"/>
    </body>
  </worldbody>
</mujoco>"""


def run_settle(xml_string, steps=10000):
    """Run physics simulation and return settled body poses."""
    model = mujoco.MjModel.from_xml_string(xml_string)
    data = mujoco.MjData(model)

    # Step simulation
    for i in range(steps):
        mujoco.mj_step(model, data)
        if i % 2000 == 0:
            # Check if settled (low velocity)
            max_vel = np.max(np.abs(data.qvel))
            print(f"  Step {i:5d}: max_vel = {max_vel:.8f}")
            if i > 2000 and max_vel < 1e-6:
                print(f"  Settled at step {i}")
                break

    return model, data


def main():
    print("=" * 60)
    print("Mount-Plug Settle & Bake")
    print("=" * 60)

    print("\nRunning physics settle...")
    model, data = run_settle(SETTLE_XML)

    results = {}

    for mount_name, plug_name, label in [
        ("sfp_mount", "sfp_plug", "SFP"),
        ("sc_mount",  "sc_plug",  "SC"),
        ("lc_mount",  "lc_plug",  "LC"),
    ]:
        mount_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, mount_name)
        plug_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, plug_name)

        if mount_id < 0 or plug_id < 0:
            print(f"\n{label}: Body not found! mount={mount_id}, plug={plug_id}")
            continue

        mount_pos = data.xpos[mount_id].copy()
        mount_quat = data.xquat[mount_id].copy()
        plug_pos = data.xpos[plug_id].copy()
        plug_quat = data.xquat[plug_id].copy()

        print(f"\n--- {label} ---")
        print(f"  Mount world pos:  {mount_pos}")
        print(f"  Mount world quat: {mount_quat}")
        print(f"  Plug world pos:   {plug_pos}")
        print(f"  Plug world quat:  {plug_quat}")

        p_rel, q_rel = relative_pose(mount_pos, mount_quat, plug_pos, plug_quat)
        print(f"  Relative pos:  {p_rel}")
        print(f"  Relative quat: {q_rel}")

        # Format for XML
        pos_str = f"{p_rel[0]:.6f} {p_rel[1]:.6f} {p_rel[2]:.6f}"
        quat_str = f"{q_rel[0]:.6f} {q_rel[1]:.6f} {q_rel[2]:.6f} {q_rel[3]:.6f}"

        print(f"\n  XML for randomize_board.py:")
        print(f'    pos="{pos_str}" quat="{quat_str}"')

        results[label.lower()] = {
            "pos": p_rel.tolist(),
            "quat": q_rel.tolist(),
            "pos_str": pos_str,
            "quat_str": quat_str,
        }

    # Save results
    out_path = os.path.join(MJCF_DIR, "baked_mount_poses.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved baked poses to {out_path}")

    # Also save the settle scene for visual inspection
    scene_path = os.path.join(MJCF_DIR, "test_mounts_settle.xml")
    with open(scene_path, "w") as f:
        f.write(SETTLE_XML)
    print(f"Saved settle scene to {scene_path}")

    print("\nTo visually inspect the settle result:")
    print(f"  pixi run python3 -m mujoco.viewer --mjcf={scene_path}")


if __name__ == "__main__":
    main()
