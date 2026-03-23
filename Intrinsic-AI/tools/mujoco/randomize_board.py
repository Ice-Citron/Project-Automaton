#!/usr/bin/env python3
"""
Randomize MuJoCo task board component placement.

Reads aic_world.xml, duplicates component bodies at random rail positions
within the AIC config constraints, and writes the result.

Usage:
  python3 randomize_board.py [--seed 42] [--out aic_world_rand.xml]
"""

import xml.etree.ElementTree as ET
import random
import argparse
import copy
import math
import os
import sys

# ── Rail constraints from sample_config.yaml ──────────────────────────
LIMITS = {
    "nic_rail":   {"min": -0.0215, "max": 0.0234},
    "sc_rail":    {"min": -0.06,   "max": 0.055},
    "mount_rail": {"min": -0.09425,"max": 0.09425},
}

# ── NIC card rail positions (Y offsets relative to task_board_base_link) ─
NIC_RAILS = {
    0: {"y": -0.1745, "x": -0.081418, "z": 0.012},
    1: {"y": -0.1345, "x": -0.081418, "z": 0.012},
    2: {"y": -0.0945, "x": -0.081418, "z": 0.012},
    3: {"y": -0.0545, "x": -0.081418, "z": 0.012},
    4: {"y": -0.0145, "x": -0.081418, "z": 0.012},
}

# ── SC port rail positions (Y offsets relative to task_board_base_link) ──
SC_RAILS = {
    0: {"y": 0.0295, "x": -0.075, "z": 0.0165},
    1: {"y": 0.0705, "x": -0.075, "z": 0.0165},
}

# ── Mount rails (zones 3-4): left side Y=-0.10625, right side Y=0.10625 ─
MOUNT_RAILS = {
    # Exact positions from task_board.urdf.xacro
    "lc_mount_rail_0":  {"x": 0.01,   "y": -0.10625, "z": 0.012},
    "sfp_mount_rail_0": {"x": 0.055,  "y": -0.10625, "z": 0.01},
    "sc_mount_rail_0":  {"x": 0.1,    "y": -0.10625, "z": 0.012},
    "lc_mount_rail_1":  {"x": 0.01,   "y": 0.10625,  "z": 0.012},
    "sfp_mount_rail_1": {"x": 0.055,  "y": 0.10625,  "z": 0.01},
    "sc_mount_rail_1":  {"x": 0.0985, "y": 0.10625,  "z": 0.01},
}

# ── Orientation limits (radians) ──────────────────────────────────────
NIC_YAW_RANGE = (0.0, 0.0)           # Zero yaw — screwed to rails
MOUNT_YAW_RANGE = (0.0, 0.0)  # Zero yaw — components are screwed to rails


def find_body(root, name):
    for body in root.iter("body"):
        if body.get("name") == name:
            return body
    return None


def find_task_board(root):
    return find_body(root, "task_board_base_link")


def strip_collision_geoms(body):
    """Remove group=3 collision geoms from a body tree to avoid visual clutter."""
    to_remove = []
    for elem in body.iter():
        if elem.tag == "geom":
            group = elem.get("group", "0")
            if group == "3":
                to_remove.append(elem)
    # Remove from parents
    for geom in to_remove:
        for parent in body.iter():
            if geom in list(parent):
                parent.remove(geom)
                break


def rename_elements(body, suffix, idx):
    """Rename body/geom/joint/site names to avoid duplicates."""
    for elem in body.iter():
        name = elem.get("name")
        if name is None:
            continue
        tag = elem.tag
        if tag in ("body", "geom", "joint", "site"):
            if tag == "body":
                old = elem.get("name")
                if "nic_card_mount_0" in old:
                    elem.set("name", old.replace("nic_card_mount_0", f"nic_card_mount_{idx}"))
                elif "sc_port_0" in old:
                    elem.set("name", old.replace("sc_port_0", f"sc_port_{idx}"))
                elif old == "nic_card_link":
                    elem.set("name", f"nic_card_link_{idx}")
                elif not old.endswith(suffix):
                    elem.set("name", old + suffix)
            else:
                if not name.endswith(suffix):
                    elem.set("name", name + suffix)


