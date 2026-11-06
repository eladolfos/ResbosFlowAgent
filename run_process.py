#!/usr/bin/env python3
"""
run_process.py -- copy a template ResBos-Legacy folder to a new place, put the
right energy / PDF / boson in every .in file, and chain the jobs with shards.

    python3 run_process.py Examples/pp_7TeV_WpWmZ0_CT25NLO.ini            # prepare <dest>, write <dest>/submit_all.sh
    python3 run_process.py Examples/pp_7TeV_WpWmZ0_CT25NLO.ini --submit   # ... and run it (on the HPCC login node)

The .ini names a SOURCE folder that holds get_yk_new/ legacy/ resbos/ w_asym/ w_pert/
(e.g. templates/7TeV_WpWm) and a DEST folder.  Only what a run needs is copied to
DEST: the executables (the fresh build in bin/ made by setup.sb, or the
ones named in [executables] in the .ini; never the old ones inside the source), the grids (./inp/*.inp) and make_dummy_rai.py.  The source
does NOT need the outputs of earlier steps: get_yk_new needs the w_pert / w_asym /
legacy outputs and resbos needs the legacy and Yk grids, so each of those jobs
brings its inputs next to itself (symlink or copy) when it starts, once the upstream
jobs have produced them.  Everything else in the source (outputs, logs, .git, old
.in files, old shard scripts) is left behind.

The .in files are the source's W+ files used as templates: the script rewrites ECM,
PDF, Type_V / JWTYPE and the active grid range; for resbos only what the .ini
overrides (cuts, seed, luminosity, ...) is changed.

Per boson:
    w_pert  ----------------\\
    w_asym  ------------------> get_yk_new --> Yk grid --\\
    legacy LTO=3 (Y piece) --/                            +--> resbos  (never sharded:
    legacy LTO=0 (main grid) -----------------------------/             it is a VEGAS MC)

w_pert, w_asym and legacy are split along Q with the scripts of scripts/
(make_shards.py, merge_shards.py, run_*_array.sb, merge_*_array.sb, submit_*_array.sh,
make_grid_from_data.py), copied into each folder with the executable name and the header
length of that code. [paths] scripts says where this folder is -- run_process.py itself is
the only file you need to copy elsewhere; point [paths] scripts (and [paths] source) back at
wherever scripts/ (and the source template) actually live.
"""
import argparse
import configparser
import hashlib
import math
import os
import re
import shutil
import subprocess
import sys
from types import SimpleNamespace

SELF = os.path.abspath(__file__)
HERE = os.path.dirname(SELF)
HDR_RE = re.compile(rb"\s*Q\s*,\s*qT\s*,\s*y")
PROCS = {                                            # Type_V -> (file tag, JWTYPE)
    "W+": ("Wp", 1),
    "W-": ("Wm", -1),
    "Z0": ("Z0", 2),                                 # w_pert/w_asym: JWTYPE=2 ("neutral current"); Legacy Type_V
    "A0": ("A0", 2),                                 # distinguishes Z0 (resonance) from A0 (pure photon) -- both
    "ZU": ("ZU", 2),                                 # full Z/gamma* + interference ('DY' in resbos_root.f), u-type
    "ZD": ("ZD", 2),                                 # / d-type initial quarks; sigma(Z/gamma*) = ZU + ZD.
}                                                     # use the SAME JWTYPE=2 in w_pert/w_asym (confirmed against
                                                      # a real working E605 w_pert.in in New_kFactorCT25/
                                                      # FixedTarget_pp830a016_yao_09182026/, NOT the naive
                                                      # DATA jwm,jwp,jz,jph,JHB /-1,1,2,3,4/ jph=3 reading).
                                                      # NOTE: get_yk_new.f only knows ZU/ZD/W+/W-/A0 (get_yk_new.f:
                                                      # 181-200) -- Z0 still STOPs ('convert is not assigned to
                                                      # this Boson yet!'); A0 works at NLO (its convert factor is
                                                      # provably unused there) but STOPs at NNLO (no real
                                                      # conversion constant implemented). Z0/NNLO-A0: known, not
                                                      # handled here.
# w_pert/w_asym JZ_TYPE for JWTYPE=2 (w_pert.f ~235): 1=ZU, -1=ZD, 0=Z0/A0 (general couplings).
# ZU/ZD keep only the u-/d-type couplings there, as Legacy (pert.for) and get_yk_new (Facu/Facd) do.
JZ_TYPE = {"ZU": "1", "ZD": "-1"}
# [campaign] processes also accepts "Zgamma" = ZU + ZD (the full Z/gamma*: sigma = ZU + ZD, one chain each; the analysis adds
# the two .root files itself, so no file is ever called Zgamma).
PROC_ALIASES = {"Zgamma": ("ZU", "ZD")}
# [campaign] w_grid = resbos2: the "Main data grid" of the resNLO (CSS function W) is computed by ResBos2 (XSec = Resummation)
# instead of Legacy's LTO=0 -- Legacy's own grid is exactly 0 for qT >= 2Q (res.for), which inflates W321/NLO at pT_ll >~ 2Q
# (docs/COLLIDER_RESBOS2_W_WORKFLOW.md). Legacy Type_V -> ResBos2 `Process`; Legacy iBeam -> ResBos2 `beam`.
W_GRIDS = ("legacy", "resbos2")
R2W_PROCESS = {"W+": "WPlus", "W-": "WMinus", "Z0": "Z0", "ZU": "ZU", "ZD": "ZD"}
R2W_BEAM = {"1": "pp", "-1": "ppb"}
R2W_HEADER_LINES = 15                      # header of a ResBos2 grid file and of a Legacy grid file
# Names of the files the analysis (KFactor_Raw_simulations: extract_tables.py) reads: {beam}_{TeV}_{PDF}_{PROCESS}_{CUTS}_{ORDER}.root
CONVENTION_BEAM = {"1": "pp", "-1": "ppbar"}
CONVENTIONS = ("analysis", "none")
# [physics]: masses, widths and EW inputs. Where each key lives (marker of the '> comment', token index) in the Legacy .in and in resbos.in,
# and the key of the ResBos2 config. A key set in the .ini is written to every place that has it; with w_grid = resbos2 the electroweak
# ones default to the ResBos2 config and the quark masses to the Legacy template, and are written to ALL the places (see resolve_physics).
PHYS_LEGACY = {"mt": ("t,W,Z,h", 0), "mw": ("t,W,Z,h", 1), "mz": ("t,W,Z,h", 2), "mh": ("t,W,Z,h", 3),
               "mu": ("Quark masses", 0), "md": ("Quark masses", 1), "ms": ("Quark masses", 2),
               "mc": ("Quark masses", 3), "mb": ("Quark masses", 4)}
PHYS_RESBOS = {"mt": ("Luminosity", 1), "mh": ("Luminosity", 2), "mw": ("W mass and width", 0), "gamw": ("W mass and width", 1),
               "mz": ("Z mass and width", 0), "gamz": ("Z mass and width", 1)}
PHYS_R2W = {"mt": "mT", "mw": "mW", "mz": "mZ", "mh": "mH", "gamw": "gamW", "gamz": "gamZ", "gamt": "gamT", "gamh": "gamH",
            "mu": "mu", "md": "md", "ms": "ms", "mc": "mc", "mb": "mb",
            "gf": "GF", "alpha_em0": "AlphaEM0", "alpha_em_mz": "AlphaEMMZ"}
PHYS_R2W_STR = {"ew_mass_scheme": "EWMassScheme"}
# ResBos2 hard-wires EWInputs = GFMWMZ (Electroweak.cc) and derives sin^2(theta_W) = 1 - mW^2/mZ^2: these config keys are never read
PHYS_UNUSED = {"sinw2": "ResBos2 does not read it (sin^2(theta_W) = 1 - mW^2/mZ^2 from the GFMWMZ inputs)",
               "ew_inputs": "ResBos2 hard-wires EWInputs = GFMWMZ (Electroweak.cc)"}
PHYS_QUARK = ("mt", "mu", "md", "ms", "mc", "mb")          # default: the Legacy template (with w_grid = resbos2)
PHYS_EW = ("mw", "mz", "mh", "gamw", "gamz")               # default: the ResBos2 config (with w_grid = resbos2)
PHYS_KEYS = tuple(PHYS_R2W) + tuple(PHYS_R2W_STR)
# stage: (folder, executable, label used in the shard scripts, header lines, lines/point)
# legacy_dsi (LTO=1, NLO_Sig/DeltaSigma) and legacy_asy (LTO=2, Asymptotic) are the two
# extra pieces [campaign] compute = NLO needs on top of legacy_Y (LTO=3, shared with
# resNLO) -- confirmed against legacy_final_vesion/main.for: the ~14-line preamble
# (ECM/IBEAM/PDF/masses/TYPE_V/g1-g3/... echo, written unconditionally before the LTO
# branch) plus one LTO-specific column-header line = 15 total header lines for every LTO
# value (matches the already-validated LTO=0/3 count), and both LTO=1 and LTO=2 write
# exactly one data line per (Q,qT,y) point (same shape as LTO=0/legacy_main, not LTO=3's
# 3-lines/point) -- WRITE(22,122)/WRITE(22,102) each called once per point, no inner loop
# writes multiple lines. Not yet run for real (no gfortran here); spot-check against a
# real LTO=1/LTO=2 output on the HPCC before trusting this at scale.
STAGES = {
    "w_pert":      ("w_pert", "w_pert", "w_pert", 3, 1),
    "w_asym":      ("w_asym", "w_asym", "w_asym", 3, 1),
    "legacy_Y":    ("legacy", "main", "legacy", 15, 3),
    "legacy_main": ("legacy", "main", "legacy", 15, 1),
    "legacy_dsi":  ("legacy", "main", "legacy", 15, 1),
    "legacy_asy":  ("legacy", "main", "legacy", 15, 1),
}
LTO_BY_STAGE = {"legacy_Y": "3", "legacy_main": "0", "legacy_dsi": "1", "legacy_asy": "2",
                "legacy_LO": "-1"}          # legacy_LO: [campaign] mode = fixedtarget only (build_fixedtarget())
LEGACY_SUFFIX = {"legacy_Y": "Y", "legacy_main": "main", "legacy_dsi": "dsi", "legacy_asy": "asy"}
RESNLO_STAGES = ("w_pert", "w_asym", "legacy_Y", "legacy_main")
NLO_STAGES = ("legacy_Y", "legacy_dsi", "legacy_asy")
CHUNK = 16 << 20
MODES = ("collider", "fixedtarget")
# [campaign] mode = fixedtarget datasets. targets: (suffix, Legacy iBeam, FRACT_N, name GetFixed knows the set by).
# The name selects beam and ECM inside GetFixed (FixedTarget.cc); ecm/iBeam/FRACT_N/jacobian as in Yao's own runs
# (FIXED_TARGET_WORKFLOW.md, section 0): E605 is Q^3 dsigma/dQ/dy (no Jacobian), the others are in xF (dy/dxF inside the
# integral); E866f / E906aF are ratios pd/2pp and need both targets (pd = Legacy iBeam=0, FRACT_N=0.5 = per-nucleon average).
FT_DATASETS = {
    "e605":     dict(ecm="38.8",  jac="none", qtmax=10.0, targets=(("", "0", "0.54d0", "e605"),)),
    "e866ppxf": dict(ecm="38.75", jac="mT",   qtmax=10.0, targets=(("", "1", "0.d0", "e866ppxf"),)),
    "e866f":    dict(ecm="38.76", jac="mT",   qtmax=10.0, targets=(("pp", "1", "0.d0", "e866f_pp"),
                                                                   ("pd", "0", "0.5d0", "e866f_pd"))),
    "e906aF":   dict(ecm="15.07", jac="mT",   qtmax=10.0, targets=(("pp", "1", "0.d0", "e906aF_pp"),
                                                                   ("pd", "0", "0.5d0", "e906aF_pd"))),
}


def die(msg):
    sys.exit("ERROR: " + msg)


# ------------------------------------------------------------------ .in editing
def find(lines, marker, what):
    """Index of the first line whose trailing '> comment' contains marker."""
    for i, l in enumerate(lines):
        if ">" in l and marker in l.split(">", 1)[1]:
            return i
    die(f"template for {what} has no line commented '> ...{marker}...'")


def put(lines, i, text):
    val, com = lines[i].rstrip("\n").split(">", 1)
    lines[i] = text.ljust(max(len(val), len(text) + 1)) + ">" + com + "\n"


def set_token(lines, i, k, new):
    """Replace the k-th comma-separated token of line i, keeping its spacing."""
    parts = lines[i].split(">", 1)[0].split(",")
    m = re.match(r"(\s*)(.*?)(\s*)$", parts[k])
    if m.group(2) == new:
        return
    parts[k] = m.group(1) + new + m.group(3)
    put(lines, i, ",".join(parts).rstrip())


def set_active(lines, act, full):
    for marker, want in (("Active setting", act), ("Full range", full)):
        i = find(lines, marker, marker)
        if [int(t) for t in lines[i].split(">", 1)[0].split()] != list(want):
            put(lines, i, "  ".join(str(a) for a in want))


def grid_paths(lines):
    return [lines[find(lines, m, m)].split(">", 1)[0].strip()
            for m in ("Q grid file name", "qT grid file name", "y grid file name")]


def max_safe_q_index(q_vals, ecm):
    """Largest 1-based index i with q_vals[i-1] <= ecm (0 if even q_vals[0] is already too
    high). q_vals must be ascending (true of every q_grid.inp in this repo).

    Q <= ECM is the limit legacy_final_vesion/pert.for's PERTURB imposes (see
    check_q_kinematics()). Q == ECM is accepted: the shard with Q=1800 at ECM=1800 finished clean."""
    safe = 0
    for i, q in enumerate(q_vals, start=1):
        if q <= ecm:
            safe = i
        else:
            break
    return safe


def check_q_kinematics(cfg, q_vals, act):
    """Catch a doomed multi-hour run before it starts, for every [energies] entry (active is
    shared across all of them -- see Cfg._parse_energies()). legacy_final_vesion/pert.for's
    PERTURB computes per point TM_V=sqrt(QT_V^2+Q_V^2), RTAUP=(TM_V+QT_V)/ECM,
    X1LOW=RTAUP*exp(Y_V), X2LOW=RTAUP/exp(Y_V), and does `CALL QUIT` (killing the whole shard)
    when BOTH exceed 1. That first happens at the smallest qT and y closest to 0, where
    RTAUP~=Q_V/ECM, so any active Q above ECM is kinematically impossible. Observed: Q-shards
    with Q<=ECM finished; shards with Q>ECM died with "ERROR IN PERTURB. x1Low, x2Low = ..."."""
    qmin_idx, qmax_idx, qstep = act[6], act[7], act[8]
    q_active_max = q_vals[qmax_idx - 1]
    bad, safe_idxs = [], []
    for energy in cfg.energies:
        ecm_f = float(energy.ecm)
        safe_idx = max_safe_q_index(q_vals, ecm_f)
        safe_idxs.append(safe_idx)
        if safe_idx == 0:
            bad.append(f"  {energy.name} (ecm={energy.ecm}): NO Q grid point is <= this energy -- "
                       f"the active Q range (up to index {qmax_idx}, Q={q_active_max}) is entirely "
                       f"out of kinematic reach; check [campaign]/[energies] ecm")
        elif qmax_idx > safe_idx:
            bad.append(f"  {energy.name} (ecm={energy.ecm}): active Q goes up to index {qmax_idx} "
                       f"(Q={q_active_max} GeV) but only up to index {safe_idx} (Q={q_vals[safe_idx - 1]} "
                       f"GeV) is <= this energy's ECM")
    if not bad:
        return
    safe_nonzero = [i for i in safe_idxs if i > 0]
    if safe_nonzero:
        shared_cap = min(safe_nonzero)
        fix = (f"lower [grids] active's Q_max index (last-but-one of the 9 numbers) to "
               f"{shared_cap} or less -- e.g.:\n"
               f"       active = {act[0]} {act[1]} {act[2]}  {act[3]} {act[4]} {act[5]}  "
               f"{qmin_idx} {shared_cap} {qstep}\n"
               f"       (that's the cap set by the LOWEST energy below; a HIGHER energy could "
               f"safely use a larger index -- give it its own .ini with its own [grids] active)")
    else:
        fix = ("no Q index is safe for every energy here -- split [energies] into separate "
               ".ini files, one per energy, each with its own [grids] active")
    die("[grids] active includes Q points above (at least) one [energies]/[campaign] ecm -- "
        "legacy_final_vesion/pert.for's PERTURB will CALL QUIT partway through a shard (parton "
        "x=Q/ECM>1 is kinematically impossible), after burning hours of w_pert/w_asym/legacy "
        "compute on the shards before it:\n" + "\n".join(bad) + "\n       fix: " + fix)


def check_q_kinematics_points(cfg, points, qt_min):
    """Same CALL QUIT failure mode as check_q_kinematics(), for [grids] experimental mode's
    per-point (y, Q) table: each point has its own fixed y, checked at the mode's shared qt_min
    (every point runs across the same qT grid -- see build_points()). Checked for every
    [energies] entry."""
    bad = []
    for energy in cfg.energies:
        ecm_f = float(energy.ecm)
        worst = []
        for y_s, q_s in points:
            y, q = float(y_s), float(q_s)
            tm_v = math.sqrt(qt_min ** 2 + q ** 2)
            rtaup = (tm_v + qt_min) / ecm_f
            if rtaup * math.exp(y) > 1.0 and rtaup / math.exp(y) > 1.0:
                worst.append((q, y))
        if worst:
            worst.sort()
            bad.append(f"  {energy.name} (ecm={energy.ecm}): {len(worst)}/{len(points)} "
                       f"experimental points are kinematically impossible at this energy, e.g. "
                       f"Q={worst[-1][0]}, y={worst[-1][1]}")
    if not bad:
        return
    die("[grids] experimental's data table includes (Q,y) points above (at least) one "
        "[energies]/[campaign] ecm -- legacy_final_vesion/pert.for's PERTURB will CALL QUIT "
        "partway through that point's job (parton x>1 is kinematically impossible), after "
        "burning compute on the points before it:\n" + "\n".join(bad) + "\n"
        "       fix: drop those rows from the experimental data table (or fix [energies]/ecm)")


def patch_stage(cfg, tlines, stage, tag, jw, vtype, ecm):
    """Apply the ECM/PDF/boson/[legacy] overrides common to a normal grid campaign
    (build()) and a per-experimental-point campaign (build_points()); caller still
    has to set_active() (build()) or write single-point grid files (build_points())."""
    lines = list(tlines[stage])
    if stage in ("w_pert", "w_asym"):
        ecm_line = find(lines, "ECM,iBeam", "ECM")
        set_token(lines, ecm_line, 0, ecm)
        ibeam = cfg.get("legacy", "ibeam")
        if ibeam:
            ibeam = check_ibeam(ibeam)
            if ibeam in ("1", "-1"):
                set_token(lines, ecm_line, 1, ibeam)
            # else (0=pN, -2=PiN): w_pert.f/w_asym.f's own "ECM,iBeam=-1,1:ppB/pp" only
            # supports pp/ppbar -- there is no genuine nuclear/pion-target mode there, so for
            # a fixed-target campaign (the established E605 approach) their iBeam stays at
            # whatever [templates] w_pert/w_asym already have (normally 1/pp: the nuclear
            # target's physics lives entirely in Legacy's iBeam+FRACT_N, and w_pert/w_asym
            # always compute the plain-pp partonic piece per nucleon).
        pert_ibeam = cfg.get("legacy", "pert_ibeam")
        if pert_ibeam:
            # Explicit override of w_pert/w_asym's own iBeam, for targets whose PDFs PdfH does
            # provide (Ihadron 2=D, 3=Cu): Yao's own w_pert.in use 2 for the E866/E906 pd runs
            # (and 3 for E605) while Legacy gets iBeam=0+FRACT_N=0.5. Wins over `ibeam` above.
            pert_ibeam = pert_ibeam.strip()
            if pert_ibeam not in PERT_IBEAM_VALUES:
                die(f"[legacy] pert_ibeam = '{pert_ibeam}' not recognized -- must be one of "
                    f"{', '.join(f'{k} ({v})' for k, v in PERT_IBEAM_VALUES.items())}")
            set_token(lines, ecm_line, 1, pert_ibeam)
        jwtype_line = find(lines, "JWTYPE", "JWTYPE")
        set_token(lines, jwtype_line, 0, str(jw))
        if jw == 2:
            # JWTYPE=2 (jz): w_pert.f/w_asym.f pick BOSON from JZ_TYPE (1=ZU,-1=ZD,0=Z0/general
            # couplings), a DIFFERENT token the W+/W- template this was copied from leaves at 1
            # (ZU) -- confirmed against a real working w_pert.in (New_kFactorCT25/
            # FixedTarget_pp830a016_yao_09182026/Workspace/FixedTargetKFactor/e605/w_pert.in:
            # "2,0,0") that it must be reset to 0 for both our Z0 and A0 (Legacy's Type_V is what
            # actually distinguishes them there), or w_pert/w_asym silently compute wrong (ZU)
            # physics instead. w_pert: JWTYPE,IDO_CBAR,JZ_TYPE; w_asym: JWTYPE,JZ_TYPE.
            # ZU/ZD set it to 1/-1 (JZ_TYPE above).
            set_token(lines, jwtype_line, 2 if stage == "w_pert" else 1, JZ_TYPE.get(vtype, "0"))
        put(lines, find(lines, "PDF file name", "PDF"), "lha_" + cfg.pdf)
    else:
        l2 = find(lines, "ECM,LTO", "ECM,LTO")
        set_token(lines, l2, 0, ecm if "." in ecm else ecm + ".0")
        set_token(lines, l2, 1, LTO_BY_STAGE[stage])
        if stage == "legacy_dsi":
            # res.for's SetC1_4: LTO=1 (DeltaSigma) hard-STOPs in main.for ("THIS ONLY WORKS
            # FOR IFLAG_C3 = 1") unless the scale choice is the canonical one (IFLAG_C3=1).
            # IFLAG_C3=99 (custom C1/B0,C2,C3/B0) is only safe to auto-convert when its values
            # are numerically identical to canonical (C1/B0=C2=C3/B0=1 -> C1=B0,C2=1,C3=B0,C4=1
            # either way) -- otherwise forcing IFLAG_C3=1 would silently give legacy_dsi a
            # different renormalization/factorization scale than legacy_asy/legacy_Y use,
            # breaking the qT_Sep cancellation between them (see README.md's NLO section).
            l3 = find(lines, "IFLAG_C3", "IFLAG_C3")
            toks = [t.strip() for t in lines[l3].split(">", 1)[0].split(",")]
            iflag_c3, c_vals = toks[1], toks[2:5]
            if iflag_c3 != "1":
                same_as_canonical = iflag_c3 == "99" and all(
                    float(t.lower().replace("d", "e")) == 1.0 for t in c_vals)
                if same_as_canonical:
                    set_token(lines, l3, 1, "1")
                else:
                    die(f"legacy_dsi (LTO=1) needs IFLAG_C3=1 (Legacy's res.for STOPs otherwise: "
                        f"'THIS ONLY WORKS FOR IFLAG_C3 = 1'), but the legacy_dsi template has "
                        f"IFLAG_C3={iflag_c3} with C1/B0,C2,C3/B0={','.join(c_vals)}, not "
                        f"numerically identical to canonical (C1/B0=C2=C3/B0=1) -- auto-forcing it "
                        f"would silently run DeltaSigma at a different scale than legacy_asy/"
                        f"legacy_Y, breaking the qT_Sep cancellation between them. Point "
                        f"[templates] legacy_dsi at a template using IFLAG_C3=1 (or IFLAG_C3=99 "
                        f"with C1/B0=C2=C3/B0=1), or drop 'NLO' from [campaign] compute.")
        put(lines, find(lines, "Type_V", "Type_V"), vtype)
        put(lines, find(lines, "Evolved PDF file", "PDF"), "lha_" + cfg.pdf)
        for k, (marker, tok) in PHYS_LEGACY.items():
            if k in cfg.phys:
                set_token(lines, find(lines, marker, marker), tok, f"{cfg.phys[k]:.10g}")
        if cfg.get("legacy", "bmax"):
            put(lines, find(lines, "bMax", "bMax"), cfg.get("legacy", "bmax"))
        if cfg.get("legacy", "nonpert"):
            put(lines, find(lines, "g1, g2, g3, Q0, nG", "nonpert"), cfg.get("legacy", "nonpert"))
        if cfg.get("legacy", "ibeam"):
            set_token(lines, find(lines, "FRACT_N", "ibeam/fract_n"), 0,
                      check_ibeam(cfg.get("legacy", "ibeam")))
        if cfg.get("legacy", "fract_n"):
            set_token(lines, find(lines, "FRACT_N", "ibeam/fract_n"), 1, cfg.get("legacy", "fract_n"))
    return lines


