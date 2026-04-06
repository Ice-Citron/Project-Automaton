# Session 7 Handoff — Fresh Ubuntu 24.04 Setup

**Date:** 2026-04-02
**Machine:** StarForge SF95 Desktop (RTX 5090, 32GB VRAM)
**OS:** Ubuntu 24.04.4 LTS (Noble Numbat), kernel 6.17.0-19
**NVIDIA Driver:** 580.126.09 (pre-installed, working)

---

## Context

Shi Hao moved from Windows + WSL2 to a fresh native Ubuntu 24.04 install because WSL2 kept breaking (Docker networking, Isaac Sim Vulkan rendering, line ending issues). This session focused on getting the new Ubuntu system set up with all development tools needed for the AIC competition and general workflow.

---

## What Was Done This Session

### 1. Full Repo & History Review

Read through the entire Project-Automaton repository, including:
- All handoff files from Sessions 4-6 (2026-03-22, 2026-03-23, 2026-03-28)
- Evan's AWS branch (`EVAN-add-AWS-dcv-with-claude-code-and-aic-setup`) — contains `/aws/` directory with full setup scripts for Gazebo, MuJoCo, Isaac Lab
- Understood the three-lane sim model (Gazebo truth, MuJoCo controller sweeps, Isaac Lab RL)
- Noted key discovery: plugs don't start in mounts; mounts are empty fixtures

### 2. Software Installation — Complete List

All of the following were installed and verified working:

#### Build Tools & CLI Utilities
| Tool | Version | Status |
|------|---------|--------|
| build-essential | GCC 13.3.0 | OK |
| cmake | 3.28.3 | OK |
| curl, wget | system | OK |
| git | 2.43.0 | OK |
| git-lfs | 3.4.1 | OK |
| pkg-config, libssl-dev, libffi-dev | system | OK |
| unzip, p7zip-full | system | OK |
| jq | 1.7 | OK |
| tree | system | OK |
| ripgrep (rg) | 14.1.0 | OK |
| fd-find (fdfind) | 9.0.0 | OK |
| bat (batcat) | 0.24.0 | OK |
| eza | 0.18.2 | OK |
| fzf | 0.44.1 | OK |
| tmux | 3.4 | OK |
| htop | system | OK |
| btop | system | OK |
| nvtop | system | OK |

#### Languages & Runtimes
| Tool | Version | Install Method | Status |
|------|---------|---------------|--------|
| Python 3.12 | 3.12.3 | system + pip/venv/dev | OK |
| Node.js | v24.14.1 (LTS) | NVM v0.40.0 | OK |
| npm | 11.11.0 | via NVM | OK |
| Bun | 1.3.11 | curl installer | OK |
| pnpm | 10.33.0 | npm global | OK |

#### AI/Dev CLIs
| Tool | Version | Status |
|------|---------|--------|
| Claude Code | 2.1.89 | OK |
| GitHub CLI (gh) | 2.45.0 | OK |
| uv | 0.11.3 | OK |
| Pixi | 0.66.0 | OK |

#### Docker & GPU
| Tool | Version | Status |
|------|---------|--------|
| Docker Engine CE | 29.3.1 | OK |
| NVIDIA Container Toolkit | 1.19.0 | OK |
| Docker GPU passthrough | CUDA 13.0 visible in container | OK |
| CUDA Toolkit (nvcc) | 12.0 (apt) | OK (driver supports 13.0) |
| nvidia-smi | 580.126.09 | OK |

#### Shell
| Tool | Version | Status |
|------|---------|--------|
| Zsh | 5.9 | OK, set as default shell |
| Oh-My-Zsh | latest | OK |
| NVM sourced in .zshrc | — | OK |

