#!/usr/bin/env python3
"""
make_grid_from_data.py -- build q_grid.inp/y_grid.inp for a run_process.py campaign.
Two modes:

  unique    -- take the UNIQUE Q/y values out of an experimental data table (e.g. for
               E605: 119 measured points, 18 unique Q x 7 unique y -- only 7 unmeasured
               "extra" grid points). Good when the table's unique-Q x unique-y product is
               close to its row count; check the printed "extra" count -- if it's a large
               fraction of the grid, this wastes compute on unmeasured points and a true
               per-point ExpCustomGrid campaign ([grids] experimental in the .ini) fits
               better instead.

  generate  -- build a genuine FINE, DENSE rectangular grid (the same role as
               templates/7TeV_WpWm's 80 Q x 143 y grid) spanning a continuous Q/y range,
               with N evenly- or log-spaced points -- NOT tied to where any experiment
               happened to measure. This is what a campaign needs to get real resNLO
               results out of resbos (which interpolates over the grid; it needs it dense
               and complete, not just wherever data exists). The range can be given
               explicitly (--q-min/--q-max) or taken from a data table's min/max
               (--q-from TABLE) -- the latter only borrows the table's *span*, not its
               individual values, unlike `unique` mode.

In both modes the qT grid is left untouched -- point [templates] at a source whose
qt_grid.inp is already the one you want (e.g. the real per-experiment qT binning), and
only q_grid.inp/y_grid.inp get replaced. Remember to copy the same two output files into
every one of legacy/w_pert/w_asym's inp/ (run_process.py's grid-lockstep check requires
byte-identical files across all three).

Usage:
    python3 make_grid_from_data.py unique <data_table> <out_q_grid.inp> <out_y_grid.inp> \\
        [--y-col N] [--q-col N]

    python3 make_grid_from_data.py generate <out_q_grid.inp> <out_y_grid.inp> \\
        --n-q N --n-y N \\
        (--q-min MIN --q-max MAX | --q-from TABLE [--q-col N]) \\
        (--y-min MIN --y-max MAX | --y-from TABLE [--y-col N]) \\
        [--q-spacing linear|log] [--y-spacing linear|log]

    data_table    whitespace-separated table, one row per measured point (blank lines and
                  lines starting with '#' are skipped)
    out_*.inp     one value per line -- the same format already used by
                  templates/*/legacy/inp/q_grid.inp etc.
    --y-col N     1-based column holding y (default 1, matching the e605/e866/e906 tables
                  under New_kFactorCT25/FixedTarget_pp830a016_yao_09182026/)
    --q-col N     1-based column holding Q (default 2)
    --q-spacing / --y-spacing   linear (default) or log (needs strictly positive bounds;
                  matches how templates/7TeV_WpWm/*/inp/qt_grid.inp is spaced, since qT
                  resolution matters most near qT->0 -- Q/y are usually fine linear, e.g.
                  templates/7TeV_WpWm's own y_grid.inp is uniform step 0.1)

Examples (E605, ECM=38.8, real data spans Q~7-17 GeV, y~-0.2 to 0.4):
    # unique mode (already used for E201_e605_full.ini):
    python3 make_grid_from_data.py unique \\
        ".../Workspace/FixedTargetKFactor/e605/e605" \\
        templates/E605_full/legacy/inp/q_grid.inp templates/E605_full/legacy/inp/y_grid.inp

    # generate mode, explicit range (a real dense grid for resbos):
    python3 make_grid_from_data.py generate \\
        templates/E605_fine/legacy/inp/q_grid.inp templates/E605_fine/legacy/inp/y_grid.inp \\
        --n-q 40 --n-y 25 --q-min 4.0 --q-max 20.0 --y-min -0.5 --y-max 0.5

    # generate mode, range taken from the data table's own min/max instead of typed by hand:
    python3 make_grid_from_data.py generate \\
        templates/E605_fine/legacy/inp/q_grid.inp templates/E605_fine/legacy/inp/y_grid.inp \\
        --n-q 40 --n-y 25 \\
        --q-from ".../Workspace/FixedTargetKFactor/e605/e605" \\
        --y-from ".../Workspace/FixedTargetKFactor/e605/e605"
"""
import argparse
import math
import sys


def unique_sorted(values):
    """De-dup by float value, keep first-seen string form, sort ascending by value."""
    seen = {}
    for v in values:
        key = float(v)
        if key not in seen:
            seen[key] = v
    return [seen[k] for k in sorted(seen)]


def read_column(path, col):
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < col:
                sys.exit(f"{path}: line has fewer than {col} columns: {line!r}")
            out.append(parts[col - 1])
    if not out:
        sys.exit(f"{path}: no data rows found")
    return out


def fmt(x):
    return f"{x:.6g}"