def read_points(path, y_col, q_col):
    """Parse an experimental data table (whitespace-separated, blank/'#' lines skipped)
    into a list of (y, Q) string pairs, 1-based y_col/q_col -- same convention as Yao's
    run.sh scripts (awk '{print $1}'=y, '{print $2}'=Q) in New_kFactorCT25/
    FixedTarget_pp830a016_yao_09182026/Workspace/*/e605(etc.)/run.sh."""
    if not os.path.isfile(path):
        die(f"[grids] experimental: {path} not found")
    pts = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            need = max(y_col, q_col)
            if len(parts) < need:
                die(f"{path}: line has fewer than {need} columns: {line!r}")
            pts.append((parts[y_col - 1], parts[q_col - 1]))
    if not pts:
        die(f"{path}: no data rows found")
    return pts


def read_lines(path):
    if not os.path.isfile(path):
        die(f"missing template {path}")
    with open(path) as f:
        return f.readlines()


# ------------------------------------------------------------------ [scheduler]
# Opt-in. Without a [scheduler] section every script is written exactly as generated (partition general-long, no account).
# With it, write() rewrites the #SBATCH header of every generated script: partition, account, qos, constraint, extra
# options, and a cap on --time. Nothing else in the scripts changes.
SCHEDULER = None
SCHEDULER_KEYS = ("partition", "account", "qos", "constraint", "extra", "max_time")


def walltime_seconds(t):
    """SLURM time formats: M, M:S, H:M:S, D-H, D-H:M, D-H:M:S."""
    days = 0
    if "-" in t:
        d, t = t.split("-", 1)
        days = int(d)
        parts = [int(x) for x in t.split(":")]
        parts += [0] * (3 - len(parts))
        return days * 86400 + parts[0] * 3600 + parts[1] * 60 + parts[2]
    parts = [int(x) for x in t.split(":")]
    if len(parts) == 1:
        return parts[0] * 60
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def init_scheduler(cfg):
    global SCHEDULER
    if not cfg.cp.has_section("scheduler"):
        return
    bad = [k for k, _ in cfg.cp.items("scheduler") if k not in SCHEDULER_KEYS]
    if bad:
        die(f"[scheduler] unknown key(s) {', '.join(bad)}; valid: {', '.join(SCHEDULER_KEYS)}")
    g = lambda k: cfg.cp.get("scheduler", k).strip() if cfg.cp.has_option("scheduler", k) else None
    extra = [x.strip() for x in (g("extra") or "").split(";") if x.strip()]
    for x in extra:
        if not x.startswith("--"):
            die(f"[scheduler] extra: '{x}' is not an sbatch option (use '--name=value', separated by ';')")
    max_time = g("max_time")
    if max_time:
        try:
            walltime_seconds(max_time)
        except ValueError:
            die(f"[scheduler] max_time = '{max_time}' is not a SLURM time (M, M:S, H:M:S, D-H, D-H:M, D-H:M:S)")
    SCHEDULER = SimpleNamespace(partition=g("partition"), account=g("account"), qos=g("qos"), constraint=g("constraint"),
                                extra=extra, max_time=max_time, capped=[], touched=0)


def apply_scheduler(text):
    s = SCHEDULER
    if s is None or "#SBATCH" not in text:
        return text
    s.touched += 1
    lines, last = text.split("\n"), -1
    out = []
    for line in lines:
        m = re.match(r"(#SBATCH\s+--partition=)(\S*)(.*)$", line)
        if m and s.partition is not None:
            if s.partition == "":
                continue                      # empty partition = the site's default one
            line = f"{m.group(1)}{s.partition}{m.group(3)}"
        m = re.match(r"(#SBATCH\s+--time=)(\S+)(.*)$", line)
        if m and s.max_time and walltime_seconds(m.group(2)) > walltime_seconds(s.max_time):
            s.capped.append(m.group(2))
            line = f"{m.group(1)}{s.max_time}{m.group(3)}"
        out.append(line)
        if line.startswith("#SBATCH"):
            last = len(out) - 1
    add = [f"--{k}={v}" for k, v in (("account", s.account), ("qos", s.qos), ("constraint", s.constraint)) if v] + s.extra
    if add and last >= 0:
        out[last + 1:last + 1] = [f"#SBATCH {a}" for a in add]
    return "\n".join(out)


def report_scheduler():
    s = SCHEDULER
    if s is None:
        return
    print(f"[scheduler] applied to {s.touched} generated script(s): partition={'<site default>' if s.partition == '' else (s.partition or 'general-long (driver default)')}"
          f", account={s.account or '-'}, qos={s.qos or '-'}, constraint={s.constraint or '-'}, extra={'; '.join(s.extra) or '-'}")
    if s.capped:
        longest = max(s.capped, key=walltime_seconds)
        print(f"[scheduler] WARNING: {len(s.capped)} --time line(s) were longer than max_time = {s.max_time} and were capped "
              f"(longest original: {longest}). A shard may now hit the walltime: raise [shards] so each task is shorter.")


def write(path, text, exe=False):
    text = apply_scheduler(text)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    if exe:
        os.chmod(path, 0o755)


def copy(src, dst, exe=False):
    if not os.path.isfile(src):
        die(f"missing {src}")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(src, dst)
    os.chmod(dst, 0o755 if exe else 0o644)


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(CHUNK), b""):
            h.update(b)
    return h.hexdigest()


def check_jobname(job, multi_energy=False):
    name = f"{job}_shards/{job}_shard00"      # Fortran job names are character*100
    if len(name) > 95:
        where = "[energies] prefix" if multi_energy else "[campaign] name"
        die(f"'{name}' is {len(name)} chars; the codes truncate at 100. Shorten {where}")


def bash_token(s):
    """Sanitize an [energies] prefix into a valid bash identifier fragment, for the
    M_*/YK_*/ASY_*/DSI_* dependency-tracking variable names in submit_all.sh (see build())."""
    return re.sub(r"[^A-Za-z0-9]", "_", s.upper())


# w_pert.f/w_asym.f hand iBeam straight to PdfH as Ihadron (pert.f rejects |iBeam|>3)
PERT_IBEAM_VALUES = {"-1": "pbar", "1": "p", "2": "D", "3": "Cu"}
IBEAM_VALUES = {"-2": "PiN", "-1": "ppB (ppbar)", "0": "pN", "1": "pp"}


def check_ibeam(ibeam):
    ibeam = ibeam.strip()
    if ibeam not in IBEAM_VALUES:
        die(f"[legacy] ibeam = '{ibeam}' not recognized -- must be one of "
            f"{', '.join(f'{k} ({v})' for k, v in IBEAM_VALUES.items())}")
    return ibeam


# ------------------------------------------------------------------ config
class Cfg:
    def __init__(self, path):
        cp = configparser.ConfigParser(inline_comment_prefixes=("#",), interpolation=None)
        cp.optionxform = str
        if not cp.read(path):
            die(f"cannot read {path}")
        self.cp, self.path = cp, os.path.abspath(path)
        base = os.path.dirname(self.path)
        self.rel = lambda p: os.path.abspath(os.path.join(base, os.path.expanduser(p)))
        # [campaign] mode: collider (default; rectangular (Q,qT,y) grid, Legacy-family chain) or
        # fixedtarget (one job per measured (y,Q) point: Legacy LO/NLO + ResBos2 W321). A [fixedtarget]
        # section without mode = fixedtarget is refused, so a campaign never silently runs the wrong chain.
        self.mode = self.get("campaign", "mode", "collider").strip().lower()
        if self.mode not in MODES:
            die(f"[campaign] mode = '{self.mode}' not recognized (use {' or '.join(MODES)})")
        if self.mode == "collider" and self.cp.has_section("fixedtarget"):
            die("this .ini has a [fixedtarget] section but [campaign] mode is not 'fixedtarget': "
                "add  mode = fixedtarget  to [campaign] (or remove [fixedtarget] for a collider campaign)")
        if self.mode == "fixedtarget":
            src = self.get("paths", "source")
            self.src = self.rel(src) if src and src.strip() else os.path.join(HERE, "templates", "FixedTarget")
        else:
            self.src = self.rel(self.req("paths", "source"))
        self.dest = self.rel(self.req("paths", "dest"))
        self.scripts = self.rel(self.get("paths", "scripts", os.path.join(HERE, "scripts")))
        self.stage = self.get("paths", "stage_outputs", "link")      # how a job receives upstream outputs
        if self.stage not in ("link", "copy"):
            die("[paths] stage_outputs must be 'link' or 'copy'")
        self.experimental, self.gen_grid, self.exp_throttle = None, False, None
        self.w_grid, self.use_r2w, self.r2w = "legacy", False, None
        self.skip_wpa = False                                 # [get_yk_new] skip_pert_asym (collider)
        self.phys_sync = True                                 # [physics] sync = no: every template keeps its own values (Yao's templates)
        self.phys_ini, self.phys, self.phys_src = {}, {}, {}   # [physics] as given; values applied (resolve_physics); where each came from
        self.conv = "none"                                    # file names for the analysis: only collider campaigns (below)
        if self.mode == "fixedtarget":
            self._init_fixedtarget()
            return
        # [energies]: run the SAME campaign (processes/pdf/order/templates/grids/shards/
        # [legacy]/[resbos] all shared) at several collider energies from one .ini, each with
        # its own file prefix so outputs never collide -- see _parse_energies(). Absent: single
        # energy from [campaign] name/ecm, unchanged behaviour (self.energies has one entry).
        self.energies = self._parse_energies()
        self.name, self.ecm = self.energies[0].name, self.energies[0].ecm
        self.pdf = self.req("campaign", "pdf")
        self.order = self.req("campaign", "order").upper()
        if self.order not in ("NLO", "NNLO"):
            die("[campaign] order must be NLO or NNLO")
        self.procs = []
        for p in (x.strip() for x in self.req("campaign", "processes").split(",") if x.strip()):
            for q in PROC_ALIASES.get(p, (p,)):
                if q not in PROCS:
                    die(f"process '{p}' not supported yet (supported: {', '.join(list(PROCS) + list(PROC_ALIASES))})")
                if q not in self.procs:
                    self.procs.append(q)
        # [campaign] compute: resNLO (default, unchanged behaviour), NLO (fixed order via
        # Legacy LTO=1+LTO=2+LTO=3 phase-space slicing + two resbos runs + hadd -- see
        # README.md "NLO (fixed order)"), or "NLO, resNLO" for both in one campaign (legacy_Y,
        # LTO=3, is computed once and shared between them).
        norm = {"nlo": "NLO", "resnlo": "resNLO"}
        self.compute = set()
        for c in self.get("campaign", "compute", "resNLO").split(","):
            c = c.strip()
            if not c:
                continue
            key = norm.get(c.lower())
            if not key:
                die(f"[campaign] compute: '{c}' not recognized (use NLO, resNLO, or 'NLO, resNLO')")
            self.compute.add(key)
        if not self.compute:
            die("[campaign] compute: at least one of NLO, resNLO required")
        # [grids] experimental: "ExpCustomGrid" mode -- one job per (y,Q) row of a real
        # experimental data table (like Yao's run.sh), instead of one shared rectangular
        # grid. Only worth it when the table's unique-Q x unique-y product is close to its
        # row count (e.g. E605: 119 points, 18x7=126); otherwise a normal template grid
        # (this key unset) or a grid built with make_grid_from_data.py fits better -- see
        # that script's docstring and E201_e605_full.ini vs the run.sh-loop experiments
        # (e866f/e906aF/e866ppxf) discussed when this feature was added.
        self.experimental = self.get("grids", "experimental")
        if self.experimental:
            self.experimental = self.rel(self.experimental)
        self.exp_y_col = int(self.get("grids", "exp_y_col", "1"))
        self.exp_q_col = int(self.get("grids", "exp_q_col", "2"))
        self.exp_throttle = self.get("grids", "throttle")   # e.g. "20" -> SLURM --array=1-N%20

        # [grids] generate: build a fine, dense Q x y rectangle (make_grid_from_data.py's
        # "generate" mode, called in-process) into the template's own legacy/w_pert/w_asym
        # inp/ before the normal build() runs -- so [templates] doesn't need a pre-baked
        # grid checked in. Mutually exclusive with [grids] experimental (that mode doesn't
        # use a shared rectangular grid at all).
        self.gen_grid = self.get("grids", "generate", "").strip().lower() in ("yes", "true", "1")
        if self.gen_grid:
            if self.experimental:
                die("[grids] generate and [grids] experimental are mutually exclusive")
            self.gen_n_q = int(self.req("grids", "n_q"))
            self.gen_n_y = int(self.req("grids", "n_y"))
            self.gen_q_min = self.get("grids", "q_min")
            self.gen_q_max = self.get("grids", "q_max")
            self.gen_q_from = self.get("grids", "q_from")
            if self.gen_q_from:
                self.gen_q_from = self.rel(self.gen_q_from)
            self.gen_q_col = int(self.get("grids", "q_col", "2"))
            self.gen_q_spacing = self.get("grids", "q_spacing", "linear")
            self.gen_y_min = self.get("grids", "y_min")
            self.gen_y_max = self.get("grids", "y_max")
            self.gen_y_from = self.get("grids", "y_from")
            if self.gen_y_from:
                self.gen_y_from = self.rel(self.gen_y_from)
            self.gen_y_col = int(self.get("grids", "y_col", "1"))
            self.gen_y_spacing = self.get("grids", "y_spacing", "linear")

        # Validate and set defaults for [resbos] section if it exists
        self._ensure_resbos_defaults()
        self._init_w_grid()
        self._init_physics()
        self._init_skip_wpa()
        self._init_convention()

    def _init_fixedtarget(self):
        """[campaign] mode = fixedtarget: one dataset of FT_DATASETS, one job per measured point.
        Everything collider-specific ([energies], [grids] experimental/generate, order, processes) is refused
        or ignored here so the two chains can never be mixed up."""
        from types import SimpleNamespace
        for sec, why in (("energies", "ECM is fixed by the dataset"),):
            if self.cp.has_section(sec):
                die(f"[{sec}] is not used in mode = fixedtarget ({why})")
        if self.get("grids", "experimental") or self.get("grids", "generate"):
            die("[grids] experimental/generate belong to mode = collider; fixedtarget builds its own per-point "
                "grids from [fixedtarget] dataset/table")
        if self.cp.has_section("physics"):
            die("[physics] belongs to mode = collider; fixedtarget takes its inputs from the GetFixed/Legacy templates")
        ignored = [sec for sec in ("shards", "get_yk_new", "resbos", "templates") if self.cp.has_section(sec)]
        if ignored:
            print("note: mode = fixedtarget ignores section(s) " + ", ".join(f"[{x}]" for x in ignored))
        ds = self.req("fixedtarget", "dataset")
        if ds not in FT_DATASETS:
            die(f"[fixedtarget] dataset = '{ds}' not recognized (use {', '.join(FT_DATASETS)})")
        d = FT_DATASETS[ds]
        self.ft = SimpleNamespace(dataset=ds, spec=d)
        self.name = self.req("campaign", "name")
        self.pdf = self.req("campaign", "pdf")
        self.procs = ["A0"]
        self.order = "NLO"
        self.ecm = self.get("campaign", "ecm", d["ecm"]).strip()
        float(self.ecm)
        self.energies = [SimpleNamespace(label=None, ecm=self.ecm, name=self.name)]
        norm = {"lo": "LO", "nlo": "NLO", "resnlo": "resNLO"}
        self.compute = set()
        for c in self.get("campaign", "compute", "LO, NLO, resNLO").split(","):
            c = c.strip()
            if c:
                if c.lower() not in norm:
                    die(f"[campaign] compute: '{c}' not recognized in mode = fixedtarget (use LO, NLO, resNLO)")
                self.compute.add(norm[c.lower()])
        if not self.compute:
            die("[campaign] compute: at least one of LO, NLO, resNLO required")
        f = lambda k, dflt=None: self.get("fixedtarget", k, dflt)
        tbl = f("table")
        self.ft.table = self.rel(tbl) if tbl else os.path.join(HERE, "templates", "FixTargetTables", ds)
        self.ft.legacy_tpl = f("legacy_template", "legacy/fixedtarget_legacy.in").strip()
        self.ft.config_tpl = f("resbos2_config", "resbos2/fixedtarget.config").strip()
        want = [t.strip() for t in f("targets", ",".join(t[0] or "-" for t in d["targets"])).split(",") if t.strip()]
        self.ft.targets = []
        for t in d["targets"]:
            if (t[0] or "-") in want:
                self.ft.targets.append(t)
        if len(self.ft.targets) != len(want):
            die(f"[fixedtarget] targets = {', '.join(want)}: {ds} has only {', '.join(t[0] or '-' for t in d['targets'])}")
        self.ft.jac = f("jacobian", d["jac"]).strip()
        if self.ft.jac not in ("none", "mT"):
            die("[fixedtarget] jacobian must be none or mT")
        for k in ("qtsep", "qtmax"):
            if f(k):
                die(f"[fixedtarget] {k} is fixed by Yao's getnlo macro (qT_sep = 0.01, qT_max = 10, 1000 points in ln qT) and cannot be changed from the .ini")
        self.ft.throttle = f("throttle", "50")
        self.ft.getfixed = self.rel(f("getfixed")) if f("getfixed") else os.path.join(HERE, "bin", "resbos2", "bin", "GetFixed")
        self.ft.env = self.rel(f("resbos2_env")) if f("resbos2_env") else os.path.join(HERE, "bin", "resbos2", "env_getfixed.sh")
        self.ft.convgrids = self.rel(f("convgrids")) if f("convgrids") else None
        self.ft.lhapdf_data_path = f("lhapdf_data_path", "").strip()
        self.ft.final_modules = f("final_modules", "").strip()
        self.ft.conda_env = f("conda_env", "").strip()
        self.ft.conda_module = f("conda_module", "Miniforge3/25.11.0-1").strip()

    def _init_w_grid(self):
        """[campaign] w_grid = legacy (default) | resbos2, and [resbos2_w] (read only for resbos2)."""
        from types import SimpleNamespace
        self.w_grid = self.get("campaign", "w_grid", "legacy").strip().lower()
        if self.w_grid not in W_GRIDS:
            die(f"[campaign] w_grid = '{self.w_grid}' not recognized (use {' or '.join(W_GRIDS)})")
        if self.w_grid == "legacy":
            if self.cp.has_section("resbos2_w"):
                print("note: [resbos2_w] is ignored because [campaign] w_grid is not resbos2")
            return
        if "resNLO" not in self.compute:
            print("note: [campaign] w_grid = resbos2 only changes the resNLO; compute has no resNLO, so it is ignored")
            return
        if self.experimental:
            die("[campaign] w_grid = resbos2 does not apply in [grids] experimental mode")
        for p in self.procs:
            if p not in R2W_PROCESS:
                die(f"[campaign] w_grid = resbos2 supports {', '.join(R2W_PROCESS)} (and Zgamma = ZU, ZD); '{p}' has no ResBos2 W grid")
        ib = (self.get("legacy", "ibeam") or "").strip()
        if ib not in R2W_BEAM:
            die("[campaign] w_grid = resbos2 needs [legacy] ibeam = 1 (pp) or -1 (ppbar)")
        g = lambda k, d=None: self.get("resbos2_w", k, d)
        path = lambda k, dflt: self.rel(g(k)) if g(k) and g(k).strip() else dflt
        qtmax = (g("qtmax", "auto") or "auto").strip().lower()
        settings = (g("settings", "derive") or "derive").strip().lower()
        if settings not in ("derive", "template"):
            die("[resbos2_w] settings must be derive (CSS settings read from the Legacy .in, BLNY only) or template (the ResBos2 config as it is)")
        ymax_raw = (g("ymax") or "").strip()
        ymax = float(ymax_raw) if ymax_raw else (None if settings == "template" else 6.0)
        self.use_r2w = True
        self.r2w = SimpleNamespace(
            resbos=path("resbos", os.path.join(HERE, "bin", "resbos2", "bin", "resbos")),
            env=path("env", os.path.join(HERE, "bin", "resbos2", "env_getfixed.sh")),
            config=path("config", os.path.join(HERE, "templates", "ResBos2W", "resbos_w.config")),
            qtmax=None if qtmax == "auto" else float(qtmax), settings=settings,
            ymax=ymax, margin=int(g("margin", "2")), threads=int(g("threads", "4")),
            time=g("time", "02:00:00").strip(), mem=g("mem", "8G").strip(),
            partition=g("partition", "general-long").strip(), throttle=(g("throttle", "") or "").strip())
        if self.r2w.margin < 0 or self.r2w.threads < 1 or (self.r2w.ymax is not None and self.r2w.ymax <= 0):
            die("[resbos2_w] margin >= 0, threads >= 1 and ymax > 0 are required")

    def _init_skip_wpa(self):
        """[get_yk_new] skip_pert_asym = yes: do not run w_pert and w_asym; get_yk_new gets placeholder files with the points of the
        Legacy Y piece. get_yk_new only checks their grid at order = NLO (their values are used at NNLO only), so the Yk is the same."""
        v = (self.get("get_yk_new", "skip_pert_asym", "no") or "no").split("#", 1)[0].strip().lower()
        if v not in ("yes", "no", "true", "false", "1", "0"):
            die(f"[get_yk_new] skip_pert_asym = '{v}' must be yes or no")
        self.skip_wpa = v in ("yes", "true", "1")
        if not self.skip_wpa:
            return
        if self.order != "NLO":
            die("[get_yk_new] skip_pert_asym = yes needs [campaign] order = NLO: at NNLO get_yk_new uses the w_pert/w_asym values")
        if "resNLO" not in self.compute:
            print("note: [get_yk_new] skip_pert_asym has no effect: compute has no resNLO (w_pert/w_asym are only run for the resNLO)")
            self.skip_wpa = False

    def _init_physics(self):
        """[physics]: values of masses, widths and EW inputs that override the templates (see PHYS_* and resolve_physics)."""
        if not self.cp.has_section("physics"):
            return
        for k, v in self.cp.items("physics"):
            if k == "sync":
                sv = v.split("#", 1)[0].strip().lower()
                if sv not in ("yes", "no", "true", "false", "1", "0"):
                    die(f"[physics] sync = '{sv}' must be yes or no")
                self.phys_sync = sv in ("yes", "true", "1")
                continue
            if k in PHYS_UNUSED:
                die(f"[physics] {k}: {PHYS_UNUSED[k]}")
            if k not in PHYS_KEYS:
                die(f"[physics] {k}: not recognized (use {', '.join(PHYS_KEYS)})")
            v = v.split("#", 1)[0].strip()
            if not v:
                continue
            if k in PHYS_R2W_STR:
                self.phys_ini[k] = v
            else:
                try:
                    self.phys_ini[k] = fnum(v)
                except ValueError:
                    die(f"[physics] {k} = '{v}' is not a number")
        for k in ("mw", "mz", "mt", "mh"):
            if k in self.phys_ini and self.phys_ini[k] <= 0:
                die(f"[physics] {k} must be > 0")

    def _init_convention(self):
        """[output] convention: analysis (default) also gives every final .root the file name that
        KFactor_Raw_simulations/extract_tables.py reads (hard link in dest/for_analysis/<generator>/); none = campaign names only."""
        self.conv = self.get("output", "convention", "analysis").strip().lower()
        if self.conv not in CONVENTIONS:
            die(f"[output] convention = '{self.conv}' not recognized (use {' or '.join(CONVENTIONS)})")
        if self.conv == "analysis" and (self.get("legacy", "ibeam") or "").strip() not in CONVENTION_BEAM:
            print("note: [output] convention = analysis names exist for pp and ppbar only (set [legacy] ibeam = 1 or -1); "
                  "no analysis file names will be made")
            self.conv = "none"

    def _ensure_resbos_defaults(self):
        """Ensure [resbos] vegas parameter has sensible default to avoid ambiguity."""
        if not self.cp.has_section("resbos"):
            return  # No resbos section, nothing to validate

        if not self.cp.has_option("resbos", "vegas"):
            # Vegas not specified: set production default (31.5M events)
            # iGen=1, ITMX1=30, NCALL1=30000, ITMX2=300, NCALL2=100000
            # Total = 30*30000 + 300*100000 = 900K + 30M = 30.9M events
            default_vegas = "1,30,30000,300,100000"
            print(f"INFO: [resbos] vegas not specified in {os.path.basename(self.path)}")
            print(f"      Using production default: {default_vegas} (~31.5M events)")
            print(f"      To override, add to [resbos]: vegas = <iGen>,<ITMX1>,<NCALL1>,<ITMX2>,<NCALL2>")
            self.cp.set("resbos", "vegas", default_vegas)

    def _parse_energies(self):
        """[energies]: '<label> = <ecm_GeV>, <file_prefix>' per line, one per energy to run
        this campaign at (same [paths]/[templates]/[grids]/[shards]/[legacy]/[resbos] for all of
        them). Requires [campaign] name/ecm to be absent -- each energy supplies its own. Falls
        back to a single energy from [campaign] name/ecm when the section is absent (unchanged
        single-energy behaviour, self.energies has exactly one entry)."""
        from types import SimpleNamespace
        if not self.cp.has_section("energies"):
            ecm = self.req("campaign", "ecm")
            float(ecm)
            return [SimpleNamespace(label=None, ecm=ecm, name=self.req("campaign", "name"))]
        if self.cp.has_option("campaign", "ecm") or self.cp.has_option("campaign", "name"):
            die("[energies] is set -- remove [campaign] ecm/name (each energy supplies its own "
                "ecm and file prefix as '<label> = <ecm_GeV>, <file_prefix>' under [energies])")
        energies, seen = [], set()
        for label, value in self.cp.items("energies"):
            parts = [p.strip() for p in value.split(",")]
            if len(parts) != 2 or not parts[0] or not parts[1]:
                die(f"[energies] {label} = {value!r}: expected '<ecm_GeV>, <file_prefix>'")
            ecm, name = parts
            try:
                float(ecm)
            except ValueError:
                die(f"[energies] {label}: '{ecm}' is not a number (GeV)")
            if name in seen:
                die(f"[energies]: prefix '{name}' is used by more than one energy -- "
                    f"prefixes must be unique so their outputs don't collide in [paths] dest")
            seen.add(name)
            energies.append(SimpleNamespace(label=label, ecm=ecm, name=name))
        if not energies:
            die("[energies] section is present but empty")
        return energies

    def get(self, sec, key, default=None):
        return self.cp.get(sec, key, fallback=default)

    def req(self, sec, key):
        v = self.get(sec, key)
        if v is None or not v.strip():
            die(f"missing [{sec}] {key}")
        return v.strip()

    def exe_src(self, folder, exe):
        """Executable to copy for <folder>: [executables] <folder> = file; else <dir>/<folder>/<exe> with
        [executables] dir (default: bin/ next to this script, where setup.sb puts the fresh build).
        The executables stored in the source template are never used unless dir points at it."""
        p = self.get("executables", folder, "").strip()
        if p:
            return self.rel(p)
        d = self.get("executables", "dir", "").strip()
        return os.path.join(self.rel(d) if d else os.path.join(HERE, "bin"), folder, exe)

    def ft_legacy_src(self):
        """Legacy main of mode = fixedtarget: [executables] legacy = file if given (explicit wins); else <dir>/legacy_ft/main, the
        build with the Type_V = A0 normalisation override off (setup.sb, ONLY=legacy_ft). bin/legacy/main would give LO/NLO ~1250 Q^2 too large."""
        return self.exe_src("legacy_ft", "main") if not self.get("executables", "legacy", "").strip() else self.exe_src("legacy", "main")

    def shards(self, stage):
        return int(self.get("shards", stage.split("_")[0] if stage.startswith("legacy") else stage, "1"))


