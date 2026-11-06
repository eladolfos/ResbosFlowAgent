#!/usr/bin/env python3
"""Final LO / NLO / W321 tables for the fixed-target Drell-Yan sets, following Yao's chain.

Per experiment <exp> the input directory <root>/<exp>/ must contain
  out_lo.txt                  Legacy LTO=-1, one line per point ("Q 0 y value err")
  getnlo_results.txt          output of Yao's getnlo.cpp (macro getnlo, or getnlo_nojac for E605):
                              "i only_pert NLO"  for qT_sep = 0.01 (already converted to Q^3 dsigma/dQ/d{y|xF})
  <exp>_ResBos2_w321.dat      GetFixed output: y Q data total intW intY intPert (already converted)
The LO is converted here with Q^3/1000*2Q (x ECM/(2 Q cosh y) for the xF-binned sets, none for E605), exactly as in
getnlo.cpp / FixedTarget.cc.

Sets
  e605, e866ppxf             absolute cross sections:   K_NLO = NLO/LO,  K_res = W321/NLO
  e866f, e906aF  (pp & pd)   data are RATIOS sigma(pd)/2sigma(pp); Legacy/GetFixed with FRACT_N=0.5 give the
                             per-nucleon average, so  ratio = X_pd / X_pp  and the neutron piece is
                             sigma_pn = 2 sigma_pd - sigma_pp  (this definition reproduces Yao's up2025 columns).
                             K "proton" = K of pp,  K "neutron" = K of sigma_pn.
Usage:  make_fixedtarget_tables.py --root DIR --outdir DIR [--label CT25NLO]
"""
import argparse
import math
import os

import numpy as np

ECM = {"e605": 38.8, "e866ppxf": 38.75, "e866f": 38.76, "e906aF": 15.07}


def base(Q):
    return Q ** 3 / 1000.0 * 2.0 * Q


