The best next move is **not** “jump into Isaac RL now.” It is: **use your existing local dataset to get one learned policy online in Gazebo first, while bringing Isaac up only far enough to prove the official AIC Isaac lane works.** That keeps Gazebo as the oracle, uses the shortest existing learning path in the repo, and avoids spending another week on simulator plumbing. The official AIC docs already give you three key facts that point this way: qualification is only a **single insertion** with the plug already in hand and the target port kept within view; AIC already ships a **LeRobot ACT** example policy; and the Isaac integration already supports **teleop, demo recording/replay, and `rsl-rl` training** using the official `AIC-Task-v0` and NVIDIA-prepared assets. ([GitHub][1])

The biggest place I differ from your current idea is this: I would **not** start by making a zoo of separate ACT experts for SC vs SFP and then hope to continue them directly into Isaac PPO. AIC qualification only covers SFP→SFP-port and SC→SC-port insertions, with the task explicitly specified and the target in view, so a **single task-conditioned model** is the right first bet. Also, the shipped learned baseline is **LeRobot ACT**, while the Isaac RL lane is wired around **`rsl-rl` PPO**; those are different policy families, so “ACT first, then continue with PPO” is not automatic unless you deliberately make the architectures compatible or distill from one into the other. Modularize the **pipeline** first—dataset adapter, learner, policy wrapper, evaluator—not the model zoo. ([GitHub][1])

Direct answers to your five questions:

1. **Start with ACT / BC first, not RL.** The repo already has a proof-of-concept `RunACT` path, and AIC’s Isaac lane already has recording and RL hooks, so the low-risk order is imitation first, RL second. That matters even more because the benchmark is insertion-dominated: full insertion is worth **75**, proximity is up to **25**, wrong-port insertion is **-12**, excessive force is **-12**, and off-limit contact is **-24**. RL from scratch can waste a lot of time on the wrong objective surface; BC gets you into the right part of state space first. ([GitHub][2])

2. **Use the existing local datasets first.** Based on your note, `experiment_8` is the only dataset large enough to matter immediately. But do a **2-hour schema audit first**. The current `RunACT.py` consumes three RGB images, a **26-dim state**, and a **7-dim action** with the first six values interpreted as Cartesian twist. Since your note says `experiment_8` is **48-dim state / 19-dim action**, do not assume it drops straight into the official path. If you can map it cleanly into the `RunACT` interface, use it. If not, stop and record a small clean canonical dataset instead of reverse-engineering a deployment-incompatible action space for days. ([GitHub][3])

3. **The smallest useful experiment** is not full Isaac RL. It is: overfit a tiny BC/ACT model on **3 high-quality episodes** from `experiment_8`, wrap it in a local policy class, and run **1 Gazebo trial** through your existing evaluator. The loop is “real” once the policy loads cleanly, emits stable commands, and gives you either **Tier 3 > 0** or at least clearly non-random target-seeking behavior. The AIC policy API already gives you synchronized RGB, joints, wrist wrench, TCP pose, and TCP velocity at up to **20 Hz**, so you do not need a giant architecture to prove the learning loop. ([GitHub][4])

4. **The first success criterion for Isaac Sim** should be modest and concrete: **`AIC-Task-v0` boots, teleop works, 10 demos record, 10 demos replay, and one learned policy beats `random_agent.py` / `zero_agent.py` on a simple internal metric such as final port distance or episode reward.** Do not make the first Isaac milestone “full RL solved insertion.” The official AIC Isaac README already gives you the scripts for `teleop.py`, `record_demos.py`, `replay_demos.py`, `random_agent.py`, `zero_agent.py`, and `rsl_rl/train.py`, and it explicitly recommends using the NVIDIA-prepared asset pack. It also explicitly lists **SDF world → USD export** as future work, which is your signal to stop sinking time into hand-fixing the taskboard USD. ([GitHub][5])

5. **Postpone**: custom USD export work, a router / MoE of many niche ACT models, direct PPO from scratch on 1000 envs, custom cable-physics hacking, Pi-0 / VLA work, and big “let’s clone 10 repos and integrate all of them” sprints. AIC explicitly encourages **training across simulators** rather than trying to force one simulator to become physically perfect, and the official Isaac path already assumes you will use the provided assets rather than building a fresh import pipeline first. ([GitHub][1])

## What to do now

Do these three things next, in this order:

1. **Audit `experiment_8` against the deployment interface.**
   Build one small script that prints the exact feature names, tensor shapes, and action semantics for `experiment_8`. Your decision gate is simple: can you project this dataset into the `RunACT`-style contract, or not? Since `experiment_8` already includes task IDs and score tiers, use those immediately: first training pass should use the best episodes or best segments, not the whole dataset blindly.

2. **Train one tiny BC/ACT baseline before touching RL.**
   Use 3 episodes first and deliberately overfit them. That tells you whether the dataset, loader, learner, checkpoint loader, and policy wrapper are coherent. Only after that should you scale to the full filtered dataset.

