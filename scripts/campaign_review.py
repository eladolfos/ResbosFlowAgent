#!/usr/bin/env python3
"""
campaign_review.py -- show where a campaign reads and writes, and gate the submission on a recorded human approval.

  show    <ini> [--full]   path map (read/write, exists, free space), environment, scheduler, and, if the campaign is
                           prepared, what the generated scripts will send (partitions, accounts, walltimes, array tasks)
  approve <ini> --yes-i-reviewed [--note TEXT]
                           record the approval: sha256 of the .ini and of the prepared dest/ scripts.
                           THIS IS THE USER'S DECISION: the user runs it (in Claude Code: type  ! python3 scripts/campaign_review.py approve ...),
                           or tells the assistant explicitly, after the review, to approve that campaign (the assistant quotes their words in --note).
  submit  <ini>            run dest/submit_all.sh only if the approval matches the current .ini and the current dest/ scripts

The approval is stored in local/approvals/<ini name>.json (git-ignored). Editing the .ini or re-preparing dest/ with different
content invalidates it: review and approve again. This guards against accidents and drift; it is not a security boundary.
Standard library only.
"""
import argparse
import configparser
import datetime
import getpass
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPROVALS = os.path.join(HERE, "local", "approvals")
HASHED_SUFFIXES = (".sb", ".sh", ".in")
AUTHOR_MARK = "lopezels"       # the original author's account: a leftover path from the examples

# (section, key, role, what) -> keys whose value is a path
PATH_KEYS = [
    ("paths", "dest", "WRITE", "campaign folder: every job runs here, outputs land here"),
    ("paths", "source", "READ", "template folder (.in files, grids)"),
    ("paths", "scripts", "READ", "shard/merge/validation scripts"),
    ("executables", "dir", "READ", "folder with <code>/<exe>"),
    ("executables", "w_pert", "READ", "executable"),
    ("executables", "w_asym", "READ", "executable"),
    ("executables", "legacy", "READ", "executable"),
    ("executables", "get_yk_new", "READ", "executable"),
    ("executables", "resbos", "READ", "executable"),
    ("environment", "lhapdf", "READ", "LHAPDF prefix put on PATH/LD_LIBRARY_PATH in every job"),
    ("environment", "hoppet", "READ", "HOPPET prefix put on LD_LIBRARY_PATH in every job"),
    ("environment", "root_setup", "READ", "thisroot.sh sourced by jobs that need ROOT"),
    ("fixedtarget", "table", "READ", "measured (y,Q) table"),
    ("fixedtarget", "legacy_template", "READ", "Legacy .in"),
    ("fixedtarget", "resbos2_config", "READ", "GetFixed config"),
    ("fixedtarget", "getfixed", "READ", "GetFixed executable"),
    ("fixedtarget", "resbos2_env", "READ", "environment script for GetFixed"),
    ("fixedtarget", "convgrids", "READ", "finished ConvGrids to reuse"),
    ("fixedtarget", "lhapdf_data_path", "READ", "LHAPDF data path for Legacy"),
    ("resbos2_w", "resbos", "READ", "ResBos2 executable (W grid)"),
    ("resbos2_w", "env", "READ", "environment script for ResBos2"),
    ("resbos2_w", "config", "READ", "ResBos2 W config"),
]


def load_ini(path):
    cp = configparser.ConfigParser(inline_comment_prefixes=("#",), interpolation=None)
    cp.optionxform = str
    if not cp.read(path):
        sys.exit(f"ERROR: cannot read {path}")
    return cp


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def resolve(ini_path, value):
    return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(ini_path)), os.path.expanduser(value.strip())))


def dest_of(ini_path, cp):
    if not cp.has_option("paths", "dest"):
        sys.exit("ERROR: [paths] dest is missing in the .ini")
    return resolve(ini_path, cp.get("paths", "dest"))


def dest_hash(dest):
    """sha256 over (relative path, sha256) of the generated scripts and inputs; None if dest is not prepared."""
    if not os.path.isfile(os.path.join(dest, "submit_all.sh")):
        return None
    items = []
    for root, dirs, files in os.walk(dest):
        dirs[:] = sorted(d for d in dirs if not d.endswith("_shards") and d != "work")
        for fn in sorted(files):
            if fn.endswith(HASHED_SUFFIXES) or fn == "campaign.ini":
                p = os.path.join(root, fn)
                items.append((os.path.relpath(p, dest), sha256_file(p)))
    h = hashlib.sha256()
    for rel, digest in sorted(items):
        h.update(f"{rel}\0{digest}\n".encode())
    return h.hexdigest()


def free_space_of(path):
    p = path
    while p and not os.path.exists(p):
        p = os.path.dirname(p)
    try:
        return shutil.disk_usage(p).free / 1e9, p
    except OSError:
        return None, p


def approval_file(ini_path):
    return os.path.join(APPROVALS, os.path.splitext(os.path.basename(ini_path))[0] + ".json")


