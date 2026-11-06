# Remote mode: agent on your laptop, jobs on the cluster

The agent (Claude Code) runs on your laptop. The campaigns run on the cluster, because that is where the executables, LHAPDF, the scheduler and the scratch space are.
Everything between the two goes through one script, `scripts/remote.py`, over **one persistent SSH connection that you open yourself**.

```
laptop                                              cluster (login/dev node)
  agent + skills + rules                              ~/ResbosFlowAgent/   (copy of the toolchain, made by `remote.py sync`)
  local/*.ini, local/env.md   --- remote.py push -->    local/*.ini
                              --- remote.py run  -->    run_process.py, campaign_review.py, validate_campaign.py, collect_env.sh
                              <-- output of the command
                              <-- remote.py pull ---    small logs/summaries
        \________ one SSH connection (ControlMaster), opened by you ________/
```

Nothing is installed on the cluster by hand: `sync` copies the toolchain (Python scripts and templates). The cluster needs `rsync` and Python 3.

## One-time setup (laptop)

1. **SSH config.** In `~/.ssh/config` (replace `<netid>`; the host names are the ones of the MSU HPCC gateway and development node; use your own site's if different):

   ```sshconfig
   Host msu-hpcc
       HostName hpcc.msu.edu
       User <netid>
       IdentitiesOnly yes

   Host msu-dev
       HostName dev-amd20
       User <netid>
       ProxyJump msu-hpcc
       IdentitiesOnly yes

   Host msu-hpcc msu-dev
       ControlMaster auto
       ControlPath ~/.ssh/cm-%C
       ControlPersist 30m
   ```

   An SSH key with a passphrase (`ssh-keygen -t ed25519`, `ssh-copy-id <netid>@hpcc.msu.edu`) saves retyping the password; it is optional.

2. **Repo config.** `cp local/remote.example.conf local/remote.conf` and set `host` (the alias, `msu-dev`) and `repo` (folder on the cluster, for example `~/ResbosFlowAgent`).

## Windows

The laptop side needs `ssh` with connection multiplexing (`ControlMaster`), `rsync` and bash. As far as we know the Windows OpenSSH client has no `ControlMaster`, and Windows has no `rsync`, so **run the whole laptop side inside WSL2**
(Ubuntu): Claude Code, the repository, `ssh`, `rsync` and `~/.ssh/config` all live in WSL. The steps are in `QUICKSTART.md` ("Windows"). Points that matter:

- Clone the repository inside WSL's home (`~/ResbosFlowAgent`), not under `/mnt/c`; the symlink `.claude/skills` and the file permissions need a Linux file system. `.gitattributes` forces LF line endings so a clone made by mistake with Git for Windows
  does not send CRLF scripts to the cluster (they fail with `bash\r: No such file or directory`), but a Windows clone still breaks the symlink.
- WSL has its own `~/.ssh`. Keys must have mode 600 (`chmod 600 ~/.ssh/id_*`).
- Open the SSH connection (`ssh -fN <alias>`, or let `ResbosFlowAI` do it) from the Ubuntu terminal, so the socket exists where `remote.py` looks for it.
- If the first `wsl --install` fails, virtualization is off in the BIOS or the PC is managed: ask IT. A native Windows alternative (a Python process that holds the connection instead of `ControlMaster`) is not written.

## Each session

The launcher `./ResbosFlowAI` does steps 1 and 2 for you (it writes `local/remote.conf` the first time, offers to open the connection, and starts the assistant). The manual way:

1. **Open the connection yourself**, in a terminal (password, passphrase or 2FA are typed here, not to the agent):

   ```sh
   ssh -fN msu-dev          # opens it in the background
   ssh -O check msu-dev     # "Master running (pid=...)"
   ```

   `ControlPersist 30m` closes it after 30 idle minutes; open it again when the agent says "no open connection". `ssh -O exit msu-dev` closes it.
2. Start the agent in the repo folder: `claude`.
3. First time, or after updating the repo: `python3 scripts/remote.py sync` (the agent can run it). `python3 scripts/remote.py status` says whether the connection is open and whether the
   cluster copy of the toolchain matches yours.

From then on the agent works as in `AGENTS.md`, with every cluster command written as `python3 scripts/remote.py run -- <command>` after `python3 scripts/remote.py push`.

## What `remote.py` does

| Command | Does |
|---|---|
| `status` | connection open? toolchain on the cluster identical to this copy? |
| `sync` | copies `run_process.py`, `scripts/`, `templates/`, `examples/` to the cluster repo |
| `push` | copies `local/` (campaign `.ini`, recipes) to the cluster repo; never `approvals/`, `remote.conf` or logs |
| `run -- CMD` | runs one allowed command in the cluster repo, in a login shell (so `module` works), output streamed back |
| `pull PATH` | fetches a small file or folder (files over 20 MB and `.root` are skipped) into `local/remote_files/` |
| `queue [JOBID...]` | `squeue` for your user, or `sacct` for given job ids; at most once per 5 minutes |

`run` accepts only: `run_process.py` (never `--submit`), `campaign_review.py show|approve|submit`, `preflight.py prepare|submit|result`, `validate_campaign.py`, `collect_env.sh`, and read-only inspection
(`lhapdf-config`, `hoppet-config`, `root-config`, compiler/python versions, `lhapdf ls --installed`, `sinfo -s`, `module list|avail`, `test`, `ls`, `head`, `tail`, `wc -l`, `df -h`, `sha256sum`).
Anything else is refused with exit code 5.

Limits and records:
- It never opens a connection: if the master is not open it stops (exit 3) and tells you how to open it. Commands use `BatchMode`, so they cannot hang on a password prompt.
- At most `max_calls_per_minute` (default 20) remote calls per minute, and one `queue` per `queue_min_interval` (default 300 s). Many short *logins* are what gets accounts blocked; channels over your open connection are
  not logins, but the limit also stops an accidental loop.
- Every call is appended to `local/remote.log` (time, operation, command, exit code).

## Approval in remote mode

`campaign_review.py` runs on the cluster, so the approval record (`local/approvals/<ini>.json`) lives there, next to the prepared `dest`. Flow: edit the `.ini` locally, `push`, `run -- python3 run_process.py local/<x>.ini`,
`run -- python3 scripts/campaign_review.py show local/<x>.ini --full`, then the authorization (`approve ... --yes-i-reviewed`), then `submit`. The skill `review-and-authorize` describes it. You can also type
`! python3 scripts/remote.py run -- python3 scripts/campaign_review.py approve local/<x>.ini --yes-i-reviewed` yourself in Claude Code.

## What this protects, and what it does not

- The agent never sees your credentials; it only uses the connection you opened.
- `.claude/settings.json` denies `ssh`, `scp`, `sftp`, `rsync`, `sbatch` and `srun` to the agent's shell tool, so it has to go through `remote.py`. `remote.py` itself calls `ssh` and `rsync` (the deny rules apply to the agent's own commands,
  not to what a script does). If you remove those rules, nothing technical stops the agent from calling `ssh` directly; the allow list is a guard rail against accidents and loops, not a sandbox.
