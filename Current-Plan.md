One correction before the plan: the public AIC pages I could verify today are not fully aligned on the exact qualification cutoff. The Open Robotics challenge-details post says qualification runs roughly three months and is “by June 30, 2026,” while the Intrinsic event page says the challenge starts March 2 and runs through September 2026, with qualification lasting about 2.5 months. So I would treat **May 27** as your internal freeze if that came from team mail or the portal, and the public late-June date as the outer bound. The plan below still works either way. ([Open Robotics Discourse][1])

The big revision is real: Gazebo is still the evaluator, but AIC now officially ships **Isaac Lab** and **MuJoCo** mirror environments for training. The Isaac package is for teleop, demo recording/replay, and `rsl-rl` training; the MuJoCo package can load exported Gazebo worlds, expose the same ROS topics, and run the same `ros2_control` interface so policies can move between Gazebo and MuJoCo without policy-code changes. ([GitHub][2])

Another doc mismatch matters: `scoring.md` now gives Tier-2 ceilings of **6 / 12 / 6** and Tier-3 full insertion of **75**, while `scoring_tests.md` still shows older **5 / 10 / 5 / 60** examples. Use **`scoring.md` as the truth** for thresholds, and use `scoring_tests.md` only for launch recipes and qualitative expectations. Also, the public evaluation cloud is a single **NVIDIA L4 with 24 GB VRAM**, so train on your 5090, but always keep at least one inference path that fits that cloud budget. ([GitHub][3])

## Revised operating model

Use three lanes, with Gazebo at the center.

* **Gazebo/Kilted = truth lane.** All real decisions get validated here, and every serious experiment ends in a fresh `scoring.yaml`. Official evaluation is ROS 2 Kilted, and cross-distro communication is explicitly not guaranteed, so Gazebo is where you measure progress. ([GitHub][4])
* **MuJoCo = controller lane.** Export Gazebo world to `/tmp/aic.sdf` → fix URIs → `sdf2mjcf` → `add_cable_plugin.py` → `aic_mujoco_bringup.launch.py` → sweep gains fast → bring best gains back into Gazebo. The AIC MuJoCo docs are already set up for this. ([GitHub][5])
* **Isaac Lab = data/learning lane.** Use the official AIC Isaac task and NVIDIA-prepared assets for teleop, demo recording, replay, and RL training. Bridge **datasets and checkpoints** back into Kilted/Gazebo instead of trying to live-wire Isaac ROS into your Kilted stack. ([GitHub][6])

I’m treating this as the **next 100 hours from now**, so effectively **hour 5 → hour 105**.

---

## Hours 5–15: finish the official baseline map and build the harness

The goal of this block is to make your local loop boring and repeatable. You already have WaveArm and a CheatCode run in progress. Finish that, then run the remaining official baselines: `GentleGiant`, `SpeedDemon`, `WallToucher`, and `WallPresser`. Those examples are useful because the AIC docs spell out what each one is meant to teach you: low jerk, high jerk, off-limit contact, and excessive force. ([GitHub][7])

Use one repeatable three-terminal pattern for all Gazebo/source-based runs:

```bash
# terminal 0
source ~/ws_aic/install/setup.bash
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
export ZENOH_ROUTER_CHECK_ATTEMPTS=-1
export ZENOH_CONFIG_OVERRIDE='transport/shared_memory/enabled=true;transport/shared_memory/transport_optimization/pool_size=536870912'
ros2 run rmw_zenoh_cpp rmw_zenohd
```

```bash
# terminal 1 (example: GentleGiant)
source ~/ws_aic/install/setup.bash
ros2 run aic_model aic_model --ros-args \
  -p use_sim_time:=true \
  -p policy:=aic_example_policies.ros.GentleGiant
```

```bash
# terminal 2
source ~/ws_aic/install/setup.bash
AIC_RESULTS_DIR=~/aic_results/gentle_giant_$(date +%F_%H%M%S) \
ros2 launch aic_bringup aic_gz_bringup.launch.py \
  ground_truth:=true \
  start_aic_engine:=true
```

