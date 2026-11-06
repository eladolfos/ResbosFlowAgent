#!/usr/bin/env python3
"""
ssh_check.py -- check what this computer already has for reaching a cluster over SSH, and help set up what is missing.

  inspect [--json]                 LOCAL ONLY (no network): OS, ssh/rsync/ssh-keygen, ~/.ssh/config aliases with their effective settings
                                   (ssh -G), keys and their permissions, ssh-agent, and whether a persistent connection is open
  test ALIAS                       ONE non-interactive login attempt to ALIAS (BatchMode: it cannot ask for a password, 2FA or a passphrase)
                                   that also reports hostname and whether sbatch, rsync and python3 exist on the node. Limited to 3 tests / 10 min.
  snippet --alias A --hostname H --user U [--jump-alias J --jump-hostname G] [--identity PATH] [--write --yes-i-reviewed]
                                   print the ~/.ssh/config block (ControlMaster included) for the cluster; with --write, back up and append it
  set-remote ALIAS [--repo PATH] [--replace]
                                   write local/remote.conf (the alias and the toolchain folder on the cluster)

It never reads a private key, never creates keys, never types or stores a password: keys are made with ssh-keygen / ssh-copy-id by the user,
who types the passphrase and password in their own terminal. Standard library only.
"""
import argparse
import datetime
import glob
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SSH_DIR = os.path.expanduser("~/.ssh")
CONFIG = os.path.join(SSH_DIR, "config")
CONF = os.path.join(HERE, "local", "remote.conf")
STATE = os.path.join(HERE, "local", ".ssh_check_state.json")
NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
MAX_TESTS, WINDOW = 3, 600
# Optional: RESBOSFLOWAI_SSH_CONFIG=<file> makes every ssh call here use that config (-F); for tests only.
SSH = ["ssh"] + (["-F", os.environ["RESBOSFLOWAI_SSH_CONFIG"]] if os.environ.get("RESBOSFLOWAI_SSH_CONFIG") else [])


def run(cmd, timeout=20):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except FileNotFoundError:
        return 127, "", f"{cmd[0]}: not found"
    except subprocess.TimeoutExpired:
        return 124, "", "timed out"


def os_kind():
    if sys.platform.startswith("win"):
        return "windows-native"
    try:
        if "microsoft" in open("/proc/version").read().lower():
            return "wsl"
    except OSError:
        pass
    return "macos" if sys.platform == "darwin" else "linux"


# ------------------------------------------------------------------ ~/.ssh/config
def config_aliases(path=CONFIG, depth=0):
    """Concrete Host names (no wildcards) from the config and its Include files (one level of recursion)."""
    names = []
    if not os.path.isfile(path) or depth > 2:
        return names
    for line in open(path, errors="replace"):
        s = line.strip()
        if s.lower().startswith("host ") or s.lower().startswith("host\t"):
            for n in s.split()[1:]:
                if not any(c in n for c in "*?!") and n not in names:
                    names.append(n)
        elif s.lower().startswith("include "):
            for pat in s.split()[1:]:
                pat = os.path.expanduser(pat if os.path.isabs(os.path.expanduser(pat)) else os.path.join(SSH_DIR, pat))
                for f in sorted(glob.glob(pat)):
                    names += [n for n in config_aliases(f, depth + 1) if n not in names]
    return names


def effective(alias):
    rc, out, err = run(SSH + ["-G", alias])
    if rc != 0:
        return None
    d = {}
    for line in out.splitlines():
        k, _, v = line.partition(" ")
        d.setdefault(k.lower(), []).append(v.strip())
    first = lambda k, dflt="": (d.get(k) or [dflt])[0]
    mux = first("controlmaster", "false")
    cpath = first("controlpath", "none")
    rc2, _, _ = run(SSH + ["-O", "check", alias], timeout=10) if cpath != "none" else (1, "", "")
    return {
        "hostname": first("hostname"), "user": first("user"), "port": first("port", "22"), "proxyjump": first("proxyjump", "none"),
        "controlmaster": mux, "controlpath": cpath, "controlpersist": first("controlpersist", "no"),
        "identityfiles": [os.path.basename(x) for x in d.get("identityfile", []) if os.path.exists(os.path.expanduser(x))],
        "mux_ready": mux in ("auto", "yes", "autoask") and cpath != "none",
        "master_open": rc2 == 0,
    }


