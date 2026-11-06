#!/usr/bin/env python3
"""
validate_campaign.py DEST [--cross-tol FRAC] [--min-root-mb MB]

Post-run check of a finished run_process.py campaign, written to DEST/validation_summary.txt
and printed to stdout. Exit status 1 if any ERROR.

Checks
  1. Every resbos log (resbos/resbos_output_*.log, latest job per piece) has a finite
     TOTAL CROSS SECTION, reached "finished with exit code 0", and contains no NaN.
  2. Each resbos piece produced a .root in DEST with a plausible size (stubs are ~60 KB,
     real outputs are ~1 GB; below --min-root-mb is an ERROR).
  3. The merged grids (*.out in legacy/, w_pert/, w_asym/, get_yk_new/, resbos/Resbos_grids/, resbos2_w/)
     contain no NaN/Inf tokens.
  4. If resNLO, nloasy and nlodsi are all present for a process: resNLO should agree with
     nloasy + nlodsi (WARN if the relative difference exceeds --cross-tol).
"""
import argparse
import glob
import math
import os
import re
import sys

RESBOS_LOG = re.compile(r"^resbos_output_(.+)_(resNLO|nloasy|nlodsi)_(\d+)\.log$")
XSEC = re.compile(r"TOTAL CROSS SECTION\s*=\s*(\S+)\s+PB\s*\+/-\s*(\S+)")
NAN_TOKEN = re.compile(r"(?<![A-Za-z0-9_])(NaN|Inf|Infinity)(?![A-Za-z0-9_])", re.IGNORECASE)
PIECES = ("resNLO", "nloasy", "nlodsi")

lines = []      # every printed line, also written to validation_summary.txt
errors, warns = [], []


def emit(text=""):
    lines.append(text)
    print(text)


def ok(msg):
    emit(f"OK    {msg}")


def warn(msg):
    warns.append(msg)
    emit(f"WARN  {msg}")


def error(msg):
    errors.append(msg)
    emit(f"ERROR {msg}")


def latest_logs(dest):
    """{(base, piece): (logpath, jobid)} keeping only the highest job id per (base, piece)."""
    found = {}
    for path in glob.glob(os.path.join(dest, "resbos", "resbos_output_*.log")):
        m = RESBOS_LOG.match(os.path.basename(path))
        if not m:
            continue
        key = (m.group(1), m.group(2))
        jid = int(m.group(3))
        if key not in found or jid > found[key][1]:
            found[key] = (path, jid)
    return found


def parse_log(path):
    with open(path, errors="replace") as f:
        text = f.read()
    m = None
    for m in XSEC.finditer(text):
        pass  # keep the last TOTAL CROSS SECTION line
    xs = (m.group(1), m.group(2)) if m else None
    nan_count = len(re.findall(r"\bNaN\b", text))
    finished = "finished with exit code 0" in text
    has_events = "EVENTS PASSING CUTS" in text
    return xs, nan_count, finished, has_events


def check_resbos(dest, logs):
    """Returns {(base, piece): dict} with sigma, err, finite, finished, nan, job."""
    rows = {}
    for (base, piece), (path, jid) in sorted(logs.items()):
        name = f"{base} {piece} (job {jid})"
        xs, nan_count, finished, has_events = parse_log(path)
        row = {"job": jid, "sigma": None, "err": None, "finite": False,
               "finished": finished, "nan": nan_count}
        rows[(base, piece)] = row
        if xs is None:
            error(f"{name}: no 'TOTAL CROSS SECTION' line -- run did not finish")
            continue
        try:
            v, e = float(xs[0]), float(xs[1])
        except ValueError:
            v, e = float("nan"), float("nan")
        row["sigma"], row["err"] = v, e
        row["finite"] = math.isfinite(v) and math.isfinite(e)
        if not row["finite"]:
            error(f"{name}: cross section is not finite ({xs[0]} +/- {xs[1]})")
            continue
        if nan_count:
            error(f"{name}: {nan_count} NaN tokens in the resbos log, although the final value is finite")
        if not finished:
            error(f"{name}: missing 'finished with exit code 0'")
        if not has_events:
            error(f"{name}: no 'EVENTS PASSING CUTS' line")
        if finished and has_events and not nan_count:
            ok(f"{name}: sigma = {v:.6g} +/- {e:.4g} pb, finite, finished")
    return rows


def check_roots(dest, logs, min_mb, rows):
    pieces = sorted({piece for (_, piece) in logs})
    for piece in pieces:
        matches = sorted(glob.glob(os.path.join(dest, f"*_{piece}.root")))
        if not matches:
            error(f"no *_{piece}.root in {dest}")
            continue
        for path in matches:
            mb = os.path.getsize(path) / 1e6
            base = os.path.basename(path)[: -len(f"_{piece}.root")]
            if (base, piece) in rows:
                rows[(base, piece)]["root_mb"] = mb
            if mb < min_mb:
                error(f"{os.path.basename(path)}: {mb:.2f} MB -- stub (real outputs are ~1 GB)")
            else:
                ok(f"{os.path.basename(path)}: {mb:.0f} MB")