3. **Bring up official Isaac AIC using the provided assets, not your own taskboard USD.**
   The moment `AIC-Task-v0` teleops, records, and replays, Isaac becomes “real enough” for the next phase.

For the 5090 specifically, there is one known repo-level footgun: AIC’s troubleshooting doc says the Pixi-locked PyTorch can miss RTX 50xx support, and they report success on a 5090 by overriding to `torch >= 2.7.1` and `torchvision >= 0.22.1`. ([GitHub][6])

## One-week plan

**Day 1**
Freeze the Gazebo evaluator and do the `experiment_8` schema audit. Decide whether you can map it into the current `RunACT` contract. If yes, create a converter. If no, create a canonical schema spec and prepare to record a small clean dataset in that schema. Also patch Pixi for the 5090 if LeRobot / RunACT complains. ([GitHub][3])

**Day 2**
Train the smallest possible learner on **3 episodes**. Start narrow: one model, one checkpoint, one policy wrapper. Do not try to make it general. Your goal is a first deployable checkpoint, not a good policy yet. Use the current AIC ACT/LeRobot path wherever it reduces code you have to write. ([GitHub][2])

**Day 3**
Deploy that checkpoint through your existing Gazebo wrapper and run **1 trial**, then **3 trials**. Require that it loads, stays stable, and gives you a measurable signal such as nonzero Tier 3 or clear target-seeking behavior. Since Tier 2 is only awarded when Tier 3 is positive, keep your eyes on Tier 3 first. ([GitHub][7])

**Day 4**
Bring up the official Isaac AIC task. Use the official assets and scripts only. Run these as your smoke test inside the Isaac Lab setup:

```bash
isaaclab -p aic/aic_utils/aic_isaac/aic_isaaclab/scripts/list_envs.py
isaaclab -p aic/aic_utils/aic_isaac/aic_isaaclab/scripts/teleop.py \
  --task AIC-Task-v0 --num_envs 1 --teleop_device keyboard --enable_cameras
isaaclab -p aic/aic_utils/aic_isaac/aic_isaaclab/scripts/record_demos.py \
  --task AIC-Task-v0 --teleop_device keyboard --enable_cameras \
  --dataset_file ./datasets/aic_smoke.hdf5 --num_demos 10
isaaclab -p aic/aic_utils/aic_isaac/aic_isaaclab/scripts/replay_demos.py \
  --dataset_file ./datasets/aic_smoke.hdf5
```

The AIC Isaac docs already define these as the supported workflow, and they note that teleop-data recording requires wiring the external environment correctly, so this is a smoke test—not the new main blocker. ([GitHub][5])

**Day 5**
Fine-tune or retrain the BC/ACT baseline with mixed data: your best Gazebo dataset plus the tiny Isaac smoke dataset. Keep the model small and task-conditioned. Since your local dataset already includes task target IDs, use those as conditioning before you even think about separate SC/SFP experts.

**Day 6**
Only now do the first RL pilot in Isaac. Start **small**: 16–64 envs, short runs, and a low-dimensional or residual policy rather than full end-to-end vision RL. The official Isaac AIC task already includes `observations.py`, `rewards.py`, and `rsl_rl_ppo_cfg.py`, so start by reading those and modifying the existing reward and config instead of inventing a whole RL stack. Align your shaped reward with the benchmark: distance/alignment/insertion depth positive terms, plus force and off-limit penalties inspired by the official thresholds. ([GitHub][5])

**Day 7**
Run a bake-off through Gazebo, not just Isaac. Compare:
(1) Gazebo-only BC/ACT,
(2) mixed Gazebo+Isaac BC/ACT,
(3) the first Isaac RL fine-tune / residual policy.
Keep only the branch that actually improves Gazebo evaluation. Gazebo remains the benchmark truth branch even if Isaac becomes the main learning lane. ([GitHub][1])

## What not to do yet

Do **not** keep fighting the taskboard USD. The AIC Isaac path already recommends NVIDIA-prepared assets, and the README still lists SDF→USD export as future work. ([GitHub][5])

Do **not** build a router of separate ACT models yet. Qualification is only a single insertion task with the plug already in hand and the target in view, across only SFP and SC cases. One conditional model is the right first bet. ([GitHub][1])

Do **not** start with full RL from scratch on raw vision and huge parallel counts. Use RL only after a learned policy already reaches the right neighborhood. The benchmark’s biggest points are still insertion/proximity, and the big penalties are discontinuous enough that naive early RL is a time sink. ([GitHub][7])

Do **not** spend time trying to make cable physics “perfect” in Isaac or MuJoCo yet. AIC explicitly frames multi-simulator variation as something to exploit via domain randomization, not something you must eliminate before learning can begin. ([GitHub][1])

## Contingency plans and which papers to start with first

