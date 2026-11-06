#!/usr/bin/env python3
"""
remote.py -- the single, rate-limited channel between the assistant (on the user's laptop) and the cluster.

The assistant never opens SSH connections itself. The USER opens one persistent connection (ControlMaster) in a terminal, typing their
password/passphrase/2FA there; this script only reuses that open connection and refuses to run when it is not open. See docs/REMOTE.md.

  status                    is the connection open? is the cluster copy of the toolchain the same as this one?
  sync                      copy the toolchain (run_process.py, scripts/, templates/, examples/) to the cluster repo
  push                      copy local/ (campaign .ini files, recipes) to the cluster repo
  run -- CMD...             run ONE allowed command in the cluster repo (see ALLOWED below), output streamed back
  pull REMOTE [--to DIR]    fetch a small file or folder (<= 20 MB per file, no .root) into local/remote_files/
  queue [JOBID...]          squeue (or sacct for the given job ids); at most one call per 5 minutes

Configuration: local/remote.conf (template local/remote.example.conf). Every call is logged in local/remote.log and counted in a sliding
one-minute window. Exit codes: 2 usage/config, 3 connection not open, 4 rate limit, 5 command refused, otherwise the remote exit code.

ALLOWED with `run`:
  python3 run_process.py local/X.ini [--reuse] [--resbos-only] [--clean-shards]     (never --submit)
  python3 scripts/campaign_review.py show|approve|submit local/X.ini [--full] [--yes-i-reviewed] [--note TEXT]
  python3 scripts/preflight.py prepare|submit|result local/X.ini [--yes-i-reviewed]
  python3 scripts/validate_campaign.py DEST [--cross-tol X] [--min-root-mb X]
  bash scripts/collect_env.sh [--check PATH]...
  read-only: lhapdf-config/hoppet-config/root-config flags, gcc|gfortran|python3 --version, python3 -c "import numpy", lhapdf ls --installed,
             sinfo -s, module list|avail PATTERN, test -e|-d|-f|-x|-w PATH, ls [-l -a -h -1] PATH..., head|tail -n N FILE, wc -l FILE, df -h PATH, sha256sum FILE

This is a guard rail against loops and accidents, not a sandbox: the project's .claude/settings.json also denies ssh/scp/rsync/sbatch to the assistant.
Standard library only; needs ssh and rsync on the laptop and rsync on the cluster.
"""
import argparse
import configparser
import datetime
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF = os.path.join(HERE, "local", "remote.conf")
STATE = os.path.join(HERE, "local", ".remote_state.json")
LOG = os.path.join(HERE, "local", "remote.log")
INI_RE = re.compile(r"^(local|examples)/[A-Za-z0-9_.+-]+\.ini$")
HOST_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
TOOLCHAIN = ["run_process.py", "scripts", "templates", "examples"]
HASHED = ["run_process.py", "scripts/campaign_review.py"]
EXIT_USAGE, EXIT_NOCONN, EXIT_RATE, EXIT_REFUSED = 2, 3, 4, 5


# ------------------------------------------------------------------ config, state, log
def die(msg, code=EXIT_USAGE):
    print(f"remote.py: {msg}", file=sys.stderr)
    sys.exit(code)


def load_conf():
    if not os.path.isfile(CONF):
        die(f"{CONF} not found: copy local/remote.example.conf to local/remote.conf and set host and repo (docs/REMOTE.md)")
    cp = configparser.ConfigParser(inline_comment_prefixes=("#",), interpolation=None)
    cp.read(CONF)
    if not cp.has_section("remote"):
        die("local/remote.conf needs a [remote] section")
    bad = [k for k, _ in cp.items("remote") if k not in ("host", "repo", "max_calls_per_minute", "queue_min_interval", "timeout")]
    if bad:
        die(f"local/remote.conf: unknown key(s) {', '.join(bad)}")
    g = lambda k, d=None: (cp.get("remote", k, fallback="") or "").strip() or d
    host, repo = g("host"), g("repo")
    if not host or not repo:
        die("local/remote.conf needs host (an alias from ~/.ssh/config) and repo (the toolchain folder on the cluster)")
    if not HOST_RE.match(host):
        die("host must be an alias from ~/.ssh/config (letters, digits, . _ -), not user@host or an option")
    return type("Cfg", (), dict(host=host, repo=repo, rate=int(g("max_calls_per_minute", "20")),
                                qmin=int(g("queue_min_interval", "300")), timeout=int(g("timeout", "1800"))))