- **What the agent reads is sent to the model provider.** Output of `run` and `pull` (paths, module lists, logs, your username in paths) goes into the conversation. Do not run it on a site whose policy forbids that, and do not put
  secrets in the files the agent reads.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `no open connection` (exit 3) | open it: `ssh -fN <alias>`; it also expires after `ControlPersist` idle time |
| `WARNING: no ControlPath for ...` in `status` | the `ControlMaster`/`ControlPath` lines are missing for that alias in `~/.ssh/config` |
| `rate limit` (exit 4) | wait the seconds it prints; use `collect_env.sh` instead of many single queries; ask the user whether jobs finished instead of calling `queue` |
| `REFUSED` (exit 5) | the command is not on the list; ask the user to run it, or extend `check_allowed` in `remote.py` on purpose |
| `status`: toolchain NOT INSTALLED / DIFFERENT | `python3 scripts/remote.py sync` |
| `bash\r: No such file or directory` on the cluster | a script reached the cluster with Windows line endings: clone again inside WSL; `.gitattributes` prevents it in new clones |
| `rsync: command not found` on the cluster | `rsync` is needed on both ends; ask the site or use `scp` by hand for the first copy |
| `module: command not found` in a remote command | the site's login shell does not define `module`; report it in `local/env.md`: the job scripts need it |

## Status

Tested only with a fake `ssh` that runs the commands in a local folder (connection check, sync/push idempotence, prepare/review/approve/submit through `run`, refusals, rate limit, queue interval, closed connection).
It has not been used against the real HPCC: the first real session is the test of the ControlMaster, `ProxyJump` and `bash -lc` assumptions.