That launch pattern, the unique `AIC_RESULTS_DIR`, and the fact that results land in `scoring.yaml` all come straight from the official docs. ([GitHub][8])

Tasks for this block:

* Let `CheatCode` finish and save its run folder untouched.
* Run `GentleGiant`, `SpeedDemon`, `WallToucher`, `WallPresser`.
* Create one script, e.g. `scripts/run_gazebo_eval.sh`, that takes `policy`, `ground_truth`, and `results_dir`.
* Create one parser, e.g. `scripts/collect_scores.py`, that reads every `scoring.yaml` and writes a single CSV.

Done when:

* you have one CSV with all official example policies,
* you can explain one concrete example of each penalty/reward,
* every new Gazebo run takes one command and leaves behind logs plus `scoring.yaml`. ([GitHub][8])

---

## Hours 15–25: bring up the official MuJoCo mirror

This block is now early, not optional. The AIC MuJoCo integration is the fastest way to get controller intuition while staying simulator-compatible with Gazebo. It converts Gazebo SDF to MJCF, adds cable/FT/TCP details, and exposes the same controller interface so example policies can run unchanged. ([GitHub][5])

Because you already have a separate MuJoCo/MJX/Warp setup, do this first:

```bash
env | grep MUJOCO
```

If you see old `MUJOCO_PATH`, `MUJOCO_PLUGIN_PATH`, or `MUJOCO_DIR` exports, remove them before building `mujoco_vendor`; the AIC docs explicitly warn about this conflict. ([GitHub][5])

Then do the official AIC MuJoCo path:

```bash
cd ~/ws_aic/src
vcs import < aic/aic_utils/aic_mujoco/mujoco.repos

cd ~/ws_aic
source /opt/ros/kilted/setup.bash
colcon build --packages-select sdformat_mjcf
source install/setup.bash
```

```bash
# export the Gazebo world
ros2 launch aic_bringup aic_gz_bringup.launch.py \
  spawn_task_board:=true \
  spawn_cable:=true \
  cable_type:=sfp_sc_cable \
  attach_cable_to_gripper:=true \
  ground_truth:=true
```

```bash
# fix the exported SDF and convert
sed -i 's|file:///model://|model://|g' /tmp/aic.sdf
sed -i 's|file:///lc_plug_visual.glb|model://LC Plug/lc_plug_visual.glb|g' /tmp/aic.sdf
sed -i 's|file:///sc_plug_visual.glb|model://SC Plug/sc_plug_visual.glb|g' /tmp/aic.sdf
sed -i 's|file:///sfp_module_visual.glb|model://SFP Module/sfp_module_visual.glb|g' /tmp/aic.sdf

mkdir -p ~/aic_mujoco_world
sdf2mjcf /tmp/aic.sdf ~/aic_mujoco_world/aic_world.xml
cp ~/aic_mujoco_world/* ~/ws_aic/src/aic/aic_utils/aic_mujoco/mjcf
```

Run `add_cable_plugin.py` in a fresh terminal without your ROS workspace sourced, exactly as the docs note, then rebuild `aic_mujoco`. After that, launch:

```bash
source ~/ws_aic/install/setup.bash
ros2 launch aic_mujoco aic_mujoco_bringup.launch.py
```

The docs also say any example policy in `aic_example_policies` can be used in MuJoCo, so your 2-hour smoke test is simply: **launch MuJoCo, run `WaveArm`, then run one more example policy unchanged**. ([GitHub][5])

Done when:

* `scene.xml` opens in MuJoCo,
* `aic_mujoco_bringup.launch.py` launches,
* `WaveArm` runs in MuJoCo with the same `aic_model` command you use in Gazebo,
* you have one note documenting any behavior differences between Gazebo and MuJoCo. ([GitHub][5])

---

## Hours 25–35: bring up the official Isaac Lab lane

Isaac Lab should now come in early because AIC’s own Isaac package already supports teleop, demo recording/replay, and `rsl-rl` training, and it is tested with **Isaac Lab 2.3.2**. It also ships a reference RL env, `AIC-Task-v0`. ([GitHub][6])