def keys():
    out = []
    for pub in sorted(glob.glob(os.path.join(SSH_DIR, "*.pub"))):
        priv = pub[:-4]
        try:
            kind = open(pub).read().split()[0]
        except (OSError, IndexError):
            kind = "?"
        info = {"name": os.path.basename(priv), "type": kind, "private_exists": os.path.isfile(priv)}
        if info["private_exists"]:
            mode = stat.S_IMODE(os.stat(priv).st_mode)
            info["perms_ok"] = (mode & 0o077) == 0 if os.name == "posix" else None
            info["mode"] = oct(mode)
        out.append(info)
    return out


def inspect():
    r = {"os": os_kind(), "python": platform.python_version(), "tools": {}}
    for t in ("ssh", "rsync", "ssh-keygen", "ssh-add", "git"):
        r["tools"][t] = shutil.which(t)
    rc, _, err = run(["ssh", "-V"]) if r["tools"]["ssh"] else (1, "", "")
    r["ssh_version"] = err.strip() or None
    r["ssh_dir_exists"] = os.path.isdir(SSH_DIR)
    r["config_exists"] = os.path.isfile(CONFIG)
    r["keys"] = keys()
    if r["tools"]["ssh-add"]:
        rc, out, _ = run(["ssh-add", "-l"], timeout=5)
        r["agent"] = {"running": rc in (0, 1), "keys_loaded": out.count("\n") if rc == 0 else 0}
    else:
        r["agent"] = {"running": False, "keys_loaded": 0}
    r["aliases"] = {}
    if r["tools"]["ssh"]:
        for a in config_aliases():
            e = effective(a)
            if e:
                r["aliases"][a] = e
    r["remote_conf"] = open(CONF).read().strip() if os.path.isfile(CONF) else None
    return r


def cmd_inspect(args):
    r = inspect()
    if args.json:
        print(json.dumps(r, indent=2))
        return 0
    yes = lambda b: "yes" if b else "NO"
    print(f"Operating system     {r['os']}   (python {r['python']})")
    if r["os"] == "windows-native":
        print("  !! native Windows: the persistent SSH connection and rsync used by remote mode are not available. Use WSL2 (QUICKSTART.md, \"Windows\"),\n"
              "     or run the assistant on the cluster itself.")
    for t, p in r["tools"].items():
        print(f"  {t:11} {p or 'NOT FOUND'}")
    if r["ssh_version"]:
        print(f"  ssh version {r['ssh_version']}")
    print(f"\n~/.ssh               exists: {yes(r['ssh_dir_exists'])}   config file: {yes(r['config_exists'])}")
    print("Keys (public key found next to the private one):")
    if not r["keys"]:
        print("  none found")
    for k in r["keys"]:
        flag = "" if k.get("perms_ok") in (True, None) else "   !! permissions too open: run  chmod 600 ~/.ssh/" + k["name"]
        print(f"  {k['name']:20} {k['type']:12} private key present: {yes(k['private_exists'])}{flag}")
    ag = r["agent"]
    print(f"ssh-agent            {'running, ' + str(ag['keys_loaded']) + ' key(s) loaded' if ag['running'] else 'not running'}")
    print("\nHosts in ~/.ssh/config (effective settings, from `ssh -G`; no network used):")
    if not r["aliases"]:
        print("  none")
    for a, e in r["aliases"].items():
        mux = "ready" if e["mux_ready"] else "NOT set (needs ControlMaster auto + ControlPath)"
        print(f"  {a:14} -> {e['user']}@{e['hostname']}:{e['port']}   jump: {e['proxyjump']}   persistent connection: {mux};  open now: {yes(e['master_open'])}")
    print(f"\nlocal/remote.conf    {r['remote_conf'].replace(chr(10), '; ') if r['remote_conf'] else 'not written yet'}")
    ready = [a for a, e in r["aliases"].items() if e["mux_ready"]]
    print("\nVerdict")
    if r["os"] == "windows-native":
        print("  - Not usable for remote mode on native Windows.")
    elif not r["tools"]["ssh"] or not r["tools"]["rsync"]:
        print("  - Missing tool(s): " + ", ".join(t for t in ("ssh", "rsync") if not r["tools"][t]) + ".")
    elif ready:
        print("  - Ready on this side: " + ", ".join(ready) + " has a persistent-connection setup. Next: `test <alias>` (one login attempt) or open the connection yourself.")
    elif r["aliases"]:
        print("  - Hosts exist but none has ControlMaster/ControlPath: the persistent connection must be added (`snippet`).")
    else:
        print("  - No hosts configured: a block must be added to ~/.ssh/config (`snippet`).")
    return 0


