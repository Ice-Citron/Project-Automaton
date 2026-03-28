# Handoff to Isaac Lab Instance — Critical Findings (2026-03-28)

## TL;DR

**The component placement blocker is a non-issue.** Plugs DON'T go on the task board. They're cable endpoints held by the gripper. Mounts start EMPTY. Stop trying to place plugs inside mounts.

---

## What We Discovered (MuJoCo Instance)

After reading the official AIC docs (`sample_config.yaml`, `scene_description.md`, `aic_bringup/README.md`), the actual competition flow is:

1. **Task board spawns** with EMPTY mount fixtures on rails (LC/SFP/SC mounts)
2. **Cable spawns** near the gripper, attached to it (`attach_cable_to_gripper:=true`)
3. **Plugs are cable endpoints** — LC plug + SFP module on one end, SC plug on the other
4. **The robot's task** is to INSERT the plugs INTO the empty mounts
5. **Mounts never have plugs pre-inserted**

### What the randomizer should do:
- Randomize board pose (x, y, z, yaw)
- Randomize which rails have mount fixtures and where (translation along rail)
- Randomize NIC card positions on NIC rails
- Randomize SC port positions on SC rails
- Randomize cable type (`sfp_sc_cable` or `sfp_sc_cable_reversed`)
- Do NOT place plugs inside mounts

### Rail translation limits (from sample_config.yaml):
```yaml
nic_rail:   min=-0.0215, max=0.0234
sc_rail:    min=-0.06, max=0.055
mount_rail: min=-0.09425, max=0.09425
```

### Mount rail types (6 total):
| Rail | Component Type | Side |
|------|---------------|------|
| lc_mount_rail_0 | LC mount | Left (Y=-0.10625) |
| sfp_mount_rail_0 | SFP mount | Left |
| sc_mount_rail_0 | SC mount | Left |
| lc_mount_rail_1 | LC mount | Right (Y=+0.10625) |
| sfp_mount_rail_1 | SFP mount | Right |
| sc_mount_rail_1 | SC mount | Right |

### Competition evaluation constraints:
- Roll and pitch are ALWAYS 0.0 during eval
- SC port yaw is ALWAYS 0.0 during eval
- But you CAN randomize orientations for domain randomization during training

---

## For Your Component Placement

Your 3 known-good positions ARE correct:
```python
task_board.init_state.pos = (0.2837, 0.229, 0.0)
sc_port.init_state.pos = (0.2904, 0.1928, 0.005)
nic_card.init_state.pos = (0.25135, 0.25229, 0.0743)
```

For the mount fixtures (LC/SFP/SC mounts), you just need to:
1. Compute the board→world transform from the known-good positions
2. Apply XACRO rail positions through that transform
3. Add a translation offset along the rail Y-axis

The mounts are visual-only fixtures that define WHERE the robot should insert. They don't need complex collision or physics.

---

## MuJoCo Pipeline Status (For Reference)

- sdf2mjcf conversion already done (hash-named OBJ/PNG files in mjcf/)
- Material fixes applied (textures visible, glass transparent)
- randomize_board.py working (empty mounts on rails)
- CheatCode policy has direct body position access via `data.xpos`
- Camera rate needs fixing (1Hz → 20Hz)
- Gazebo launch broken in WSL2 (transport issue), eval container not set up yet

---

## Key Docs to Read

If you haven't already:
- `aic/aic_engine/config/sample_config.yaml` — Master trial/scene config
- `aic/docs/scene_description.md` — Official pipeline (Gazebo → export → convert)
- `aic/aic_bringup/README.md` — All launch parameters documented
- `aic/aic_utils/aic_isaac/README.md` — Isaac Lab integration guide