def scan_grid_nan(dest):
    patterns = ["legacy/*.out", "w_pert/*.out", "w_asym/*.out", "get_yk_new/*.out",
                "resbos/Resbos_grids/*.out", "resbos2_w/*_main.out", "resbos2_w/*/Q*/Grids/ResBos_GridFile_0.out"]
    files = []
    for pat in patterns:
        files += [p for p in glob.glob(os.path.join(dest, pat)) if "_shards" not in p]
    bad_files = []
    for path in sorted(files):
        with open(path, errors="replace") as f:
            bad = any(NAN_TOKEN.search(line) for line in f)
        rel = os.path.relpath(path, dest)
        if bad:
            bad_files.append(rel)
            error(f"{rel}: contains NaN/Inf values -- the grid is corrupt")
        else:
            ok(f"{rel}: no NaN/Inf")
    return len(files), bad_files


def comparisons(rows, tol):
    """{base: dict} for every process that has all three pieces."""
    out = {}
    bases = sorted({b for (b, _) in rows})
    for base in bases:
        if not all((base, p) in rows and rows[(base, p)]["finite"] for p in PIECES):
            continue
        rn = rows[(base, "resNLO")]
        a = rows[(base, "nloasy")]
        d = rows[(base, "nlodsi")]
        total = a["sigma"] + d["sigma"]
        rel = (rn["sigma"] - total) / total
        sig_total = math.hypot(a["err"], d["err"])
        out[base] = {"resNLO": rn["sigma"], "resNLO_err": rn["err"], "sum": total,
                     "sum_err": sig_total, "rel": rel, "ok": abs(rel) <= tol}
        if abs(rel) > tol:
            warn(f"{base}: resNLO vs nloasy+nlodsi differs by {100*rel:+.2f} % "
                 f"(above tolerance {100*tol:.1f} %)")
        else:
            ok(f"{base}: resNLO vs nloasy+nlodsi differs by {100*rel:+.2f} %")
    return out


def piece_table(rows):
    emit("")
    emit("Table 1. Resbos pieces")
    emit(f"{'Run':<40}{'Piece':<9}{'Sigma (pb)':>14}{'Error':>11}{'Finite':>8}{'Finished':>10}{'ROOT (MB)':>11}{'Status':>9}")
    emit("-" * 112)
    for (base, piece) in sorted(rows, key=lambda k: (k[0], PIECES.index(k[1]))):
        r = rows[(base, piece)]
        sigma = f"{r['sigma']:.4f}" if r["sigma"] is not None and r["finite"] else "NaN"
        err = f"{r['err']:.4f}" if r["err"] is not None and r["finite"] else "NaN"
        root = f"{r['root_mb']:.0f}" if "root_mb" in r else "-"
        status = "PASS" if r["finite"] and r["finished"] and r["nan"] == 0 else "FAIL"
        emit(f"{base:<40}{piece:<9}{sigma:>14}{err:>11}{('yes' if r['finite'] else 'no'):>8}"
             f"{('yes' if r['finished'] else 'no'):>10}{root:>11}{status:>9}")


def comparison_table(comp, tol):
    emit("")
    emit("Table 2. resNLO vs nloasy + nlodsi")
    emit(f"{'Run':<40}{'resNLO (pb)':>16}{'nloasy+nlodsi (pb)':>22}{'Rel. diff':>12}{'Status':>9}")
    emit("-" * 99)
    for base, c in sorted(comp.items()):
        emit(f"{base:<40}{c['resNLO']:>12.3f} +/-{c['resNLO_err']:.2f}"
             f"{c['sum']:>14.3f} +/-{c['sum_err']:.2f}"
             f"{100*c['rel']:>+11.2f}%{('PASS' if c['ok'] else 'WARN'):>9}")
    emit(f"Tolerance: {100*tol:.1f} %")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dest")
    ap.add_argument("--cross-tol", type=float, default=0.03,
                    help="relative tolerance for resNLO vs nloasy+nlodsi (default 3 percent)")
    ap.add_argument("--min-root-mb", type=float, default=100.0,
                    help="ROOT files smaller than this are reported as stubs (default 100 MB)")
    args = ap.parse_args()

    emit(f"Validation of {args.dest}")
    emit("=" * 72)
    logs = latest_logs(args.dest)
    rows, comp, n_grids, bad_grids = {}, {}, 0, []
    if not logs:
        error("no resbos logs found under resbos/ -- nothing to validate")
    else:
        rows = check_resbos(args.dest, logs)
        check_roots(args.dest, logs, args.min_root_mb, rows)
        comp = comparisons(rows, args.cross_tol)
    n_grids, bad_grids = scan_grid_nan(args.dest)

    if rows:
        piece_table(rows)
    if comp:
        comparison_table(comp, args.cross_tol)

    emit("")
    verdict = "PASSED" if not errors else f"FAILED ({len(errors)} error(s))"
    extra = f", {len(warns)} warning(s)" if warns else ""
    emit(f"Grids scanned: {n_grids}, with NaN/Inf: {len(bad_grids)}")
    emit(f"VALIDATION {verdict}{extra}")

    with open(os.path.join(args.dest, "validation_summary.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
