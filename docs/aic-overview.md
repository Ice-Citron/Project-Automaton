# AI for Industry Challenge — Competition Overview

## What Is AIC?

The **AI for Industry Challenge (AIC)** is a robotics competition hosted by **Intrinsic AI** (Alphabet/Google's industrial robotics division). The task is to build an autonomous policy that can insert fiber-optic connectors (LC/SC/SFP cables) into ports on a task board, using only wrist cameras and force-torque feedback — mimicking real factory cable-routing work.

---

## Competition Format

### Timeline
- **Challenge start:** March 2, 2026
- **Qualification phase:** ~2.5 months (internal freeze ~May 27, outer bound June 30, 2026)
- **Full challenge end:** September 2026

### Environment
- **Robot:** UR5e arm with a parallel-jaw gripper
- **Task board:** Randomized rail positions and angles, with connector ports
- **Cables:** SFP module, LC plug, SC plug
- **Simulator:** Gazebo (ROS 2 Kilted) — the **official evaluator**
- **Cloud eval hardware:** Single NVIDIA L4 (24 GB VRAM) — your policy must fit here

### What a Trial Looks Like
1. Robot starts already holding the plug
2. Target port is guaranteed visible in at least one wrist camera
3. Robot must approach, align, and insert — **one insertion per trial**
4. Trial is scored and logged to `scoring.yaml`

### Observation Interface (20 Hz)
| Modality | Detail |
|----------|--------|
| 3x wrist RGB images | left, center, right |
| 3x CameraInfo | intrinsics per camera |
| Joint states | position, velocity, effort |
| Wrist wrench | 6-axis F/T sensor |
| Controller state | current impedance/mode |

---

## Scoring System

Source of truth: `docs/scoring.md` (NOT `scoring_tests.md`)

| Tier | Achievement | Points |
|------|-------------|--------|
| Tier 1 | Approach — cable moved into target region | up to 6 |
| Tier 2 | Alignment — plug oriented at port entrance | up to 12 |
| Tier 3 | Partial insertion | up to 6 |
| Full insertion | Plug fully seated | **75** |

### Penalties (score reductions)
- Wrist force > 20N
- Contact with off-limit zones (e.g., wrong ports, board edges)
- Excessive trial duration

**Winning means maximizing full insertions (75 pts each) while minimizing penalties.**

---

## The Competition Aims

1. **Advance physical AI** — demonstrate that learned policies can handle high-precision, contact-rich manipulation in unstructured environments
2. **Sim-to-real generalization** — policies trained in simulation must work on the randomized eval setup without GT poses
3. **Industrial relevance** — cable routing/insertion is a real unsolved bottleneck in electronics manufacturing
4. **Multi-modal perception** — teams must fuse wrist RGB + force/torque without depth sensors
5. **Safe compliance** — policies must be force-aware to avoid damaging cables or hardware

---

## How Novelty Is Explored

### Why this is genuinely hard
- No depth sensor — you only get RGB + F/T
- Task board geometry is randomized — no fixed port positions
- Connector insertion requires ~1mm precision
- Cable compliance means the object deforms unpredictably
- Force penalties punish naive stiff control

### Novelty vectors teams are exploring

**1. Perception**
- Keypoint detectors for plug-tip and target port localization from RGB only
- Cable state estimation (HANDLOOM-style iterative tracers for centerline)
- Multi-view fusion (left + center + right cameras for depth cues without a depth sensor)

**2. Control**
- **Variable impedance:** dynamically switching stiffness/damping per task phase
  - High stiffness in free-space approach (speed)
  - Low stiffness during insertion (compliance, avoids >20N penalty)
- **Force-guided primitives:** using wrist wrench to detect contact and switch phases
- MuJoCo gain sweeps → fast Bayesian optimization of impedance parameters

**3. Learning Paradigms**
- **Teacher-Student Distillation** (dominant approach):
  - CheatCode (GT oracle) generates perfect demos at scale
  - ACT/Diffusion policy (student) trains on oracle's RGB → action pairs
  - Student deploys with zero GT access
- **Asymmetric Actor-Critic (LUPI)**:
  - Critic sees full GT during RL training
  - Actor sees only cameras + joint states
  - Only Actor deployed at eval time
- **Hybrid:** analytic state machine wrapper around a learned spatial policy

**4. Data**
- Synthetic GT demos (CheatCode in Gazebo/Isaac)
- Human teleop demos (LeRobot + AIC keyboard teleop)
- Isaac Lab parallel envs for massively scaled RL (AIC-Task-v0, `rsl-rl`)
- Cross-simulator consistency (MuJoCo ↔ Gazebo policy transfer)

**5. Architecture**
- **ACT** (Action Chunking with Transformers) — predicts action sequences
- **Diffusion Policy** — stochastic, handles multimodal action distributions
- Hybrid analytic + learned (state machine wrapping neural net output)

---

## How to Win — Fundamentally

### The Core Loop
```
CheatCode (GT oracle, Gazebo)
  → 10,000+ perfect demo recordings (RGB images + joint velocities)
  → Train ACT/Diffusion student policy
  → State machine wrapper (approach: stiff → insertion: compliant)
  → Non-GT perception (keypoint detectors for plug-tip + port)
  → Validate ALL decisions in Gazebo (truth lane)
  → Submit policy package that fits L4 (24 GB)
```

### The Three-Lane Development Model
| Lane | Simulator | Purpose |
|------|-----------|---------|
| **Truth** | Gazebo / Kilted | Every real decision validated here, `scoring.yaml` is the metric |
| **Controller** | MuJoCo mirror | Fast gain/impedance sweeps without Gazebo overhead |
| **Learning** | Isaac Lab | Parallel RL, demo recording, policy pretraining |

### Priority Order
1. **Tier 3 > 0 without GT** — prove your perception can localize the port
2. **Full insertion > 50%** — prove your insertion primitive is reliable
3. **Force penalties < 10%** — prove your compliance switching works
4. **Duration minimized** — speed matters for ranking when insertion rates are equal

### The One-Line Strategy
> Train a compliant, force-aware student policy via Teacher-Student Distillation from a GT oracle, with a state-machine wrapper that drops stiffness at contact, validated entirely in Gazebo.

---

## Key Repos

| Repo | Role |
|------|------|
| `intrinsic-dev/aic` | Official competition repo |
| `huggingface/lerobot` | ACT, Diffusion Policy, teleop recording |
| `vainaviv/handloom` | Cable state estimation (perception) |
| `MarkFzp/act-plus-plus` | ACT++ training loops |
| `real-stanford/diffusion_policy` | Diffusion Policy baseline |
| `NVlabs/industreallib` | Insertion controller patterns (Franka-based donor) |
| `RMDLO/trackdlo` | DLO shape tracking (RGB-D, may need adaptation) |