def write_grid(path, vals):
    with open(path, "w") as f:
        f.write("\n".join(vals) + "\n")


def cmd_unique(args):
    y_vals = unique_sorted(read_column(args.data_table, args.y_col))
    q_vals = unique_sorted(read_column(args.data_table, args.q_col))
    n_rows = sum(1 for line in open(args.data_table)
                 if line.strip() and not line.strip().startswith("#"))
    grid_pts = len(q_vals) * len(y_vals)

    write_grid(args.out_q_grid, q_vals)
    write_grid(args.out_y_grid, y_vals)

    print(f"{args.data_table}: {n_rows} measured points -> "
          f"{len(q_vals)} unique Q x {len(y_vals)} unique y = {grid_pts} grid points "
          f"({grid_pts - n_rows} not actually measured)")
    print(f"wrote {args.out_q_grid} ({len(q_vals)} values)")
    print(f"wrote {args.out_y_grid} ({len(y_vals)} values)")


def spaced(lo, hi, n, spacing):
    if n < 1:
        sys.exit("--n-q/--n-y must be >= 1")
    if n == 1:
        return [lo]
    if spacing == "log":
        if lo <= 0 or hi <= 0:
            sys.exit(f"log spacing needs strictly positive bounds, got [{lo}, {hi}]")
        llo, lhi = math.log(lo), math.log(hi)
        step = (lhi - llo) / (n - 1)
        return [math.exp(llo + i * step) for i in range(n)]
    step = (hi - lo) / (n - 1)
    return [lo + i * step for i in range(n)]


def resolve_range(args, axis):
    lo, hi, frm, col = (getattr(args, f"{axis}_min"), getattr(args, f"{axis}_max"),
                         getattr(args, f"{axis}_from"), getattr(args, f"{axis}_col"))
    if frm:
        vals = [float(v) for v in read_column(frm, col)]
        lo, hi = min(vals), max(vals)
        print(f"{axis}: range taken from {frm} col {col} -> [{fmt(lo)}, {fmt(hi)}]")
    elif lo is None or hi is None:
        sys.exit(f"give either --{axis}-min/--{axis}-max or --{axis}-from")
    return lo, hi


def cmd_generate(args):
    q_lo, q_hi = resolve_range(args, "q")
    y_lo, y_hi = resolve_range(args, "y")
    q_vals = [fmt(v) for v in spaced(q_lo, q_hi, args.n_q, args.q_spacing)]
    y_vals = [fmt(v) for v in spaced(y_lo, y_hi, args.n_y, args.y_spacing)]

    write_grid(args.out_q_grid, q_vals)
    write_grid(args.out_y_grid, y_vals)

    print(f"generated {args.n_q} Q points ({args.q_spacing}, [{fmt(q_lo)}, {fmt(q_hi)}]) x "
          f"{args.n_y} y points ({args.y_spacing}, [{fmt(y_lo)}, {fmt(y_hi)}]) = "
          f"{args.n_q * args.n_y} grid points")
    print(f"wrote {args.out_q_grid} ({len(q_vals)} values)")
    print(f"wrote {args.out_y_grid} ({len(y_vals)} values)")
    print("remember: qT grid is untouched -- point [templates] at a source with the "
          "qt_grid.inp you want, and copy these two files into legacy/w_pert/w_asym's "
          "inp/ so all three match by md5 (run_process.py's grid-lockstep check).")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="mode", required=True)

    p_u = sub.add_parser("unique", help="grid from a table's unique Q/y values")
    p_u.add_argument("data_table")
    p_u.add_argument("out_q_grid")
    p_u.add_argument("out_y_grid")
    p_u.add_argument("--y-col", type=int, default=1)
    p_u.add_argument("--q-col", type=int, default=2)
    p_u.set_defaults(func=cmd_unique)

    p_g = sub.add_parser("generate", help="fine dense grid over a continuous range")
    p_g.add_argument("out_q_grid")
    p_g.add_argument("out_y_grid")
    p_g.add_argument("--n-q", type=int, required=True)
    p_g.add_argument("--n-y", type=int, required=True)
    p_g.add_argument("--q-min", type=float)
    p_g.add_argument("--q-max", type=float)
    p_g.add_argument("--q-from", metavar="TABLE")
    p_g.add_argument("--q-col", type=int, default=2)
    p_g.add_argument("--q-spacing", choices=("linear", "log"), default="linear")
    p_g.add_argument("--y-min", type=float)
    p_g.add_argument("--y-max", type=float)
    p_g.add_argument("--y-from", metavar="TABLE")
    p_g.add_argument("--y-col", type=int, default=1)
    p_g.add_argument("--y-spacing", choices=("linear", "log"), default="linear")
    p_g.set_defaults(func=cmd_generate)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