Use the official AIC Isaac path, not a custom local Frankenstein install. The AIC docs recommend cloning Isaac Lab, cloning AIC inside it, using the Docker container, installing `aic_task`, then running teleop/record/replay/train inside that container. Isaac Lab’s own docs also require **Python 3.11** for Isaac Sim 5.x. ([GitHub][6])

Core setup:

```bash
cd ~
git clone https://github.com/isaac-sim/IsaacLab.git
cd ~/IsaacLab
git clone https://github.com/intrinsic-dev/aic.git

./docker/container.py build base
./docker/container.py start base
./docker/container.py enter base

python -m pip install -e aic/aic_utils/aic_isaac/aic_isaaclab/source/aic_task
```

Then, after placing the NVIDIA-prepared asset pack where the AIC README instructs:

```bash
isaaclab -p aic/aic_utils/aic_isaac/aic_isaaclab/scripts/list_envs.py

isaaclab -p aic/aic_utils/aic_isaac/aic_isaaclab/scripts/teleop.py \
  --task AIC-Task-v0 --num_envs 1 --teleop_device keyboard --enable_cameras

isaaclab -p aic/aic_utils/aic_isaac/aic_isaaclab/scripts/record_demos.py \
  --task AIC-Task-v0 --teleop_device keyboard --enable_cameras \
  --dataset_file ./datasets/aic_demo.hdf5 --num_demos 10

isaaclab -p aic/aic_utils/aic_isaac/aic_isaaclab/scripts/replay_demos.py \
  --dataset_file ./datasets/aic_demo.hdf5
```

Those commands and file paths are straight from the AIC Isaac README. ([GitHub][6])

After the single-env smoke test, scale `--num_envs` upward cautiously. Isaac Lab is built around vectorized environments and massively parallel RL, but the exact ceiling is task-dependent. On your 5090, start at **64**, then **128**, then **256**, and only go higher if GPU memory and step time remain healthy. Do not hardcode “thousands” on day one just because the GPU is strong; find the stable knee first. ([Isaac Sim][9])

One important limitation: the AIC Isaac README still lists **“Add SDF World to USD asset export pipeline”** as future work. So do **not** spend early time trying to build a perfect Gazebo→USD exporter; use the provided AIC Isaac task and NVIDIA-prepared assets first. ([GitHub][6])

Done when:

* `AIC-Task-v0` runs,
* you recorded and replayed at least 10 demos,
* you know the highest stable `num_envs` for your machine at this stage.

---

## Hours 35–45: create your own policy package and logger

Now that all three simulator lanes exist, make your own policy node. The AIC policy docs say the policy gets time-synchronized `Observation` data at up to 20 Hz: three wrist RGB images, three `CameraInfo`s, joint states, wrist wrench, and controller state. That is the exact interface your logger should mirror. ([GitHub][10])

Follow the official tutorial once, but stop at the minimal working custom node:

```bash
cd ~/ws_aic/src/aic
pixi shell
ros2 pkg create my_policy_node --build-type ament_python
cp aic_example_policies/aic_example_policies/ros/WaveArm.py \
   my_policy_node/my_policy_node/WaveArm.py
pixi reinstall ros-kilted-my-policy-node
pixi run ros2 run aic_model aic_model --ros-args \
  -p use_sim_time:=true \
  -p policy:=my_policy_node.WaveArm
```

That package-creation and run flow is the official AIC path. ([GitHub][10])

Then add a logger with this directory shape:

```text
runs/
  2026-03-21_run_001/
    metadata.json
    scoring.yaml
    task.json
    observations/
      frame_000001/
        left.png
        center.png
        right.png
        left_camera_info.json
        center_camera_info.json
        right_camera_info.json
        joint_states.json
        wrist_wrench.json
        controller_state.json
```

Do not overengineer it. The point is reproducibility.

Done when:

* your own package runs through `aic_model`,
* your logger saves one full trial end to end,
* you can replay one trial offline without Gazebo running.

---

## Hours 45–55: build the cross-simulator data factory

This is the first block where the three lanes start feeding each other.

