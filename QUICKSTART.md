# Quickstart

For someone who already has ResBos (Legacy family and/or ResBos2), LHAPDF, HOPPET and ROOT installed on a SLURM cluster, and wants to run campaigns with an assistant on their laptop.
Nothing is built or installed on the cluster. About 15 minutes the first time.

## You need

- On your laptop: `git`, Python 3, `ssh`, `rsync`, and [Claude Code](https://claude.com/claude-code) (or another agent that reads `AGENTS.md`).
- On the cluster: Python 3 and `rsync`, plus your own ResBos executables and libraries.
- A batch script that works on your cluster (any one you normally submit): the assistant adapts the campaign scripts from it.

## 1. Set up (once)

```sh
git clone <repository URL> && cd ResbosFlowAgent
cp local/remote.example.conf local/remote.conf
```

Add the SSH block from `docs/REMOTE.md` to `~/.ssh/config` (your user name, your gateway and node, `ControlMaster auto`, `ControlPath`, `ControlPersist 30m`),
then edit `local/remote.conf`: `host` = the alias you defined, `repo` = a folder on the cluster, for example `~/ResbosFlowAgent`.

## 2. Each session

```sh
ssh -fN <alias>            # you type the password / passphrase / 2FA here, never to the assistant
ssh -O check <alias>       # must print "Master running"
claude                     # in the ResbosFlowAgent folder
```

## 3. First conversation

Say these, in order. The assistant runs the matching skill and shows you what it did.

1. *"Check the connection and sync the toolchain."* → `remote.py status`, `sync`.
2. *"Describe my environment. My executables are in `<path>`, I want to write results under `<scratch path>`."* → `discover-environment` fills `local/env.md`. Anything it could not verify is listed as such.
3. *"Here is a batch script that works for me: `<paste it>`."* → `adapt-scheduler` writes `[scheduler]` and `[environment]` for your `.ini` and shows what it could not carry over.
4. *"Prepare a small test: W+ at 13 TeV with `<your PDF>`, a few Q points."* → `new-collider-campaign` writes `local/<name>.ini` and prepares it on the cluster. Start small: this is the first run of the toolchain on your installation.
5. The assistant then runs `review-and-authorize`: it tells you where files will be read and written, shows the `.ini` and what the scripts will ask the scheduler for. **Nothing is submitted until you say yes** to that campaign by name.
6. When your jobs finish, tell it: *"The campaign finished, validate it."* → `validate-and-diagnose`. It does not watch the queue; it asks you.

## 4. Your own rules and recipes

Say *"Add a recipe for `<what you want to compute>`"* (skill `add-recipe`). Your files go in `local/` and survive `git pull`. A new recipe starts as `unvalidated` until it reproduces a reference of yours.

## If something goes wrong

| You see | Do |
|---|---|
| `no open connection` | run step 2 again (the connection closes after 30 idle minutes) |
| `rate limit` | wait the seconds shown; do not ask for many single checks |
| `REFUSED` | the command is not on the allow list; run it yourself or ask for it to be added deliberately |
| a refusal to submit | the `.ini` or the scripts changed after you approved; review and approve again |
| jobs rejected by the scheduler | give the assistant the scheduler's message and your batch script (`adapt-scheduler`) |

## What is not verified

This toolchain has been run on one cluster (the authors'). On a second installation, remote mode, the scheduler adaptation and the compatibility of your ResBos builds are untested: expect to find
things, and read `docs/LIMITATIONS.md` first. What the assistant reads (paths, module lists, logs) is sent to the model provider; check that your site allows it.

More: `README.md`, `AGENTS.md`, `docs/REMOTE.md`, `rules/`, `skills/`, `recipes/`.