# ------------------------------------------------------------------ pieces
def instantiate_shard_scripts(cfg, folder, label, exe, header_lines, npts, clean_shards):
    """Copy scripts/ into dest/<folder>, renaming w_asym -> label (exe for the srun line)."""
    d = os.path.join(cfg.dest, folder)
    sd = cfg.scripts

    def conv(text):
        text = text.replace("srun ./w_asym", "srun ./@EXE@").replace("w_asym", label)
        return text.replace("@EXE@", exe)

    def read(name):
        p = os.path.join(sd, name)
        if not os.path.isfile(p):
            die(f"{p} not found (set [paths] scripts)")
        return open(p).read()

    write(os.path.join(d, "make_shards.py"), conv(read("make_shards.py")), exe=True)
    ms = conv(read("merge_shards.py"))
    ms, n = re.subn(r"(?m)^HEADER_LINES = \d+.*$", f"HEADER_LINES = {header_lines}", ms)
    if n != 1:
        die("could not find 'HEADER_LINES = N' in scripts/merge_shards.py")
    write(os.path.join(d, "merge_shards.py"), ms, exe=True)
    run_sb = conv(read("run_w_asym_array.sb"))
    if cfg.cp.has_section("environment"):
        # The shard script ships with the author's modules and LHAPDF/HOPPET paths. When the .ini has an [environment]
        # section, write that environment instead (same lines the other jobs get), so shards and the rest of the chain agree.
        run_sb, n = re.subn(r"(?m)^module purge\nmodule load [^\n]*\n(?:\n)?export PATH=[^\n]*LHAPDF/bin:\$PATH\n"
                            r"export LD_LIBRARY_PATH=[^\n]*LHAPDF/lib:\$LD_LIBRARY_PATH\n"
                            r"export LD_LIBRARY_PATH=[^\n]*HOPPET1/lib:\$LD_LIBRARY_PATH\n",
                            lambda m: env_lines(cfg, prov=False) + "\n", run_sb)
        if n != 1:
            die("could not find the module/LHAPDF/HOPPET block in scripts/run_w_asym_array.sb (needed to apply [environment])")
    write(os.path.join(d, f"run_{label}_array.sb"), run_sb, exe=True)
    # after merging, verify the row count (legacy Y-piece files have 3 lines per point, the rest 1)
    check = (f'\n# row-count check + timing log added by run_process.py\n'
             f'STAGE_T0="$2"   # submit_*_array.sh passes when the array job was submitted\n'
             f'case "$JOBNAME" in *_legacy_*_Y) K=3;; *) K=1;; esac\n'
             f'python3 "{SELF}" _check "${{JOBNAME}}.out" $K {npts}\n'
             f'CHECK_EXIT=$?\n'
             f'{timing_fn(cfg)}'
             f'log_elapsed "{label} merge ($JOBNAME, exit=$CHECK_EXIT)" "$STAGE_T0" "$CHECK_EXIT"\n'
             f'[ $CHECK_EXIT -eq 0 ] || exit 1\n')
    if clean_shards:
        # only reached if the check above passed (it exits 1 otherwise): the shards are kept for debugging on failure
        check += (f'echo "--clean-shards: removing ${{JOBNAME}}_shards/ (merged output verified above)"\n'
                  f'rm -rf "${{JOBNAME}}_shards"\n')
    write(os.path.join(d, f"merge_{label}_array.sb"), conv(read("merge_w_asym_array.sb")) + check, exe=True)
    write(os.path.join(d, f"submit_{label}_array.sh"), conv(read("submit_w_asym_array.sb")), exe=True)


def prov_runtime_lines(cfg):
    """Appended to every job's environment block: one record per job (array tasks: only task 0/1) in
    dest/provenance_runtime.log with the node, compiler, loaded modules and library/PDF search paths the job
    actually ran with. The prepare-time record is dest/PROVENANCE.txt (scripts/provenance.py)."""
    log = os.path.join(cfg.dest, "provenance_runtime.log")
    return ('case "${SLURM_ARRAY_TASK_ID:-0}" in 0|1) {\n'
            '  echo "$(date \'+%F %T\')  job=${SLURM_JOB_NAME:-?} id=${SLURM_JOB_ID:-?} node=$(hostname)  $(gcc --version 2>/dev/null | head -1)"\n'
            '  echo "    modules: $(module -t list 2>&1 | tr \'\\n\' \' \')"\n'
            '  echo "    LD_LIBRARY_PATH=$LD_LIBRARY_PATH"\n'
            '  echo "    LHAPDF_DATA_PATH=${LHAPDF_DATA_PATH:-<unset: LHAPDF default>}"\n'
            f'}} >> "{log}" 2>&1 || true ;; esac\n')


def env_lines(cfg, root=False, prov=True):
    g = lambda k, d: cfg.get("environment", k, d)
    out = ["module purge", "module load " + g("modules", "GCC/13.2.0 OpenMPI/4.1.6-GCC-13.2.0 powertools")]
    if root:
        out.append("source " + g("root_setup", "/mnt/home/lopezels/InstallSources/ROOT/bin/thisroot.sh"))
    for key, d in (("lhapdf", "/mnt/home/lopezels/InstallSources/LHAPDF"),
                   ("hoppet", "/mnt/home/lopezels/InstallSources/HOPPET1")):
        p = g(key, d)
        out += [f"export PATH={p}/bin:$PATH", f"export LD_LIBRARY_PATH={p}/lib:$LD_LIBRARY_PATH"]
    return "\n".join(out) + "\n" + (prov_runtime_lines(cfg) if prov else "")


def _env_file_paths(path):
    """(LD_LIBRARY_PATH dirs, LHAPDF_DATA_PATH, ROOT lib dir) as set by a generated env_getfixed.sh."""
    ld, pdf, root = [], "", ""
    try:
        for line in open(path):
            line = line.strip()
            m = re.match(r"export LD_LIBRARY_PATH=(.*)", line)
            if m:
                ld = [x for x in m.group(1).split(":") if x and not x.startswith(("$", "\\$"))]
            m = re.match(r"export LHAPDF_DATA_PATH=(.*)", line)
            if m:
                pdf = m.group(1)
            m = re.match(r"source\s+(\S*thisroot\.sh)", line)
            if m:
                root = os.path.join(os.path.dirname(os.path.dirname(m.group(1))), "lib")
    except OSError:
        pass
    return ld + ([root] if root else []), pdf


