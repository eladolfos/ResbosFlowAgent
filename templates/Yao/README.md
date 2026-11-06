# templates/Yao

Inputs of Yao's collider chain (`New_kFactorCT25/YAORESBOS/Overall`, pp and p pbar differ only in `iBeam` / `beam`), made by `scripts/make_yao_templates.py`
with only his placeholders filled. Use them with `[physics] sync = no` and `[resbos2_w] settings = template` (campaigns: `Examples/CT25NLOExpYao/`).

| File | What it is | Values of Yao kept as they are |
|---|---|---|
| `legacy/Yao_legacy_Y.in` | Legacy input (his `y_piece/00legacy.in`; the asy and delsig ones differ only in LTO and IFLAG_C3, which the driver sets) | t,W,Z,h = **173.2**, 80.385, 91.1876, 125; quark masses 0.06983, 0.06984, 0.15, 1.3, 4.75; iNONPERT **4** (BLNY g = 0.21, 0.68, -0.126, Q0 1.6), bMax 0.5, IFLAG_C3 99, C1/B0 = C2 = C3/B0 = 1, iscale 1 (MT), orders 3,2,1 |
| `legacy/inp/{q,qt,y}_grid.inp` | his Legacy grids | 33 Q (20 ... 500 GeV), 106 qT (0.0826 ... 3000: the ResBos2 qT mesh for qtMax 3000), 100 y (-5 ... 4.9) |
| `resbos/Yao_resbos.in` | `resbos_root` input (his `samplefile/00resbos.in`) | W 80.385 / **2.0895**, Z 91.1876 / **2.498353**, mt 173.5, mh 125, **EW flag 2, qed flag 2**, CKM 0, KFAC_ANGFUNC 0; cuts: no lepton cuts, **40 < Q < 500**, qT < 3000, y free; VEGAS `1,30,30000,100,250000` |
| `resbos2/Yao_resbos2_w321_IY6.config` | ResBos2 W grid (his `ResBos2/00resbos.config`) | A,B,C = 3,2,1 (his `run_multiy.sh` has 4,3,2 = W432); scale 908: C1 = C2 = muF = muR = 1; **C3 = 4**; NonPert **IY6**, g = 1.034, 0.053, 0.0, -0.143, 13.45, 1.468; **bMax 1.123**, Q0 1.6; mT 173.5, gamW **2.108**, gamZ 2.4952; **mu = md = ms = 0**, mc 1.3, mb 4.75; GF 1.1663787E-5; qtMax 3000, y in [-5, 5] |
| `resbos2/Yao_resbos2_w321_BLNY.config` | the same with his commented BLNY choice | NonPert BLNY, g = 0.21, 0.68, -0.126 |
| `w_pert/`, `w_asym/` | his inputs (norder 2), kept for completeness | not run with `skip_pert_asym` |

**Changed on purpose:** PDF `CT25NLO` (his `PDFNumber = 7` is CT18NNLO); `ROOTNT1` -> `ROOTNT2` (ROOTNT1 stores the boson variables Q, y, qT, cos theta, phi; the analysis reads the lepton variables of ROOTNT2); a fixed VEGAS seed (182019, replaces `RANDOMSEED`);
his placeholders `IWGT` = 0 and `ISYGRID` (set by the driver). Orders A,B,C = 3,2,1 because the CT25 tables call the resummed calculation W321.

**Not settled by his files:** (1) which non-perturbative function his W321 results used: his scripts run IY6 (`overall.sh`: `NonPertFormat=IY6`), but his delivered histograms are in folders called `*_BLNY` and `run_multiy.sh` keeps a commented BLNY block;
(2) his Y piece for W321 is `YConfig = 1` (`..._y.out`, made with `get_yk_new_NoRAI`, whose source is not in his folder): it is assumed to be our `get_yk_new` at `order = NLO` (Singular and Pert unchanged, angular columns as ratios, no `R_Ai`);
(3) his own files disagree with each other (gamW 2.108 in the ResBos2 config, 2.0895 in `resbos_root`; mt 173.2 in Legacy, 173.5 in the others).