If the **policy/control** part is what keeps failing, start with **Cable Routing and Assembly using Tactile-driven Motion Primitives** and **IndustReal**. The tactile paper is the closest conceptual match to AIC’s reconfigurable cable-manipulation board: high-level visual task parsing plus low-level insertion/routing primitives. IndustReal is the most practical code-backed insertion reference: it is built around contact-rich insertion with perturb-and-insert structure and explicit deployment code, even though its hardware stack is Franka/RealSense/Isaac-Gym-oriented rather than AIC-native. From the sources I checked, I verified the tactile paper and project page, but I did **not** verify a public code release for it. I did verify the IndustRealLib repo. ([arXiv][8])

If the **single-model vs router** debate becomes the blocker, read **CableRouting** next—but treat it as a later-stage donor, not your first implementation target. Its repo is explicitly organized around routing data, primitive-selection data, and scripts for pretraining an embedding, training a routing BC model, training a high-level policy, and fine-tuning it. That is useful if you eventually need a primitive library or expert-selection policy, but it is overkill for the current qualification setup, which is only one insertion with the target already specified. ([GitHub][9])

If **cable perception** is the blocker, start with **HANDLOOM** first and only then look at **TrackDLO**. HANDLOOM is directly about cable state estimation from visual data with an iterative tracer and crossing classifier, and its repo ships real and simulated data examples for tracer training. TrackDLO is strong, but its own docs say it tracks DLO shape from **RGB-D image sequences** under occlusion. AIC’s policy interface gives you RGB images, wrench, joints, and controller state, but no official depth stream in the main observation contract, so TrackDLO is the lower-fit option unless you are generating depth only inside Isaac for auxiliary labels. ([GitHub][10])

If the blocker is **sim-to-sim robustness or cable stiffness variation**, start with **Learning for Deformable Linear Object Insertion Leveraging Flexibility Estimation from Visual Cues**. That paper is directly about conditioning DLO insertion on estimated flexibility and reports a two-stage pipeline of flexibility estimation plus policy learning. From the sources I checked, I verified the paper and project page, but I did **not** verify a public code repo for the full method. The idea is still immediately useful: use one conditional policy with a “material / stiffness” token before you try expert routing or simulator-physics surgery. ([arXiv][11])

If you need **dataset-design inspiration** rather than a direct method, start with **REASSEMBLE** and **WireFishing-M**. REASSEMBLE is a large multimodal contact-rich assembly dataset with 4,551 demonstrations, and WireFishing-M is a cable-insertion dataset with tactile, multi-view RGB, proprioceptive, and force signals. Neither is the fastest thing to “plug in” this week, but both are very good references for how to structure multimodal logs, align modalities, and think about failure labels. ([GitHub][12])

The most important sharpening of your current view is this: **“ACT first, RL second” is correct, but “many ACT experts first” is not.** At this stage, build **one** conditional learned policy, prove it in Gazebo, bring up the official Isaac task with the official assets, and only then decide whether the next increment is mixed-data fine-tuning or RL. The immediate move is:

**Stop touching custom USD import. Audit `experiment_8` against `RunACT`, train one tiny BC/ACT checkpoint, and run it through your Gazebo evaluator. In parallel, get `AIC-Task-v0` to teleop / record / replay with the official asset pack.**

[1]: https://raw.githubusercontent.com/intrinsic-dev/aic/main/docs/qualification_phase.md "https://raw.githubusercontent.com/intrinsic-dev/aic/main/docs/qualification_phase.md"
[2]: https://raw.githubusercontent.com/intrinsic-dev/aic/main/aic_example_policies/README.md "https://raw.githubusercontent.com/intrinsic-dev/aic/main/aic_example_policies/README.md"
[3]: https://raw.githubusercontent.com/intrinsic-dev/aic/main/aic_example_policies/aic_example_policies/ros/RunACT.py "https://raw.githubusercontent.com/intrinsic-dev/aic/main/aic_example_policies/aic_example_policies/ros/RunACT.py"
[4]: https://raw.githubusercontent.com/intrinsic-dev/aic/main/docs/policy.md "https://raw.githubusercontent.com/intrinsic-dev/aic/main/docs/policy.md"
[5]: https://raw.githubusercontent.com/intrinsic-dev/aic/main/aic_utils/aic_isaac/README.md "https://raw.githubusercontent.com/intrinsic-dev/aic/main/aic_utils/aic_isaac/README.md"
[6]: https://raw.githubusercontent.com/intrinsic-dev/aic/main/docs/troubleshooting.md "https://raw.githubusercontent.com/intrinsic-dev/aic/main/docs/troubleshooting.md"
[7]: https://raw.githubusercontent.com/intrinsic-dev/aic/main/docs/scoring.md "https://raw.githubusercontent.com/intrinsic-dev/aic/main/docs/scoring.md"
[8]: https://arxiv.org/abs/2303.11765 "https://arxiv.org/abs/2303.11765"
[9]: https://github.com/tan-liam/CableRouting "https://github.com/tan-liam/CableRouting"
[10]: https://github.com/vainaviv/handloom "https://github.com/vainaviv/handloom"
[11]: https://arxiv.org/abs/2410.23428 "https://arxiv.org/abs/2410.23428"
[12]: https://github.com/TUWIEN-ASL/REASSEMBLE "https://github.com/TUWIEN-ASL/REASSEMBLE"