def write_provenance(cfg):
    """Record the software/inputs behind this campaign: dest/PROVENANCE.txt and .json (scripts/provenance.py).
    Never fails the preparation."""
    try:
        prov = os.path.join(cfg.scripts, "provenance.py")
        if not os.path.exists(prov):
            prov = os.path.join(HERE, "scripts", "provenance.py")
        g = lambda k, d: cfg.get("environment", k, d)
        lhapdf, hoppet = g("lhapdf", "/mnt/home/lopezels/InstallSources/LHAPDF"), g("hoppet", "/mnt/home/lopezels/InstallSources/HOPPET1")
        root_lib = os.path.join(os.path.dirname(os.path.dirname(g("root_setup", "/mnt/home/lopezels/InstallSources/ROOT/bin/thisroot.sh"))), "lib")
        ld = f"{lhapdf}/lib:{hoppet}/lib:{root_lib}"
        cmd = [sys.executable, prov, "--dest", cfg.dest, "--ini", cfg.path, "--repo", HERE,
               "--modules", g("modules", "GCC/13.2.0 OpenMPI/4.1.6-GCC-13.2.0 powertools")]
        for folder, exe in (("w_pert", "w_pert"), ("w_asym", "w_asym"), ("legacy", "main"),
                            ("get_yk_new", "get_yk_new"), ("resbos", "resbos_root")):
            p = os.path.join(cfg.dest, folder, exe)
            if os.path.exists(p):
                cmd += ["--exe", f"{folder}={p};ld={ld};src={cfg.exe_src(folder, exe)}"]
        pdf_search = [os.path.join(lhapdf, "share", "LHAPDF")]
        inputs = [("source_template", cfg.src), ("scripts", cfg.scripts)]
        if getattr(cfg, "use_r2w", False):
            envld, envpdf = _env_file_paths(cfg.r2w.env)
            cmd += ["--exe", f"resbos2_resbos={cfg.r2w.resbos};ld={':'.join(envld)};env={cfg.r2w.env};src={cfg.r2w.resbos}"]
            inputs += [("env_getfixed.sh", cfg.r2w.env), ("resbos2_w_config_template", cfg.r2w.config)]
            if envpdf:
                pdf_search.append(envpdf)
        for folder in ("legacy", "w_pert", "w_asym"):
            if os.path.isdir(os.path.join(cfg.dest, folder, "inp")):
                inputs.append((f"grids_{folder}", os.path.join(cfg.dest, folder, "inp")))
        if cfg.mode == "fixedtarget":
            ft = cfg.ft
            envld, envpdf = _env_file_paths(ft.env)
            cmd += ["--exe", f"GetFixed={ft.getfixed};ld={':'.join(envld)};env={ft.env};src={ft.getfixed}"]
            if ft.lhapdf_data_path:
                pdf_search = [ft.lhapdf_data_path]
            inputs += [("data_table", ft.table)] + ([("convgrids_given", ft.convgrids)] if ft.convgrids else [])
            inputs += [("env_getfixed.sh", ft.env)]
            cmd += ["--pdf", f"{cfg.pdf}={ft.lhapdf_data_path or envpdf}"]
        cmd += ["--pdf", f"{cfg.pdf}={':'.join(pdf_search)}"]
        for lab, p in inputs:
            if p and os.path.exists(p):
                cmd += ["--input", f"{lab}={p}"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        print(r.stdout.strip() if r.returncode == 0 else f"warning: provenance not written ({r.stderr.strip()[-200:]})")
    except Exception as e:  # provenance must never block a campaign
        print(f"warning: provenance not written ({e})")


def stage_fn(cfg):
    """Bash function `stage SRC DST`: bring the output of an earlier step next to the job that needs it."""
    if cfg.stage == "copy":
        op = 'cp -f "$1" "$2"'
    else:
        op = 'ln -sfn "$(realpath --relative-to="$(dirname "$2")" "$1")" "$2"'
    return ('stage() {   # stage SRC DST\n'
            '  [ -s "$1" ] || { echo "ERROR: missing input $1 (did the upstream job fail?)"; exit 1; }\n'
            f'  {op}\n'
            '}\n')


def timing_header_lines(cfg):
    """submit_all.sh: write dest/timing.log's first line (T0, the campaign's own start time,
    as an epoch timestamp) so every later stage's log_elapsed() can report elapsed-since-start."""
    log = os.path.join(cfg.dest, "timing.log")
    return [f'TIMING_LOG="{log}"',
            'echo "T0 $(date +%s)  ($(date \'+%F %T\'), campaign start)" > "$TIMING_LOG"', '']


def timing_fn(cfg):
    """Bash function `log_elapsed STAGE [STAGE_START_EPOCH]`: append a locked, timestamped
    line to dest/timing.log. Always reports elapsed-since-campaign-start (T0, written by
    submit_all.sh). Also reports that STAGE's own isolated duration, two ways:
    - STAGE_START_EPOCH given (array+merge stages: w_pert/w_asym/legacy_Y/legacy_main --
      the merge job doesn't know how long the preceding array took, so build()/build_points()
      pass down the epoch when the array was submitted -- the array itself has no
      dependency, so submission time is effectively its start time).
    - STAGE_START_EPOCH omitted (get_yk_new/resbos -- single, non-array jobs that DO have a
      --dependency on earlier stages, so bash's own $SECONDS, counting from when this
      script itself started running, i.e. only once SLURM actually dispatched it, already
      excludes time spent waiting on those dependencies -- no argument-passing needed)."""
    log = os.path.join(cfg.dest, "timing.log")
    return (f'TIMING_LOG="{log}"\n'
            'log_elapsed() {   # log_elapsed STAGE [STAGE_START_EPOCH] [EXIT_CODE]\n'
            '  local t0 now elapsed stage_t0 dur dur_str exit_code error_msg\n'
            '  t0=$(awk \'/^T0 /{print $2; exit}\' "$TIMING_LOG" 2>/dev/null)\n'
            '  now=$(date +%s)\n'
            '  elapsed=$([ -n "$t0" ] && echo $((now - t0)) || echo -1)\n'
            '  stage_t0="$2"\n'
            '  exit_code="${3:-0}"\n'
            '  dur=$([ -n "$stage_t0" ] && echo $((now - stage_t0)) || echo $SECONDS)\n'
            '  dur_str=$(printf \'%ss (%dh%02dm%02ds)\' "$dur" $((dur/3600)) $(((dur%3600)/60)) $((dur%60)))\n'
            '  { flock -x 201\n'
            '    if [ "$exit_code" -eq 0 ]; then\n'
            '      printf \'%s  %-40s  duration=%-18s elapsed_since_start=%ss (%dh%02dm%02ds)\\n\' \\\n'
            '        "$(date \'+%F %T\')" "$1" "$dur_str" "$elapsed" \\\n'
            '        $((elapsed/3600)) $(((elapsed%3600)/60)) $((elapsed%60)) \\\n'
            '        >> "$TIMING_LOG"\n'
            '    else\n'
            '      error_msg=$(tail -n5 "$0".err 2>/dev/null | grep -i "error\\|failed" | head -n1 | cut -c1-80)\n'
            '      printf \'%s  %-40s  exit=%d  ERROR: %s\\n\' \\\n'
            '        "$(date \'+%F %T\')" "$1" "$exit_code" "$error_msg" \\\n'
            '        >> "$TIMING_LOG"\n'
            '    fi\n'
            '  } 201>>"$TIMING_LOG.lock"\n'
            '}\n')


def yk_script(cfg, tag, vtype, jobs, npts, rai_file, make_rai):
    job = f"{cfg.name}_Yk_{tag}_{cfg.order}"
    ins = [(f'../{folder}/{jobs[stage]}.out', f'{jobs[stage]}.out')
           for folder, stage in (("w_pert", "w_pert"), ("w_asym", "w_asym"), ("legacy", "legacy_Y"))]
    skip_note = ""
    if cfg.skip_wpa:          # w_pert/w_asym are not run: placeholders with the points of the Legacy Y piece (values unused at NLO)
        skip_note = "# w_pert/w_asym were not run (skip_pert_asym): placeholders with the Legacy Y points, values unused at order = NLO\n"
        staging = f"stage {ins[2][0]} {ins[2][1]}\n" \
                  f'python3 "{SELF}" _wpa_placeholders {ins[2][1]} {ins[0][1]} {ins[1][1]} || exit 1\n'
    else:
        staging = "".join(f"stage {src} {dst}\n" for src, dst in ins)
    body = f"""#!/bin/bash --login
#SBATCH --job-name={job}
#SBATCH --output=slurm_yk_{cfg.name}_{tag}_%j.out
#SBATCH --error=slurm_yk_{cfg.name}_{tag}_%j.err
#SBATCH --time=12:00:00
#SBATCH --nodes=1 --ntasks=1 --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --partition=general-long

cd ${{SLURM_SUBMIT_DIR}}
{env_lines(cfg)}
{stage_fn(cfg)}
# inputs = outputs of w_pert, w_asym and legacy (LTO=3)
{skip_note}{staging}{make_rai}srun ./get_yk_new {" ".join(dst for _, dst in ins)} {rai_file} {job}.out {vtype} {cfg.order} {cfg.pdf}
EXIT_CODE=$?
echo "get_yk_new finished with exit code $EXIT_CODE"
[ $EXIT_CODE -eq 0 ] && python3 "{SELF}" _check {job}.out 3 {npts} || EXIT_CODE=1
{timing_fn(cfg)}
log_elapsed "get_yk_new ({tag}, exit=$EXIT_CODE)" "" "$EXIT_CODE"
exit $EXIT_CODE
"""
    return job, body


def resbos_script(cfg, rjob, main_src, y_src, final=None):
    """main_src/y_src are (folder, job) pairs naming the "Main data grid"/"Y piece grid"
    inputs -- for resNLO these are legacy(LTO=0)/get_yk_new's Yk grid; for NLO's two
    phase-space-slicing runs they're both legacy outputs (asy=LTO=2 main + Y=LTO=3 Y-piece
    directly, or dsi=LTO=1 main + no Y piece at all, y_src=None -> the .in gets "-")."""
    main_folder, main_job = main_src
    staging = f"stage ../{main_folder}/{main_job}.out Resbos_grids/{main_job}.out\n"
    if y_src:
        y_folder, y_job = y_src
        staging += f"stage ../{y_folder}/{y_job}.out Resbos_grids/{y_job}.out\n"
    return f"""#!/bin/bash --login
#SBATCH --job-name={rjob}
#SBATCH --output=slurm_{rjob}_%j.out
#SBATCH --error=slurm_{rjob}_%j.err
#SBATCH --time=12:00:00
#SBATCH --nodes=1 --ntasks=1 --cpus-per-task=1      # resbos_root is serial
#SBATCH --mem-per-cpu=8G
#SBATCH --partition=general-long

cd ${{SLURM_SUBMIT_DIR}}
{env_lines(cfg, root=True)}
{stage_fn(cfg)}
mkdir -p Resbos_grids
{staging}
LOG_FILE="resbos_output_{rjob}_${{SLURM_JOB_ID}}.log"
srun ./resbos_root {rjob} >> "$LOG_FILE" 2>&1
EXIT_CODE=$?
echo "resbos_root finished with exit code $EXIT_CODE" | tee -a "$LOG_FILE"
# resbos_root.f writes "<jobname>.root" in the CWD -- move the final result up to the
# campaign's top-level dest/ folder so it's easy to find/copy without digging into resbos/
if [ $EXIT_CODE -eq 0 ] && [ -f "{rjob}.root" ]; then
  mv -f "{rjob}.root" "{cfg.dest}/{rjob}.root"
  echo "moved {rjob}.root -> {cfg.dest}/{rjob}.root" | tee -a "$LOG_FILE"
{analysis_link_lines(cfg, f"{cfg.dest}/{rjob}.root", final, '$LOG_FILE')}fi
{timing_fn(cfg)}
log_elapsed "resbos ({rjob}, exit=$EXIT_CODE)" "" "$EXIT_CODE"
exit $EXIT_CODE
"""


def hadd_script(cfg, hjob, asy_root, dsi_root, out_root, final=None):
    """NLO = phase-space-sliced fixed order: qT>qT_Sep (asy+Y piece resbos run) + qT<qT_Sep
    (dsi-alone resbos run), combined event-by-event with ROOT's hadd -- the qT_Sep
    dependence is designed to cancel between the two files (see README.md "NLO (fixed
    order)"). hadd needs ROOT on PATH, same as resbos_root (env_lines(cfg, root=True))."""
    return f"""#!/bin/bash --login
#SBATCH --job-name={hjob}
#SBATCH --output=slurm_{hjob}_%j.out
#SBATCH --error=slurm_{hjob}_%j.err
#SBATCH --time=00:30:00
#SBATCH --nodes=1 --ntasks=1 --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --partition=general-long

cd ${{SLURM_SUBMIT_DIR}}
{env_lines(cfg, root=True)}
hadd -f "{cfg.dest}/{out_root}" "{cfg.dest}/{asy_root}" "{cfg.dest}/{dsi_root}"
EXIT_CODE=$?
echo "hadd finished with exit code $EXIT_CODE"
if [ $EXIT_CODE -eq 0 ] && [ -f "{cfg.dest}/{out_root}" ]; then
{analysis_link_lines(cfg, f"{cfg.dest}/{out_root}", final)}fi
{timing_fn(cfg)}
log_elapsed "hadd NLO ({hjob}, exit=$EXIT_CODE)" "" "$EXIT_CODE"
exit $EXIT_CODE
"""


def infer_vegas_events(cfg, rdir, tag, suffix):
    """[DEPRECATED] Vegas parameters are now set via _ensure_resbos_defaults() in Cfg.
    This function is kept for backward compatibility but returns None (uses config directly)."""
    # After _ensure_resbos_defaults() runs, [resbos] vegas is always defined
    # write_resbos_run() will use cfg.get("resbos", "vegas") which won't be None
    return None


def write_resbos_run(cfg, rdir, tag, run, main_src, y_src, resbos_lines, suffix=None):
    """Write resbos/<name>_<tag>_<run>[_<suffix>].in + its .sb from the resbos template +
    [cuts.<run>]; return the job name. main_src/y_src: see resbos_script(); y_src=None
    writes "-" (no Y piece) for the NLO dsi-alone run."""
    sec = "cuts." + run
    if run != "default" and not cfg.cp.has_section(sec):
        die(f"[resbos] runs lists '{run}' but there is no [{sec}] section")
    lines = list(resbos_lines)
    for k, (marker, tok) in PHYS_RESBOS.items():
        if k in cfg.phys:
            set_token(lines, find(lines, marker, marker), tok, f"{cfg.phys[k]:.10g}")
    # ISEED and the VEGAS settings: only what the .ini overrides
    i = find(lines, "seed for random", "seed")
    toks = [t.strip() for t in lines[i].split(">", 1)[0].split(",")]
    if cfg.get("resbos", "vegas"):
        toks[:5] = [t.strip() for t in cfg.req("resbos", "vegas").split(",")]
    elif suffix in ("NLO", "resNLO"):
        # Auto-scale VEGAS params if not explicitly configured
        inferred = infer_vegas_events(cfg, rdir, tag, suffix)
        if inferred:
            toks[:5] = inferred.split(",")
    if cfg.get("resbos", "seed"):
        toks[5] = cfg.req("resbos", "seed")
    put(lines, i, ",".join(toks))
    put(lines, find(lines, "Main data grid", "main grid"), f"./Resbos_grids/{main_src[1]}.out")
    put(lines, find(lines, "Y piece grid", "Y grid"),
        f"./Resbos_grids/{y_src[1]}.out" if y_src else "-")
    if y_src and y_src[0] == "legacy":
        # NLO's asy+Y run feeds Legacy's raw LTO=3 output directly (10 columns, 15 header
        # lines: 'Q,qT,y, Singular (L0,A3), Pert. (L0,A3,A1,A2,A4)', main.for ~1872) --
        # resbos_root.f's iYGrid selects the Y-grid *format* it expects (read from resbos.in,
        # not auto-detected from the file): iYGrid=1 is exactly this raw 15-header/10-column
        # layout; iYGrid=2 (what every resbos.in template ships with, tuned for resNLO) is
        # get_yk_new's newer 17-header/11-column format with the extra R_Ai columns appended
        # -- feeding it a raw Legacy file makes resbos_root.f print "Must have 17 comment
        # lines in the Y-Grid file" and Call Exit (silently, exit code 0, no events). Force
        # iYGrid=1 only for this run; resNLO's own run (y_src=("get_yk_new", ...)) keeps
        # whatever the template already has.
        set_token(lines, find(lines, "iYG", "iYGrid"), 3, "1")
    for key, marker in (("lepton", "Cuts(1)"), ("mass_qt_y", "Cuts(2)"), ("mt_met", "Cuts(3)")):
        v = cfg.get(sec, key)
        if v:
            if "{qwindow}" in v:
                v = v.replace("{qwindow}", cfg.req("resbos", "qwindow"))
            put(lines, find(lines, marker, key), v)
    if cfg.get("resbos", "lumi"):
        set_token(lines, find(lines, "Luminosity", "luminosity"), 0, cfg.req("resbos", "lumi"))
    if cfg.get("resbos", "output"):
        put(lines, find(lines, "Output fromat", "output"), cfg.req("resbos", "output"))
    rjob = f"{cfg.name}_{tag}_{run}" + (f"_{suffix}" if suffix else "")
    write(os.path.join(rdir, rjob + ".in"), "".join(lines))
    final = (tag, run, "resNLO") if suffix == "resNLO" else None      # nloasy / nlodsi are pieces: only the hadd'ed NLO is final
    write(os.path.join(rdir, f"run_{rjob}.sb"), resbos_script(cfg, rjob, main_src, y_src, final), exe=True)
    return rjob


def resbos_add(cfg, args):
    """--resbos-only: dest already has the w_pert/w_asym/legacy/get_yk_new outputs of an earlier run;
    only (re)generate and optionally submit the resbos job(s) for [resbos] runs, reusing them directly."""
    if "resNLO" not in cfg.compute:
        die("--resbos-only re-runs the resNLO resbos step (Legacy main grid + get_yk_new's Yk grid); "
            "add 'resNLO' to [campaign] compute")
    if not os.path.isdir(cfg.dest):
        die(f"{cfg.dest} does not exist: run the full campaign first (no --resbos-only)")
    resbos_lines = read_lines(os.path.join(cfg.src, cfg.req("templates", "resbos")))
    resolve_physics(cfg, legacy_template_lines(cfg))
    rdir = os.path.join(cfg.dest, "resbos")
    os.makedirs(os.path.join(rdir, "Resbos_grids"), exist_ok=True)
    exe_src = cfg.exe_src("resbos", "resbos_root")
    if not os.path.isfile(exe_src):
        die(f"executable not found: {exe_src}\n       build it first with:  ONLY=resbos_legacy sbatch setup.sb")
    copy(exe_src, os.path.join(rdir, "resbos_root"), exe=True)
    runs = [r.strip() for r in cfg.get("resbos", "runs", "default").split(",") if r.strip()]
    to_submit = []
    multi_energy = len(cfg.energies) > 1
    for energy in cfg.energies:
        cfg.name, cfg.ecm = energy.name, energy.ecm
        if multi_energy:
            elabel = f" ({energy.label})" if energy.label else ""
            print(f"\n### energy{elabel}: {energy.ecm} GeV -- prefix {energy.name}")
        for vtype in cfg.procs:
            tag, _ = PROCS[vtype]
            if cfg.use_r2w:
                main_folder, main_job = "resbos2_w", f"{cfg.name}_r2w_{tag}_main"
            else:
                main_folder, main_job = "legacy", f"{cfg.name}_legacy_{tag}_main"
            yk_job = f"{cfg.name}_Yk_{tag}_{cfg.order}"
            main_out = os.path.join(cfg.dest, main_folder, main_job + ".out")
            yk_out = os.path.join(cfg.dest, "get_yk_new", yk_job + ".out")
            missing = [p for p in (main_out, yk_out) if not os.path.isfile(p)]
            if missing:
                die("missing output(s) of the main campaign, run (and wait for) it first:\n       "
                    + "\n       ".join(missing))
            print(f"\n== {vtype}")
            for run in runs:
                rjob = write_resbos_run(cfg, rdir, tag, run, (main_folder, main_job), ("get_yk_new", yk_job),
                                         resbos_lines, suffix="resNLO")
                print(f"  resbos       {rjob}.in")
                to_submit.append((rdir, f"run_{rjob}.sb", rjob))
    if args.submit:
        if not shutil.which("sbatch"):
            die("sbatch not found: use --submit on the HPCC login node")
        for d, script, rjob in to_submit:
            out = subprocess.check_output(["sbatch", "--parsable", script], cwd=d, text=True).strip()
            print(f"submitted {rjob}: job {out}")
    else:
        print("\nnext:")
        for d, script, _ in to_submit:
            print(f'  (cd "{d}" && sbatch {script})')


# ------------------------------------------------------------------ ExpCustomGrid (ye. one job per point)
def points_array_script(cfg, exe, prefix, width, npts):
    """SLURM array job: task i cds into points/pt<i>/ (already holding <prefix>_pt<i>.in
    and its own single-point inp/) and runs the executable there, Yao-run.sh-style."""
    job = f"{prefix}_points"
    arr = f"1-{npts}" + (f"%{cfg.exp_throttle}" if cfg.exp_throttle else "")
    return job, f"""#!/bin/bash --login
#SBATCH --job-name={job}
#SBATCH --output=slurm_{job}_%A_%a.out
#SBATCH --error=slurm_{job}_%A_%a.err
#SBATCH --time=02:00:00
#SBATCH --nodes=1 --ntasks=1 --cpus-per-task=1
#SBATCH --mem-per-cpu=4G
#SBATCH --partition=general-long
#SBATCH --array={arr}

cd ${{SLURM_SUBMIT_DIR}}
{env_lines(cfg)}
PT=$(printf "%0{width}d" $SLURM_ARRAY_TASK_ID)
JOBNAME="{prefix}_pt${{PT}}"
cd "points/pt${{PT}}"
srun ../../{exe} "$JOBNAME"
EXIT_CODE=$?
echo "$JOBNAME finished with exit code $EXIT_CODE"
exit $EXIT_CODE
"""


def points_merge_script(cfg, prefix, width, npts, header_lines, per_point, nqt):
    """Strip each point's header (merge_points.py CLI below) and concatenate, then verify
    the combined row count -- same idea as merge_shards.py/the shard-array's row-count check."""
    job = f"{prefix}_merge"
    return job, f"""#!/bin/bash --login
#SBATCH --job-name={job}
#SBATCH --output=slurm_{job}_%j.out
#SBATCH --error=slurm_{job}_%j.err
#SBATCH --time=00:30:00
#SBATCH --nodes=1 --ntasks=1 --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --partition=general-long

cd ${{SLURM_SUBMIT_DIR}}
STAGE_T0="$1"   # when the points array job was submitted, passed by build_points()
python3 "{SELF}" _merge_points {prefix} {width} {npts} {header_lines} {prefix}_combined.out
EXIT_CODE=$?
[ $EXIT_CODE -eq 0 ] && python3 "{SELF}" _check {prefix}_combined.out {per_point} {npts * nqt} || EXIT_CODE=1
{timing_fn(cfg)}
log_elapsed "{prefix} merge (exit=$EXIT_CODE)" "$STAGE_T0" "$EXIT_CODE"
exit $EXIT_CODE
"""


def unique_sorted_vals(values):
    """De-dup a list of number strings by float value (keep first-seen string form),
    sorted ascending -- same rule as make_grid_from_data.py's unique_sorted()."""
    seen = {}
    for v in values:
        k = float(v)
        if k not in seen:
            seen[k] = v
    return [seen[k] for k in sorted(seen)]


def write_rect_rai(path, q_vals, y_vals, qt_vals, ecm, vtype, pdf):
    """Write a dummy (all R_Ai=1) R_Ai file as a genuine rectangular grid (Q outer, y
    middle, qT inner -- CheckSum's required nesting), covering every unique Q/y pair from
    an ExpCustomGrid campaign's points instead of just its (irregular) real point set.
    Exact for NLO (get_yk_new.f only applies R_Ai when iorder=="NNLO"): the combined
    w_pert/w_asym/legacy_Y files still only have the real points -- this file only has to
    satisfy get_yk_new.f's CheckSum (Sample()'s block-counting requires NQ*Ny*NqT ==
    total rows, which an irregular point set can't provide even with all-1 values)."""
    lines = ["ECM, TYPE_V, PDF\n", f"{ecm} {vtype} {pdf}\n", "  Q,qT,y R_A0 R_A1 R_A2 R_A3\n"]
    for q in q_vals:
        for y in y_vals:
            for qt in qt_vals:
                lines.append(f"{q} {qt} {y} 1 1 1 1\n")
    write(path, "".join(lines))


def build_points(cfg, args):
    """[grids] experimental set: one job per (y,Q) row of the data table (Yao's run.sh
    pattern) instead of one shared rectangular grid. w_pert/w_asym/legacy_Y/legacy_main
    run per point and are merged into <prefix>_combined.out each; get_yk_new and resbos
    then run once per boson against those combined files, exactly like build()'s normal
    campaign does against its single shared grid's outputs -- the merged files keep the
    same (Q,qT,y) row order across w_pert/w_asym/legacy_Y (same points, same qT grid,
    written identically for all four stages), which is all get_yk_new's row-by-row match
    check (eps=1e-8) needs. Only resNLO is supported here (NLO fixed order needs a genuine
    dense Q x y rectangle for its LTO=1/2/3 pieces, same reason resbos itself can't run on
    an irregular ExpCustomGrid point set -- see the WARNING below)."""
    if cfg.compute != {"resNLO"}:
        die("[grids] experimental only supports [campaign] compute = resNLO "
            "(NLO fixed order needs a dense Q x y rectangle -- use [grids] generate instead)")
    for d in ("get_yk_new", "legacy", "resbos", "w_asym", "w_pert"):
        if not os.path.isdir(os.path.join(cfg.src, d)):
            die(f"source folder {cfg.src} has no '{d}/'")
    if os.path.exists(cfg.dest) and not args.reuse:
        die(f"{cfg.dest} already exists (use --reuse to refresh its .in files and scripts)")
    if os.path.realpath(cfg.dest) == os.path.realpath(cfg.src):
        die("dest must differ from source")
    if args.clean_shards:
        print("note: --clean-shards has no effect in [grids] experimental mode (no shard dirs are made)")

    tpl = {k: cfg.req("templates", k) for k in ("legacy_Y", "legacy_main", "w_pert", "w_asym", "resbos")}
    tlines = {k: read_lines(os.path.join(cfg.src, v)) for k, v in tpl.items()}
    points = read_points(cfg.experimental, cfg.exp_y_col, cfg.exp_q_col)
    npts = len(points)
    width = len(str(npts))

    # ---- qT grid: every code must read the identical one. Q/y become single-value files
    # the driver writes itself (identically for all four stages), so no lockstep check is
    # needed for those the way build() needs one for its one shared Q/qT/y grid files.
    ref_qt = None
    for stage in ("w_pert", "w_asym", "legacy_Y", "legacy_main"):
        folder = STAGES[stage][0]
        qt_rel = grid_paths(tlines[stage])[1]
        p = os.path.join(cfg.src, folder, qt_rel)
        if not os.path.isfile(p):
            die(f"grid {p} not found")
        if ref_qt is None:
            ref_qt = (p, md5(p))
        elif md5(p) != ref_qt[1]:
            die(f"qT grid differs between {ref_qt[0]} and {p}: all codes must use the same qT grid")
    nqt = sum(1 for l in open(ref_qt[0]) if l.strip())
    total_pts = npts * nqt
    print(f"{cfg.experimental}: {npts} experimental points x {nqt} qT points each "
          f"({total_pts} rows/stage/boson)")

    exes = [(STAGES[k][0], STAGES[k][1]) for k in ("w_pert", "w_asym", "legacy_Y")]
    exes += [("get_yk_new", "get_yk_new"), ("resbos", "resbos_root")]
    missing = [cfg.exe_src(f, e) for f, e in exes if not os.path.isfile(cfg.exe_src(f, e))]
    if missing:
        die("executable(s) not found:\n       " + "\n       ".join(missing) + "\n"
            "       build them first with:  ONLY=resbos_legacy sbatch setup.sb   (writes bin/<code>/<exe>)\n"
            "       or point to them in the .ini:  [executables] dir = <folder>  (or one key per code)")

    print(f"copying to {cfg.dest}")
    for folder, exe in exes:
        src = cfg.exe_src(folder, exe)
        print(f"  {folder}/{exe} <- {src}")
        copy(src, os.path.join(cfg.dest, folder, exe), exe=True)
    # (make_dummy_rai.py isn't used here: it reads a real w_pert.out's own point set, which
    # in this mode is the irregular one that fails get_yk_new.f's CheckSum -- see
    # write_rect_rai() below, which builds the full rectangular Q x y closure instead)
    q_vals = unique_sorted_vals([q for _, q in points])
    y_vals = unique_sorted_vals([y for y, _ in points])
    qt_vals = [l.strip() for l in open(ref_qt[0]) if l.strip()]
    check_q_kinematics_points(cfg, points, min(float(v) for v in qt_vals))

    if npts != len(q_vals) * len(y_vals):
        print(f"WARNING: these {npts} points are not a perfect Q x y rectangle "
              f"({len(q_vals)} unique Q x {len(y_vals)} unique y = "
              f"{len(q_vals) * len(y_vals)}, {len(q_vals) * len(y_vals) - npts} missing). "
              f"get_yk_new's R_Ai dummy is padded to the full rectangle to pass its own\n"
              f"         CheckSum (harmless -- unused values), but resbos_root.f's OWN "
              f"CheckSum on the 'Main data grid' (Legacy's REAL, non-dummy output) has the\n"
              f"         same NQ*Ny*NqT==rows requirement and CANNOT be padded the same way "
              f"without faking real physics -- get_yk_new will likely still produce a Yk\n"
              f"         grid, but resbos will very likely fail with 'File checksum BAD. The "
              f"grid file is corrupt!' on legacy_..._main_combined.out. For a real resbos/\n"
              f"         .root result, use a rectangular grid instead (make_grid_from_data.py "
              f"+ a normal [templates] campaign, e.g. E201_e605_full.ini for E605).")

    sub = ["#!/bin/bash", "set -e", *timing_header_lines(cfg)]
    multi_energy = len(cfg.energies) > 1
    for energy in cfg.energies:
        cfg.name, cfg.ecm = energy.name, energy.ecm
        etok = bash_token(energy.name) + "_" if multi_energy else ""
        if multi_energy:
            elabel = f" ({energy.label})" if energy.label else ""
            print(f"\n### energy{elabel}: {energy.ecm} GeV -- prefix {energy.name}")
            sub.append(f'echo "=== {energy.name}: {energy.ecm} GeV{elabel} ==="')
        ecm = cfg.ecm
        for vtype in cfg.procs:
            tag, jw = PROCS[vtype]
            print(f"\n== {vtype}")
            combined, merge_ids = {}, {}
            for stage in ("w_pert", "w_asym", "legacy_Y", "legacy_main"):
                folder, exe, _, hdr, k = STAGES[stage]
                prefix = (f"{cfg.name}_{stage}_{tag}" if stage in ("w_pert", "w_asym") else
                          f"{cfg.name}_legacy_{tag}_{'Y' if stage == 'legacy_Y' else 'main'}")
                for i, (y_val, q_val) in enumerate(points, start=1):
                    pt = str(i).zfill(width)
                    job = f"{prefix}_pt{pt}"
                    if len(job) > 95:
                        die(f"'{job}' is {len(job)} chars; the codes truncate at 100. "
                            f"Shorten {'[energies] prefix' if multi_energy else '[campaign] name'}")
                    lines = patch_stage(cfg, tlines, stage, tag, jw, vtype, ecm)
                    q_rel, qt_rel, y_rel = grid_paths(lines)
                    set_active(lines, (1, nqt, 1, 1, 1, 1, 1, 1, 1), (1, nqt, 1, 1, 1, 1, 1, 1, 1))
                    pdir = os.path.join(cfg.dest, folder, "points", f"pt{pt}")
                    write(os.path.join(pdir, q_rel), q_val + "\n")
                    write(os.path.join(pdir, y_rel), y_val + "\n")
                    copy(os.path.join(cfg.src, folder, qt_rel), os.path.join(pdir, qt_rel))
                    write(os.path.join(pdir, job + ".in"), "".join(lines))
                fdir = os.path.join(cfg.dest, folder)
                aj, abody = points_array_script(cfg, exe, prefix, width, npts)
                write(os.path.join(fdir, f"run_{aj}.sb"), abody, exe=True)
                mj, mbody = points_merge_script(cfg, prefix, width, npts, hdr, k, nqt)
                write(os.path.join(fdir, f"run_{mj}.sb"), mbody, exe=True)
                var = f"M_{etok}{stage.upper()}_{tag}"
                merge_ids[stage] = var
                combined[stage] = f"{prefix}_combined"       # basename (no .out) of the merged file
                sub.append('STAGE_T0=$(date +%s)')
                sub.append(f'ARRAY_ID=$(cd "{fdir}" && sbatch --parsable run_{aj}.sb)')
                sub.append(f'{var}=$(cd "{fdir}" && sbatch --parsable --dependency=afterok:$ARRAY_ID '
                           f'run_{mj}.sb "$STAGE_T0")')
                print(f"  {stage:<12} {npts} points -> {prefix}_combined.out")

            # ---- get_yk_new: same as build(), but fed the merged _combined.out files
            yk_dir = os.path.join(cfg.dest, "get_yk_new")
            rai = cfg.get("get_yk_new", f"r_ai_{tag}")
            if rai:
                rai_file = os.path.basename(rai)
                copy(cfg.rel(rai), os.path.join(yk_dir, rai_file))
                make_rai = ""
            else:
                if cfg.order == "NNLO":
                    die(f"NNLO needs a real R_Ai table: set [get_yk_new] r_ai_{tag}")
                rai_file = f"{cfg.name}_dummy_R_Ai_{tag}.txt"           # all ones; exact for NLO
                write_rect_rai(os.path.join(yk_dir, rai_file), q_vals, y_vals, qt_vals,
                                int(float(ecm)), vtype, cfg.pdf)
                make_rai = ""
            yk_job, body = yk_script(cfg, tag, vtype, combined, total_pts, rai_file, make_rai)
            yk_script_name = f"run_get_yk_new_{etok}{tag}.sb"
            write(os.path.join(yk_dir, yk_script_name), body, exe=True)
            sub.append(f'YK_{etok}{tag}=$(cd "{yk_dir}" && sbatch --parsable --dependency=afterok:'
                       f'${merge_ids["w_pert"]}:${merge_ids["w_asym"]}:${merge_ids["legacy_Y"]} '
                       f'--kill-on-invalid-dep=yes {yk_script_name})')
            print(f"  get_yk_new   {yk_job}.out  ({cfg.order})")

            # ---- resbos: one job per [resbos] run, fed the merged legacy_main + the Yk grid above
            rdir = os.path.join(cfg.dest, "resbos")
            os.makedirs(os.path.join(rdir, "Resbos_grids"), exist_ok=True)
            runs = [r.strip() for r in cfg.get("resbos", "runs", "default").split(",") if r.strip()]
            for run in runs:
                rjob = write_resbos_run(cfg, rdir, tag, run, ("legacy", combined["legacy_main"]),
                                         ("get_yk_new", yk_job), tlines["resbos"], suffix="resNLO")
                sub.append(f'(cd "{rdir}" && sbatch --parsable --dependency=afterok:$YK_{etok}{tag}:'
                           f'${merge_ids["legacy_main"]} --kill-on-invalid-dep=yes run_{rjob}.sb)')
                print(f"  resbos       {rjob}.in")
            sub.append("")

    sub.append('echo "all jobs submitted; watch with: squeue -u $USER"')
    # Add monitoring command that shows progress in real-time
    sub.append(f'echo "Monitoring progress: tail -f {os.path.join(cfg.dest, "timing.log")}"')
    # Schedule background monitor to add final summary when campaign completes
    sub.append(f'sbatch {os.path.join(cfg.dest, "analysis.sb")}')
    write(os.path.join(cfg.dest, "submit_all.sh"), "\n".join(sub) + "\n", exe=True)
    shutil.copyfile(cfg.path, os.path.join(cfg.dest, "campaign.ini"))
    write_provenance(cfg)

    write_analysis(cfg)

    print(f"\nprepared {cfg.dest}\nnext: bash {os.path.join(cfg.dest, 'submit_all.sh')}")
    if args.submit:
        if not shutil.which("sbatch"):
            die("sbatch not found: use --submit on the HPCC login node")
        subprocess.check_call(["bash", os.path.join(cfg.dest, "submit_all.sh")])


def load_mgfd(cfg):
    """Load scripts/make_grid_from_data.py from [paths] scripts by file path (not a plain
    `import`, which would only work if it happened to sit next to run_process.py) -- so
    run_process.py stays the only file you need to copy elsewhere; [paths] scripts says where
    the rest (this script, the shard scripts) actually lives."""
    import importlib.util
    path = os.path.join(cfg.scripts, "make_grid_from_data.py")
    if not os.path.isfile(path):
        die(f"{path} not found (set [paths] scripts)")
    spec = importlib.util.spec_from_file_location("make_grid_from_data", path)
    mgfd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mgfd)
    return mgfd