### 1) Gazebo GT demos

Use `CheatCode` with `ground_truth:=true` to collect auto-demonstrations and labels. This is exactly what the official docs position it for: training and debugging only, not evaluation. Also, the qualification setup is a **single insertion per trial**, with the robot already holding the plug and starting close to the target, so your early dataset should focus on the approach/alignment/insertion window rather than full routing. ([GitHub][7])

### 2) Gazebo human demos

Use the AIC LeRobot adapter to teleoperate and record a small human dataset in the exact controller stack you will deploy:

```bash
cd ~/ws_aic/src/aic
pixi run lerobot-record \
  --robot.type=aic_controller --robot.id=aic \
  --teleop.type=aic_keyboard_ee --teleop.id=aic \
  --robot.teleop_target_mode=cartesian --robot.teleop_frame_id=base_link \
  --dataset.repo_id=${HF_USER}/aic_demo_v0 \
  --dataset.single_task=aic_insert \
  --dataset.push_to_hub=false --dataset.private=true \
  --play_sounds=false --display_data=true
```

The same package also supports teleoperation. ([GitHub][11])

### 3) Isaac demos

Use the Isaac Lab `record_demos.py` path to collect a second, separate demo set from the same task environment. Because the task-board geometry is randomized and the target is guaranteed to be within camera view, these demos are useful for perception and policy pretraining even before they are perfect. ([GitHub][6])

Your output at the end of this block should be:

* `dataset_gazebo_gt_v0`
* `dataset_gazebo_teleop_v0`
* `dataset_isaac_teleop_v0`

Done when:

* you have at least 30 GT trials,
* at least 15 human teleop trials,
* at least 10 Isaac teleop trials,
* all three datasets can be indexed by task type and trial ID.

---

## Hours 55–65: first non-GT controller and first MuJoCo sweep

This is the most important block in the whole plan.

The qualification task is still single insertion, the plug starts already in hand, and the target is within view of the robot cameras. That means your first non-GT policy should **not** start with full cable understanding. Start with:

1. target module / target port localization,
2. plug-tip localization,
3. analytic two-phase controller,
4. MuJoCo gain sweep. ([GitHub][2])

### Controller shape

Copy the good structure from `CheatCode`, but remove the cheating:

* phase A: move to pre-insert pose above target,
* phase B: align orientation,
* phase C: guarded descend,
* phase D: low-speed insertion hold / settle. ([GitHub][7])

### Minimal perception v0

Train the smallest thing that can possibly score:

* one detector / keypoint head for the target port,
* one detector / keypoint head for the plug tip,
* optionally center camera only first, then add left/right fusion later.

Because the task board randomizes rail positions and angles, but the target remains visible, this should be enough to chase **Tier 3 > 0** before you attempt richer cable-state models. ([GitHub][2])

### MuJoCo sweep

Use the official MuJoCo mirror path for controller gains:

* export current Gazebo world,
* convert to MJCF,
* sweep stiffness/damping/feedforward and insertion speed,
* take the top 5 settings back into Gazebo.

Keep a simple CSV:
`gain_id, sim, success, max_force, off_limit, duration, tier3, notes`

Done when:

* your non-GT controller reaches the port entrance reliably in sim,
* at least one Gazebo run earns **Tier 3 > 0** without GT,
* you have one “best-so-far” gain set from MuJoCo that also survives Gazebo.

---

## Hours 65–75: perception repo sprint — HANDLOOM and TrackDLO

### `vainaviv/handloom`

Map: **perception**. The repo is explicitly a cable state-estimation pipeline with a learned iterative tracer and crossing handling. ([GitHub][12])

Clone now.
2-hour smoke test:

* run the repo on 20–50 logged AIC RGB frames,
* crop around the cable,
* check whether it produces a stable centerline and a useful end-of-cable / local cable orientation cue.

Keep if:

* it improves plug-end localization, cable ROI selection, or occlusion handling.

Kill if:

* it needs more than ~4 extra hours just to get first useful output on AIC images,
* or the traced centerline is too unstable to help insertion.