#### Desktop Apps
| App | Version | Install Method | Status |
|-----|---------|---------------|--------|
| VS Code | 1.114.0 | snap | OK |
| Brave Browser | 146.1.88.138 | apt repo (pre-installed) | OK |
| Blender | 5.1.0 | snap | OK |
| Discord | latest | snap | OK |
| VLC | 3.0.20 | apt | OK |
| GIMP | 2.10.36 | apt | OK |
| Flameshot | 12.1.0 | apt | OK |
| Dropbox | system | apt | OK |

#### System Monitoring & Utilities
| Tool | Status |
|------|--------|
| lm-sensors | OK |
| xdotool | OK |
| wmctrl | OK |
| Tailscale | 1.96.4, OK |

### 3. XFCE Window Tiling

- Configured XFCE built-in window tiling keybinds (Super+Arrow keys) via Settings > Window Manager > Keyboard
- Installed xdotool + wmctrl for scriptable window management
- Tried i3 tiling WM — removed it (not suitable for this workflow)

### 4. Memory System Created

Saved persistent memories for future Claude Code sessions:
- `user_profile.md` — Shi Hao's background, tools, working style
- `project_aic_status.md` — AIC competition status, three-lane model, deadline
- `system_ubuntu_setup.md` — Fresh Ubuntu 24.04 system state
- `reference_evan_aws_branch.md` — Evan's AWS setup scripts location
- `feedback_ask_before_install.md` — Always ask before installing software

---

## What's NOT Done Yet

### Still Need to Install
- **OpenAI Codex CLI** — `npm install -g @openai/codex`
- **Rust** — not installed, unclear if needed on this machine
- **Go** — not installed, unclear if needed on this machine

### AIC-Specific Setup (Not Started)
- MuJoCo Python venv (`~/envs/mujoco` with mujoco, mujoco-mjx, warp-lang, jax[cuda12])
- ROS 2 Kilted (system-level or via Pixi)
- Gazebo Ionic
- Isaac Sim / Isaac Lab
- AIC workspace (`pixi install` in `References/aic/`)
- Colcon workspace build (`~/ws_aic/`)

### Configuration (Not Started)
- Git config (user.name, user.email, credential.helper)
- Shell aliases in `.zshrc` (automaton, aic, mujoco venv, ll, cat→bat, etc.)
- VS Code extensions (anthropic.claude-code, ms-python.python, etc.)

### Reminders from User
- Add UI feature to point to git repo link for each project on website
- Polish GitHub README files + cite sienarindustries website links
- Fix picture problems on website

---

## CUDA Version Note

The `nvidia-cuda-toolkit` from apt gives nvcc 12.0, but the NVIDIA driver supports CUDA 13.0. This is fine for basic compilation. If Isaac Sim or JAX needs a newer CUDA toolkit, install from NVIDIA's official repo instead:
- https://developer.nvidia.com/cuda-downloads → Ubuntu 24.04 → deb (network)

---

## Key Insight: WSL2 Blockers Now Resolved

Moving to native Ubuntu should fix ALL previous WSL2-specific blockers:
1. **Docker `--network host`** — works natively (no VM layer)
2. **Isaac Sim Vulkan rendering** — native GPU, no WSL2 driver mismatch
3. **`bash\r` line endings** — no Windows/Linux line ending conflicts
4. **Gazebo transport** — no WSL2 networking quirks

---

## Quick Reference — Verified Working Commands

```bash
# Docker GPU test
docker run --rm --gpus all nvidia/cuda:12.6.0-base-ubuntu24.04 nvidia-smi

# GPU monitoring
nvtop

# Node/npm/Claude
nvm use --lts
claude --version

# Python venv (template for MuJoCo setup)
python3 -m venv ~/envs/mujoco
source ~/envs/mujoco/bin/activate
```

---

## Next Session Priority

1. Set up git config + shell aliases
2. Create MuJoCo venv and install packages
3. Set up AIC workspace with Pixi
4. Test Gazebo + Docker eval pipeline on native Ubuntu
5. Set up Isaac Sim/Lab (should be much smoother on native Ubuntu)
