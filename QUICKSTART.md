# Quickstart

For someone who already has ResBos (Legacy family and/or ResBos2), LHAPDF, HOPPET and ROOT installed on a SLURM cluster, and wants to run campaigns with an assistant on their laptop.
Nothing is built or installed on the cluster. About 15 minutes the first time.

## You need

**Windows:** do the "Windows" section below first. The assistant runs inside WSL2 (Ubuntu); the cluster is Linux as usual. macOS and Linux need nothing special.

- On your laptop: `git`, Python 3, `ssh`, `rsync`, and [Claude Code](https://claude.com/claude-code) (or another agent that reads `AGENTS.md`).
- On the cluster: Python 3 and `rsync`, plus your own ResBos executables and libraries.
- A batch script that works on your cluster (any one you normally submit): the assistant adapts the campaign scripts from it.

## Windows (once): run everything inside WSL2

The launcher, the persistent SSH connection and `rsync` need Linux tools that Windows does not provide. WSL2 gives you an Ubuntu inside Windows; **the assistant, the repository and SSH all live there**. The cluster is not affected.
You need administrator rights and virtualization enabled (on a university-managed PC, ask IT if the first command fails).

1. PowerShell as administrator: `wsl --install -d Ubuntu`, then restart Windows and finish the Ubuntu user setup.
2. Open **Ubuntu** (Windows Terminal has a tab for it). Everything below is typed there:
   ```sh
   sudo apt update && sudo apt install -y git python3 rsync openssh-client
   ```
3. Install Claude Code **inside Ubuntu**, following its Linux installation instructions (https://claude.com/claude-code). A Claude Code installed on Windows does not see WSL's SSH.
4. Clone the repository **inside Ubuntu's own home** (`~/`), not under `/mnt/c/...` (slow, and it loses file permissions and the skills link):
   ```sh
   cd ~ && git clone https://github.com/eladolfos/ResbosFlowAgent.git
   ```
   Do not clone it with Git for Windows: it would break the symlink `.claude/skills` and the line endings.
5. Ubuntu has its own `~/.ssh`, separate from Windows. Do SSH setup **in Ubuntu**: the assistant checks what is there and offers to write the missing `~/.ssh/config` block (or put the block of `docs/REMOTE.md` there yourself). If you reuse a key from Windows, copy it into Ubuntu's `~/.ssh` and run `chmod 600 ~/.ssh/id_*` (SSH refuses keys with open permissions).
6. Then follow the sections below, always in the Ubuntu tab: `~/ResbosFlowAgent/ResbosFlowAI`.

Results stay on the cluster. If you need a file on Windows, it appears under `\\wsl$\Ubuntu\home\<you>\ResbosFlowAgent\local\remote_files` after a `pull`.
Not tested on a real Windows machine by the authors: report what you find.

## What it can compute

| | |
|---|---|
| Orders | `NLO` (fixed order), `resNLO` (CSS resummed, "W321", matched to NLO), `LO` (fixed target); `NNLO` only if you supply `R_Ai` tables |
| Collider, Drell-Yan type | W+, W-, Z0, photon (A0), Z/gamma* (ZU + ZD) in pp (5.02, 7, 8, 13 TeV) and ppbar (1.8, 1.96 TeV); other energies on request; any LHAPDF set installed; (Q, qT, y) grids and Monte Carlo events (`.root`) |
| Fixed-target Drell-Yan | E605 (p+Cu), E866 (pp and pd/pp), E906/SeaQuest (pd/pp): LO, NLO, resNLO at each measured point, plus K-factors |
| Not available | W432, the fixed-xF refinement, other processes (for example Higgs) |

Details, what you must have installed for each, and known issues: `docs/CAPABILITIES.md`.

## 1. Set up (once)

```sh
git clone https://github.com/eladolfos/ResbosFlowAgent.git && cd ResbosFlowAgent
ln -s "$PWD/ResbosFlowAI" ~/.local/bin/ResbosFlowAI      # optional: start it from any folder
```

SSH needs no manual setup here: if you already have working SSH to your cluster the assistant uses it; if not, it offers to write the `~/.ssh/config` block for you (or you can add the one in `docs/REMOTE.md` yourself).

## 2. Start

```sh
ResbosFlowAI               # or ./ResbosFlowAI from the repository folder
```

The launcher only checks that Python and Claude Code are installed and starts the assistant. It does **not** ask for SSH details: the assistant finds out how you reach your cluster, and if you use SSH it first looks at what your computer
already has (`~/.ssh/config`, keys, a running agent) and uses it. Only if something is missing does it ask whether you want help configuring it. You type any password, passphrase or 2FA code yourself, in your own terminal.
If an earlier session saved your SSH alias, the launcher offers to reopen the connection.

## 3. What the assistant does

It greets you, shows the menu above, and asks: **"Do you want me to review your software and paths now?"** If you say yes, it goes through these steps, asking before each one that changes anything:

1. **Where your jobs run and how to reach it** (`setup-ssh`): if you use SSH it inspects your computer first, tests one non-interactive login with your consent, and offers to configure only what is missing. Then `remote.py sync` copies the Python scripts and templates to the cluster; nothing else is installed.
2. **What you have:** it asks where your ResBos executables are, which LHAPDF/HOPPET/ROOT and PDF set you use, where to write results (you choose), and for a batch script that works on your cluster.
3. **Review** (`discover-environment`, `adapt-scheduler`): one read-only report of your cluster, your batch script translated into the `[scheduler]` and `[environment]` settings, and a first campaign `.ini` in `local/` with your paths.
   It tells you what is found, what is missing and what it could not verify.
4. **Preflight job** (`preflight.py`): a ten-minute job with your scheduler settings that checks executables, shared libraries, LHAPDF and the PDF set, ROOT, numpy and write access. It runs no ResBos code.
   You read the script, say yes, and tell the assistant when it has finished; it reads the PASS/FAIL result.
5. **Small test campaign** (optional): W+ at 13 TeV, three Q points, short VEGAS run (`recipes/smoke-test-collider.md`). The assistant shows you where it reads and writes, how many jobs and cores it will use and how they run (you can ask for fewer), and what the scripts will request;
   **nothing is submitted until you say yes to that campaign by name.** When the jobs finish, tell it and it validates the outputs.

After that you can ask for your own work: *"Prepare W+ and W- at 8 TeV with my PDF"*. Each campaign goes through the same review and your authorization.

## 4. Your own rules and recipes

Say *"Add a recipe for `<what you want to compute>`"* (skill `add-recipe`). Your files go in `local/` and survive `git pull`. A new recipe starts as `unvalidated` until it reproduces a reference of yours.

## If something goes wrong

| You see | Do |
|---|---|
| `no open connection` | run `ResbosFlowAI` again, or `ssh -fN <alias>` (the connection closes after 30 idle minutes) |
| `rate limit` | wait the seconds shown; do not ask for many single checks |
| `REFUSED` | the command is not on the allow list; run it yourself or ask for it to be added deliberately |
| a refusal to submit | the `.ini` or the scripts changed after you approved; review and approve again |
| jobs rejected by the scheduler | give the assistant the scheduler's message and your batch script (`adapt-scheduler`) |

## What is not verified

This toolchain has been run on one cluster (the authors'). On a second installation, remote mode, the launcher, the preflight job, the scheduler adaptation, the small test campaign (never run yet; its wall time is unknown) and the compatibility of your ResBos builds are untested: expect to find
things, and read `docs/LIMITATIONS.md` first. What the assistant reads (paths, module lists, logs) is sent to the model provider; check that your site allows it.

More: `docs/CAPABILITIES.md`, `README.md`, `AGENTS.md`, `docs/REMOTE.md`, `rules/`, `skills/`, `recipes/`.