### `RMDLO/trackdlo`

Map: **perception**, but high risk. The repo is a ROS/C++ implementation of TrackDLO, and the paper targets shape tracking of DLOs under occlusion from **RGB-D** sequences. AIC’s observation API gives you RGB images, camera intrinsics, joint state, wrench, and controller state, but no official depth stream. ([GitHub][13])

Clone now anyway.
2-hour smoke test:

* build the package,
* run its sample/demo path,
* identify exactly where RGB-D is assumed,
* decide whether you can use it only in the **Isaac synthetic lane** to generate pseudo-labels or temporal cable priors.

Keep if:

* there is a short path to RGB-only / multi-view adaptation,
* or it becomes a useful offline label generator in Isaac.

Kill if:

* the RGB-D assumption is hard-baked and gives you no short bridge into AIC.

At the end of this block, you should either keep one perception repo or cut both quickly.

---

## Hours 75–85: learner sprint 1 — RunACT and LeRobot

This block is about getting one learning-based policy to boot in the actual AIC loop.

First, patch the 5090 issue. AIC’s troubleshooting doc explicitly says the Pixi-locked PyTorch can fail on RTX 50xx cards and suggests overriding to `torch >= 2.7.1` and `torchvision >= 0.22.1`. ([GitHub][14])

Add this to `~/ws_aic/src/aic/pixi.toml`:

```toml
[pypi-options.dependency-overrides]
torch = ">=2.7.1"
torchvision = ">=0.22.1"
```

Then reinstall and run the official learned baseline:

```bash
cd ~/ws_aic/src/aic
pixi install
pixi run ros2 run aic_model aic_model --ros-args \
  -p use_sim_time:=true \
  -p policy:=aic_example_policies.ros.RunACT
```

The AIC docs describe `RunACT` as a proof-of-concept LeRobot ACT policy trained from a small dataset collected with `lerobot-record`. ([GitHub][7])

Then train your own tiny ACT baseline with LeRobot:

* dataset = your `dataset_gazebo_teleop_v0` or converted LeRobotDataset,
* model = ACT,
* objective = just prove train → load → inference.

LeRobot’s current README says it provides a hardware-agnostic robot interface, a standardized dataset format, and pure-PyTorch implementations of ACT, Diffusion, and other policies. ([GitHub][15])

Keep if:

* you can train one checkpoint and load it into an AIC policy class.

Kill if:

* the stack still fights the 5090 after the documented PyTorch override,
* or the inference path bloats beyond what you can plausibly fit on the public L4 evaluator. ([GitHub][4])

---

## Hours 85–95: learner/planner sprint 2 — ACT++, Diffusion Policy, CableRouting, IndustReal, tactile paper, reference datasets

### `MarkFzp/act-plus-plus`

Map: **learner**. This repo includes ACT, Diffusion Policy, VINN, and two sim environments, including bimanual insertion. It expects an older stack: Python 3.8, MuJoCo 2.3.7, `dm_control`, and optional `robomimic` for Diffusion Policy. ([GitHub][16])

Clone in an isolated env.
2-hour smoke test:

* get `sim_insertion_scripted` or `sim_transfer_cube_scripted` running,
* generate 5–10 episodes,
* run one ACT training/eval command.

Keep if:

* the code is easy to mine for training loops and action chunking,
* and converting your AIC demos into its format looks tractable.

Kill if:

* the environment/version lock costs too much time.

### `real-stanford/diffusion_policy`

Map: **learner**. The repo’s own README points to self-contained state and vision Colabs as the easiest entry. ([GitHub][17])

Clone in an isolated env.
2-hour smoke test:

* run the vision demo path,
* identify required dataset schema,
* decide whether your Gazebo/Isaac demo format can be converted in under a day.

Keep if:

* it gives you a clean second learner baseline after ACT.

Kill if:

* dataset conversion or environment assumptions are too far from AIC.

### `tan-liam/CableRouting`

Map: **planner / high-level policy**. The repo has a routing dataset, preprocessing, and policy-training flow, and the paper is about multi-stage cable routing through primitives. But AIC qualification is only a **single insertion** with the plug already grasped and starting near the target. ([GitHub][18])

