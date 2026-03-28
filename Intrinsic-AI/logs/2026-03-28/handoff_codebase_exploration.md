# Handoff: Codebase Exploration (2026-03-28)

## What's been explained so far

### Part 1: sample_config.yaml ✅
- Scoring topics (ROS 2 topics the evaluator watches)
- task_board_limits (legal rail translation ranges)
- Trial definitions (scene + cable + task per trial)
- Robot home joint positions
- Key insight: cable is pre-attached to gripper, plugs are cable endpoints

### Part 2: scene_description.md + aic_bringup/README.md ✅
- Official 4-step pipeline: Configure → Spawn in Gazebo → Export SDF → Convert to MuJoCo/Isaac
- ground_truth:=true flag gives GT TF frames (needed for CheatCode policy)
- Complete parameterization of mount rails (6 mount rails, 2 SC port rails, 5 NIC rails)
- Training scenario generation workflow (randomize in Gazebo, export, convert)
- Cable types: sfp_sc_cable vs sfp_sc_cable_reversed

## What still needs explaining

### Part 3: aic_utils/aic_mujoco/ (NEXT)
Files to cover:
- `README.md` — MuJoCo integration guide, known issues, setup instructions
- `launch/aic_mujoco_bringup.launch.py` — How MuJoCo launches with ROS 2
- `scripts/load_aic_world.py` — How sdf2mjcf conversion works
- `scripts/add_cable_plugin.py` — Post-processing for cable physics
- `scripts/view_scene.py` — Scene viewer
- `mujoco.repos` — Dependencies
- The relationship between the converter output and aic_world.xml

### Part 4: aic_utils/aic_isaac/ (AFTER PART 3)
Files to cover:
- `README.md` — Isaac Lab integration guide, known issues
- `aic_isaaclab/scripts/` — random_agent, teleop, record_demos, replay_demos, train, play
- `aic_isaaclab/source/aic_task/` — The actual Isaac Lab task definition
  - `aic_task_env_cfg.py` — Environment configuration
  - `mdp/observations.py` — What the agent sees
  - `mdp/rewards.py` — How the agent is scored
  - `mdp/events.py` — Domain randomization events
  - `agents/rsl_rl_ppo_cfg.py` — RL training hyperparameters

### Part 5: Other docs not yet explored
- `docs/aic_controller.md` — Impedance controller details
- `docs/policy.md` — Policy integration guide
- `docs/aic_interfaces.md` — ROS 2 interface specs
- `docs/scoring.md` — How scoring works
- `aic_example_policies/` — Example policy implementations

## Key discoveries that affect our approach
1. Mount→plug alignment should come from Gazebo export (physics-settled), not manual placement
2. ground_truth:=true gives CheatCode the TF frames it needs
3. Official workflow: randomize in Gazebo → export SDF → convert to MuJoCo/Isaac
4. Our MuJoCo-native randomizer is still useful but should generate scenes matching the Gazebo parameterization