def load_exp(root, name, ecm, jac):
    d = os.path.join(root, name)
    w = np.loadtxt(os.path.join(d, f"{name}_ResBos2_w321.dat"))
    lo_raw = np.loadtxt(os.path.join(d, "out_lo.txt"))
    nlo = np.loadtxt(os.path.join(d, "getnlo_results.txt"))
    if not (len(w) == len(lo_raw) == len(nlo)):
        raise SystemExit(f"{name}: inconsistent number of points {len(w)}/{len(lo_raw)}/{len(nlo)}")
    y, Q = w[:, 0], w[:, 1]
    # Yao's LO tables round y to 3 decimals while GetFixed's tables keep 4 (e.g. E906aF 0.772 vs 0.7717): allow the rounding
    if not (np.allclose(lo_raw[:, 0], Q, atol=6e-3, rtol=0) and np.allclose(lo_raw[:, 2], y, atol=6e-4, rtol=0)):
        raise SystemExit(f"{name}: LO points are not in the same order as GetFixed output")
    f = np.array([base(q) * (1.0 if jac == "none" else ecm / (2.0 * q * math.cosh(yy))) for q, yy in zip(Q, y)])
    return dict(y=y, Q=Q, data=w[:, 2], LO=lo_raw[:, 3] * f, NLO=nlo[:, 2], W=w[:, 3])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--label", default="CT25NLO")
    ap.add_argument("--only", help="comma-separated subset of e605,e866ppxf,e866f,e906aF (default: all four)")
    a = ap.parse_args()
    only = set(a.only.split(",")) if a.only else set(ECM)
    bad = only - set(ECM)
    if bad:
        raise SystemExit(f"--only: unknown set(s) {sorted(bad)}")
    os.makedirs(a.outdir, exist_ok=True)

    for e in [x for x in ("e605", "e866ppxf") if x in only]:
        t = load_exp(a.root, e, ECM[e], "none" if e == "e605" else "mT")
        lines = [f"# {a.label}: {e}  ECM={ECM[e]}  Q^3 dsigma/dQ/d{'y' if e == 'e605' else 'xF'} [nb GeV^2/nucleon]",
                 "# LO = Legacy LTO=-1 ; NLO = Yao's getnlo.cpp (qT_sep=0.01, qT_max=10; Legacy LTO=3,1) ; W321 = ResBos2 GetFixed",
                 "#      y       Q        data          LO           NLO          W321     NLO/LO  W321/NLO"]
        for i in range(len(t["y"])):
            lines.append(f"{t['y'][i]:8.3f} {t['Q'][i]:7.2f} {t['data'][i]:11.4e} {t['LO'][i]:12.5e} {t['NLO'][i]:12.5e} "
                         f"{t['W'][i]:12.5e} {t['NLO'][i] / t['LO'][i]:9.5f} {t['W'][i] / t['NLO'][i]:9.5f}")
        open(os.path.join(a.outdir, f"{e}_{a.label}_LO_NLO_W321.txt"), "w").write("\n".join(lines) + "\n")
        print(f"{e:9s} n={len(t['y']):3d}  K_NLO range [{(t['NLO'] / t['LO']).min():.3f},{(t['NLO'] / t['LO']).max():.3f}]  "
              f"K_res range [{(t['W'] / t['NLO']).min():.3f},{(t['W'] / t['NLO']).max():.3f}]")

    for e in [x for x in ("e866f", "e906aF") if x in only]:
        pp = load_exp(a.root, f"{e}_pp", ECM[e], "mT")
        pd = load_exp(a.root, f"{e}_pd", ECM[e], "mT")
        if not (np.allclose(pp["Q"], pd["Q"]) and np.allclose(pp["y"], pd["y"])):
            raise SystemExit(f"{e}: pp and pd points differ")
        pn = {k: 2.0 * pd[k] - pp[k] for k in ("LO", "NLO", "W")}
        lines = [f"# {a.label}: {e}  ECM={ECM[e]}  data = sigma(pd)/2sigma(pp);  columns per target: LO NLO W321 [Q^3 dsigma/dQ/dxF, per nucleon]",
                 "# pn = 2*pd - pp (per order).  ratio = pd/pp.  K_proton = K(pp), K_neutron = K(pn).",
                 "#      y       Q   data(ratio) | pp: LO NLO W321 | pd: LO NLO W321 | pn: LO NLO W321 | ratio LO NLO W321 | "
                 "NLO/LO(neutron) W321/NLO(neutron) NLO/LO(proton) W321/NLO(proton)"]
        for i in range(len(pp["y"])):
            vals = [pp["y"][i], pp["Q"][i], pp["data"][i]]
            for t in (pp, pd):
                vals += [t["LO"][i], t["NLO"][i], t["W"][i]]
            vals += [pn["LO"][i], pn["NLO"][i], pn["W"][i]]
            vals += [pd["LO"][i] / pp["LO"][i], pd["NLO"][i] / pp["NLO"][i], pd["W"][i] / pp["W"][i]]
            vals += [pn["NLO"][i] / pn["LO"][i], pn["W"][i] / pn["NLO"][i], pp["NLO"][i] / pp["LO"][i], pp["W"][i] / pp["NLO"][i]]
            lines.append(" ".join(f"{v:12.5e}" if k > 2 else f"{v:8.3f}" for k, v in enumerate(vals)))
        open(os.path.join(a.outdir, f"{e}_{a.label}_LO_NLO_W321.txt"), "w").write("\n".join(lines) + "\n")
        kn = pn["NLO"] / pn["LO"]; kp = pp["NLO"] / pp["LO"]
        print(f"{e:9s} n={len(pp['y']):3d}  K_NLO proton [{kp.min():.3f},{kp.max():.3f}]  neutron [{kn.min():.3f},{kn.max():.3f}]  "
              f"ratio_W321 [{(pd['W'] / pp['W']).min():.3f},{(pd['W'] / pp['W']).max():.3f}]  data ratio [{pp['data'].min():.3f},{pp['data'].max():.3f}]")


if __name__ == "__main__":
    main()
