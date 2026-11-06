# Quickstart

For someone who already has ResBos (Legacy family and/or ResBos2), LHAPDF, HOPPET and ROOT installed on a SLURM cluster, and wants to run campaigns with an assistant on their laptop.
Nothing is built or installed on the cluster. About 15 minutes the first time.

## You need

- On your laptop: `git`, Python 3, `ssh`, `rsync`, and [Claude Code](https://claude.com/claude-code) (or another agent that reads `AGENTS.md`).
- On the cluster: Python 3 and `rsync`, plus your own ResBos executables and libraries.
- A batch script that works on your cluster (any one you normally submit): the assistant adapts the campaign scripts from it.

## 1. Set up (once)

```sh
git clone https://github.com/eladolfos/ResbosFlowAgent.git && cd ResbosFlowAgent
ln -s "$PWD/ResbosFlowAI" ~/.local/bin/ResbosFlowAI      # optional: start it from any folder
```

Add the SSH block from `docs/REMOTE.md` to `~/.ssh/config` (your user name, your gateway and node, `ControlMaster auto`, `ControlPath`, `ControlPersist 30m`). That is all you configure by hand.

## 2. Start

```sh
ResbosFlowAI               # or ./ResbosFlowAI from the repository folder
```

The first time it asks whether your jobs run on a cluster you reach over SSH (the usual case) or on this machine, and for the SSH alias and a folder on the cluster. It writes `local/remote.conf` for you.
Whenever the SSH connection is closed it offers to open it: **you** type the password / passphrase / 2FA in that terminal, never to the assistant. Then it starts Claude Code with the onboarding.

## 3. What the assistant does

It greets you and asks: **"Do you want me to review your software and paths now?"** If you say yes, it goes through these steps, asking before each one that changes anything:

1. **Connection and toolchain** (`remote.py status`, `sync`): copies the Python scripts and templates to the cluster; nothing else is installed.
2. **What you have:** it asks where your ResBos executables are, which LHAPDF/HOPPET/ROOT and PDF set you use, where to write results (you choose), and for a batch script that works on your cluster.
3. **Review** (`discover-environment`, `adapt-scheduler`): one read-only report of your cluster, your batch script translated into the `[scheduler]` and `[environment]` settings, and a first campaign `.ini` in `local/` with your paths.
   It tells you what is found, what is missing and what it could not verify.
4. **Preflight job** (`preflight.py`): a ten-minute job with your scheduler settings that checks executables, shared libraries, LHAPDF and the PDF set, ROOT, numpy and write access. It runs no ResBos code.
   You read the script, say yes, and tell the assistant when it has finished; it reads the PASS/FAIL result.
5. **Small test campaign** (optional): W+ at 13 TeV, three Q points, short VEGAS run (`recipes/smoke-test-collider.md`). The assistant shows you where it reads and writes and what the scripts will request;
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

More: `README.md`, `AGENTS.md`, `docs/REMOTE.md`, `rules/`, `skills/`, `recipes/`.