# ------------------------------------------------------------------ main flow
def generate_grid_files(cfg, tlines):
    """[grids] generate: build a fine Q x y rectangle in-process (same math as
    make_grid_from_data.py's "generate" mode) and write it into the template's own
    legacy/w_pert/w_asym inp/, at whatever relative paths their .in files already name --
    so [templates] doesn't need a pre-baked grid checked in, just the .in structure.
    w_pert/w_asym are skipped when compute = NLO only (build() doesn't load their
    templates then -- see tlines' conditional keys in build()); legacy_dsi/legacy_asy
    don't need their own entry since their grid paths come from the same file as
    legacy_Y by default (patch_stage() only rewrites the LTO token, not the grid paths)."""
    mgfd = load_mgfd(cfg)
    from types import SimpleNamespace

    q_ns = SimpleNamespace(q_min=float(cfg.gen_q_min) if cfg.gen_q_min else None,
                            q_max=float(cfg.gen_q_max) if cfg.gen_q_max else None,
                            q_from=cfg.gen_q_from, q_col=cfg.gen_q_col)
    y_ns = SimpleNamespace(y_min=float(cfg.gen_y_min) if cfg.gen_y_min else None,
                            y_max=float(cfg.gen_y_max) if cfg.gen_y_max else None,
                            y_from=cfg.gen_y_from, y_col=cfg.gen_y_col)
    q_lo, q_hi = mgfd.resolve_range(q_ns, "q")
    y_lo, y_hi = mgfd.resolve_range(y_ns, "y")
    q_vals = [mgfd.fmt(v) for v in mgfd.spaced(q_lo, q_hi, cfg.gen_n_q, cfg.gen_q_spacing)]
    y_vals = [mgfd.fmt(v) for v in mgfd.spaced(y_lo, y_hi, cfg.gen_n_y, cfg.gen_y_spacing)]

    targets = [("legacy_Y", "legacy")]
    targets += [(k, k) for k in ("w_pert", "w_asym") if k in tlines]
    for key, folder in targets:
        q_rel, qt_rel, y_rel = grid_paths(tlines[key])
        write(os.path.join(cfg.src, folder, q_rel), "\n".join(q_vals) + "\n")
        write(os.path.join(cfg.src, folder, y_rel), "\n".join(y_vals) + "\n")

    print(f"[grids] generate: wrote {cfg.gen_n_q} Q ({cfg.gen_q_spacing}, [{mgfd.fmt(q_lo)}, "
          f"{mgfd.fmt(q_hi)}]) x {cfg.gen_n_y} y ({cfg.gen_y_spacing}, [{mgfd.fmt(y_lo)}, "
          f"{mgfd.fmt(y_hi)}]) into {cfg.src}'s {'/'.join(f for _, f in targets)} inp/")


ANALYSIS_TEMPLATE = """#!/bin/bash --login
#SBATCH --job-name=validate___JOBTAG__
#SBATCH --output=__DEST__/slurm_validate_%j.out
#SBATCH --error=__DEST__/slurm_validate_%j.err
#SBATCH --time=2-00:00:00                       # waits for the whole campaign (hours): a 2 h limit killed it before the campaign ended
#SBATCH --nodes=1 --ntasks=1 --cpus-per-task=1      # validation is serial (pure Python)
#SBATCH --mem-per-cpu=4G
#SBATCH --partition=general-long

# Wait until no job of this campaign is still pending or running. Jobs stuck in
# DependencyNeverSatisfied (an upstream step failed) are ignored, otherwise we would wait forever.
DEST="__DEST__"
TIMING_LOG="$DEST/timing.log"
PREFIXES=(__PREFIXES__)

campaign_busy() {
    local p
    for p in "${PREFIXES[@]}"; do
        if squeue -u "$USER" -h -o "%j|%r" 2>/dev/null | \
           awk -F'|' -v p="$p" 'index($1, p) == 1 && $2 != "DependencyNeverSatisfied" {found=1} END {exit !found}'; then
            return 0
        fi
    done
    return 1
}
while campaign_busy; do
    sleep 120
done

python3 "$DEST/validate_campaign.py" "$DEST" > "$DEST/validation_summary.txt" 2>&1
VALID_RC=$?

{
    flock -x 201 2>/dev/null || true
    t0=$(awk '/^T0 /{print $2; exit}' "$TIMING_LOG" 2>/dev/null)
    if [ -n "$t0" ]; then
        now=$(date +%s)
        total_seconds=$((now - t0))
        printf '\n%s\n' "================================================" >> "$TIMING_LOG"
        printf '%s  %-40s  TOTAL TIME: %dh%02dm%02ds\n' "$(date '+%F %T')" "CAMPAIGN COMPLETE" \
            $((total_seconds / 3600)) $(((total_seconds % 3600) / 60)) $((total_seconds % 60)) >> "$TIMING_LOG"
    fi
    printf '%s\n' "--- validate_campaign.py (exit $VALID_RC), full table in validation_summary.txt ---" >> "$TIMING_LOG"
    cat "$DEST/validation_summary.txt" >> "$TIMING_LOG"
    printf '%s\n' "==================================================" >> "$TIMING_LOG"
} 201>>"$TIMING_LOG.lock" 2>/dev/null || true
"""


# ------------------------------------------------------------------ file names for the analysis
def analysis_name(cfg, tag, run, order):
    """{beam}_{TeV}_{PDF}_{PROCESS}_{CUTS}_{ORDER} (no extension): the convention of KFactor_Raw_simulations/Simulations/README.md,
    e.g. pp_8TeV_CT25NLO_ZU_nocuts_resNLO, ppbar_1.96TeV_CT25NLO_Wp_nocuts_NLO. `tag` is Wp, Wm, Z0, ZU, ZD; `order` NLO or resNLO."""
    beam = CONVENTION_BEAM[cfg.get("legacy", "ibeam").strip()]
    return f"{beam}_{float(cfg.ecm) / 1000:g}TeV_{cfg.pdf}_{tag}_{run}_{order}"


def analysis_dir(cfg, order):
    """dest/for_analysis/<generator>/: the folder name is the one of Simulations/ in the analysis project, so the files can be
    copied there as they are. NLO never uses the W grid (ResbosLegacy); the resNLO is ResbosR2W when the W grid is ResBos2's."""
    gen = "ResbosR2W" if (order == "resNLO" and cfg.use_r2w) else "ResbosLegacy"
    return os.path.join(cfg.dest, "for_analysis", gen)


def analysis_link_lines(cfg, src, final, log_var=None):
    """Bash lines giving the final root file `src` its analysis name as a hard link (no extra disk; a copy if the link fails).
    final = (tag, run, order) or None."""
    if cfg.conv != "analysis" or not final:
        return ""
    tag, run, order = final
    adir, name = analysis_dir(cfg, order), analysis_name(cfg, tag, run, order) + ".root"
    echo = f'echo "analysis name: {adir}/{name}"' + (f' | tee -a "{log_var}"' if log_var else "")
    return (f'  mkdir -p "{adir}"\n'
            f'  ln -f "{src}" "{adir}/{name}" 2>/dev/null || cp -f "{src}" "{adir}/{name}"\n'
            f'  {echo}\n')


# ------------------------------------------------------------------ ResBos2 W grid ([campaign] w_grid = resbos2)
def fnum(tok):
    """Fortran number ('0.21d0') -> float."""
    return float(re.sub(r"[dD]", "e", tok.strip()))


def set_cfg_key(lines, key, value, add=False):
    """Set `key = value` in the lines of a ResBos2 .config, keeping the trailing comment; add=True appends the line when the key is missing."""
    rx = re.compile(r"^(\s*" + re.escape(key) + r"\s*=\s*)([^#\n]*?)(\s*(#.*)?)$")
    for i, l in enumerate(lines):
        m = rx.match(l.rstrip("\n"))
        if m:
            lines[i] = f"{m.group(1)}{value}{m.group(3)}\n"
            return
    if add:
        lines.append(f"{key} = {value}\n")
        return
    die(f"the ResBos2 W config template has no '{key} = ...' line")


def get_cfg_key(lines, key):
    rx = re.compile(r"^\s*" + re.escape(key) + r"\s*=\s*([^#\n]*?)\s*(#.*)?$")
    for l in lines:
        m = rx.match(l.rstrip("\n"))
        if m:
            return m.group(1)
    die(f"the ResBos2 W config template has no '{key} = ...' line")


def legacy_value(lines, key):
    marker, tok = PHYS_LEGACY[key]
    return fnum(lines[find(lines, marker, marker)].split(">", 1)[0].split(",")[tok])


def legacy_template_lines(cfg):
    """The Legacy .in the campaign is built from (the main-grid one when it is named, else the Y-piece one)."""
    return read_lines(os.path.join(cfg.src, cfg.get("templates", "legacy_main") or cfg.req("templates", "legacy_Y")))


def resolve_physics(cfg, legacy_lines):
    """Fill cfg.phys (values written into the files) and cfg.phys_src (where each came from).
    Priority: [physics] in the .ini > (w_grid = resbos2 only) the electroweak keys from the ResBos2 config and the quark masses
    (incl. the top) from the Legacy template > nothing, i.e. each template keeps its own values. Only the keys in `cfg.phys` are
    written, to every place that has them: the Legacy .in, resbos.in and (w_grid = resbos2) the ResBos2 configs."""
    vals, src = dict(cfg.phys_ini), {k: ".ini [physics]" for k in cfg.phys_ini}
    if not cfg.phys_sync:                       # sync = no: only what the .ini sets; every template keeps its own masses, widths and EW flags
        cfg.phys, cfg.phys_src = vals, src
        return
    if cfg.use_r2w:
        if not os.path.isfile(cfg.r2w.config):
            die(f"[resbos2_w] config template not found: {cfg.r2w.config}")
        c2 = read_lines(cfg.r2w.config)
        for k in PHYS_EW:
            if k not in vals:
                vals[k], src[k] = fnum(get_cfg_key(c2, PHYS_R2W[k])), os.path.basename(cfg.r2w.config)
        for k in PHYS_QUARK:
            if k not in vals:
                vals[k], src[k] = legacy_value(legacy_lines, k), "Legacy template"
    else:
        dead = [k for k in cfg.phys_ini if k not in PHYS_LEGACY and k not in PHYS_RESBOS]
        if dead:
            print(f"note: [physics] {', '.join(dead)} only apply to the ResBos2 W grid (w_grid = resbos2); ignored")
            for k in dead:
                vals.pop(k), src.pop(k)
    cfg.phys, cfg.phys_src = vals, src
    physics_check(cfg, legacy_lines)


def physics_check(cfg, legacy_lines):
    """Warn when a value the templates give differently is not set by [physics] (so each file would keep its own number)."""
    try:
        res = read_lines(os.path.join(cfg.src, cfg.req("templates", "resbos")))
        r = lambda k: fnum(res[find(res, PHYS_RESBOS[k][0], PHYS_RESBOS[k][0])].split(">", 1)[0].split(",")[PHYS_RESBOS[k][1]])
        bad = []
        for k in PHYS_RESBOS:
            if k in cfg.phys:
                continue
            vals = {"resbos.in": r(k)}
            if k in PHYS_LEGACY:
                vals["Legacy .in"] = legacy_value(legacy_lines, k)
            if len({round(v, 8) for v in vals.values()}) > 1:
                bad.append(f"{k}: " + ", ".join(f"{n} {v:g}" for n, v in vals.items()))
        if bad:
            print("WARNING: the templates disagree on " + "; ".join(bad) + " (set them in [physics] to use one value everywhere)")
    except SystemExit:
        pass


def physics_report(cfg):
    """Text table of the effective values (printed and written to dest/PHYSICS.txt) and the reminder of what is not controllable."""
    if not cfg.phys and not cfg.phys_sync:
        return "physics: sync = no: every template keeps its own masses, widths and EW flags (nothing is copied from one file to another)\n"
    if not cfg.phys:
        return ("physics: [physics] is empty and w_grid is not resbos2: the templates are used as they are (they share one set of masses and widths)\n"
                "  w_pert/w_asym have built-in values (GF = 1.16637e-5, M_Z = 91.1875, M_W = 80.385) that no .in changes.\n")
    out = ["physics (value, source); written to the Legacy .in, resbos.in" + (" and the ResBos2 configs" if cfg.use_r2w else "") + ":"]
    for k in PHYS_KEYS:
        if k in cfg.phys:
            v = cfg.phys[k]
            where = [n for n, d in (("Legacy", PHYS_LEGACY), ("resbos.in", PHYS_RESBOS)) if k in d]
            if cfg.use_r2w and (k in PHYS_R2W or k in PHYS_R2W_STR):
                where.append("ResBos2")
            out.append(f"  {k:<15} {v if isinstance(v, str) else f'{v:.10g}':<14} {cfg.phys_src[k]:<22} -> {', '.join(where)}")
    out.append("  w_pert/w_asym have built-in values (GF = 1.16637e-5, M_Z = 91.1875, M_W = 80.385) that no .in changes.")
    return "\n".join(out) + "\n"


