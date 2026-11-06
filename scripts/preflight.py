#!/usr/bin/env python3
"""
preflight.py -- a short job that checks, on a compute node, what a campaign will need, before any real campaign is submitted.

  prepare <ini>                         write <dest>.preflight/preflight.sb and print it
  submit  <ini> --yes-i-reviewed        sbatch it (the user has seen the script printed by `prepare`)
  result  <ini>                         read its output; exit 0 = PASS, 1 = FAIL, 2 = not finished yet

The script uses the same #SBATCH header ([scheduler]) and the same module/library block ([environment]) that the real jobs of the .ini get, so a PASS
means those two sections work on a compute node. It checks, for the executables and inputs of that .ini: the files exist and are executable, every shared
library of each executable resolves (ldd; the executables are NOT run), LHAPDF and the requested PDF set are visible, ROOT is visible, python3/numpy for
fixed target, and the folder that will hold `dest` is writable. It runs no ResBos code, takes seconds, and writes only into <dest>.preflight/ and a test file
in the parent of dest.

Standard library only; imports run_process.py from the repository root to reuse its own resolution of executables, header and environment.
"""
import argparse
import glob
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import run_process as rp  # noqa: E402

COLLIDER_EXES = [("w_pert", "w_pert"), ("w_asym", "w_asym"), ("legacy", "main"), ("get_yk_new", "get_yk_new"), ("resbos", "resbos_root")]


def collect(cfg):
    """(label, path) of every executable/input this .ini uses, from run_process's own resolution."""
    if cfg.mode == "fixedtarget":
        return [("Legacy main (fixed target)", cfg.ft_legacy_src()), ("ResBos2 GetFixed", cfg.ft.getfixed)], cfg.ft.env
    return [(f, cfg.exe_src(f, e)) for f, e in COLLIDER_EXES], None


def build_script(cfg, pdir):
    exes, env_script = collect(cfg)
    name = os.path.basename(cfg.dest.rstrip("/"))
    job = f"{name}_preflight"
    if len(job) > 95:
        rp.die(f"job name {job} is longer than 95 characters: shorten the last folder of [paths] dest")
    pdf = (cfg.get("campaign", "pdf", "") or "").strip()
    ft = cfg.mode == "fixedtarget"
    lines = [
        "#!/bin/bash --login",
        f"#SBATCH --job-name={job}",
        f"#SBATCH --output={pdir}/preflight_%j.out",
        f"#SBATCH --error={pdir}/preflight_%j.err",
        "#SBATCH --time=00:10:00",
        "#SBATCH --nodes=1 --ntasks=1 --cpus-per-task=1",
        "#SBATCH --mem=2G",
        "#SBATCH --partition=general-long",
        "",
        rp.env_lines(cfg, root=True, prov=False).rstrip("\n"),
        "",
        "FAILS=0",
        'ok()   { echo "OK    $*"; }',
        'warn() { echo "WARN  $*"; }',
        'fail() { echo "FAIL  $*"; FAILS=$((FAILS+1)); }',
        'echo "== node: $(hostname)  date: $(date \'+%F %T\')  job: ${SLURM_JOB_ID:-?}  partition: ${SLURM_JOB_PARTITION:-?}  account: ${SLURM_JOB_ACCOUNT:-?}"',
        'echo "== modules: $(module -t list 2>&1 | tr \'\\n\' \' \')"',
        'echo "== LD_LIBRARY_PATH=$LD_LIBRARY_PATH"',
        'echo "== LHAPDF_DATA_PATH=${LHAPDF_DATA_PATH:-<unset>}"',
        "",
    ]
    if env_script:
        lines += [f'source {_q(env_script)} 2>/dev/null || fail "cannot source {env_script}"', ""]
    for label, path in exes:
        q = _q(path)
        lines += [
            f'if [ -x {q} ]; then ok "{label}: {path} is executable"',
            f'  LDD=$(ldd {q} 2>&1); MISSING=$(echo "$LDD" | grep "not found")',
            f'  if [ -n "$MISSING" ]; then fail "{label}: unresolved libraries:"; echo "$MISSING" | sed \'s/^/        /\'; '
            f'elif echo "$LDD" | grep -q "not a dynamic"; then warn "{label}: not a dynamic executable (a wrapper script?); its libraries were not checked"; '
            f'else ok "{label}: all shared libraries resolve"; fi',
            f'else fail "{label}: {path} missing or not executable"; fi',
        ]
    lines += [
        "",
        'if command -v lhapdf-config >/dev/null 2>&1; then ok "LHAPDF $(lhapdf-config --version) at $(lhapdf-config --prefix)"; else fail "lhapdf-config not found (set [environment] lhapdf)"; fi',
    ]
    if pdf:
        lines += [f'if lhapdf ls --installed 2>/dev/null | grep -qxw {_q(pdf)}; then ok "PDF set {pdf} is installed"; else fail "PDF set {pdf} not found by lhapdf ls --installed"; fi']
    lines += [
        'if command -v hoppet-config >/dev/null 2>&1; then ok "HOPPET $(hoppet-config --version)"; else warn "hoppet-config not in PATH; record the HOPPET version by hand (it changes results at the 0.1% level)"; fi',
        'if command -v root-config >/dev/null 2>&1; then ok "ROOT $(root-config --version)"; else fail "root-config not found (set [environment] root_setup); needed for events and the fixed-target final job"; fi',
    ]
    lines += ['if python3 -c "import numpy" 2>/dev/null; then ok "python3 numpy"; else ' + ('fail' if ft else 'warn') + ' "python3 cannot import numpy' + (' (needed by the fixed-target final job)' if ft else '') + '"; fi']
    parent = os.path.dirname(cfg.dest.rstrip("/"))
    lines += [
        f'if mkdir -p {_q(parent)} 2>/dev/null && touch {_q(parent)}/.preflight_write_test 2>/dev/null; then rm -f {_q(parent)}/.preflight_write_test; ok "can write in {parent}"; else fail "cannot write in {parent}"; fi',
        f'df -h {_q(parent)} 2>&1 | tail -n 1',
        "",
        'if [ "$FAILS" -eq 0 ]; then echo "PREFLIGHT_RESULT=PASS"; else echo "PREFLIGHT_RESULT=FAIL ($FAILS failed checks)"; fi',
        'exit 0',
    ]
    return "\n".join(lines) + "\n", job


