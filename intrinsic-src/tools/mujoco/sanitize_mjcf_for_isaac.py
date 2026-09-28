#!/usr/bin/env python3
"""
Create a sanitized copy of aic_world.xml with short filenames.
Isaac Sim's MJCF importer crashes on the long hash-based filenames.

This script:
1. Copies aic_world.xml to a temp directory
2. Renames all mesh/texture files to short names
3. Updates all XML references
4. Copies the referenced mesh/texture files with new names

Usage:
  pixi run python3 sanitize_mjcf_for_isaac.py
  Then copy the output directory to Windows for Isaac Sim import.
"""

import os
import re
import shutil
import xml.etree.ElementTree as ET

MJCF_DIR = os.path.expanduser(
    "~/projects/Project-Automaton/References/aic/aic_utils/aic_mujoco/mjcf"
)
OUTPUT_DIR = os.path.expanduser(
    "~/projects/Project-Automaton/Intrinsic-AI/data/mujoco/sanitized_mjcf"
)


def sanitize_filename(name):
    """Convert long hash filename to short clean name."""
    # Remove the long hash prefix (everything before the first underscore after the hash)
    # Pattern: <64-char-hash>_<descriptive_name>-<hash>.ext
    # We want just the descriptive part

    base, ext = os.path.splitext(name)

    # Try to extract the descriptive middle part
    # Example: "3c8f16...6b5_sc_plug_visual_merged_0-67f94a...f2.obj"
    #       → "sc_plug_visual_merged_0.obj"
    parts = base.split("_")

    # Find where the hash ends (hashes are 64 hex chars)
    desc_start = 0
    for i, part in enumerate(parts):
        if len(part) < 20 and not all(c in "0123456789abcdef" for c in part):
            desc_start = i
            break

    if desc_start > 0:
        desc = "_".join(parts[desc_start:])
        # Remove trailing hash after dash
        if "-" in desc:
            desc = desc.rsplit("-", 1)[0]
        return desc + ext

    return name  # Can't parse, keep original


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Parse aic_world.xml
    xml_path = os.path.join(MJCF_DIR, "aic_world.xml")
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Build rename mapping for all referenced files
    rename_map = {}
    used_names = set()

    # Find all file references in mesh and texture elements
    for elem in root.iter():
        file_attr = elem.get("file")
        if file_attr and ("." in file_attr):
            if file_attr not in rename_map:
                new_name = sanitize_filename(file_attr)
                # Handle duplicates
                base_new = new_name
                counter = 1
                while new_name in used_names:
                    base, ext = os.path.splitext(base_new)
                    new_name = f"{base}_{counter}{ext}"
                    counter += 1
                rename_map[file_attr] = new_name
                used_names.add(new_name)

    # Also rename mesh/material name attributes (they use the same long hashes)
    name_map = {}
    for elem in root.iter():
        name = elem.get("name", "")
        if len(name) > 60:
            short = sanitize_filename(name + ".tmp").replace(".tmp", "")
            base_short = short
            counter = 1
            while short in name_map.values():
                short = f"{base_short}_{counter}"
                counter += 1
            name_map[name] = short

    # Apply file renames
    for elem in root.iter():
        file_attr = elem.get("file")
        if file_attr and file_attr in rename_map:
            elem.set("file", rename_map[file_attr])

    # Apply name renames (mesh names, material names, and references)
    for elem in root.iter():
        for attr in ["name", "mesh", "material", "texture"]:
            val = elem.get(attr)
            if val and val in name_map:
                elem.set(attr, name_map[val])

        # Also check body1/body2 in contact excludes
        for attr in ["body1", "body2"]:
            val = elem.get(attr)
            if val and val in name_map:
                elem.set(attr, name_map[val])

    # Write sanitized XML
    out_xml = os.path.join(OUTPUT_DIR, "aic_world.xml")
    ET.indent(tree, space="  ")
    tree.write(out_xml, encoding="unicode", xml_declaration=False)

    # Copy renamed files
    copied = 0
    missing = 0
    for old_name, new_name in rename_map.items():
        src = os.path.join(MJCF_DIR, old_name)
        dst = os.path.join(OUTPUT_DIR, new_name)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            copied += 1
        else:
            print(f"  MISSING: {old_name}")
            missing += 1

    print(f"Sanitized {len(rename_map)} file references, {len(name_map)} name references")
    print(f"Copied {copied} files, {missing} missing")
    print(f"\nOutput: {OUTPUT_DIR}")
    print(f"XML: {out_xml}")

    # Print rename mapping for debugging
    print(f"\nFile renames:")
    for old, new in sorted(rename_map.items()):
        print(f"  {new}")


if __name__ == "__main__":
    main()