def load_state():
    try:
        return json.load(open(STATE))
    except (OSError, ValueError):
        return {"calls": [], "last_queue": 0}


def save_state(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(st, open(STATE, "w"))


def log(op, text, rc, secs):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f:
        f.write(f"{datetime.datetime.now().isoformat(timespec='seconds')}  {op:6} rc={rc} {secs:5.1f}s  {text}\n")


def rate_limit(cfg, queue=False):
    st, now = load_state(), time.time()
    st["calls"] = [t for t in st.get("calls", []) if now - t < 60]
    if len(st["calls"]) >= cfg.rate:
        wait = int(60 - (now - min(st["calls"]))) + 1
        die(f"rate limit: {cfg.rate} remote calls in the last minute. Wait {wait} s. Do not loop; batch the work (collect_env.sh gathers the whole environment in one call).", EXIT_RATE)
    if queue and now - st.get("last_queue", 0) < cfg.qmin:
        wait = int(cfg.qmin - (now - st["last_queue"]))
        die(f"queue was checked {int(now - st['last_queue'])} s ago; the minimum interval is {cfg.qmin} s. Wait {wait} s, or ask the user whether the jobs have finished.", EXIT_RATE)
    st["calls"].append(now)
    if queue:
        st["last_queue"] = now
    save_state(st)


# ------------------------------------------------------------------ ssh plumbing
SSH_OPTS = ["-o", "BatchMode=yes", "-o", "ControlMaster=no", "-o", "ConnectTimeout=15"]


def master_alive(cfg):
    r = subprocess.run(["ssh", "-O", "check", cfg.host], capture_output=True, text=True)
    return r.returncode == 0, (r.stderr or r.stdout).strip()


def require_master(cfg):
    ok, msg = master_alive(cfg)
    if not ok:
        die(f"no open connection to '{cfg.host}' ({msg}).\n"
            f"  The user must open it in their own terminal (password/passphrase/2FA are typed there, never here):\n"
            f"      ssh -fN {cfg.host}\n"
            f"  then check with:  ssh -O check {cfg.host}\n"
            f"  This script never opens a connection itself.", EXIT_NOCONN)


def rq(arg):
    """Quote for the remote shell, keeping a leading ~/ expandable."""
    if arg.startswith("~/"):
        return '"$HOME"/' + shlex.quote(arg[2:])
    return shlex.quote(arg)


def remote_repo_expr(cfg):
    return rq(cfg.repo)


def rsync_path(cfg, sub=""):
    repo = cfg.repo[2:] if cfg.repo.startswith("~/") else cfg.repo
    return f"{cfg.host}:{repo.rstrip('/')}/{sub}"


def rsync_base():
    return ["rsync", "-az", "-e", "ssh " + " ".join(SSH_OPTS)]


def exec_remote(cfg, shell_text, op, shown, timeout=None):
    """Run shell_text on the cluster inside the repo, in a login shell; stream output; return the exit code."""
    require_master(cfg)
    rate_limit(cfg)
    full = f"cd {remote_repo_expr(cfg)} && {shell_text}"
    cmd = ["ssh", *SSH_OPTS, cfg.host, "bash -lc " + shlex.quote(full)]
    t0 = time.time()
    try:
        rc = subprocess.run(cmd, timeout=timeout or cfg.timeout).returncode
    except subprocess.TimeoutExpired:
        rc = 124
        print(f"remote.py: timed out after {timeout or cfg.timeout} s (the remote command may still be running)", file=sys.stderr)
    log(op, shown, rc, time.time() - t0)
    return rc


# ------------------------------------------------------------------ allow list
def _flags(rest, allowed, with_value=()):
    """rest must consist only of allowed flags (and values for with_value flags). Returns error text or None."""
    i = 0
    while i < len(rest):
        a = rest[i]
        if a in allowed:
            i += 1
        elif a in with_value:
            if i + 1 >= len(rest) or "\n" in rest[i + 1]:
                return f"{a} needs a value"
            i += 2
        else:
            return f"argument '{a}' is not allowed here"
    return None


def check_allowed(argv):
    """None if the command may run, else the reason it is refused."""
    if not argv:
        return "empty command"
    a0, rest = argv[0], argv[1:]
    if a0 == "python3":
        if rest[:1] == ["run_process.py"]:
            if len(rest) < 2 or not INI_RE.match(rest[1]):
                return "usage: python3 run_process.py local/<name>.ini [--reuse] [--resbos-only] [--clean-shards]"
            if "--submit" in rest:
                return "--submit bypasses the approval. Use: python3 scripts/campaign_review.py submit local/<name>.ini (skill review-and-authorize)"
            return _flags(rest[2:], ("--reuse", "--resbos-only", "--clean-shards"))
        if rest[:1] == ["scripts/campaign_review.py"]:
            if len(rest) < 3 or rest[1] not in ("show", "approve", "submit") or not INI_RE.match(rest[2]):
                return "usage: python3 scripts/campaign_review.py show|approve|submit local/<name>.ini [--full] [--yes-i-reviewed] [--note TEXT]"
            return _flags(rest[3:], ("--full", "--yes-i-reviewed"), ("--note",))
        if rest[:1] == ["scripts/preflight.py"]:
            if len(rest) < 3 or rest[1] not in ("prepare", "submit", "result") or not INI_RE.match(rest[2]):
                return "usage: python3 scripts/preflight.py prepare|submit|result local/<name>.ini [--yes-i-reviewed]"
            return _flags(rest[3:], ("--yes-i-reviewed",))
        if rest[:1] == ["scripts/validate_campaign.py"]:
            if len(rest) < 2 or rest[1].startswith("-"):
                return "usage: python3 scripts/validate_campaign.py DEST [--cross-tol X] [--min-root-mb X]"
            err = _flags(rest[2:], (), ("--cross-tol", "--min-root-mb"))
            if err:
                return err
            return None if all(re.match(r"^[0-9.eE+-]+$", v) for v in rest[3::2]) else "numeric value expected"
        if rest == ["--version"] or rest == ["-c", "import numpy"]:
            return None
        return "python3 is allowed only for run_process.py, scripts/campaign_review.py, scripts/validate_campaign.py, --version and -c 'import numpy'"
    if a0 == "bash":
        if rest[:1] == ["scripts/collect_env.sh"]:
            r = rest[1:]
            if len(r) % 2 or any(x != "--check" for x in r[0::2]):
                return "usage: bash scripts/collect_env.sh [--check PATH]..."
            return None
        return "bash is allowed only for scripts/collect_env.sh"
    if a0 in ("lhapdf-config", "hoppet-config", "root-config"):
        return _flags(rest, ("--version", "--prefix", "--datadir", "--libdir", "--incdir", "--cflags", "--libs"))
    if a0 in ("gcc", "gfortran", "g++") and rest == ["--version"]:
        return None
    if a0 == "lhapdf" and rest == ["ls", "--installed"]:
        return None
    if a0 == "sinfo" and rest == ["-s"]:
        return None
    if a0 == "module" and (rest == ["list"] or rest == ["-t", "list"] or (len(rest) == 3 and rest[:2] in (["avail", "-t"], ["-t", "avail"]) and re.match(r"^[A-Za-z0-9_./+-]*$", rest[2]))):
        return None
    if a0 == "test" and len(rest) == 2 and rest[0] in ("-e", "-d", "-f", "-x", "-w", "-r"):
        return None
    if a0 == "ls":
        flags = [x for x in rest if x.startswith("-")]
        paths = [x for x in rest if not x.startswith("-")]
        if paths and all(re.match(r"^-[lah1]+$", f) for f in flags):
            return None
        return "usage: ls [-l -a -h -1] PATH..."
    if a0 in ("head", "tail"):
        if len(rest) == 3 and rest[0] == "-n" and rest[1].isdigit() and int(rest[1]) <= 500 and not rest[2].startswith("-"):
            return None
        return f"usage: {a0} -n N FILE   (N <= 500)"
    if a0 == "wc" and len(rest) == 2 and rest[0] == "-l" and not rest[1].startswith("-"):
        return None
    if a0 == "df" and len(rest) == 2 and rest[0] == "-h" and not rest[1].startswith("-"):
        return None
    if a0 == "sha256sum" and len(rest) == 1 and not rest[0].startswith("-"):
        return None
    return f"'{a0}' is not on the allow list (see `remote.py --help`). Ask the user to run it, or add it to remote.py deliberately."


# ------------------------------------------------------------------ commands
def cmd_status(cfg, args):
    g = subprocess.run(["ssh", "-G", cfg.host], capture_output=True, text=True)
    cpath = next((l.split(None, 1)[1] for l in g.stdout.splitlines() if l.startswith("controlpath ")), "none")
    print(f"host alias      {cfg.host}    repo on the cluster  {cfg.repo}")
    if g.returncode != 0 or cpath == "none":
        print(f"WARNING: no ControlPath for '{cfg.host}' in ~/.ssh/config; without ControlMaster/ControlPath this script cannot reuse a connection (docs/REMOTE.md)")
    ok, msg = master_alive(cfg)
    print(f"connection      {'OPEN' if ok else 'NOT OPEN'}  ({msg})")
    if not ok:
        print(f"  open it yourself in a terminal:  ssh -fN {cfg.host}")
        return EXIT_NOCONN
    local = {p: hashlib.sha256(open(os.path.join(HERE, p), "rb").read()).hexdigest() for p in HASHED}
    require_master(cfg)
    rate_limit(cfg)
    cmd = ["ssh", *SSH_OPTS, cfg.host, "bash -lc " + shlex.quote(f"cd {remote_repo_expr(cfg)} 2>/dev/null && sha256sum {' '.join(HASHED)} 2>/dev/null; echo rc=$?")]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=cfg.timeout)
    log("status", "sha256 of toolchain", r.returncode, time.time() - t0)
    remote = {}
    for line in r.stdout.splitlines():
        m = re.match(r"^([0-9a-f]{64})\s+(\S+)$", line)
        if m:
            remote[m.group(2)] = m.group(1)
    if not remote:
        print("toolchain       NOT INSTALLED on the cluster: run  python3 scripts/remote.py sync")
        return 1
    same = all(remote.get(p) == local[p] for p in HASHED)
    print(f"toolchain       {'same as this copy' if same else 'DIFFERENT from this copy: run  python3 scripts/remote.py sync'}")
    return 0 if same else 1