Clone now, but treat it as a **planner donor**, not a full solver.
2-hour smoke test:

* inspect the primitive library and policy decomposition,
* run the dataset preprocessing once,
* extract whether its state-machine structure helps your AIC controller phases.

Keep if:

* it gives you a cleaner hierarchical policy skeleton.

Kill if:

* it remains mostly about long-horizon routing that qualification does not need.

### `NVlabs/industreallib`

Map: **controller / insertion donor**. IndustRealLib has explicit task/sequence structure, insertion examples, and code organization around pick/place/insert; but it is heavily Franka- and real-workcell-oriented, with perception models and RL policies tested on a different stack. ([GitHub][19])

Clone now as a donor.
2-hour smoke test:

* inspect `run_task.py`, `run_sequence.py`, and `insert_*` configs,
* identify observation → action → guide-mode → insertion-policy flow,
* extract any reward-shaping, guarded-motion, or sequence ideas worth transplanting.

Keep if:

* you can lift a concrete insertion pattern into AIC within a day.

Kill if:

* it stays too hardware-specific to Franka/IndustRealKit.

### “Cable Routing and Assembly using Tactile-driven Motion Primitives”

Map: **controller design donor**, not a code integration sprint. I verified the paper and project page, but I did **not** verify a public code release from the sources I checked. The main idea is still highly relevant: high-level vision parsing plus tactile-guided low-level primitives on a reconfigurable task board. ([arXiv][20])

2-hour smoke test:

* write down three AIC primitives inspired by it:

  1. guarded align,
  2. force-guided descend,
  3. insertion settle/hold,
* implement one of those using AIC wrist wrench + controller gains.

Keep if:

* it improves your controller spec.

Kill if:

* it stays “interesting paper” with no immediate code consequence.

### `TUWIEN-ASL/REASSEMBLE` and `WireFishing-M`

Map: **reference datasets only**. REASSEMBLE is a multimodal assembly dataset with 4,551 demos and modalities including event cameras, F/T, microphones, and multi-view RGB. WireFishing-M is a multimodal deformable cable-insertion dataset with seven cable types and synchronized tactile, multi-view RGB, joint, pose, and force data. ([GitHub][21])

2-hour smoke test:

* download metadata or one sample,
* compare their schema against your own logger,
* borrow ideas for labeling, failure taxonomy, and modality alignment.

Keep if:

* they improve your logger or evaluation design.

Kill if:

* they stay purely inspirational and do not sharpen your AIC datasets.

---

## Hours 95–105: Gazebo bake-off, freeze the mainline, and package the winner

Finish by comparing only the branches that survived:

1. analytic controller + GT-fed poses,
2. analytic controller + non-GT perception v0,
3. controller + kept perception repo features,
4. ACT baseline,
5. any hybrid policy with MuJoCo-tuned gains.

Every comparison goes through Gazebo scoring, because that is the evaluator. Track:

* Tier 3 average,
* full-insert count,
* force penalties,
* off-limit penalties,
* duration,
* failure mode. ([GitHub][3])

At the end of hour 105 you should have:

* one Gazebo truth branch,
* one MuJoCo sweep lane that you trust,
* one Isaac Lab recording / RL lane,
* one custom `aic_model` policy package,
* one working logger,
* one non-GT baseline that has already hit **Tier 3 > 0** in Gazebo,
* one learned-policy path that at least boots,
* one short list of external repos you are **keeping**, and a longer list you have **killed** deliberately.

That is the right base for the next 100 hours.

## The repository recap

* **Clone now (hours 65–95):** `handloom`, `trackdlo`, `act-plus-plus`, `diffusion_policy`, `CableRouting`, `industreallib`. ([GitHub][12])
* **Run early and keep as core tools:** AIC `RunACT`, AIC `lerobot_robot_aic`, AIC MuJoCo mirror, AIC Isaac Lab mirror. ([GitHub][7])
* **Read/borrow, not full-code integrate:** tactile motion-primitives paper, REASSEMBLE, WireFishing-M. ([arXiv][20])