def sbatch_summary(dest):
    """What the generated scripts will ask the scheduler for."""
    part, acct, qos, times, arrays, nscripts = {}, {}, {}, {}, 0, 0
    for root, dirs, files in os.walk(dest):
        dirs[:] = [d for d in dirs if not d.endswith("_shards")]
        for fn in files:
            if not fn.endswith((".sb", ".sh")):
                continue
            text = open(os.path.join(root, fn), errors="replace").read()
            if "#SBATCH" not in text:
                continue
            nscripts += 1
            for line in text.splitlines():
                m = re.match(r"#SBATCH\s+--(partition|account|qos|time)=(\S+)", line)
                if m:
                    tgt = {"partition": part, "account": acct, "qos": qos, "time": times}[m.group(1)]
                    tgt[m.group(2)] = tgt.get(m.group(2), 0) + 1
                m = re.match(r"#SBATCH\s+--array=(\d+)-(\d+)", line)       # fixed target / ResBos2 arrays
                if m:
                    arrays += int(m.group(2)) - int(m.group(1)) + 1
    sa = os.path.join(dest, "submit_all.sh")
    if os.path.isfile(sa):                                                # collider shard arrays: run_shards "<dir>" <script> <job> <N>
        for m in re.finditer(r'run_shards\s+"[^"]*"\s+\S+\s+\S+\s+(\d+)\)', open(sa).read()):
            arrays += int(m.group(1))
    return nscripts, part, acct, qos, times, arrays


def fmt(d):
    return ", ".join(f"{k} x{v}" for k, v in sorted(d.items())) or "-"


def cmd_show(args):
    ini = os.path.abspath(args.ini)
    cp = load_ini(ini)
    dest = dest_of(ini, cp)
    warns = []
    print(f"CAMPAIGN  {ini}")
    print(f"  ini sha256  {sha256_file(ini)}")
    print(f"  mode        {cp.get('campaign', 'mode', fallback='collider')}    name = {cp.get('campaign', 'name', fallback='?')}"
          f"    pdf = {cp.get('campaign', 'pdf', fallback='?')}")
    print("\nPATHS (relative values are relative to the .ini; this table is what the jobs will read and write)")
    print(f"  {'':5} {'section.key':26} {'resolved path':60} state")
    for sec, key, role, what in PATH_KEYS:
        if not cp.has_option(sec, key) or not cp.get(sec, key).strip():
            continue
        raw = cp.get(sec, key)
        path = resolve(ini, raw)
        if role == "WRITE":
            gb, base = free_space_of(path)
            state = ("ALREADY EXISTS (use --reuse or choose a new folder)" if os.path.exists(path) else
                     "new" + (f"; {gb:,.0f} GB free on {base}" if gb is not None else ""))
        else:
            state = "exists" if os.path.exists(path) else "NOT FOUND here (ok if it only exists on the cluster)"
        flag = "  <-- author's path?" if AUTHOR_MARK in path else ""
        if flag:
            warns.append(f"[{sec}] {key} = {raw.strip()} contains '{AUTHOR_MARK}' (the original author's account): replace it with your own path")
        print(f"  {role:5} {sec + '.' + key:26} {path:60} {state}{flag}")
        print(f"        {'':26} ({what})")
    if not cp.has_option("executables", "dir") and cp.get("campaign", "mode", fallback="collider") == "collider":
        print(f"  READ  {'executables.dir':26} {os.path.join(HERE, 'bin'):60} (default; no [executables] dir in the .ini)")
    if cp.has_option("paths", "scripts") is False:
        print(f"  READ  {'paths.scripts':26} {os.path.join(HERE, 'scripts'):60} (default)")

    print("\nENVIRONMENT of every job")
    if cp.has_section("environment"):
        for k in ("modules", "lhapdf", "hoppet", "root_setup"):
            print(f"  {k:11} {cp.get('environment', k, fallback='<driver default: the original author\'s>')}")
        for k in ("lhapdf", "hoppet", "root_setup"):
            if not cp.has_option("environment", k):
                warns.append(f"[environment] {k} is not set: the driver falls back to the original author's path")
        if not cp.has_option("environment", "modules"):
            warns.append("[environment] modules is not set: jobs load 'GCC/13.2.0 OpenMPI/4.1.6-GCC-13.2.0 powertools' (the author's)")
    else:
        warns.append("no [environment] section: every job uses the original author's modules and library paths")
        print("  (no [environment] section)")

    print("\nSCHEDULER")
    if cp.has_section("scheduler"):
        for k, v in cp.items("scheduler"):
            print(f"  {k:11} {v}")
    else:
        warns.append("no [scheduler] section: scripts ask for partition 'general-long' and no account (the author's cluster)")
        print("  (no [scheduler] section: driver defaults)")

    h = dest_hash(dest)
    print(f"\nPREPARED DEST  {dest}")
    if h is None:
        print("  not prepared yet: run  python3 run_process.py <ini>  (no --submit), then show again")
    else:
        same = os.path.isfile(os.path.join(dest, "campaign.ini")) and sha256_file(os.path.join(dest, "campaign.ini")) == sha256_file(ini)
        n, part, acct, qos, times, arrays = sbatch_summary(dest)
        print(f"  dest sha256 {h}")
        print(f"  dest/campaign.ini {'matches' if same else 'DIFFERS from'} this .ini" + ("" if same else "  <-- the .ini changed after preparing: prepare again (--reuse)"))
        if not same:
            warns.append("dest/campaign.ini differs from the .ini: re-run run_process.py with --reuse")
        print(f"  scripts with #SBATCH: {n}")
        print(f"    partitions: {fmt(part)}")
        print(f"    accounts:   {fmt(acct)}")
        print(f"    qos:        {fmt(qos)}")
        print(f"    walltimes:  {fmt(times)}")
        print(f"  array tasks in total (shards + --array lines): {arrays}   (compare with the site's queue limit; each task counts)")
        if not acct and cp.has_section("scheduler") is False:
            warns.append("no account in any script; many sites require one")
    af = approval_file(ini)
    print("\nAPPROVAL")
    if not os.path.isfile(af):
        print("  none recorded")
    else:
        a = json.load(open(af))
        ok_ini = a["ini_sha256"] == sha256_file(ini)
        ok_dest = h is not None and a["dest_sha256"] == h
        print(f"  approved {a['approved_at']} by {a['approved_by']}@{a['host']}  note: {a.get('note') or '-'}")
        print(f"  .ini unchanged since approval: {ok_ini}    dest scripts unchanged: {ok_dest}    submitted: {a.get('submitted_at') or 'no'}")
    if warns:
        print("\nWARNINGS")
        for w in warns:
            print(f"  - {w}")
    if args.full:
        print("\n===== .ini =====")
        print(open(ini).read())
    return 0


