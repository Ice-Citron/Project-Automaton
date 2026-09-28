#!/usr/bin/env python3
"""
Extract PBR colors/textures from AIC GLB files and patch MuJoCo MJCF.

This script:
1. Reads each GLB file in aic_assets/models/
2. Extracts baseColorFactor (RGBA) and baseColorTexture (PNG) from PBR materials
3. Matches them to OBJ mesh names in the MuJoCo MJCF
4. Patches the MJCF <material> elements with correct colors
5. Saves embedded textures as PNG files for MuJoCo to reference

Usage:
  cd ~/projects/Project-Automaton/References/aic
  python3 ~/projects/Project-Automaton/Intrinsic-AI/patch_mujoco_materials.py
"""

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import trimesh


AIC_ROOT = os.path.expanduser("~/projects/Project-Automaton/References/aic")
MODELS_DIR = os.path.join(AIC_ROOT, "aic_assets/models")
MJCF_DIR = os.path.join(AIC_ROOT, "aic_utils/aic_mujoco/mjcf")
TEXTURE_DIR = os.path.join(MJCF_DIR, "textures")


def extract_glb_materials(glb_path):
    """Extract material colors and textures from a GLB file."""
    materials = {}
    try:
        scene = trimesh.load(glb_path)
    except Exception as e:
        print(f"  Failed to load {glb_path}: {e}")
        return materials

    if not hasattr(scene, "geometry"):
        return materials

    for mesh_name, mesh in scene.geometry.items():
        if not hasattr(mesh, "visual") or mesh.visual is None:
            continue
        v = mesh.visual
        if not hasattr(v, "material"):
            continue
        m = v.material

        color = None
        texture = None

        if hasattr(m, "baseColorFactor") and m.baseColorFactor is not None:
            color = np.array(m.baseColorFactor, dtype=float) / 255.0

        if hasattr(m, "baseColorTexture") and m.baseColorTexture is not None:
            texture = m.baseColorTexture

        if color is not None or texture is not None:
            materials[mesh_name] = {"color": color, "texture": texture}

    return materials


def build_color_map():
    """Build a map of GLB model name → dominant RGBA color."""
    color_map = {}

    for model_dir in sorted(Path(MODELS_DIR).iterdir()):
        if not model_dir.is_dir():
            continue

        glb_files = list(model_dir.glob("*.glb"))
        if not glb_files:
            continue

        for glb_path in glb_files:
            print(f"Processing: {glb_path.name}")
            materials = extract_glb_materials(str(glb_path))

            # Compute average color across all meshes in this GLB
            colors = [m["color"] for m in materials.values() if m["color"] is not None]
            if colors:
                avg_color = np.mean(colors, axis=0)
                # Also get the most common color (mode-ish)
                dominant = max(colors, key=lambda c: c[3] if len(c) > 3 else 1.0)
                glb_key = glb_path.stem  # e.g., "enclosure_visual"
                color_map[glb_key] = {
                    "avg": avg_color,
                    "dominant": dominant,
                    "all_colors": colors,
                    "per_mesh": materials,
                }
                print(f"  → dominant RGBA: ({dominant[0]:.2f}, {dominant[1]:.2f}, {dominant[2]:.2f}, {dominant[3]:.2f})")

            # Save any textures
            for mesh_name, mat_info in materials.items():
                if mat_info["texture"] is not None:
                    os.makedirs(TEXTURE_DIR, exist_ok=True)
                    tex = mat_info["texture"]
                    safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", f"{glb_path.stem}_{mesh_name}")
                    tex_path = os.path.join(TEXTURE_DIR, f"{safe_name}.png")
                    try:
                        from PIL import Image
                        if isinstance(tex, np.ndarray):
                            img = Image.fromarray(tex)
                            img.save(tex_path)
                            print(f"  Saved texture: {safe_name}.png ({tex.shape})")
                    except Exception as e:
                        print(f"  Failed to save texture {safe_name}: {e}")

    return color_map


def patch_mjcf_materials(color_map):
    """Patch MuJoCo MJCF material elements with extracted colors."""
    for xml_name in ["aic_world.xml", "aic_robot.xml"]:
        xml_path = os.path.join(MJCF_DIR, xml_name)
        if not os.path.exists(xml_path):
            continue

        print(f"\nPatching {xml_name}...")
        tree = ET.parse(xml_path)
        root = tree.getroot()

        patched = 0
        for mat_elem in root.iter("material"):
            mat_name = mat_elem.get("name", "")

            # Match material name to a GLB source
            # Material names look like: material_<hash>_<glb_stem>_<mesh_name>
            matched_glb = None
            for glb_key in color_map:
                if glb_key in mat_name:
                    matched_glb = glb_key
                    break

            if matched_glb and matched_glb in color_map:
                color = color_map[matched_glb]["dominant"]
                rgba_str = f"{color[0]:.4f} {color[1]:.4f} {color[2]:.4f} {color[3]:.4f}"
                old_rgba = mat_elem.get("rgba", "")
                mat_elem.set("rgba", rgba_str)
                mat_elem.set("shininess", "0.5")
                mat_elem.set("specular", "0.3")
                patched += 1

        # Also patch geom elements that have rgba but no material
        for geom in root.iter("geom"):
            geom_name = geom.get("name", "")
            if geom.get("rgba") is not None:
                continue  # Already has color
            # Try to match by mesh name
            mesh_ref = geom.get("mesh", "")
            for glb_key in color_map:
                if glb_key in mesh_ref or glb_key in geom_name:
                    color = color_map[glb_key]["dominant"]
                    rgba_str = f"{color[0]:.4f} {color[1]:.4f} {color[2]:.4f} {color[3]:.4f}"
                    # Don't override material reference, just note it
                    break

        print(f"  Patched {patched} materials")
        tree.write(xml_path, xml_declaration=False)


def main():
    print("=" * 60)
    print("AIC GLB → MuJoCo Material Patcher")
    print("=" * 60)
    print(f"Models dir: {MODELS_DIR}")
    print(f"MJCF dir: {MJCF_DIR}")
    print()

    color_map = build_color_map()

    print(f"\n{'=' * 60}")
    print(f"Color map summary ({len(color_map)} GLBs):")
    for key, info in sorted(color_map.items()):
        c = info["dominant"]
        print(f"  {key:40s} RGBA({c[0]:.2f}, {c[1]:.2f}, {c[2]:.2f}, {c[3]:.2f})")

    patch_mjcf_materials(color_map)
    print("\nDone! Reload the MuJoCo scene to see updated materials.")


if __name__ == "__main__":
    main()