def _q(s):
    return "'" + s.replace("'", "'\\''") + "'"


def pdir_of(cfg):
    return cfg.dest.rstrip("/") + ".preflight"


def cmd_prepare(args):
    cfg = rp.Cfg(args.ini)
    rp.init_scheduler(cfg)
    pdir = pdir_of(cfg)
    os.makedirs(pdir, exist_ok=True)
    for f in glob.glob(os.path.join(pdir, "preflight_*")) + [os.path.join(pdir, "job_id")]:
        if os.path.exists(f):
            os.remove(f)
    text, job = build_script(cfg, pdir)
    path = os.path.join(pdir, "preflight.sb")
    rp.write(path, text, exe=True)
    print(f"preflight script: {path}\n{'=' * 70}\n{open(path).read()}{'=' * 70}")
    rp.report_scheduler()
    print("It runs no ResBos code and submits nothing by itself. After the user has read it:\n"
          "  python3 scripts/preflight.py submit <ini> --yes-i-reviewed")
    return 0


def cmd_submit(args):
    if not args.yes_i_reviewed:
        sys.exit("ERROR: submitting is the user's decision. Show the output of `prepare`, get an explicit yes, then run with --yes-i-reviewed")
    cfg = rp.Cfg(args.ini)
    pdir = pdir_of(cfg)
    sb = os.path.join(pdir, "preflight.sb")
    if not os.path.isfile(sb):
        sys.exit("ERROR: run `prepare` first")
    if os.path.isfile(os.path.join(pdir, "job_id")):
        sys.exit("REFUSED: already submitted (job " + open(os.path.join(pdir, "job_id")).read().strip() + "). Run `prepare` again to resubmit after a change.")
    if not shutil.which("sbatch"):
        sys.exit("ERROR: sbatch not found on this machine; run this on the cluster")
    r = subprocess.run(["sbatch", "--parsable", "preflight.sb"], cwd=pdir, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("ERROR: sbatch failed:\n" + r.stdout + r.stderr)
    jid = r.stdout.strip().split(";")[0]
    open(os.path.join(pdir, "job_id"), "w").write(jid + "\n")
    print(f"submitted preflight job {jid}. It should take seconds once it starts. Ask the user whether it has finished, then run `result`.")
    return 0


def cmd_result(args):
    cfg = rp.Cfg(args.ini)
    pdir = pdir_of(cfg)
    outs = sorted(glob.glob(os.path.join(pdir, "preflight_*.out")), key=os.path.getmtime)
    if not outs:
        print("no output yet: the job is pending or running, was not submitted, or failed before starting (look at preflight_*.err)")
        return 2
    text = open(outs[-1]).read()
    errs = glob.glob(outs[-1][:-4] + ".err")
    print(text.rstrip())
    if errs and os.path.getsize(errs[0]) > 0:
        print("\n--- stderr (module/source messages are normal; read them) ---")
        print(open(errs[0]).read().rstrip()[-2000:])
    m = re.search(r"PREFLIGHT_RESULT=(PASS|FAIL[^\n]*)", text)
    if not m:
        print("\nNo PREFLIGHT_RESULT line: the job did not reach the end (killed, walltime, or crashed). Check preflight_*.err.")
        return 2
    return 0 if m.group(1) == "PASS" else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("prepare", cmd_prepare), ("submit", cmd_submit), ("result", cmd_result)):
        s = sub.add_parser(name)
        s.add_argument("ini")
        if name == "submit":
            s.add_argument("--yes-i-reviewed", action="store_true")
        s.set_defaults(fn=fn)
    args = ap.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
