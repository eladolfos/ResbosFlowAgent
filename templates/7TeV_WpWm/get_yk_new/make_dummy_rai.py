#!/usr/bin/env python3
"""
Build a dummy R_Ai file (all angular-correction factors = 1) for get_yk_new,
using the Q,qT,y grid points from an existing w_pert_*.out (or w_asym_*.out)
file as the template.

Only valid for NLO runs: get_yk_new.f only applies the R_Ai interpolation
when iorder=="NNLO" (get_yk_new.f:234); for NLO the R_A0..R_A3 values are
hardwired to 1.0 regardless of what's in the R_Ai file, so this dummy file
produces the same NLO output as a real R_Ai file would -- it only exists to
satisfy the program's unconditional file-open/parse step at startup.
See README.md, "Running without a real R_Ai file", for details.

Usage:
    python3 make_dummy_rai.py <w_pert_file> <output_R_Ai_file> [ECM] [TYPE_V] [PDF_SET]

Example:
    python3 make_dummy_rai.py w_pert_ZU.out R_Ai_dummy_ZU.txt 8000.0 DY CT14nn.00
"""
import sys

def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    src = sys.argv[1]
    dst = sys.argv[2]
    ecm = sys.argv[3] if len(sys.argv) > 3 else "8000.0"
    type_v = sys.argv[4] if len(sys.argv) > 4 else "DY"
    pdf_set = sys.argv[5] if len(sys.argv) > 5 else "CT14nn.00"

    rows = []
    with open(src) as f:
        for line in f:
            # get_yk_new.f's iHeadLen() marks the end of the header by the
            # first 8 characters of a line being "  Q,qT,y" -- skip
            # everything up to and including that line the same way.
            if line[:8] == "  Q,qT,y":
                break
        else:
            raise SystemExit(f"Never found a '  Q,qT,y' header line in {src}")

        for line in f:
            parts = line.split()
            if len(parts) < 3:
                continue
            q, qt, y = parts[0], parts[1], parts[2]
            rows.append((q, qt, y))

    if not rows:
        raise SystemExit(f"No data rows found in {src} after the header")

    with open(dst, "w") as f:
        f.write("ECM, TYPE_V, PDF\n")
        f.write(f"{ecm} {type_v} {pdf_set}\n")
        f.write("  Q,qT,y R_A0 R_A1 R_A2 R_A3\n")
        for q, qt, y in rows:
            f.write(f"{q} {qt} {y} 1 1 1 1\n")

    print(f"Wrote {len(rows)} grid points to {dst}")

if __name__ == "__main__":
    main()