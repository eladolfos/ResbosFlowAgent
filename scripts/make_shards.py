#!/usr/bin/env python3
"""
Split a w_asym .in file into N shards along the Q grid (the outermost
loop in w_asym.f), so the shards can be run in parallel and their
outputs concatenated back into one file with no reordering.

Usage:
    python3 make_shards.py BASE_IN JOBNAME N_SHARDS

Example:
    python3 make_shards.py E211_w_asym_Wm.in E211_w_asym_Wm 20

Produces (inside ./<JOBNAME>_shards/, created if it doesn't exist):
    <JOBNAME>_shard00.in ... <JOBNAME>_shardNN.in
    <JOBNAME>_shards.manifest   (one shard name + Q range per line, in order)

w_asym is always run from this directory (so its relative ./inp/*.inp
paths keep working), so shard names in the manifest are stored as paths
relative to this directory, e.g. "<JOBNAME>_shards/<JOBNAME>_shard00".
"""
import os
import re
import sys


def split_ranges(lo, hi, n_shards):
    total = hi - lo + 1
    n_shards = min(n_shards, total)
    base, extra = divmod(total, n_shards)
    ranges = []
    start = lo
    for i in range(n_shards):
        size = base + (1 if i < extra else 0)
        end = start + size - 1
        ranges.append((start, end))
        start = end + 1
    return ranges


def main():
    if len(sys.argv) != 4:
        print("Usage: python3 make_shards.py BASE_IN JOBNAME N_SHARDS")
        sys.exit(1)

    base_in, jobname, n_shards = sys.argv[1], sys.argv[2], int(sys.argv[3])

    with open(base_in) as f:
        lines = f.readlines()

    active_idx = None
    for i, line in enumerate(lines):
        if "Active setting" in line:
            active_idx = i
            break
    if active_idx is None:
        print("ERROR: could not find the 'Active setting' line in", base_in)
        sys.exit(1)

    m = re.match(r"\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)",
                 lines[active_idx])
    if not m:
        print("ERROR: could not parse 9 integers from Active setting line:")
        print(lines[active_idx])
        sys.exit(1)

    iqtmn, iqtmx, iqtst, iymn, iymx, iyst, iqmn, iqmx, iqst = map(int, m.groups())
    print(f"Full grid from {base_in}: qT[{iqtmn}-{iqtmx}] y[{iymn}-{iymx}] Q[{iqmn}-{iqmx}]")

    if iqst != 1:
        print("WARNING: Q step != 1 was found; splitting along Q assumes "
              "step=1 there so shard boundaries stay aligned with the "
              "original grid points. Aborting to avoid silently producing "
              "a wrong/incomplete grid. (qT/y steps are not split and may "
              "be anything.)")
        sys.exit(1)

    q_ranges = split_ranges(iqmn, iqmx, n_shards)

    shard_dir = f"{jobname}_shards"
    os.makedirs(shard_dir, exist_ok=True)

    manifest_path = os.path.join(shard_dir, f"{jobname}_shards.manifest")
    with open(manifest_path, "w") as manifest:
        for i, (qlo, qhi) in enumerate(q_ranges):
            shard_rel = f"{shard_dir}/{jobname}_shard{i:02d}"
            shard_lines = list(lines)
            new_active = (f"{iqtmn}  {iqtmx}  {iqtst}   {iymn} {iymx} {iyst}"
                          f"  {qlo} {qhi} {iqst}"
                          f"                       > Active setting (shard {i}, Q[{qlo}-{qhi}])\n")
            shard_lines[active_idx] = new_active
            with open(f"{shard_rel}.in", "w") as sf:
                sf.writelines(shard_lines)
            manifest.write(f"{shard_rel}\t{qlo}\t{qhi}\n")
            print(f"Wrote {shard_rel}.in  Q[{qlo}-{qhi}]  "
                  f"({(qhi-qlo+1)*(iymx-iymn+1)*(iqtmx-iqtmn+1)} rows expected)")

    print(f"\n{len(q_ranges)} shards written under {shard_dir}/. Manifest: {manifest_path}")
    print(f"Run the array job with: ./submit_w_asym_array.sh {jobname} 0-{len(q_ranges)-1}")


if __name__ == "__main__":
    main()