# ------------------------------------------------------------------ test
def classify(rc, err):
    e = err.lower()
    if rc == 0:
        return "ok", "connected without any prompt"
    if "could not resolve hostname" in e:
        return "unresolved", "the host name cannot be resolved: a typo in HostName, or you are not on the network/VPN that can see it"
    if "remote host identification has changed" in e:
        return "hostkey-changed", "the server's key changed. Do NOT bypass this: tell the cluster's support, then remove the old entry only if they confirm"
    if "host key verification failed" in e:
        return "hostkey-new", "this host is not yet trusted on this computer: connect once by hand (ssh <alias>) and accept the fingerprint after checking it"
    if "permission denied" in e:
        return "auth", "the server needs authentication that BatchMode cannot give (password, 2FA, or a key it does not know). Open the connection by hand: ssh -fN <alias>"
    if "connection closed by" in e or "kex_exchange_identification" in e:
        return "closed", ("a server on the way closed the connection. With ProxyJump the real reason is hidden: test the jump host by itself (`test <jump alias>`) to see it. "
                         "Often the gateway needs a password/2FA that BatchMode cannot give; then open the connection by hand: ssh -fN <alias>")
    if any(s in e for s in ("timed out", "refused", "no route to host", "network is unreachable")):
        return "network", "no network path to the host or to the jump host: check the VPN / campus network, and the host names"
    if "bad configuration option" in e or "unsupported option" in e:
        return "config", "~/.ssh/config has an option this ssh does not understand: " + err.strip().splitlines()[-1]
    return "unknown", err.strip()[-300:] or f"exit code {rc}"


def test_allowed():
    try:
        st = json.load(open(STATE))
    except (OSError, ValueError):
        st = {"tests": []}
    now = time.time()
    st["tests"] = [t for t in st.get("tests", []) if now - t < WINDOW]
    if len(st["tests"]) >= MAX_TESTS:
        return False, int(WINDOW - (now - min(st["tests"]))) + 1, st
    st["tests"].append(now)
    return True, 0, st


def cmd_test(args):
    if not NAME_RE.match(args.alias):
        sys.exit("ERROR: ALIAS must be a name from ~/.ssh/config")
    if not shutil.which("ssh"):
        sys.exit("ERROR: ssh not found")
    ok, wait, st = test_allowed()
    if not ok:
        sys.exit(f"REFUSED: {MAX_TESTS} connection tests in the last {WINDOW // 60} minutes. Wait {wait} s. Repeated logins can get an account blocked; "
                 "fix the problem first or open the connection by hand.")
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(st, open(STATE, "w"))
    remote = 'echo "host=$(hostname)"; for t in sbatch rsync python3 git; do if command -v $t >/dev/null 2>&1; then echo "$t=yes"; else echo "$t=no"; fi; done'
    cmd = SSH + ["-o", "BatchMode=yes", "-o", "ControlMaster=no", "-o", "ConnectTimeout=15", args.alias, "bash -lc " + "'" + remote.replace("'", "'\\''") + "'"]
    rc, out, err = run(cmd, timeout=60)
    kind, msg = classify(rc, err)
    print(f"test {args.alias}: {kind.upper()}  -  {msg}")
    if kind == "ok":
        facts = dict(l.split("=", 1) for l in out.splitlines() if "=" in l)
        print(f"  node: {facts.get('host', '?')}")
        for t in ("sbatch", "rsync", "python3", "git"):
            note = {"sbatch": "needed to submit jobs", "rsync": "needed by remote mode (sync/push/pull)", "python3": "needed for the toolchain", "git": "optional on the cluster"}[t]
            print(f"  {t:8} {facts.get(t, '?'):4} ({note})")
    return 0 if kind == "ok" else 1


