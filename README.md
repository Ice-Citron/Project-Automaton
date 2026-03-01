# NVIDIA Isaac Sim & Physical AI: The Lego-Assembling Arm

> **A personal roadmap and codebase dedicated to mastering Reinforcement Learning (RL), hardware design, NVIDIA Isaac Sim, and autonomous robotics.**

## Project Vision
The ultimate goal of this repository is to design, develop, train, and deploy a Reinforcement Learning agent capable of autonomously assembling Lego sets using a custom-modified [SO-100](https://github.com/TheRobotStudio/SO-100) robotic arm. 

Beyond software and simulation, this project heavily involves hardware design and mechanical modification to ensure the physical arm can handle the high-precision tolerances required for Lego assembly. It serves as a comprehensive sandbox to upskill in the future of physical AI, explore autonomous manufacturing processes, and develop systems capable of replacing repetitive manual labor in factory environments.

## Development Roadmap

This project is broken down into progressive milestones, moving from foundational infrastructure and hardware prototyping to advanced RL deployment:

### Phase 1: Infrastructure & Foundations (Current)
- [x] Establish automated sync pipelines between the local Windows workstation (RTX 5090) and cloud Linux servers (Vast.ai, Tensordock utilizing RTX 6000 Pro and L40 hardware).
- [ ] Complete foundational physical AI and Isaac Sim training (via Lychee AI tutorials).
- [ ] Set up the core Reinforcement Learning environments and physics parameters.

### Phase 2: Hardware Design & Simulation Research
- [ ] Design, CAD, and prototype hardware modifications for the SO-100 robotic arm to support high-precision gripping and Lego manipulation.
- [ ] Reproduce state-of-the-art (SOTA) robotics research papers within Isaac Sim.
- [ ] Import and configure the highly accurate digital twin of the customized SO-100 robotic arm.
- [ ] Integrate ROS2 with Isaac Sim for seamless sim-to-real communication.

### Phase 3: The Capstone (Lego Assembly)
- [ ] Develop custom RL reward functions for spatial awareness, precision gripping, and structural Lego piece snapping.
- [ ] Train the agent using cloud compute clusters, iterating continuously on the digital twin.
- [ ] Deploy the trained model to the physical, custom-built SO-100 hardware for real-world testing and validation.

## Tech Stack & Hardware
* **Hardware Design:** CAD software and 3D printing/fabrication for arm modifications
* **Simulation:** NVIDIA Isaac Sim, Omniverse
* **AI / Machine Learning:** Reinforcement Learning (RL), PyTorch
* **Robotics Frameworks:** ROS2, custom kinematic controllers
* **Compute Infrastructure:** * Local Windows Workstation (NVIDIA RTX 5090)
  * Cloud Linux Servers via Vast.ai & Tensordock (NVIDIA RTX 6000 Pro, NVIDIA L40)

## Repository Contents
*(Currently tracking Phase 1 Infrastructure)*
* `sync_scripts/` - Automated synchronization tools bridging local storage, Google Drive, and cloud GPU instances for seamless model checkpointing and dataset management.
* *(Future)* `hardware_design/` - CAD files, 3D printable STLs, and schematics for the modified SO-100 arm.
* *(Future)* `isaac_envs/` - Custom Omniverse environments and Lego digital twins.
* *(Future)* `rl_training/` - Training loops, reward functions, and policy networks.

## Author
**Shi Hao Ng**
*Imperial College London*