def r2w_params(lines):
    """The physics settings of the CSS function, read from the (patched) Legacy main .in so that ResBos2 computes exactly what
    Legacy was set to compute. Only what was validated is accepted: CSS scheme and the BLNY non-perturbative form (iNONPERT=5)."""
    def toks(marker):
        i = find(lines, marker, marker)
        return [t.strip() for t in lines[i].split(">", 1)[0].split(",")]
    scheme = toks("CSS or CFG")[0].upper()
    if scheme != "CSS":
        die(f"w_grid = resbos2 needs the CSS scheme, the Legacy template has '{scheme}'")
    kin = toks("iBeam=")
    npt = toks("iNONPERT, IFLAG_C3")
    if int(npt[0]) != 5:
        die(f"w_grid = resbos2 is validated for the BLNY non-perturbative form only (iNONPERT = 5); the template has {npt[0]}")
    flag = int(npt[1])
    if flag == 99:
        c = [fnum(x) for x in npt[2:5]]
    elif flag == 1:
        c = [1.0, 1.0, 1.0]                       # canonical: C1 = b0, C2 = 1, C3 = b0  ==  C1/B0 = C2 = C3/B0 = 1
    else:
        die(f"w_grid = resbos2 supports IFLAG_C3 = 1 (canonical) or 99 (custom C1/B0, C2, C3/B0); the template has {flag}")
    sud = toks("Order of Sudakov")
    sc = toks("iscale")
    g = toks("g1, g2, g3, Q0, nG")
    qm = toks("Quark masses")
    pdf = toks("Evolved PDF file")[0]
    return dict(kincorr=int(kin[2]), c1=c[0], c2=c[1], c3=c[2], a=int(sud[0]), b=int(sud[1]), cf=int(sud[2]),
                scale="MT" if int(sc[0]) == 1 else "Q", mur=fnum(sc[1]), muf=fnum(sc[2]),
                bmax=fnum(toks("bMax")[0]), g=[fnum(x) for x in g[:3]], q0=fnum(g[3]),
                mc=fnum(qm[3]), mb=fnum(qm[4]), pdf=pdf[4:] if pdf.startswith("lha_") else pdf,
                iset=int(toks("ISTR")[0]))


def r2w_nodes(cfg, qtoks, act, ecm):
    """Indices (1-based, ascending) of the Q grid points of the ResBos2 W grid: the active Q range plus [resbos2_w] margin
    nodes on each side (the main grid is interpolated with 4 points per variable and must contain the Y grid's Q range),
    margin nodes above ECM dropped."""
    lo, hi, step = act[6], act[7], act[8]
    idx = list(range(lo, hi + 1, step))
    m = cfg.r2w.margin
    extra = [lo - k * step for k in range(m, 0, -1)] + [idx[-1] + k * step for k in range(1, m + 1)]
    keep = [i for i in extra if 1 <= i <= len(qtoks) and float(qtoks[i - 1]) <= ecm]
    return sorted(set(idx + keep))


def r2w_grid_rows(qtmax, ymax, ymin=None):
    """Rows per Q node of a ResBos2 Resummation grid: nQT x nY (Calculation::GridGen: nQT = int(10 ln(qtMax/0.1) + 3),
    qT mesh q_i = qtMax exp(-0.1 (nQT-i-1)); nY = (yMax-yMin)/0.1 + 1)."""
    ymin = -ymax if ymin is None else ymin
    return int(10 * math.log(qtmax / 0.1) + 3) * int((ymax - ymin) / 0.1 + 1)


def r2w_prepare(cfg, tag, vtype, lines_main, qtoks, act, ecm, y_job, qt_grid_max, y_grid_max):
    """Write dest/resbos2_w/: the q node list, one resbos.config per node and the two job scripts (array of ResBos2 runs, assembly
    of the Legacy-format grid); return what build() needs for the submission."""
    r = cfg.r2w
    if not os.path.isfile(r.config):
        die(f"[resbos2_w] config template not found: {r.config}")
    tmpl = read_lines(r.config)
    template_mode = r.settings == "template"
    if template_mode:
        # the ResBos2 config is used as it is (Yao's): only what belongs to the run is set (beam, ECM, process, PDF, set, Q node, qT/y range, threads);
        # orders, scales, non-perturbative function, bMax, Q0, g, quark masses and EW inputs stay as the config says
        i_set = find(lines_main, "ISTR", "ISTR")
        P = dict(pdf=cfg.pdf, iset=int(lines_main[i_set].split(">", 1)[0].split(",")[0]))
        ymn = fnum(get_cfg_key(tmpl, "yMin"))
        ymx = fnum(get_cfg_key(tmpl, "yMax"))
        if r.ymax is not None:
            ymn, ymx = -r.ymax, r.ymax
        desc = (f"config as is: {get_cfg_key(tmpl, 'NonPert')} bmax {get_cfg_key(tmpl, 'bMax')}, C3 {get_cfg_key(tmpl, 'C3')}, "
                f"A,B,C = {get_cfg_key(tmpl, 'AOrder')},{get_cfg_key(tmpl, 'BOrder')},{get_cfg_key(tmpl, 'COrder')}")
    else:
        P = r2w_params(lines_main)
        ymn, ymx = -r.ymax, r.ymax
        desc = f"BLNY bmax {P['bmax']:g}, A,B,C = {P['a']},{P['b']},{P['cf']}"
    qtmax = r.qtmax if r.qtmax else qt_grid_max
    if qtmax < qt_grid_max:
        die(f"[resbos2_w] qtmax = {qtmax:g} is below the largest qT of the grid ({qt_grid_max:g}): resbos_root would lose the events "
            f"above the last ResBos2 node; use qtmax >= {qt_grid_max:g} (or auto)")
    if max(abs(ymn), abs(ymx)) < y_grid_max:
        die(f"[resbos2_w] the y range of the ResBos2 grid ({ymn:g}, {ymx:g}) is below the largest |y| of the Legacy grid ({y_grid_max:g})")
    rows_node = r2w_grid_rows(qtmax, ymx, ymn)
    idx = r2w_nodes(cfg, qtoks, act, float(ecm))
    nodes = [qtoks[i - 1] for i in idx]
    d = os.path.join(cfg.dest, "resbos2_w")
    cdir = os.path.join(d, f"configs_{tag}")
    for q in nodes:
        lines = list(tmpl)
        run_keys = [("XSec", "Resummation"), ("beam", R2W_BEAM[cfg.get("legacy", "ibeam").strip()]), ("ECM", f"{float(ecm):g}"),
                    ("Process", R2W_PROCESS[vtype]), ("PDF", P["pdf"]), ("iSet", P["iset"])]
        if template_mode:
            for key, val in run_keys + [("qMin", q), ("qMax", q), ("qtMax", f"{qtmax:g}"), ("yMin", f"{ymn:g}"), ("yMax", f"{ymx:g}"),
                                        ("nThreads", r.threads)]:
                set_cfg_key(lines, key, val, add=True)
        else:
            for key, val in run_keys + [("KinematicCorrection", "true" if P["kincorr"] == 1 else "false"),
                                        ("AOrder", P["a"]), ("BOrder", P["b"]), ("COrder", P["cf"]),
                                        ("C1", f"{P['c1']:g}"), ("C2", f"{P['c2']:g}"), ("C3", f"{P['c3']:g}"),
                                        ("NonPert", "BLNY"), ("bMax", f"{P['bmax']:g}"), ("Q0", f"{P['q0']:g}"),
                                        ("g", ", ".join(f"{x:g}" for x in P["g"])),
                                        ("scale", P["scale"]), ("muF", f"{P['muf']:g}"), ("muR", f"{P['mur']:g}"),
                                        ("mc", f"{P['mc']:g}"), ("mb", f"{P['mb']:g}"),
                                        ("qMin", q), ("qMax", q), ("qtMin", "0"), ("qtMax", f"{qtmax:g}"),
                                        ("yMin", f"{ymn:g}"), ("yMax", f"{ymx:g}"), ("nThreads", r.threads)]:
                set_cfg_key(lines, key, val)
        for k, key in PHYS_R2W.items():
            if k in cfg.phys:
                set_cfg_key(lines, key, f"{cfg.phys[k]:.10g}")
        for k, key in PHYS_R2W_STR.items():
            if k in cfg.phys:
                set_cfg_key(lines, key, cfg.phys[k])
        write(os.path.join(cdir, f"Q{q}.config"), "".join(lines))
    qfile = f"q_nodes_{tag}.txt"
    write(os.path.join(d, qfile), "\n".join(nodes) + "\n")
    if template_mode:     # the header keeps the masses of the Legacy file (as in Yao's LegacyHeader), not those of the ResBos2 config
        masses = tuple(legacy_value(lines_main, k) for k in ("mt", "mw", "mz"))
    else:
        masses = tuple(fnum(get_cfg_key(lines, k)) for k in ("mT", "mW", "mZ"))      # as written in the configs (last node)
    job = f"{cfg.name}_r2w_{tag}"
    main_job = f"{job}_main"
    check_jobname(main_job)
    thr = f"%{r.throttle}" if r.throttle else ""
    arr = f"""#!/bin/bash --login
#SBATCH --job-name={job}
#SBATCH --output=slurm_{job}_%A_%a.out
#SBATCH --error=slurm_{job}_%A_%a.err
#SBATCH --time={r.time}
#SBATCH --nodes=1 --ntasks=1 --cpus-per-task={r.threads}
#SBATCH --mem={r.mem}
#SBATCH --partition={r.partition}
#SBATCH --array=0-{len(nodes) - 1}{thr}

# ResBos2 XSec = Resummation at one Q node of the Legacy Q grid ({vtype}, {R2W_PROCESS[vtype]}, {len(nodes)} nodes); each node in its own
# folder because ResBos2 writes Grids/ and ConvGrids/ in the working directory
cd "${{SLURM_SUBMIT_DIR}}"
source {r.env}
{prov_runtime_lines(cfg)}Q=$(sed -n "$((SLURM_ARRAY_TASK_ID + 1))p" {qfile})
d="{tag}/Q${{Q}}"
mkdir -p "$d/Grids" "$d/ConvGrids"
cp "configs_{tag}/Q${{Q}}.config" "$d/resbos.config"
cd "$d"
{r.resbos} -i resbos.config -o out > run.log 2>&1
EXIT_CODE=$?
ROWS=$(tail -n +{R2W_HEADER_LINES + 1} Grids/ResBos_GridFile_0.out 2>/dev/null | grep -c .)
echo "Q=$Q: resbos exit code $EXIT_CODE, $ROWS grid rows (expected {rows_node})"
[ "$EXIT_CODE" -eq 0 ] && [ "$ROWS" -eq {rows_node} ] || exit 1
"""
    asm_job = f"{job}_asm"
    out_rel = f"{main_job}.out"
    asm = f"""#!/bin/bash --login
#SBATCH --job-name={asm_job}
#SBATCH --output=slurm_{asm_job}_%j.out
#SBATCH --error=slurm_{asm_job}_%j.err
#SBATCH --time=00:30:00
#SBATCH --nodes=1 --ntasks=1 --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --partition={r.partition}

# ResBos2 grids of all Q nodes -> one "Main data grid" in Legacy format (header of Legacy's own Y-piece grid with LTO set to 0)
cd "${{SLURM_SUBMIT_DIR}}"
{env_lines(cfg)}python3 "{SELF}" _r2w_assemble "{os.path.join(cfg.dest, "legacy", y_job + ".out")}" "{tag}" {qfile} {out_rel} {masses[0]:g} {masses[1]:g} {masses[2]:g}
EXIT_CODE=$?
echo "r2w assemble finished with exit code $EXIT_CODE"
{timing_fn(cfg)}log_elapsed "r2w assemble ({tag}, exit=$EXIT_CODE)" "" "$EXIT_CODE"
exit $EXIT_CODE
"""
    write(os.path.join(d, f"run_{job}.sb"), arr, exe=True)
    write(os.path.join(d, f"assemble_{job}.sb"), asm, exe=True)
    return dict(job=main_job, array=f"run_{job}.sb", asm=f"assemble_{job}.sb", nodes=nodes, rows=len(nodes) * rows_node,
                dir=d, out=os.path.join(d, out_rel), qtmax=qtmax, params=P, desc=desc)


def _replace_token(line, n, new):
    """Replace the n-th (0-based) whitespace-separated token of `line`, keeping the spacing of the rest."""
    parts = re.split(r"(\s+)", line.rstrip("\n"))
    k = [i for i, x in enumerate(parts) if x.strip()][n]
    parts[k] = new
    return "".join(parts) + "\n"


def cmd_wpa_placeholders(legacy_y, w_pert_out, w_asym_out):
    """Write placeholder w_pert/w_asym outputs with the (Q, qT, y) points of Legacy's Y-piece output (15 header lines, then 3 lines per
    point, the first holding `Q qT y`): the same 3 header lines and 7 columns as the real files, all values 1.0. get_yk_new at
    order = NLO only checks that the three grids carry the same points (tested: the Yk is byte-identical with any values)."""
    note = " placeholder (skip_pert_asym): only Q,qT,y are real; get_yk_new at order = NLO does not use the values"
    heads = {w_pert_out: " ECM, IBEAM, JWTYPE_IN, NORDER, IDO_CBAR, JZ_TYPE, scale_fac_muR, scale_fac_muF, iscale=" + note,
             w_asym_out: " ECM, IBEAM, JWTYPE_IN, NORDER, KINCORR, scale_fac_muR,scale_fac_muF=" + note}
    cols = {w_pert_out: "  Q,qT,y, pertL0_1, pertA3_1,  pertL0_1+pertL0_2 pertA3_1+pertA3_2 ",
            w_asym_out: "   Q, qT, y, asymL0_1, asymA3_1, asymL0_1+asymL0_2,              asymA3_1+asymA3_2"}
    files = {k: open(k + ".tmp", "w") for k in heads}
    for k, f in files.items():
        f.write(heads[k] + "\n\n" + cols[k] + "\n")
    n = 0
    with open(legacy_y) as f:
        for _ in range(R2W_HEADER_LINES):
            f.readline()
        while True:
            first = f.readline()
            if not first.strip():
                break
            f.readline(), f.readline()
            t = first.split()
            if len(t) != 3:
                print(f"{legacy_y}: expected 'Q qT y' at point {n + 1}, got '{first.strip()}'")
                sys.exit(1)
            for fo in files.values():
                fo.write(f"  {t[0]}  {t[1]}  {t[2]}  1.0  1.0  1.0  1.0\n")
            n += 1
    for k, fo in files.items():
        fo.close()
        os.replace(k + ".tmp", k)
    print(f"placeholders for {n} points: {w_pert_out}, {w_asym_out}")


def cmd_r2w_assemble(donor, tag, qfile, out, mt, mw, mz):
    """Build the Legacy-format main grid from the ResBos2 Resummation grids: the 15 header lines of `donor` (Legacy's merged Y-piece
    output of the same campaign) with LTO -> 0 and the masses of ResBos2, then `Q qT y L0 A3` rows in increasing Q, L0 and A3 being
    ResBos2's Resum columns (summed over the process channels). Runs in dest/resbos2_w; exits 1 on any inconsistency."""
    with open(donor) as f:
        hdr = [f.readline() for _ in range(R2W_HEADER_LINES)]
    if len(hdr) < R2W_HEADER_LINES or not HDR_RE.match(hdr[R2W_HEADER_LINES - 1].encode()):
        print(f"{donor}: the first {R2W_HEADER_LINES} lines are not a Legacy grid header ending in 'Q,qT,y'")
        sys.exit(1)
    if "lto" not in hdr[0].lower() or "MT,MW,MZ" not in hdr[5]:
        print(f"{donor}: unexpected header layout (line 1 should name 'lto', line 6 'MT,MW,MZ')")
        sys.exit(1)
    hdr[1] = _replace_token(hdr[1], 2, "0")                              # ecm, ibeam, LTO, ...: the Y piece is LTO = 3, this is the CSS grid
    hdr[6] = f" {float(mt):9.3f} {float(mw):9.3f} {float(mz):9.4f}\n"      # masses the grid was computed with (resbos_root rescales W/Z0 by (M/M_grid)^2)
    hdr[R2W_HEADER_LINES - 1] = "  Q,qT,y, CSS L0, CSS A3  (ResBos2 Resummation grid reheadered with the Legacy header)\n"
    nodes = [l.strip() for l in open(qfile) if l.strip()]
    per_node, total = None, 0
    tmp = out + ".tmp"
    with open(tmp, "w") as fo:
        fo.writelines(hdr)
        for q in nodes:
            path = os.path.join(tag, f"Q{q}", "Grids", "ResBos_GridFile_0.out")
            if not os.path.isfile(path):
                print(f"{path}: not found (that Q node did not finish)")
                sys.exit(1)
            with open(path) as f:
                head = [f.readline() for _ in range(R2W_HEADER_LINES)]
                names = head[R2W_HEADER_LINES - 1].split()
                if names[:3] != ["Q", "Qt", "y"] or len(names) < 5 or (len(names) - 3) % 2:
                    print(f"{path}: unexpected column header {names}")
                    sys.exit(1)
                nch = (len(names) - 3) // 2
                rows = 0
                for line in f:
                    t = line.split()
                    if not t:
                        continue
                    if abs(float(t[0]) - float(q)) > 1e-6 * max(1.0, float(q)):
                        print(f"{path}: row with Q = {t[0]}, expected the node {q}")
                        sys.exit(1)
                    if nch == 1:
                        fo.write(line if line.endswith("\n") else line + "\n")
                    else:                                              # layout: channel-major, (L0, A3) per channel
                        l0 = sum(float(t[3 + 2 * c]) for c in range(nch))
                        a3 = sum(float(t[4 + 2 * c]) for c in range(nch))
                        fo.write(f"{t[0]}  {t[1]}  {t[2]}  {l0:.8e}  {a3:.8e}\n")
                    rows += 1
            if per_node is None:
                per_node = rows
            elif rows != per_node:
                print(f"{path}: {rows} rows but the first node has {per_node}: the nodes must share the same (qT, y) mesh")
                sys.exit(1)
            total += rows
    os.replace(tmp, out)
    print(f"{out}: {R2W_HEADER_LINES} header lines + {total} rows ({len(nodes)} Q nodes x {per_node})")



def write_analysis(cfg):
    """analysis.sb: a single-core SLURM job, submitted last by submit_all.sh. It waits until the
    campaign's jobs have left the queue, then runs validate_campaign.py and appends the total time
    and the summary tables to timing.log. Replaces the old background finalize script, which died
    with the login-node session."""
    copy(os.path.join(cfg.scripts, "validate_campaign.py"),
         os.path.join(cfg.dest, "validate_campaign.py"), exe=True)
    prefixes = " ".join('"%s"' % e.name for e in cfg.energies)
    jobtag = cfg.energies[0].name
    body = (ANALYSIS_TEMPLATE.replace("__DEST__", cfg.dest)
            .replace("__PREFIXES__", prefixes)
            .replace("__JOBTAG__", jobtag))
    write(os.path.join(cfg.dest, "analysis.sb"), body, exe=True)