def clone_nic_card(root, template_body, rail_idx, translation):
    rail = NIC_RAILS[rail_idx]
    new_mount = copy.deepcopy(template_body)
    new_mount.set("name", f"nic_card_mount_{rail_idx}::nic_card_mount_link")

    x = rail["x"] + translation
    new_mount.set("pos", f"{x:.6f} {rail['y']:.6f} {rail['z']:.6f}")

    # Strip collision geoms from cloned bodies to avoid spare screws
    strip_collision_geoms(new_mount)

    suffix = f"_r{rail_idx}"
    rename_elements(new_mount, suffix, rail_idx)
    return new_mount


def clone_sc_port(root, template_body, rail_idx, translation):
    rail = SC_RAILS[rail_idx]
    new_port = copy.deepcopy(template_body)
    new_port.set("name", f"sc_port_{rail_idx}::sc_port_link")

    x = rail["x"] + translation
    new_port.set("pos", f"{x:.6f} {rail['y']:.6f} {rail['z']:.6f}")

    # Strip collision geoms from cloned bodies
    strip_collision_geoms(new_port)

    suffix = f"_sc{rail_idx}"
    rename_elements(new_port, suffix, rail_idx)
    return new_port


def yaw_to_quat(yaw):
    """Convert yaw angle (radians) to quaternion string."""
    cy = math.cos(yaw / 2)
    sy = math.sin(yaw / 2)
    return f"{cy:.6f} 0 0 {sy:.6f}"


def make_mount_body(mount_type, rail_name, translation, yaw, mesh_names, mat_names, unique_id):
    """Create a visual-only mount body for zones 3-4 using actual converter meshes."""
    rail = MOUNT_RAILS[rail_name]

    body = ET.Element("body")
    body.set("name", f"{mount_type}_{unique_id}_body")
    x = rail["x"]
    y = rail["y"] + translation
    z = rail["z"]
    body.set("pos", f"{x:.6f} {y:.6f} {z:.6f}")

    if abs(yaw) > 0.001:
        body.set("quat", yaw_to_quat(yaw))

    inertial = ET.SubElement(body, "inertial")
    inertial.set("pos", "0 0 0")
    inertial.set("mass", "0.05")
    inertial.set("diaginertia", "1e-5 1e-5 1e-5")

    for i, (mesh, mat) in enumerate(zip(mesh_names, mat_names)):
        geom = ET.SubElement(body, "geom")
        geom.set("name", f"{mount_type}_{unique_id}_visual_{i}")
        geom.set("type", "mesh")
        geom.set("mesh", mesh)
        if mat:
            geom.set("material", mat)
        geom.set("contype", "0")
        geom.set("conaffinity", "0")

    return body


def get_visual_geom_info(root, name_contains):
    """Get mesh and material names from visual geoms matching a pattern."""
    meshes = []
    mats = []
    for geom in root.iter("geom"):
        name = geom.get("name", "")
        group = geom.get("group", "0")
        if name_contains in name and group != "3" and "collider" not in name and "collision" not in name:
            mesh = geom.get("mesh")
            mat = geom.get("material")
            if mesh:
                meshes.append(mesh)
                mats.append(mat or "")
    return meshes, mats