The immediate next move is simple: **finish CheatCode, run the four remaining official baselines, then spend your next block bringing up the official MuJoCo mirror before touching Isaac Lab.** That gives you the fastest path to a three-simulator workflow without losing Gazebo as the truth branch.

[1]: https://discourse.openrobotics.org/t/ai-for-industry-challenge-challenge-details/52380 "https://discourse.openrobotics.org/t/ai-for-industry-challenge-challenge-details/52380"
[2]: https://raw.githubusercontent.com/intrinsic-dev/aic/main/docs/qualification_phase.md "https://raw.githubusercontent.com/intrinsic-dev/aic/main/docs/qualification_phase.md"
[3]: https://raw.githubusercontent.com/intrinsic-dev/aic/main/docs/scoring.md "https://raw.githubusercontent.com/intrinsic-dev/aic/main/docs/scoring.md"
[4]: https://raw.githubusercontent.com/intrinsic-dev/aic/main/docs/getting_started.md "https://raw.githubusercontent.com/intrinsic-dev/aic/main/docs/getting_started.md"
[5]: https://raw.githubusercontent.com/intrinsic-dev/aic/main/aic_utils/aic_mujoco/README.md "https://raw.githubusercontent.com/intrinsic-dev/aic/main/aic_utils/aic_mujoco/README.md"
[6]: https://raw.githubusercontent.com/intrinsic-dev/aic/main/aic_utils/aic_isaac/README.md "https://raw.githubusercontent.com/intrinsic-dev/aic/main/aic_utils/aic_isaac/README.md"
[7]: https://raw.githubusercontent.com/intrinsic-dev/aic/main/aic_example_policies/README.md "https://raw.githubusercontent.com/intrinsic-dev/aic/main/aic_example_policies/README.md"
[8]: https://raw.githubusercontent.com/intrinsic-dev/aic/main/docs/scoring_tests.md "https://raw.githubusercontent.com/intrinsic-dev/aic/main/docs/scoring_tests.md"
[9]: https://isaac-sim.github.io/IsaacLab/main/source/setup/quickstart.html "https://isaac-sim.github.io/IsaacLab/main/source/setup/quickstart.html"
[10]: https://raw.githubusercontent.com/intrinsic-dev/aic/main/docs/policy.md "https://raw.githubusercontent.com/intrinsic-dev/aic/main/docs/policy.md"
[11]: https://raw.githubusercontent.com/intrinsic-dev/aic/main/aic_utils/lerobot_robot_aic/README.md "https://raw.githubusercontent.com/intrinsic-dev/aic/main/aic_utils/lerobot_robot_aic/README.md"
[12]: https://github.com/vainaviv/handloom "https://github.com/vainaviv/handloom"
[13]: https://github.com/RMDLO/trackdlo "https://github.com/RMDLO/trackdlo"
[14]: https://raw.githubusercontent.com/intrinsic-dev/aic/main/docs/troubleshooting.md "https://raw.githubusercontent.com/intrinsic-dev/aic/main/docs/troubleshooting.md"
[15]: https://raw.githubusercontent.com/huggingface/lerobot/main/README.md "https://raw.githubusercontent.com/huggingface/lerobot/main/README.md"
[16]: https://raw.githubusercontent.com/MarkFzp/act-plus-plus/main/README.md "https://raw.githubusercontent.com/MarkFzp/act-plus-plus/main/README.md"
[17]: https://raw.githubusercontent.com/real-stanford/diffusion_policy/main/README.md "https://raw.githubusercontent.com/real-stanford/diffusion_policy/main/README.md"
[18]: https://github.com/tan-liam/CableRouting "https://github.com/tan-liam/CableRouting"
[19]: https://github.com/NVlabs/industreallib "https://github.com/NVlabs/industreallib"
[20]: https://arxiv.org/abs/2303.11765 "https://arxiv.org/abs/2303.11765"
[21]: https://github.com/TUWIEN-ASL/REASSEMBLE "https://github.com/TUWIEN-ASL/REASSEMBLE"