def build(cfg, args):
    for d in ("get_yk_new", "legacy", "resbos", "w_asym", "w_pert"):
        if not os.path.isdir(os.path.join(cfg.src, d)):
            die(f"source folder {cfg.src} has no '{d}/'")
    if os.path.exists(cfg.dest) and not args.reuse:
        die(f"{cfg.dest} already exists (use --reuse to refresh its .in files and scripts)")
    if os.path.realpath(cfg.dest) == os.path.realpath(cfg.src):
        die("dest must differ from source")

    print(f"inputs: templates {cfg.src}  |  shard scripts {cfg.scripts}  |  executables "
          f"{cfg.get('executables', 'dir') and cfg.rel(cfg.get('executables', 'dir')) or os.path.join(HERE, 'bin')}/<code>/<exe>")
    do_resnlo = "resNLO" in cfg.compute
    do_nlo = "NLO" in cfg.compute
    needed = set()
    use_r2w = cfg.use_r2w
    if do_resnlo:
        # w_grid = resbos2: the CSS main grid comes from ResBos2 (r2w_prepare below), Legacy's LTO=0 is not run
        needed |= set(RESNLO_STAGES) - ({"legacy_main"} if use_r2w else set()) - ({"w_pert", "w_asym"} if cfg.skip_wpa else set())
    if do_nlo:
        needed |= set(NLO_STAGES)
    active_stages = [s for s in STAGES if s in needed]

    # ---- templates: legacy_dsi/legacy_asy (LTO=1/2, NLO only) default to the legacy_Y
    # template -- patch_stage() overwrites the LTO field regardless of what the template
    # started with, so no new template file is required unless [templates] overrides one.
    tpl = {"legacy_Y": cfg.req("templates", "legacy_Y"), "resbos": cfg.req("templates", "resbos")}
    if do_resnlo:
        # with w_grid = resbos2 the legacy_main template is only read for the settings ResBos2 must reproduce
        tpl["legacy_main"] = cfg.get("templates", "legacy_main", tpl["legacy_Y"]) if use_r2w else cfg.req("templates", "legacy_main")
        if not cfg.skip_wpa:
            tpl["w_pert"] = cfg.req("templates", "w_pert")
            tpl["w_asym"] = cfg.req("templates", "w_asym")
    if do_nlo:
        tpl["legacy_dsi"] = cfg.get("templates", "legacy_dsi", tpl["legacy_Y"])
        tpl["legacy_asy"] = cfg.get("templates", "legacy_asy", tpl["legacy_Y"])
    tlines = {k: read_lines(os.path.join(cfg.src, v)) for k, v in tpl.items()}
    resolve_physics(cfg, tlines.get("legacy_main", tlines["legacy_Y"]))
    print(physics_report(cfg), end="")

    if cfg.gen_grid:
        generate_grid_files(cfg, tlines)

    # ---- grids: every code that runs must read identical ones. With resNLO, w_pert/w_asym
    # are cross-checked against legacy_Y's grid; with NLO alone only Legacy itself runs, so
    # its own grid (shared automatically -- legacy_Y/legacy_main/legacy_dsi/legacy_asy all
    # read the same inp/ files) needs no cross-code check.
    ref = {}
    grid_stages = [("w_pert", "w_pert"), ("w_asym", "w_asym"), ("legacy", "legacy_Y")] if (do_resnlo and not cfg.skip_wpa) \
        else [("legacy", "legacy_Y")]
    for folder, key in grid_stages:
        for role, rel in zip(("Q", "qT", "y"), grid_paths(tlines[key])):
            p = os.path.join(cfg.src, folder, rel)
            if not os.path.isfile(p):
                die(f"grid {p} not found")
            ref.setdefault(role, (p, md5(p)))
            if md5(p) != ref[role][1]:
                die(f"{role} grid differs between {ref[role][0]} and {p}: all codes must use the same grid")
    counts = {r: sum(1 for l in open(p) if l.strip()) for r, (p, _) in ref.items()}
    full = (1, counts["qT"], 1, 1, counts["y"], 1, 1, counts["Q"], 1)
    act = tuple(int(t) for t in cfg.get("grids", "active", " ".join(map(str, full))).split())
    if len(act) != 9:
        die("[grids] active needs 9 integers")
    n_of = lambda a, b, s: len(range(a, b + 1, s))
    nqt, ny = n_of(*act[0:3]), n_of(*act[3:6])
    npts = nqt * ny * n_of(*act[6:9])
    print(f"compute: {', '.join(sorted(cfg.compute))}; grid: {counts['Q']} Q x {counts['qT']} qT x "
          f"{counts['y']} y; active {npts} points")
    check_q_kinematics(cfg, [float(l) for l in open(ref["Q"][0]) if l.strip()], act)
    qtoks = [l.split()[0] for l in open(ref["Q"][0]) if l.strip()]
    qt_grid_max = max(float(l.split()[0]) for l in open(ref["qT"][0]) if l.strip())
    y_grid_max = max(abs(float(l.split()[0])) for l in open(ref["y"][0]) if l.strip())
    if use_r2w:
        print(f"w_grid = resbos2: CSS main grid from {cfg.r2w.resbos}")

    # ---- copy only what a run needs
    exes = [("legacy", "main"), ("resbos", "resbos_root")]
    if do_resnlo:
        exes += ([] if cfg.skip_wpa else [("w_pert", "w_pert"), ("w_asym", "w_asym")]) + [("get_yk_new", "get_yk_new")]
    missing = [cfg.exe_src(f, e) for f, e in exes if not os.path.isfile(cfg.exe_src(f, e))]
    if use_r2w:
        missing += [p for p in (cfg.r2w.resbos, cfg.r2w.env, cfg.r2w.config) if not os.path.isfile(p)]
    if missing:                     # check all before copying anything: no half-made dest
        die("executable(s) not found:\n       " + "\n       ".join(missing) + "\n"
            "       build them first with:  ONLY=resbos_legacy sbatch setup.sb   (writes bin/<code>/<exe>)\n"
            "       or point to them in the .ini:  [executables] dir = <folder>  (or one key per code)")

    print(f"copying to {cfg.dest}")

    def copy_exe(folder, exe):
        src = cfg.exe_src(folder, exe)
        print(f"  {folder}/{exe} <- {src}")
        copy(src, os.path.join(cfg.dest, folder, exe), exe=True)

    for folder, exe in exes:
        copy_exe(folder, exe)
    copy(os.path.join(cfg.src, "legacy", grid_paths(tlines["legacy_Y"])[0]),
         os.path.join(cfg.dest, "legacy", grid_paths(tlines["legacy_Y"])[0]))
    copy(os.path.join(cfg.src, "legacy", grid_paths(tlines["legacy_Y"])[1]),
         os.path.join(cfg.dest, "legacy", grid_paths(tlines["legacy_Y"])[1]))
    copy(os.path.join(cfg.src, "legacy", grid_paths(tlines["legacy_Y"])[2]),
         os.path.join(cfg.dest, "legacy", grid_paths(tlines["legacy_Y"])[2]))
    if do_resnlo:
        for folder, key in (("w_pert", "w_pert"), ("w_asym", "w_asym")):
            if cfg.skip_wpa:
                break
            for rel in grid_paths(tlines[key]):
                copy(os.path.join(cfg.src, folder, rel), os.path.join(cfg.dest, folder, rel))
        if cfg.order == "NLO":
            copy(os.path.join(cfg.src, "get_yk_new", "make_dummy_rai.py"),
                 os.path.join(cfg.dest, "get_yk_new", "make_dummy_rai.py"))
    for folder, exe, label, hdr in {(STAGES[s][0], STAGES[s][1], STAGES[s][2], STAGES[s][3]) for s in active_stages}:
        instantiate_shard_scripts(cfg, folder, label, exe, hdr, npts, args.clean_shards)

    # ---- per boson: .in files + submit lines. Stages whose merged output already exists in
    # dest and passes its own row-count check are reused (not resubmitted); only stages
    # actually (re)submitted this run feed into downstream --dependency= clauses, so a
    # dest folder that already has resNLO's outputs and now also asks for NLO only computes
    # the new legacy_dsi/legacy_asy/resbos/hadd pieces (legacy_Y is shared either way).
    sub = ["#!/bin/bash", "set -e", *timing_header_lines(cfg),
           "run_shards() {   # dir script job nshards -> prints the merge job id",
           '  local out; out=$(cd "$1" && bash "$2" "$3" "0-$(($4 - 1))") || return 1',
           '  echo "$out" >&2',
           "  echo \"$out\" | sed -n 's/^Submitted merge job \\([0-9]*\\).*/\\1/p'",
           "}", ""]
    multi_energy = len(cfg.energies) > 1
    for energy in cfg.energies:
        cfg.name, cfg.ecm = energy.name, energy.ecm
        etok = bash_token(energy.name) + "_" if multi_energy else ""
        if multi_energy:
            elabel = f" ({energy.label})" if energy.label else ""
            print(f"\n### energy{elabel}: {energy.ecm} GeV -- prefix {energy.name}")
            sub.append(f'echo "=== {energy.name}: {energy.ecm} GeV{elabel} ==="')
        ecm = cfg.ecm
        for vtype in cfg.procs:
            tag, jw = PROCS[vtype]
            print(f"\n== {vtype}")
            jobs, merge_ids, submitted = {}, {}, set()
            for stage in active_stages:
                folder, exe, label, hdr, k = STAGES[stage]
                lines = patch_stage(cfg, tlines, stage, tag, jw, vtype, ecm)
                job = (f"{cfg.name}_{stage}_{tag}" if stage in ("w_pert", "w_asym") else
                       f"{cfg.name}_legacy_{tag}_{LEGACY_SUFFIX[stage]}")
                set_active(lines, act, full)
                check_jobname(job, multi_energy)
                inpath = os.path.join(cfg.dest, folder, job + ".in")
                if os.path.isdir(os.path.join(cfg.dest, folder, job + "_shards")) and \
                        (not os.path.isfile(inpath) or open(inpath).read() != "".join(lines)):
                    # submit_*_array.sh reuses existing shards, which would keep the OLD values
                    die(f"{folder}/{job}_shards/ exists from an earlier input and {job}.in changed; "
                        f"remove that folder (or use a new dest) so the shards are regenerated")
                write(inpath, "".join(lines))
                jobs[stage] = job
                out_path = os.path.join(cfg.dest, folder, job + ".out")
                if valid_output(out_path, k, npts):
                    print(f"  {stage:<12} {job}.out already exists ({k * npts} lines) -- reusing, not resubmitted")
                    continue
                submitted.add(stage)
                n = cfg.shards(stage)
                var = f"M_{etok}{stage.upper()}_{tag}"
                merge_ids[stage] = var
                sub.append(f'{var}=$(run_shards "{os.path.join(cfg.dest, folder)}" submit_{label}_array.sh {job} {n})')
                print(f"  {stage:<12} {job}.in   {n} shard(s)")

            if cfg.skip_wpa:      # names only: get_yk_new's placeholder files are written in get_yk_new/ by its job
                jobs["w_pert"], jobs["w_asym"] = f"{cfg.name}_w_pert_{tag}", f"{cfg.name}_w_asym_{tag}"
                print("  w_pert/w_asym  skipped (skip_pert_asym): placeholders with the Legacy Y points are made by the get_yk_new job")
            r2w = None
            if use_r2w:
                lines_main = patch_stage(cfg, tlines, "legacy_main", tag, jw, vtype, ecm)
                r2w = r2w_prepare(cfg, tag, vtype, lines_main, qtoks, act, ecm, jobs["legacy_Y"], qt_grid_max, y_grid_max)
                jobs["r2w"] = r2w["job"]
                rows = count_data_rows(r2w["out"])
                if rows == r2w["rows"]:
                    print(f"  r2w          {r2w['job']}.out already exists ({rows} rows) -- reusing, not resubmitted")
                else:
                    avar, mvar = f"R2WA_{etok}{tag}", f"M_{etok}R2W_{tag}"
                    # the assembly needs the header of Legacy's own Y-piece grid, and every ResBos2 node
                    deps = [f"${{{avar}}}"] + ([f"${{{merge_ids['legacy_Y']}}}"] if "legacy_Y" in merge_ids else [])
                    sub.append(f'{avar}=$(cd "{r2w["dir"]}" && sbatch --parsable {r2w["array"]})')
                    sub.append(f'{mvar}=$(cd "{r2w["dir"]}" && sbatch --parsable --dependency=afterok:{":".join(deps)} '
                               f'--kill-on-invalid-dep=yes {r2w["asm"]})')
                    merge_ids["r2w"] = mvar
                    submitted.add("r2w")
                    print(f"  r2w          {r2w['job']}.out  ({len(r2w['nodes'])} ResBos2 W nodes, {R2W_PROCESS[vtype]}, qT <= {r2w['qtmax']:g}; "
                          f"{r2w['desc']})")

            def dep_clause(dep_vars):
                """--dependency=... clause built only from stages actually (re)submitted this
                run (an unset bash var in --dependency=afterok:$VAR would break sbatch). Entries
                are stage names (resolved through merge_ids) or bare bash variable names
                (e.g. "YK_Wp") used as-is."""
                names = [merge_ids[s] if s in merge_ids else s for s in dep_vars]
                return (f'--dependency=afterok:{":".join("${" + n + "}" for n in names)} '
                        f'--kill-on-invalid-dep=yes ') if names else ""

            # ---- get_yk_new (resNLO only)
            yk_job = None
            if do_resnlo:
                yk_dir = os.path.join(cfg.dest, "get_yk_new")
                yk_job = f"{cfg.name}_Yk_{tag}_{cfg.order}"
                yk_out = os.path.join(yk_dir, yk_job + ".out")
                yk_upstream = [s for s in ("w_pert", "w_asym", "legacy_Y") if s in submitted]
                if not yk_upstream and valid_output(yk_out, 3, npts):
                    print(f"  get_yk_new   {yk_job}.out already exists -- reusing, not resubmitted")
                else:
                    rai = cfg.get("get_yk_new", f"r_ai_{tag}")
                    if rai:
                        rai_file = os.path.basename(rai)
                        copy(cfg.rel(rai), os.path.join(yk_dir, rai_file))
                        make_rai = ""
                    else:
                        if cfg.order == "NNLO":
                            die(f"NNLO needs a real R_Ai table: set [get_yk_new] r_ai_{tag}")
                        rai_file = f"{cfg.name}_dummy_R_Ai_{tag}.txt"           # all ones; exact for NLO
                        make_rai = (f'[ -f {rai_file} ] || python3 make_dummy_rai.py {"" if cfg.skip_wpa else "../w_pert/"}{jobs["w_pert"]}.out '
                                    f'{rai_file} {int(float(ecm))} {vtype} {cfg.pdf} || exit 1\n')
                    _, body = yk_script(cfg, tag, vtype, jobs, npts, rai_file, make_rai)
                    yk_script_name = f"run_get_yk_new_{etok}{tag}.sb"
                    write(os.path.join(yk_dir, yk_script_name), body, exe=True)
                    sub.append(f'YK_{etok}{tag}=$(cd "{yk_dir}" && sbatch --parsable {dep_clause(yk_upstream)}'
                               f'{yk_script_name})')
                    print(f"  get_yk_new   {yk_job}.out  ({cfg.order})")
                    submitted.add("get_yk_new")

            # ---- resbos (resNLO): one job per run, never sharded; its grids are staged by the job itself
            if do_resnlo:
                rdir = os.path.join(cfg.dest, "resbos")
                os.makedirs(os.path.join(rdir, "Resbos_grids"), exist_ok=True)
                runs = [r.strip() for r in cfg.get("resbos", "runs", "default").split(",") if r.strip()]
                for run in runs:
                    main_src = ("resbos2_w", jobs["r2w"]) if use_r2w else ("legacy", jobs["legacy_main"])
                    rjob = write_resbos_run(cfg, rdir, tag, run, main_src,
                                             ("get_yk_new", yk_job), tlines["resbos"], suffix="resNLO")
                    root_out = os.path.join(cfg.dest, rjob + ".root")
                    rdeps = [s for s in ("get_yk_new", "r2w" if use_r2w else "legacy_main") if s in submitted]
                    if not rdeps and os.path.isfile(root_out):
                        print(f"  resbos       {rjob}.root already exists -- reusing, not resubmitted")
                        continue
                    dc = dep_clause(["YK_" + etok + tag if s == "get_yk_new" else s for s in rdeps])
                    sub.append(f'(cd "{rdir}" && sbatch --parsable {dc}run_{rjob}.sb)')
                    print(f"  resbos       {rjob}.in")
                sub.append("")

            # ---- NLO fixed order: Legacy LTO=2 (asy) + LTO=3 (Y, shared with resNLO) -> resbos,
            # and Legacy LTO=1 (dsi) alone -> resbos (Y piece = "-"), then hadd the two .root
            # files -- see README.md "NLO (fixed order)" for why this equals the real-emission
            # fixed-order cross section.
            if do_nlo:
                rdir = os.path.join(cfg.dest, "resbos")
                os.makedirs(os.path.join(rdir, "Resbos_grids"), exist_ok=True)
                runs = [r.strip() for r in cfg.get("resbos", "runs", "default").split(",") if r.strip()]
                for run in runs:
                    asy_job = write_resbos_run(cfg, rdir, tag, run, ("legacy", jobs["legacy_asy"]),
                                                ("legacy", jobs["legacy_Y"]), tlines["resbos"], suffix="nloasy")
                    dsi_job = write_resbos_run(cfg, rdir, tag, run, ("legacy", jobs["legacy_dsi"]),
                                                None, tlines["resbos"], suffix="nlodsi")
                    asy_root = os.path.join(cfg.dest, asy_job + ".root")
                    dsi_root = os.path.join(cfg.dest, dsi_job + ".root")
                    asy_deps = [s for s in ("legacy_asy", "legacy_Y") if s in submitted]
                    dsi_deps = [s for s in ("legacy_dsi",) if s in submitted]
                    asy_reused = not asy_deps and os.path.isfile(asy_root)
                    dsi_reused = not dsi_deps and os.path.isfile(dsi_root)
                    if asy_reused:
                        print(f"  resbos       {asy_job}.root already exists -- reusing, not resubmitted")
                    else:
                        sub.append(f'ASY_{etok}{tag}_{run}=$(cd "{rdir}" && sbatch --parsable {dep_clause(asy_deps)}'
                                   f'run_{asy_job}.sb)')
                        print(f"  resbos       {asy_job}.in")
                    if dsi_reused:
                        print(f"  resbos       {dsi_job}.root already exists -- reusing, not resubmitted")
                    else:
                        sub.append(f'DSI_{etok}{tag}_{run}=$(cd "{rdir}" && sbatch --parsable {dep_clause(dsi_deps)}'
                                   f'run_{dsi_job}.sb)')
                        print(f"  resbos       {dsi_job}.in")

                    hjob = f"{cfg.name}_{tag}_{run}_NLO"
                    hadd_out = os.path.join(cfg.dest, hjob + ".root")
                    if asy_reused and dsi_reused and os.path.isfile(hadd_out):
                        print(f"  hadd         {hjob}.root already exists -- reusing, not resubmitted")
                    else:
                        write(os.path.join(rdir, f"run_{hjob}.sb"),
                              hadd_script(cfg, hjob, f"{asy_job}.root", f"{dsi_job}.root", f"{hjob}.root",
                                          (tag, run, "NLO")), exe=True)
                        hdeps = ([] if asy_reused else [f"${{ASY_{etok}{tag}_{run}}}"]) + \
                                ([] if dsi_reused else [f"${{DSI_{etok}{tag}_{run}}}"])
                        dc = f'--dependency=afterok:{":".join(hdeps)} --kill-on-invalid-dep=yes ' if hdeps else ""
                        sub.append(f'(cd "{rdir}" && sbatch --parsable {dc}run_{hjob}.sb)')
                        print(f"  hadd         {hjob}.root  ({asy_job}.root + {dsi_job}.root)")
                sub.append("")

    sub.append('echo "all jobs submitted; watch with: squeue -u $USER"')
    # Add monitoring command that shows progress in real-time
    sub.append(f'echo "Monitoring progress: tail -f {os.path.join(cfg.dest, "timing.log")}"')
    # Schedule background monitor to add final summary when campaign completes
    sub.append(f'sbatch {os.path.join(cfg.dest, "analysis.sb")}')
    write(os.path.join(cfg.dest, "submit_all.sh"), "\n".join(sub) + "\n", exe=True)
    shutil.copyfile(cfg.path, os.path.join(cfg.dest, "campaign.ini"))
    write(os.path.join(cfg.dest, "PHYSICS.txt"), physics_report(cfg))
    write_provenance(cfg)

    write_analysis(cfg)

    print(f"\nprepared {cfg.dest}\nnext: bash {os.path.join(cfg.dest, 'submit_all.sh')}")
    if args.submit:
        if not shutil.which("sbatch"):
            die("sbatch not found: use --submit on the HPCC login node")
        subprocess.check_call(["bash", os.path.join(cfg.dest, "submit_all.sh")])


# ------------------------------------------------------------------ helper used inside jobs
def count_data_rows(path):
    """Rows after the first 'Q,qT,y' header line, or None if the file/header is missing --
    shared by cmd_check (job scripts' own row-count check) and valid_output (the driver's
    own reuse/skip check, [campaign] "don't repeat what's already there")."""
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as f:
        while True:
            line = f.readline()
            if not line:
                return None
            if HDR_RE.match(line):
                break
        rows, last = 0, b"\n"
        while True:
            buf = f.read(CHUNK)
            if not buf:
                break
            rows += buf.count(b"\n")
            last = buf[-1:]
    return rows + (0 if last == b"\n" else 1)


def valid_output(path, per_point, npts):
    """True iff path exists, has a 'Q,qT,y' header, and its row count matches
    per_point*npts exactly -- used to decide whether a stage's output can be reused
    instead of resubmitted."""
    rows = count_data_rows(path)
    return rows is not None and rows == per_point * npts


def cmd_check(path, per_point, npts):
    """Exit 0 iff the data lines after the 'Q,qT,y' header line number per_point*npts."""
    rows = count_data_rows(path)
    if rows is None:
        print(f"{path}: file not found" if not os.path.isfile(path) else f"{path}: no 'Q,qT,y' header line")
        sys.exit(1)
    want = int(per_point) * int(npts)
    print(f"{path}: {rows} data lines, expected {want}")
    sys.exit(0 if rows == want else 1)


def cmd_merge_points(prefix, width, npts, header_lines, out_file):
    """Concatenate points/pt<i>/<prefix>_pt<i>.out (i=1..npts), stripping each one's own
    header_lines-line header and keeping only the first point's header -- combine.sh's job,
    run from run_process.py itself instead of a separate script."""
    width, npts, header_lines = int(width), int(npts), int(header_lines)
    header, body_chunks, total = None, [], 0
    for i in range(1, npts + 1):
        pt = str(i).zfill(width)
        path = os.path.join("points", f"pt{pt}", f"{prefix}_pt{pt}.out")
        if not os.path.isfile(path):
            print(f"{path}: file not found -- that point hasn't finished or failed")
            sys.exit(1)
        with open(path) as f:
            lines = f.readlines()
        if len(lines) <= header_lines:
            print(f"{path}: only {len(lines)} lines, expected a {header_lines}-line header plus data")
            sys.exit(1)
        if header is None:
            header = lines[:header_lines]
        body_chunks.append(lines[header_lines:])
        total += len(lines) - header_lines
    with open(out_file, "w") as f:
        f.writelines(header)
        for chunk in body_chunks:
            f.writelines(chunk)
    print(f"{out_file}: {header_lines} header lines + {total} data rows from {npts} points")


# ------------------------------------------------------------------ mode = fixedtarget
# One dataset (E605, E866, E906), one job per measured (y,Q) point -- Yao's chain (FIXED_TARGET_WORKFLOW.md):
#   LO     Legacy LTO=-1                                  \  per point, 3 runs in one array task
#   NLO    Legacy LTO=3 (P) + LTO=1 (DeltaSigma), qT grid  >  merged, then integrated in qT, point by point, by
#                                                         /   Yao's ROOT macro scripts/getnlo/getnlo.C (getnlo_nojac.C for E605)
#   resNLO ResBos2 GetFixed (W321), one run per target on the whole table
# and a final job that writes the LO / NLO / W321 + K-factor tables (scripts/make_fixedtarget_tables.py).
FT_PIECES = {"LO": ("legacy_LO", 1), "Y": ("legacy_Y", 3), "dsi": ("legacy_dsi", 1)}   # piece -> (stage, lines/qT row)