def randomize(xml_path, output_path, seed=None,
              nic_count=None, sc_count=None):
    if seed is not None:
        random.seed(seed)

    print(f"Loading {xml_path}...")
    tree = ET.parse(xml_path)
    root = tree.getroot()

    task_board = find_task_board(root)
    if task_board is None:
        print("ERROR: task_board_base_link not found!")
        sys.exit(1)

    # ── Find existing template bodies ──────────────────────────────
    nic_template = find_body(root, "nic_card_mount_0::nic_card_mount_link")
    sc_template = find_body(root, "sc_port_0::sc_port_link")

    # ── Get mesh/material info for mount components ────────────────
    sfp_mount_meshes, sfp_mount_mats = get_visual_geom_info(root, "sfp_mount_visual")
    # SC port uses the same textured meshes
    sc_port_meshes, sc_port_mats = get_visual_geom_info(root, "sc_port_visual")
    # SC plug (from cable end)
    sc_plug_meshes, sc_plug_mats = get_visual_geom_info(root, "sc_plug_visual")
    # SFP module (from cable end)
    sfp_mod_meshes, sfp_mod_mats = get_visual_geom_info(root, "sfp_module_visual")
    # LC plug (from cable end)
    lc_plug_meshes, lc_plug_mats = get_visual_geom_info(root, "lc_plug_visual")

    print(f"Found meshes: SFP mount={len(sfp_mount_meshes)}, SC port={len(sc_port_meshes)}, "
          f"SC plug={len(sc_plug_meshes)}, SFP module={len(sfp_mod_meshes)}, LC plug={len(lc_plug_meshes)}")

    # ── Decide how many of each component ──────────────────────────
    if nic_count is None:
        nic_count = random.randint(1, 3)
    if sc_count is None:
        sc_count = random.randint(1, 2)

    nic_rails_to_use = sorted(random.sample(range(5), min(nic_count, 5)))
    sc_rails_to_use = sorted(random.sample(range(2), min(sc_count, 2)))

    print(f"\n=== Randomization Config (seed={seed}) ===")
    print(f"NIC cards: {nic_count} on rails {nic_rails_to_use}")
    print(f"SC ports:  {sc_count} on rails {sc_rails_to_use}")

    # ── Zone 1: NIC Cards ──────────────────────────────────────────
    if nic_template is not None:
        existing_translation = random.uniform(LIMITS["nic_rail"]["min"],
                                               LIMITS["nic_rail"]["max"])
        rail0 = NIC_RAILS[0]
        new_x = rail0["x"] + existing_translation
        nic_template.set("pos", f"{new_x:.6f} {rail0['y']:.6f} {rail0['z']:.6f}")
        print(f"  NIC rail 0: translation={existing_translation:.4f}")

        for rail_idx in nic_rails_to_use:
            if rail_idx == 0:
                continue
            translation = random.uniform(LIMITS["nic_rail"]["min"],
                                          LIMITS["nic_rail"]["max"])
            new_nic = clone_nic_card(root, nic_template, rail_idx, translation)
            task_board.append(new_nic)
            print(f"  NIC rail {rail_idx}: translation={translation:.4f}")

    # ── Zone 2: SC Ports ───────────────────────────────────────────
    if sc_template is not None:
        existing_translation = random.uniform(LIMITS["sc_rail"]["min"],
                                               LIMITS["sc_rail"]["max"])
        rail0 = SC_RAILS[0]
        new_x = rail0["x"] + existing_translation
        sc_template.set("pos", f"{new_x:.6f} {rail0['y']:.6f} {rail0['z']:.6f}")
        print(f"  SC rail 0: translation={existing_translation:.4f}")

        for rail_idx in sc_rails_to_use:
            if rail_idx == 0:
                continue
            translation = random.uniform(LIMITS["sc_rail"]["min"],
                                          LIMITS["sc_rail"]["max"])
            new_sc = clone_sc_port(root, sc_template, rail_idx, translation)
            task_board.append(new_sc)
            print(f"  SC rail {rail_idx}: translation={translation:.4f}")

    # ── Zones 3-4: Mount Rails with real meshes ────────────────────
    mount_id = 0

    # Each rail type ONLY hosts its designated component:
    #   lc_mount_rail  → LC mount + LC plug inside
    #   sfp_mount_rail → SFP mount + SFP module inside
    #   sc_mount_rail  → SC mount + SC plug inside

    # SFP mounts + SFP modules on sfp_mount rails
    sfp_rails = [r for r in MOUNT_RAILS if "sfp_mount" in r]
    chosen_sfp = random.sample(sfp_rails, random.randint(1, len(sfp_rails)))
    for rail_name in chosen_sfp:
        translation = random.uniform(LIMITS["mount_rail"]["min"],
                                      LIMITS["mount_rail"]["max"])
        if sfp_mount_meshes:
            body = make_mount_body("sfp_mount", rail_name, translation, 0.0,
                                   sfp_mount_meshes, sfp_mount_mats, mount_id)
            # Nest SFP module inside the mount
            if sfp_mod_meshes:
                for i, (mesh, mat) in enumerate(zip(sfp_mod_meshes, sfp_mod_mats)):
                    geom = ET.SubElement(body, "geom")
                    geom.set("name", f"sfp_mod_in_mount_{mount_id}_{i}")
                    geom.set("type", "mesh")
                    geom.set("mesh", mesh)
                    if mat:
                        geom.set("material", mat)
                    geom.set("contype", "0")
                    geom.set("conaffinity", "0")
            task_board.append(body)
            print(f"  SFP mount+module on {rail_name}: trans={translation:.4f}")
            mount_id += 1

    # LC mounts + LC plugs on lc_mount rails
    lc_rails = [r for r in MOUNT_RAILS if "lc_mount" in r]
    chosen_lc = random.sample(lc_rails, random.randint(1, len(lc_rails)))
    for rail_name in chosen_lc:
        translation = random.uniform(LIMITS["mount_rail"]["min"],
                                      LIMITS["mount_rail"]["max"])
        body = make_mount_body("lc_mount", rail_name, translation, 0.0,
                               ["manual_lc_mount"], ["mount_grey"], mount_id)
        # Nest LC plug inside the mount
        if lc_plug_meshes:
            for i, (mesh, mat) in enumerate(zip(lc_plug_meshes, lc_plug_mats)):
                geom = ET.SubElement(body, "geom")
                geom.set("name", f"lc_plug_in_mount_{mount_id}_{i}")
                geom.set("type", "mesh")
                geom.set("mesh", mesh)
                if mat:
                    geom.set("material", mat)
                geom.set("contype", "0")
                geom.set("conaffinity", "0")
        task_board.append(body)
        print(f"  LC mount+plug on {rail_name}: trans={translation:.4f}")
        mount_id += 1

    # SC mounts + SC plugs on sc_mount rails
    sc_rails_z34 = [r for r in MOUNT_RAILS if "sc_mount" in r]
    chosen_sc = random.sample(sc_rails_z34, random.randint(1, len(sc_rails_z34)))
    for rail_name in chosen_sc:
        translation = random.uniform(LIMITS["mount_rail"]["min"],
                                      LIMITS["mount_rail"]["max"])
        body = make_mount_body("sc_mount", rail_name, translation, 0.0,
                               ["manual_sc_mount"], ["mount_grey"], mount_id)
        # Nest SC plug inside the mount
        if sc_plug_meshes:
            for i, (mesh, mat) in enumerate(zip(sc_plug_meshes, sc_plug_mats)):
                geom = ET.SubElement(body, "geom")
                geom.set("name", f"sc_plug_in_mount_{mount_id}_{i}")
                geom.set("type", "mesh")
                geom.set("mesh", mesh)
                if mat:
                    geom.set("material", mat)
                geom.set("contype", "0")
                geom.set("conaffinity", "0")
        task_board.append(body)
        print(f"  SC mount+plug on {rail_name}: trans={translation:.4f}")
        mount_id += 1

    # ── Write output ───────────────────────────────────────────────
    ET.indent(tree, space="  ")
    tree.write(output_path, encoding="unicode", xml_declaration=False)

    print(f"\nWritten to: {output_path}")
    print("View with:")
    print(f"  cd ~/projects/Project-Automaton/References/aic")
    print(f"  pixi run python3 -m mujoco.viewer --mjcf=aic_utils/aic_mujoco/mjcf/scene_rand.xml")


def main():
    parser = argparse.ArgumentParser(description="Randomize AIC task board layout")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument("--input", type=str,
                        default=os.path.expanduser(
                            "~/projects/Project-Automaton/References/aic/"
                            "aic_utils/aic_mujoco/mjcf/aic_world.xml"),
                        help="Input aic_world.xml path")
    parser.add_argument("--out", type=str,
                        default=os.path.expanduser(
                            "~/projects/Project-Automaton/References/aic/"
                            "aic_utils/aic_mujoco/mjcf/aic_world_rand.xml"),
                        help="Output randomized XML path")
    parser.add_argument("--nic", type=int, default=None, help="Number of NIC cards (0-5)")
    parser.add_argument("--sc", type=int, default=None, help="Number of SC ports (0-2)")
    args = parser.parse_args()

    randomize(args.input, args.out, seed=args.seed,
              nic_count=args.nic, sc_count=args.sc)


if __name__ == "__main__":
    main()