def cmd_sync(cfg, args):
    require_master(cfg)
    rate_limit(cfg)
    cmd = rsync_base() + ["-R", "--itemize-changes", "--exclude", "__pycache__", "--exclude", "*.pyc"] + TOOLCHAIN + [rsync_path(cfg)]
    t0 = time.time()
    r = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True, timeout=cfg.timeout)
    changed = [l for l in r.stdout.splitlines() if l[:2] in ("<f", ">f")]
    log("sync", f"{len(changed)} files", r.returncode, time.time() - t0)
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        return r.returncode
    print(f"synced the toolchain to {cfg.host}:{cfg.repo} ({len(changed)} file(s) updated)")
    return 0


def cmd_push(cfg, args):
    require_master(cfg)
    rate_limit(cfg)
    src = os.path.join(HERE, "local") + "/"
    ex = ["approvals/", "remote.conf", "remote.log", ".remote_state.json", "remote_files/", "env.md"]
    cmd = rsync_base() + ["--itemize-changes"] + [x for e in ex for x in ("--exclude", e)] + [src, rsync_path(cfg, "local/")]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=cfg.timeout)
    changed = [l[12:] for l in r.stdout.splitlines() if l[:2] in ("<f", ">f")]
    log("push", ", ".join(changed) or "nothing new", r.returncode, time.time() - t0)
    if r.returncode != 0:
        print(r.stderr + "\n(if the repo folder does not exist on the cluster yet, run: python3 scripts/remote.py sync)", file=sys.stderr)
        return r.returncode
    print("pushed local/: " + (", ".join(changed) if changed else "nothing new"))
    return 0