# ------------------------------------------------------------------ snippet
def build_snippet(a):
    for k in ("alias", "hostname", "user", "jump_alias", "jump_hostname"):
        v = getattr(a, k)
        if v and not NAME_RE.match(v):
            sys.exit(f"ERROR: --{k.replace('_', '-')} '{v}' has characters that are not allowed (letters, digits . _ -)")
    if bool(a.jump_alias) != bool(a.jump_hostname):
        sys.exit("ERROR: give both --jump-alias and --jump-hostname, or neither")
    if a.identity and (not re.match(r"^[~A-Za-z0-9_./-]+$", a.identity)):
        sys.exit("ERROR: --identity must be a simple path (no spaces or special characters)")
    lines = []
    hosts = [a.alias]
    if a.jump_alias:
        lines += [f"Host {a.jump_alias}", f"    HostName {a.jump_hostname}", f"    User {a.user}", "    IdentitiesOnly yes"]
        if a.identity:
            lines.append(f"    IdentityFile {a.identity}")
        lines.append("")
        hosts.insert(0, a.jump_alias)
    lines += [f"Host {a.alias}", f"    HostName {a.hostname}", f"    User {a.user}"]
    if a.jump_alias:
        lines.append(f"    ProxyJump {a.jump_alias}")
    lines.append("    IdentitiesOnly yes")
    if a.identity:
        lines.append(f"    IdentityFile {a.identity}")
    lines += ["", f"Host {' '.join(hosts)}", "    ControlMaster auto", "    ControlPath ~/.ssh/cm-%C", "    ControlPersist 30m", ""]
    return "\n".join(lines)


def cmd_snippet(args):
    text = build_snippet(args)
    print(text)
    if not args.write:
        print("(not written: add --write --yes-i-reviewed after the user has read it)")
        return 0
    if not args.yes_i_reviewed:
        sys.exit("ERROR: writing ~/.ssh/config is the user's decision: show the block, get an explicit yes, then use --write --yes-i-reviewed")
    existing = config_aliases()
    clash = [h for h in ([args.alias] + ([args.jump_alias] if args.jump_alias else [])) if h in existing]
    if clash:
        sys.exit(f"REFUSED: ~/.ssh/config already defines {', '.join(clash)}. Pick another alias, or edit that entry by hand.")
    os.makedirs(SSH_DIR, mode=0o700, exist_ok=True)
    backup = None
    if os.path.isfile(CONFIG):
        backup = CONFIG + ".bak-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(CONFIG, backup)
    with open(CONFIG, "a") as f:
        if backup:
            f.write("\n")
        f.write("# added by ResbosFlowAgent scripts/ssh_check.py on " + datetime.date.today().isoformat() + "\n" + text)
    if os.name == "posix":
        os.chmod(CONFIG, 0o600)
    print(f"appended to {CONFIG}" + (f" (backup: {backup})" if backup else " (new file)"))
    return 0


# ------------------------------------------------------------------ set-remote
def cmd_set_remote(args):
    if not NAME_RE.match(args.alias):
        sys.exit("ERROR: ALIAS must be a name from ~/.ssh/config")
    if not re.match(r"^[~A-Za-z0-9_./-]+$", args.repo):
        sys.exit("ERROR: --repo must be a simple path")
    if os.path.isfile(CONF) and not args.replace:
        sys.exit(f"REFUSED: {CONF} exists:\n{open(CONF).read()}\nUse --replace to overwrite it.")
    os.makedirs(os.path.dirname(CONF), exist_ok=True)
    open(CONF, "w").write(f"[remote]\nhost = {args.alias}\nrepo = {args.repo}\n")
    print(f"wrote {CONF}: host = {args.alias}, repo = {args.repo}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("inspect")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_inspect)
    s = sub.add_parser("test")
    s.add_argument("alias")
    s.set_defaults(fn=cmd_test)
    s = sub.add_parser("snippet")
    s.add_argument("--alias", required=True)
    s.add_argument("--hostname", required=True)
    s.add_argument("--user", required=True)
    s.add_argument("--jump-alias")
    s.add_argument("--jump-hostname")
    s.add_argument("--identity")
    s.add_argument("--write", action="store_true")
    s.add_argument("--yes-i-reviewed", action="store_true")
    s.set_defaults(fn=cmd_snippet)
    s = sub.add_parser("set-remote")
    s.add_argument("alias")
    s.add_argument("--repo", default="~/ResbosFlowAgent")
    s.add_argument("--replace", action="store_true")
    s.set_defaults(fn=cmd_set_remote)
    args = ap.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