def ft_legacy_env(cfg):
    out = env_lines(cfg, prov=False)
    if cfg.ft.lhapdf_data_path:
        out += f"export LHAPDF_DATA_PATH={cfg.ft.lhapdf_data_path}\n"
    return out + prov_runtime_lines(cfg)


def ft_points_script(cfg, prefix, pieces, width, npts):
    """SLURM array, task i = point i: cd points/pt<i> (own single-point inp/ and one .in per piece) and run
    Legacy once per piece (LTO=-1, 3, 1), stopping at the first failure."""
    job = f"{prefix}_points"
    arr = f"1-{npts}" + (f"%{cfg.ft.throttle}" if cfg.ft.throttle else "")
    runs = "\n".join(f'srun ../../../main "{prefix}_{pc}_pt${{PT}}" || exit 1' for pc in pieces)
    return job, f"""#!/bin/bash --login
#SBATCH --job-name={job}
#SBATCH --output=slurm_{job}_%A_%a.out
#SBATCH --error=slurm_{job}_%A_%a.err
#SBATCH --time=02:00:00
#SBATCH --nodes=1 --ntasks=1 --cpus-per-task=1
#SBATCH --mem-per-cpu=4G
#SBATCH --partition=general-long
#SBATCH --array={arr}

cd ${{SLURM_SUBMIT_DIR}}
{ft_legacy_env(cfg)}PT=$(printf "%0{width}d" $SLURM_ARRAY_TASK_ID)
cd "points/pt${{PT}}"
{runs}
echo "{prefix} point ${{PT}} done"
"""


def ft_merge_script(cfg, prefix, pieces, width, npts, nqt):
    """Strip each point's 15-line header, concatenate per piece, verify the row count (LO 1 row/point,
    LTO=1 one per qT, LTO=3 three per qT)."""
    job = f"{prefix}_merge"
    cmds = []
    for pc in pieces:
        per_point = {"LO": 1, "Y": 3 * nqt, "dsi": nqt}[pc]
        out = f"{prefix}_{pc}.out"
        cmds.append(f'python3 "{SELF}" _merge_points {prefix}_{pc} {width} {npts} 15 {out} || EXIT_CODE=1\n'
                    f'[ $EXIT_CODE -eq 0 ] && {{ python3 "{SELF}" _check {out} {per_point} {npts} || EXIT_CODE=1; }}')
    return job, f"""#!/bin/bash --login
#SBATCH --job-name={job}
#SBATCH --output=slurm_{job}_%j.out
#SBATCH --error=slurm_{job}_%j.err
#SBATCH --time=00:30:00
#SBATCH --nodes=1 --ntasks=1 --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --partition=general-long

cd ${{SLURM_SUBMIT_DIR}}
STAGE_T0="$1"
EXIT_CODE=0
{chr(10).join(cmds)}
{timing_fn(cfg)}log_elapsed "{prefix} merge (exit=$EXIT_CODE)" "$STAGE_T0" "$EXIT_CODE"
exit $EXIT_CODE
"""


def ft_getfixed_script(cfg, gname, npts, wtag):
    """GetFixed returns 1 from main() even on success, so SLURM would call every run FAILED and break the
    --dependency=afterok chain: the job's own exit code is decided from the output file instead."""
    job = f"{cfg.name}_{gname}_GetFixed"
    out = f"{gname}_ResBos2_{wtag}.dat"
    return job, f"""#!/bin/bash --login
#SBATCH --job-name={job}
#SBATCH --output=slurm_{job}_%j.out
#SBATCH --error=slurm_{job}_%j.err
#SBATCH --time=06:00:00
#SBATCH --nodes=1 --ntasks=1 --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --partition=general-long

cd "${{SLURM_SUBMIT_DIR}}"      # the run folder: fixedtarget.config, the data file {gname}, {gname}_pert.txt, ConvGrids/
source {cfg.ft.env}
{('export LHAPDF_DATA_PATH=' + cfg.ft.lhapdf_data_path) if cfg.ft.lhapdf_data_path else '# LHAPDF_DATA_PATH from env_getfixed.sh (Yao PDFs first, then yours)'}
{prov_runtime_lines(cfg)}mkdir -p Grids
rm -f {out}
{cfg.ft.getfixed} {gname} > getfixed.log 2>&1
echo "GetFixed exit code $? (1 is normal: main() returns 1)"
ROWS=$(grep -c . {out} 2>/dev/null || echo 0)
echo "{out}: $ROWS rows, expected {npts}"
{timing_fn(cfg)}EXIT_CODE=0; [ "$ROWS" -eq {npts} ] || EXIT_CODE=1
log_elapsed "{job} (exit=$EXIT_CODE)" "" "$EXIT_CODE"
exit $EXIT_CODE
"""


def ft_final_script(cfg, specs, do_tables, npts, nqt):
    """Per target: strip headers, integrate the NLO in qT with Yao's ROOT macro (getnlo.C / getnlo_nojac.C, one ROOT call per point, scripts/run_getnlo.sh),
    link GetFixed's W321; then (all three orders, all targets of the dataset) the LO/NLO/W321 + K-factor tables."""
    job = f"{cfg.name}_final"
    ft, L, T = cfg.ft, [], []
    macro = "getnlo_nojac" if ft.jac == "none" else "getnlo"
    for sp in specs:
        g, t, pre = sp["gname"], sp["tlabel"], sp["prefix"]
        L.append(f"mkdir -p work/{g}")
        if "LO" in cfg.compute or "NLO" in cfg.compute:
            L.append(f"tail -n +16 ../legacy/{t}/{pre}_LO.out > work/{g}/out_lo.txt")
        if "NLO" in cfg.compute:
            L.append(f"tail -n +16 ../legacy/{t}/{pre}_Y.out > work/{g}/lto3.txt")
            L.append(f"tail -n +16 ../legacy/{t}/{pre}_dsi.out > work/{g}/lto1.txt")
            L.append(f"bash ../scripts/run_getnlo.sh \"$PWD/../scripts/getnlo/{macro}.C\" {cfg.ecm} {npts} {nqt} work/{g} || EXIT_CODE=1")
        if "resNLO" in cfg.compute:
            L.append(f"ln -sfn ../../../resbos2/{g}/{g}_ResBos2_{sp['wtag']}.dat work/{g}/{g}_ResBos2_{sp['wtag']}.dat")
    if do_tables:
        T.append(f"python3 ../scripts/make_fixedtarget_tables.py --root work --outdir . --label {cfg.pdf} "
                 f"--only {ft.dataset} || EXIT_CODE=1")
    mods = f"module load {ft.final_modules}\n" if ft.final_modules else ""
    if ft.conda_env:
        mods += (f"module load {ft.conda_module}\n"
                 f"eval \"$(conda shell.bash hook)\" && conda activate {ft.conda_env} || "
                 f"{{ echo \"ERROR: cannot activate conda env {ft.conda_env}\"; exit 1; }}\n")
    root_line = (f"source {cfg.get('environment', 'root_setup', '/mnt/home/lopezels/InstallSources/ROOT/bin/thisroot.sh')}\n"
                 if "NLO" in cfg.compute else "")
    return job, f"""#!/bin/bash --login
#SBATCH --job-name={job}
#SBATCH --output=slurm_{job}_%j.out
#SBATCH --error=slurm_{job}_%j.err
#SBATCH --time=02:00:00
#SBATCH --nodes=1 --ntasks=1 --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --partition=general-long

cd "${{SLURM_SUBMIT_DIR}}"      # dest/results
module purge
module load {env_lines(cfg).splitlines()[1].split('module load ', 1)[1]}
{root_line}EXIT_CODE=0
{chr(10).join(L)}
{mods}python3 -c "import numpy" || {{ echo "ERROR: python3 needs numpy: set [fixedtarget] conda_env (environment.yml) or final_modules (a SciPy-bundle module)"; exit 1; }}
{chr(10).join(T)}
{timing_fn(cfg)}log_elapsed "{job} (exit=$EXIT_CODE)" "" "$EXIT_CODE"
exit $EXIT_CODE
"""


def build_fixedtarget(cfg, args):
    ft = cfg.ft
    d = ft.spec
    do_lego = bool(cfg.compute & {"LO", "NLO"})
    do_nlo, do_res = "NLO" in cfg.compute, "resNLO" in cfg.compute
    if not os.path.isdir(os.path.join(cfg.src, "legacy")) and do_lego:
        die(f"source folder {cfg.src} has no 'legacy/'")
    if os.path.exists(cfg.dest) and not args.reuse:
        die(f"{cfg.dest} already exists (use --reuse to refresh its .in files and scripts)")
    if os.path.realpath(cfg.dest) == os.path.realpath(cfg.src):
        die("dest must differ from source")
    if args.clean_shards or args.resbos_only:
        die("--clean-shards / --resbos-only do not apply to mode = fixedtarget")

    points = read_points(ft.table, 1, 2)
    npts = len(points)
    width = len(str(npts))
    ntgt = len(ft.targets)
    print(f"mode fixedtarget: {ft.dataset} ({', '.join(t[3] for t in ft.targets)}), {npts} points, ECM {cfg.ecm}, "
          f"PDF {cfg.pdf}, compute {', '.join(sorted(cfg.compute))}")

    # ---- executables (checked before anything is copied)
    need = []
    if do_lego:
        need.append(("Legacy main (fixed target)", cfg.ft_legacy_src(), "ONLY=legacy_ft sbatch setup.sb  (or [executables] legacy = <main>)"))
    if do_res:
        need.append(("ResBos2 GetFixed", ft.getfixed, "ONLY=resbos2 sbatch setup.sb  (or [fixedtarget] getfixed = ...)"))
        need.append(("ResBos2 env_getfixed.sh", ft.env, "ONLY=resbos2 sbatch setup.sb  (or [fixedtarget] resbos2_env = ...)"))
    miss = [f"{lab}: {path}\n       build it with:  {how}" for lab, path, how in need if not os.path.isfile(path)]
    if miss:
        die("not found:\n       " + "\n       ".join(miss))

    print("inputs:")
    print(f"  data table      : {ft.table}")
    print(f"  template folder : {cfg.src}  (Legacy .in {ft.legacy_tpl}, GetFixed config {ft.config_tpl})")
    if do_lego:
        print(f"  Legacy main     : {cfg.ft_legacy_src()}")
    if do_res:
        print(f"  GetFixed        : {ft.getfixed}\n  GetFixed env    : {ft.env}")
    if do_nlo:
        print(f"  final scripts   : {cfg.scripts}  (ROOT for Yao's getnlo macro, [environment] root_setup; python3 + numpy for the table: [fixedtarget] conda_env or final_modules)")
    cfg_tpl = None
    if do_res:
        cfg_tpl = read_lines(os.path.join(cfg.src, ft.config_tpl))
        orders = []
        for key in ("AOrder", "BOrder", "COrder"):
            m = [re.match(rf"\s*{key}\s*=\s*(\d+)", l) for l in cfg_tpl]
            m = [x for x in m if x]
            if not m:
                die(f"{ft.config_tpl} has no '{key} = <n>' line")
            orders.append(m[0].group(1))
        wtag = "w" + "".join(orders)
        if not any(re.match(r"\s*PDF\s*=", l) for l in cfg_tpl):
            die(f"{ft.config_tpl} has no 'PDF = <set>' line")
    else:
        wtag = "w321"

    sub = ["#!/bin/bash", "set -e", *timing_header_lines(cfg)]
    specs, merge_vars, gf_vars = [], [], []

    # ---- Legacy: per target, per point
    tpl_lines = None
    nqt = 0
    if do_lego:
        tpl_lines = read_lines(os.path.join(cfg.src, "legacy", os.path.basename(ft.legacy_tpl))
                               if not os.sep in ft.legacy_tpl else os.path.join(cfg.src, ft.legacy_tpl))
        qt_rel = grid_paths(tpl_lines)[1]
        qt_path = os.path.join(cfg.src, "legacy", qt_rel)
        if not os.path.isfile(qt_path):
            die(f"qT grid {qt_path} not found")
        qt_vals = [l.strip() for l in open(qt_path) if l.strip()]
        nqt = len(qt_vals)
        check_q_kinematics_points(cfg, points, min(float(v) for v in qt_vals))
        copy(cfg.ft_legacy_src(), os.path.join(cfg.dest, "legacy", "main"), exe=True)
    pieces = (["LO"] if do_lego else []) + (["Y", "dsi"] if do_nlo else [])

    ntasks = ntgt * npts if do_lego else 0
    if ntasks > 1000:
        print(f"WARNING: {ntasks} array tasks in one campaign; the HPCC allows 1000 queued tasks per user "
              f"(array tasks count) -- submit this dataset in a separate batch.")

    for tgt in ft.targets:
        suffix, ibeam, fract_n, gname = tgt
        tlabel = suffix or ft.dataset
        prefix = f"{cfg.name}_{suffix}" if suffix else cfg.name
        spec = dict(gname=gname, tlabel=tlabel, prefix=prefix, wtag=wtag)
        specs.append(spec)
        print(f"\n== {gname}  (Legacy iBeam={ibeam}, FRACT_N={fract_n})")
        if do_lego:
            if len(f"{prefix}_{pieces[-1]}_pt{npts}") > 95:
                die(f"'{prefix}_..._pt{npts}' is too long; the codes truncate at 100: shorten [campaign] name")
            ldir = os.path.join(cfg.dest, "legacy", tlabel)
            for i, (y_val, q_val) in enumerate(points, start=1):
                pt = str(i).zfill(width)
                pdir = os.path.join(ldir, "points", f"pt{pt}")
                write(os.path.join(pdir, "inp", "q_grid_test.inp"), q_val + "\n")
                write(os.path.join(pdir, "inp", "y_grid.inp"), y_val + "\n")
                copy(qt_path, os.path.join(pdir, "inp", "qt_grid.inp"))
                for pc in pieces:
                    stage = FT_PIECES[pc][0]
                    lines = patch_stage(cfg, {stage: tpl_lines}, stage, "A0", 2, "A0", cfg.ecm)
                    l_beam = find(lines, "FRACT_N", "iBeam/FRACT_N")
                    set_token(lines, l_beam, 0, ibeam)
                    set_token(lines, l_beam, 1, fract_n)
                    set_active(lines, (1, nqt, 1, 1, 1, 1, 1, 1, 1), (1, nqt, 1, 1, 1, 1, 1, 1, 1))
                    write(os.path.join(pdir, f"{prefix}_{pc}_pt{pt}.in"), "".join(lines))
            aj, abody = ft_points_script(cfg, prefix, pieces, width, npts)
            mj, mbody = ft_merge_script(cfg, prefix, pieces, width, npts, nqt)
            write(os.path.join(ldir, f"run_{aj}.sb"), abody, exe=True)
            write(os.path.join(ldir, f"run_{mj}.sb"), mbody, exe=True)
            var = f"M_{bash_token(tlabel)}"
            merge_vars.append(var)
            sub += ["STAGE_T0=$(date +%s)",
                    f'ARRAY_ID=$(cd "{ldir}" && sbatch --parsable run_{aj}.sb)',
                    f'{var}=$(cd "{ldir}" && sbatch --parsable --dependency=afterok:$ARRAY_ID run_{mj}.sb "$STAGE_T0")']
            print(f"  legacy   {npts} points x {' + '.join(pieces)} -> legacy/{tlabel}/{prefix}_<piece>.out")

    # ---- ResBos2 GetFixed: one run per target. ConvGrids are generated by the first run for a PDF (and shared),
    # so the first job runs alone unless [fixedtarget] convgrids already points at a finished set.
    if do_res:
        rdir = os.path.join(cfg.dest, "resbos2")
        os.makedirs(rdir, exist_ok=True)
        conv = os.path.join(rdir, "ConvGrids")
        if ft.convgrids:
            if not os.path.isdir(ft.convgrids):
                die(f"[fixedtarget] convgrids = {ft.convgrids}: not a folder")
            if os.path.islink(conv):
                os.remove(conv)
            os.symlink(ft.convgrids, conv)
        else:
            os.makedirs(conv, exist_ok=True)
        header = [f"# {ft.dataset} table written by run_process.py (mode fixedtarget): y  Q  xF  data  ...\n"] * 6
        rows = [l for l in read_lines(ft.table) if l.strip() and not l.lstrip().startswith("#")]
        for n, sp in enumerate(specs):
            g = sp["gname"]
            wdir = os.path.join(rdir, g)
            os.makedirs(os.path.join(wdir, "Grids"), exist_ok=True)
            link = os.path.join(wdir, "ConvGrids")
            if os.path.lexists(link):
                os.remove(link)
            os.symlink(os.path.join("..", "ConvGrids"), link)
            cl = [re.sub(r"^(\s*PDF\s*=).*$", rf"\g<1> {cfg.pdf}", l) for l in cfg_tpl]
            write(os.path.join(wdir, "fixedtarget.config"), "".join(cl))
            write(os.path.join(wdir, g), "".join(header) + "".join(rows))
            write(os.path.join(wdir, f"{g}_pert.txt"), "")      # only used by W432 (yk); empty is fine for W321
            gj, gbody = ft_getfixed_script(cfg, g, npts, sp["wtag"])
            write(os.path.join(wdir, "run_getfixed.sb"), gbody, exe=True)
            var = f"GF_{bash_token(sp['tlabel'])}"
            gf_vars.append(var)
            dep = "" if (ft.convgrids or n == 0) else f" --dependency=afterok:${{{gf_vars[0]}}}"
            sub.append(f'{var}=$(cd "{wdir}" && sbatch --parsable{dep} run_getfixed.sb)')
            print(f"  resbos2  {g}: GetFixed on {npts} points -> resbos2/{g}/{g}_ResBos2_{sp['wtag']}.dat"
                  + ("" if (ft.convgrids or n == 0) else "  (after the first run: shares its ConvGrids)"))

    # ---- final: NLO integration + tables
    all_targets = len(ft.targets) == len(d["targets"])
    do_tables = do_nlo and do_res and "LO" in cfg.compute and all_targets
    if do_nlo:
        scripts_needed = ["run_getnlo.sh", "make_fixedtarget_tables.py", "getnlo/getnlo.C", "getnlo/getnlo_nojac.C"]
        for sc in scripts_needed:
            copy(os.path.join(cfg.scripts, sc), os.path.join(cfg.dest, "scripts", sc), exe=True)
        fj, fbody = ft_final_script(cfg, specs, do_tables, npts, nqt)
        write(os.path.join(cfg.dest, "results", f"run_{fj}.sb"), fbody, exe=True)
        deps = ":".join(f"${{{v}}}" for v in merge_vars + gf_vars)
        sub.append(f'(cd "{os.path.join(cfg.dest, "results")}" && sbatch --parsable --dependency=afterok:{deps} '
                   f'--kill-on-invalid-dep=yes run_{fj}.sb)')
        print("\n  final    results/: " + (f"{ft.dataset}_{cfg.pdf}_LO_NLO_W321.txt (LO, NLO, W321, K-factors)" if do_tables else
              "no table: it needs compute = LO, NLO, resNLO and every target of the dataset") + "; NLO per point (Yao's getnlo) in results/work/<target>/getnlo_results.txt")
    sub.append('echo "all jobs submitted; watch with: squeue -u $USER"')
    sub.append(f'echo "Progress: tail -f {os.path.join(cfg.dest, "timing.log")}"')
    write(os.path.join(cfg.dest, "submit_all.sh"), "\n".join(sub) + "\n", exe=True)
    shutil.copyfile(cfg.path, os.path.join(cfg.dest, "campaign.ini"))
    write_provenance(cfg)
    print(f"\nprepared {cfg.dest}\nnext: bash {os.path.join(cfg.dest, 'submit_all.sh')}")
    if args.submit:
        if not shutil.which("sbatch"):
            die("sbatch not found: use --submit on the HPCC login node")
        subprocess.check_call(["bash", os.path.join(cfg.dest, "submit_all.sh")])


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "_check":
        return cmd_check(*sys.argv[2:5])
    if len(sys.argv) > 1 and sys.argv[1] == "_wpa_placeholders":
        return cmd_wpa_placeholders(*sys.argv[2:5])
    if len(sys.argv) > 1 and sys.argv[1] == "_r2w_assemble":
        return cmd_r2w_assemble(*sys.argv[2:9])
    if len(sys.argv) > 1 and sys.argv[1] == "_merge_points":
        return cmd_merge_points(*sys.argv[2:7])
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("campaign", help="campaign .ini (see Examples/pp_7TeV_WpWmZ0_CT25NLO.ini)")
    ap.add_argument("--submit", action="store_true", help="run submit_all.sh after preparing dest")
    ap.add_argument("--reuse", action="store_true", help="dest already exists: refresh .in files and scripts")
    ap.add_argument("--resbos-only", action="store_true",
                    help="dest already has finished w_pert/w_asym/legacy/get_yk_new outputs: only (re)generate "
                         "and, with --submit, run the resbos job(s) of [resbos] runs, reusing those outputs directly")
    ap.add_argument("--clean-shards", action="store_true",
                    help="w_pert/w_asym/legacy: delete each stage's <job>_shards/ folder from inside its merge job, "
                         "right after the row-count check passes (saves disk; kept on failure for debugging)")
    args = ap.parse_args()
    cfg = Cfg(args.campaign)
    init_scheduler(cfg)
    if cfg.mode == "fixedtarget":
        build_fixedtarget(cfg, args)
    elif args.resbos_only:
        if cfg.experimental:
            die("--resbos-only doesn't apply in [grids] experimental mode "
                "(get_yk_new/resbos aren't run there at all)")
        resbos_add(cfg, args)
    else:
        (build_points if cfg.experimental else build)(cfg, args)
    report_scheduler()


if __name__ == "__main__":
    main()