def cmd_approve(args):
    if not args.yes_i_reviewed:
        sys.exit("ERROR: approving is the user's decision. Review with  show --full , then run again with --yes-i-reviewed")
    ini = os.path.abspath(args.ini)
    cp = load_ini(ini)
    dest = dest_of(ini, cp)
    h = dest_hash(dest)
    if h is None:
        sys.exit("ERROR: dest is not prepared (no submit_all.sh). Run  python3 run_process.py <ini>  first, then review.")
    os.makedirs(APPROVALS, exist_ok=True)
    rec = {"ini": ini, "ini_sha256": sha256_file(ini), "dest": dest, "dest_sha256": h,
           "approved_at": datetime.datetime.now().isoformat(timespec="seconds"), "approved_by": getpass.getuser(),
           "host": socket.gethostname(), "note": args.note or "", "submitted_at": None}
    json.dump(rec, open(approval_file(ini), "w"), indent=2)
    print(f"approved: {approval_file(ini)}\n  ini  {rec['ini_sha256'][:16]}...\n  dest {h[:16]}...")
    return 0


def cmd_submit(args):
    ini = os.path.abspath(args.ini)
    cp = load_ini(ini)
    dest = dest_of(ini, cp)
    af = approval_file(ini)
    if not os.path.isfile(af):
        sys.exit("REFUSED: no approval recorded for this .ini. The user must review and approve it (skill review-and-authorize).")
    a = json.load(open(af))
    if a.get("submitted_at"):
        sys.exit(f"REFUSED: already submitted at {a['submitted_at']}. Prepare again with a new dest (or --reuse) and approve again to resubmit.")
    if a["ini_sha256"] != sha256_file(ini):
        sys.exit("REFUSED: the .ini changed after it was approved. Review and approve again.")
    h = dest_hash(dest)
    if h is None or h != a["dest_sha256"]:
        sys.exit("REFUSED: the prepared dest/ scripts changed (or dest is missing) after the approval. Review and approve again.")
    if not shutil.which("sbatch"):
        sys.exit("REFUSED: sbatch not found on this machine; run this on the cluster's login node.")
    log = os.path.join(dest, "submit_log_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".txt")
    print(f"submitting {dest}/submit_all.sh (approved {a['approved_at']} by {a['approved_by']})")
    r = subprocess.run(["bash", os.path.join(dest, "submit_all.sh")], capture_output=True, text=True)
    open(log, "w").write(r.stdout + r.stderr)
    print(r.stdout + r.stderr, end="")
    if r.returncode != 0:
        sys.exit(f"ERROR: submit_all.sh exited with {r.returncode}; some jobs may already be queued. Output saved to {log}")
    a["submitted_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    a["submit_log"] = log
    json.dump(a, open(af, "w"), indent=2)
    print(f"submitted. Output saved to {log}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("show")
    s.add_argument("ini")
    s.add_argument("--full", action="store_true", help="also print the .ini")
    s.set_defaults(fn=cmd_show)
    s = sub.add_parser("approve")
    s.add_argument("ini")
    s.add_argument("--yes-i-reviewed", action="store_true")
    s.add_argument("--note")
    s.set_defaults(fn=cmd_approve)
    s = sub.add_parser("submit")
    s.add_argument("ini")
    s.set_defaults(fn=cmd_submit)
    args = ap.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