def cmd_run(cfg, args):
    argv = args.cmd[1:] if args.cmd[:1] == ["--"] else args.cmd
    why = check_allowed(argv)
    if why:
        print(f"remote.py: REFUSED: {why}", file=sys.stderr)
        log("refuse", " ".join(argv), EXIT_REFUSED, 0)
        return EXIT_REFUSED
    return exec_remote(cfg, " ".join(rq(a) for a in argv), "run", " ".join(argv))


def cmd_pull(cfg, args):
    if args.remote.startswith("-") or ".." in args.remote.split("/"):
        die("remote path must not start with '-' or contain '..'")
    require_master(cfg)
    rate_limit(cfg)
    dest = args.to or os.path.join(HERE, "local", "remote_files")
    os.makedirs(dest, exist_ok=True)
    rp = args.remote if args.remote.startswith(("/", "~")) else os.path.join(cfg.repo, args.remote)
    rp = rp[2:] if rp.startswith("~/") else rp
    cmd = rsync_base() + ["-r", "--max-size=20m", "--exclude", "*.root", "--exclude", "*_shards", f"{cfg.host}:{rp}", dest + "/"]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=cfg.timeout)
    log("pull", rp, r.returncode, time.time() - t0)
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        return r.returncode
    print(f"pulled {rp} into {dest} (files over 20 MB and .root files are skipped)")
    return 0


