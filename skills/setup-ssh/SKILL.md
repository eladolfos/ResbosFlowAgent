---
name: setup-ssh
description: Check whether this computer can already reach the user's cluster over SSH (config, keys, agent, persistent connection) and, only if something is missing and the user agrees, help set it up. Use from the onboarding when jobs run on a cluster reached by SSH, when remote.py reports no open connection, or when the user asks to configure or test SSH.
---

# setup-ssh

Goal: find out what the user's computer already has for SSH, use it if it works, and offer to set up only what is missing. The user may already have a working alias, keys and a config;
do not redo any of that, and do not ask for an alias before looking.

Read first: `docs/REMOTE.md`, `rules/cluster_etiquette.md`. The tool is `scripts/ssh_check.py`.

## Hard limits

- Never read, create, copy or print a private key. Never ask for, type or store a password, passphrase or 2FA code. Those are typed by the user in their own terminal.
- Never call `ssh`, `scp`, `rsync` yourself (project settings deny them); use `ssh_check.py` and, later, `remote.py`.
- Do not write `~/.ssh/config` or `local/remote.conf` without showing the content and getting an explicit yes.
- Repeated logins can get an account blocked: `ssh_check.py test` is limited to 3 per 10 minutes. Do not work around it; fix the cause first.

## Steps

1. **Look first (no network):** `python3 scripts/ssh_check.py inspect`. Explain in plain words: OS; whether `ssh` and `rsync` exist; which hosts the user already has in `~/.ssh/config`, which keys, whether an agent is running,
   and whether any host already has the persistent-connection setup (ControlMaster) and is open.
   - Native Windows: stop. Remote mode needs WSL2 (`QUICKSTART.md`, "Windows") or running the assistant on the cluster itself; offer to help with either.
   - `ssh` or `rsync` missing: say how to install it on their system and stop until it exists.
2. **If a suitable host already exists:** ask which one is the cluster node where they run jobs (name the candidates from the output; do not guess). If it has no persistent-connection setup, say so and offer the `snippet` step for
   that host only. If it is ready, go to step 4.
3. **If nothing suitable exists, ask:** "I did not find a ready SSH setup for your cluster. Do you want me to help configure it?" If no: write nothing, explain that remote mode cannot work without it, and offer the other routes
   (assistant on the cluster, manual commands with `scripts/collect_env.sh`). If yes, ask, in one message, only what cannot be discovered:
   the cluster's login (gateway) host name, the user name on the cluster, whether there is a second node reached through the gateway (and its name), whether they already have a key and want to use it, and what alias they want.
   Do not invent host names. Then:
   - `python3 scripts/ssh_check.py snippet --alias <A> --hostname <H> --user <U> [--jump-alias <J> --jump-hostname <G>] [--identity <path>]` (prints; writes nothing). Show it and explain each line (`ProxyJump`, `ControlMaster`, `ControlPersist`).
   - On an explicit yes: the same command with `--write --yes-i-reviewed`. It backs up an existing config and refuses to overwrite an alias that exists.
   - **Keys:** if they have none and the cluster accepts keys, give them the commands to type themselves in their own terminal: `ssh-keygen -t ed25519`, then `ssh-copy-id <user>@<gateway>`. They type the passphrase and password.
     If the cluster asks for a password and a second factor on every login, a key may not help; say so and do not push it.
   - Permission warnings from `inspect` (`chmod 600 ~/.ssh/<key>`): tell them the command.
4. **Test, with consent:** "I will try one non-interactive login to `<alias>`. It cannot ask for a password, so it may fail if your site needs one. OK?" Then `python3 scripts/ssh_check.py test <alias>`.
   - `OK`: it also reports the node name and whether `sbatch`, `rsync` and `python3` exist there. If `rsync` or `python3` is missing on the cluster, remote mode cannot work; say so.
   - `AUTH` / `CLOSED`: the login needs a password or 2FA that the test cannot give. This is normal. Ask the user to open the persistent connection themselves in their own terminal: `ssh -fN <alias>`, then `ssh -O check <alias>`
     must say "Master running". With a jump host, test the jump host alone to see the real reason.
   - `UNRESOLVED` / `NETWORK`: a typo in a host name, or the VPN/campus network. `HOSTKEY-NEW`: they must connect once by hand and accept the fingerprint after checking it. `HOSTKEY-CHANGED`: stop; do not bypass it.
   - Do not repeat a failing test; change something first.
5. **Save the choice:** `python3 scripts/ssh_check.py set-remote <alias> --repo ~/ResbosFlowAgent` (ask where on the cluster the toolchain should live; this is the default). Then `python3 scripts/remote.py status`; if the connection is open,
   `python3 scripts/remote.py sync`.
6. **Return to the onboarding** (`resbosflow`, step 2).

## What to tell the user at the end
What was already there, what you changed (and the backup file name), what they must do in their own terminal each session (`ssh -fN <alias>`, or run `ResbosFlowAI`, which offers it), and what was not verified.
