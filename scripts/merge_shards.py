#!/usr/bin/env python3
"""
Concatenate shard .out files (produced by make_shards.py + run_w_asym_array.sb)
back into a single w_asym .out file, in the same order w_asym.f would have
written them in a single serial run.

Usage:
    python3 merge_shards.py JOBNAME OUTPUT_FILE

Example:
    python3 merge_shards.py E211_w_asym_Wm E211_w_asym_Wm.out
"""
import os
import sys

# w_asym.f writes: 1 line "ECM, IBEAM, JWTYPE_IN, ..." + 1 line (blank,
# since JWTYPE != JHB for W+/W- runs) + 1 line column header, then data
# rows start. Verified against an actual w_asym.out.
HEADER_LINES = 3


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 merge_shards.py JOBNAME OUTPUT_FILE")
        sys.exit(1)

    jobname, out_file = sys.argv[1], sys.argv[2]
    shard_dir = f"{jobname}_shards"
    manifest_path = os.path.join(shard_dir, f"{jobname}_shards.manifest")

    with open(manifest_path) as f:
        shards = [line.split("\t") for line in f if line.strip()]

    total_rows = 0
    header = None
    body_chunks = []

    for shard_name, qlo, qhi in shards:
        shard_out = f"{shard_name}.out"
        try:
            with open(shard_out) as f:
                lines = f.readlines()
        except FileNotFoundError:
            print(f"ERROR: missing {shard_out} — that shard hasn't finished "
                  f"or failed. Check its slurm log before merging.")
            sys.exit(1)

        if len(lines) <= HEADER_LINES:
            print(f"ERROR: {shard_out} only has {len(lines)} lines, expected "
                  f"a {HEADER_LINES}-line header plus data. Shard likely failed.")
            sys.exit(1)

        shard_header = lines[:HEADER_LINES]
        shard_body = lines[HEADER_LINES:]

        if header is None:
            header = shard_header
        elif shard_header != header:
            print(f"WARNING: header of {shard_out} differs from the first "
                  f"shard's header — check these files were generated with "
                  f"identical .in settings aside from the Q range.")

        body_chunks.append(shard_body)
        total_rows += len(shard_body)
        print(f"{shard_name}: Q[{qlo.strip()}-{qhi.strip()}]  {len(shard_body)} rows")

    with open(out_file, "w") as f:
        f.writelines(header)
        for chunk in body_chunks:
            f.writelines(chunk)

    print(f"\nWrote {out_file}: {HEADER_LINES} header lines + {total_rows} data rows")
    print("Sanity check this against the expected row count "
          "(Q_count * y_count * qT_count) before using it downstream.")


if __name__ == "__main__":
    main()