def cmd_queue(cfg, args):
    ids = args.jobids
    if any(not re.match(r"^\d+(_\d+)?$", j) for j in ids):
        die("job ids must be numbers")
    require_master(cfg)
    rate_limit(cfg, queue=True)        # counts the call and enforces the minimum interval between queue checks
    if ids:
        text = f"sacct -j {','.join(ids)} -X -n --format=JobID,JobName%30,State,ExitCode,Elapsed"
    else:
        text = 'squeue -u "$USER" -h -o "%i %j %T %M %R"'
    full = f"cd {remote_repo_expr(cfg)} 2>/dev/null; {text}"
    t0 = time.time()
    rc = subprocess.run(["ssh", *SSH_OPTS, cfg.host, "bash -lc " + shlex.quote(full)], timeout=cfg.timeout).returncode
    log("queue", text, rc, time.time() - t0)
    return rc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd_name", required=True)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    sub.add_parser("sync").set_defaults(fn=cmd_sync)
    sub.add_parser("push").set_defaults(fn=cmd_push)
    r = sub.add_parser("run")
    r.add_argument("cmd", nargs=argparse.REMAINDER)
    r.set_defaults(fn=cmd_run)
    p = sub.add_parser("pull")
    p.add_argument("remote")
    p.add_argument("--to")
    p.set_defaults(fn=cmd_pull)
    q = sub.add_parser("queue")
    q.add_argument("jobids", nargs="*")
    q.set_defaults(fn=cmd_queue)
    args = ap.parse_args()
    sys.exit(args.fn(load_conf(), args))


if __name__ == "__main__":
    main()
