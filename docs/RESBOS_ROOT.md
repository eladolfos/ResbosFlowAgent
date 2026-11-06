# `resbos_root`: what it uses and how it puts the pieces together

`resbos_root` (sources `codes/resbos/resbos_root.f` + `resbosm.f`, with `froot.c` for the ROOT output and `angular.cc`) is the Monte Carlo event generator at the end of the
collider chain. It contains **no** QCD resummation and **no** PDFs for the processes of this repository (W, Z, γ\*/Z = `DY`): all of that was computed earlier by Legacy,
`w_pert`, `w_asym` and `get_yk_new` and arrives as **grids** in (Q, qT, y). What `resbos_root` adds is: (i) the *matching* of the pieces into one cross section, (ii) the decay
of the boson with its full spin correlations, (iii) the electroweak couplings and the propagator, (iv) phase-space sampling (VEGAS), (v) cuts on leptons and boson and (vi) the ntuple.
`COLLIDER_WORKFLOW.md` says which code makes which grid; this note says what is done with them.

How to read it: statements are taken from the source of this repository (file and approximate line in brackets; `rr` = `resbos_root.f`, `rm` = `resbosm.f`, `gy` =
`codes/get_yk_new/get_yk_new.f`). **Verified** means read in the code and, where numbers are given, checked on the grids of the E253 campaign. *Interpretation* marks my reading of
the physics behind a line of code. Only the Legacy-grid processes (`NPART = 11…14`, bosons `W+ W- Z0 DY A0`) are described; the diphoton, ZZ and Higgs branches are not.

---

## 1. Overview

```
  resbos.in ─────────────────────────────────────────────────────────────┐
  Main data grid  (W = CSS, or A = asymptotic, or Δσ, or LO)             │
  Y-piece grid    (Singular, Pert, angular ratios)                       ▼
        │                         ReadIn / PreReadIn  ── header: process, ECM, Sudakov orders, masses, ...
        └──────────────────────────────►  MatchGrids1  ──►  one matched grid  (W+Y  →  Pert)
                                                              │
   VEGAS ─► FXN ─► MAKE_EVENT ─► WRESPH  (Q, qT, y, θ*, φ*;  boson and leptons in the lab)
                                  ├─ PRIMARY_CUTS (mass, qT, y, lepton pT/η, M_T)
                                  └─ WPRES   (interpolate the grid, couplings, propagator, angular functions)
                                       weight = PS weight × WPRES   ──► PASS_OUTPUT ──► ROOT ntuple h10  (WT00)
```

| Piece | Where it comes from | What `resbos_root` does with it | Why it matters |
|---|---|---|---|
| Main grid, `NPART=11`: $L_0^{W}, A_3^{W}$ | `legacy` `LTO=0` (or the ResBos2 grid of `COLLIDER_RESBOS2_W_WORKFLOW.md`) | interpolates it at the Y-grid nodes and adds the Y piece | the resummed small-qT region (the peak of the pT spectrum) |
| Y-piece grid: Singular $A$, Pert $P$, $r_i$ | `get_yk_new` | $Y = P - A$; $P$ for the final switch; $r_i$ give the other angular functions | the large-qT region and the angular structure |
| Main grid, `NPART=12`: asymptotic $A$ (`LTO=2`) + Y grid | `legacy` `LTO=2` | $A + (P-A) = P$ for $q_T > q_{T,\rm sep}$ | the fixed-order NLO tail |
| Main grid, `NPART=13`: $\Delta\sigma$ (`LTO=1`) | `legacy` `LTO=1` | evaluated at $q_T = q_{T,\rm sep}$ | the $\delta(q_T)$-like terms of NLO, so the NLO total is complete |
| `resbos.in` | the campaign | cuts, VEGAS settings, masses, EW flags | what is generated |

NLO is the sum of two runs (`nloasy` for $q_T>q_{T,\rm sep}$ and `nlodsi` for the $\Delta\sigma$ piece), resNLO (= W321) is one run (`NPART = 11`) *(Verified: names in `submit_all.sh`)*.

---

## 2. The physics that the grids carry

### 2.1 CSS decomposition

For $h_1 h_2 \to V(\to \ell_1\ell_2) X$ the Collins–Soper–Sterman formula gives, for the boson with invariant mass $Q$, rapidity $y$ and transverse momentum $q_T$,

$$
\frac{d\sigma}{dQ^2\,dy\,dq_T^2}
= \underbrace{\frac{\sigma_0}{S}\int\!\frac{d^2b}{(2\pi)^2}\,e^{i\vec q_T\cdot\vec b}\;\widetilde W(b,Q,x_1,x_2)}_{W(q_T,Q,y)\ \text{(resummed)}}
\;+\;\underbrace{Y(q_T,Q,y)}_{\text{regular}},
\qquad
Y = P - A ,
$$

with

$$
\widetilde W(b,Q,x_1,x_2)=e^{-S(b_*,Q)}\;
\big[\mathcal C\otimes f\big](x_1,b_*)\,\big[\mathcal C\otimes f\big](x_2,b_*)\;e^{-F_{NP}(b,Q,x_1,x_2)},
\qquad b_*=\frac{b}{\sqrt{1+(b/b_{\max})^2}} ,
$$

$$
S(b,Q)=\int_{b_0^2/b^2}^{Q^2}\frac{d\bar\mu^2}{\bar\mu^2}\Big[A(\alpha_s(\bar\mu))\ln\frac{Q^2}{\bar\mu^2}+B(\alpha_s(\bar\mu))\Big],\qquad
A=\sum_{n\ge1}\Big(\frac{\alpha_s}{\pi}\Big)^n A^{(n)},\quad B=\sum_{n\ge1}\Big(\frac{\alpha_s}{\pi}\Big)^n B^{(n)},
$$

$b_0=2e^{-\gamma_E}$. **W321** = $A$ to $\alpha_s^3$, $B$ to $\alpha_s^2$, $\mathcal C$ to $\alpha_s^1$ (NNLL), matched to the $O(\alpha_s^2)$ fixed-order tail.
*(Verified: the grid header carries `n_sud_a, n_sud_b, n_wil_c = 3, 2, 1`, read and printed at `rr` 3900–3915 as `N_SUD_A,N_SUD_B,N_WIL_C,I_SUD`.)* The non-perturbative factor of our grids is
BLNY, $F_{NP}=b^2\big[g_1+g_2\ln\frac{Q}{2Q_0}+g_1g_3\ln(100\,x_1x_2)\big]$, with the header values `bmax 0.5, g1 0.21, g2 0.68, g3-slot −0.126, Q0 1.6`
*(interpretation: the third slot is $g_1g_3 = 0.21\times(-0.6)$, the BLNY value)*.

The two other ingredients of the matching:

* the **asymptotic piece** $A(q_T,Q,y)$: the small-$q_T$ expansion of $W$ to the same order in $\alpha_s$. It is what $W$ becomes when it is expanded, so it must be subtracted from the fixed order to avoid double counting;
* the **perturbative piece** $P(q_T,Q,y)$: the fixed-order $O(\alpha_s)$ and $O(\alpha_s^2)$ cross section at $q_T>0$ (Arnold–Reno, `w_pert`).

Why each matters: $W$ alone is wrong at $q_T\gtrsim Q$ (it is not a fixed-order expansion there); $P$ alone diverges as $q_T\to0$ ($\sim \ln(Q^2/q_T^2)/q_T^2$); $A$ is the common
singular part, so $Y=P-A$ is integrable and small at low $q_T$, and $W+Y$ reduces to $P$ at high $q_T$ **provided $W\to A$ there**. That last condition is exactly what fails for
Legacy's own W grid (section 5.4).

### 2.2 Lepton level

The decay distribution of the lepton in the Collins–Soper frame ($\theta^*,\phi^*$) is

$$
\frac{d\sigma}{dQ^2\,dy\,dq_T^2\,d\cos\theta^*\,d\phi^*}\;\propto\;
\mathcal A^{E}(\theta^*,\phi^*)\;\mathcal C^{E}(Q)\;+\;\mathcal A^{O}(\theta^*,\phi^*)\;\mathcal C^{O}(Q),
$$

$$
\mathcal A^{E}=(1+\cos^2\theta^*)\,L_0+\tfrac12(1-3\cos^2\theta^*)\,A_0+\sin2\theta^*\cos\phi^*\,A_1+\tfrac12\sin^2\theta^*\cos2\phi^*\,A_2,
\qquad
\mathcal A^{O}=2\cos\theta^*\,A_3+\sin\theta^*\cos\phi^*\,A_4 .
$$

$L_0$ (unpolarised) and $A_3$ (parity-violating forward–backward term) are the only ones that are **resummed**; $A_0,A_1,A_2,A_4$ exist only from the fixed-order piece, so the grids store
them as ratios (section 3.2). The angular structure is what makes lepton cuts ($p_T^\ell$, $|\eta^\ell|$) meaningful: the same boson kinematics gives different acceptances depending on
$A_i$, and the forward–backward asymmetry changes which lepton is harder. This is the reason `resbos_root` exists instead of an integration of the boson-level grid.

### 2.3 Coupling and propagator structure

For $Z$ and $\gamma^*$ (`DY`, run as `ZU` or `ZD` = one quark class per run) the even and odd coefficients are

$$
\mathcal C^{E,O}(Q)=P_{AA}\,C^{AA}_{E,O}+2P_{ZA}\,C^{ZA}_{E,O}+P_{ZZ}\,C^{ZZ}_{E,O},
$$

$$
P_{ZZ}=\frac{Q^4}{(Q^2-M_Z^2)^2+Q^4\Gamma_Z^2/M_Z^2},\quad
P_{ZA}=\frac{Q^2(Q^2-M_Z^2)}{(Q^2-M_Z^2)^2+Q^4\Gamma_Z^2/M_Z^2}\,\frac{\alpha(Q^2)}{\alpha_{EW}},\quad
P_{AA}=\Big[\frac{\alpha(Q^2)}{\alpha_{EW}}\Big]^2 ,
$$

*(Verified, `rm` ~4413–4425: `ZZ_PROP`, `ZA_PROP`, `AA_PROP`; $\alpha(Q^2)$ is `PYALEM`)*, and $C^{XY}_{E,O}$ are products of left/right quark and lepton couplings
$(g_L^{X,q}g_L^{Y,q}\pm g_R^{X,q}g_R^{Y,q})(g_L^{X,\ell}g_L^{Y,\ell}\pm g_R^{X,\ell}g_R^{Y,\ell})$ for the flavour class selected by `IFLAV` (`Type_V = ZU` → 1, `ZD` → 2; `rr` 1295). The
photon and the interference are why the 46–66 GeV window can be computed at all. For $W^\pm$ and $Z_0$ (pure $Z$) the propagator is the plain Breit–Wigner and the couplings enter as $(f_L^2+f_R^2)$ and $(f_L^2-f_R^2)$
(`rm` 4576–4600).

---

## 3. Input files

### 3.1 `resbos.in`

| Line | Content | Used for |
|---|---|---|
| 1 | `1, ITMX1, NCALL1, ITMX2, NCALL2, ISEED` (e.g. `1,30,30000,300,100000,182019`) | VEGAS: a warm-up of `ITMX1` iterations × `NCALL1` points that **adapts the grid and is not stored**, then `ITMX2` × `NCALL2` stored points |
| 2, 3 | Main grid, Y grid (`-` for none) | sections 3.2 and 4 |
| 4 | `IWGT, iKFacP, iKFacY, iYGrid, iMatchOut, iMatchMethod` (`0,0,0,2,1,0`) | `iYGrid=2` = new Y-grid format (and forces `KFAC_ANGFUNC=2`, section 6.2); `iMatchOut=1` writes `Matched.out`; `iMatchMethod` is forced to 0 (`rr` 1029–1031) |
| 5 | `pTl_min, y_min, ΔR, pTl_max, y_max` | lepton cuts |
| 6 | `Q_min, Q_max, qT_min, qT_max, y_min, y_max` | boson cuts |
| 7 | `M_T min, max, missing-ET min` | transverse mass (W) |
| 8 | luminosity [pb⁻¹], $m_t$, $m_H$ | `WEIGHT = WT × YLUMI` (`rr` 3103); luminosity 1 gives pb |
| 9 | output (`ROOTNT1`, `ROOTNT2`, …) | ntuple variables |
| 10 | `qT_Sep, PDF, Proc, Sc, …` | `qT_Sep` is the NLO separation $q_{T,\rm sep}$ (`QT_V_SEP`) |
| 11–13 | decay mode, $M_W,\Gamma_W$, $M_Z,\Gamma_Z$ | propagators |
| 14 | `EW flag, qed flag, CKM flag, KFAC_ANGFUNC` | electroweak scheme |

With a grid of the Legacy family **no PDF is evaluated here**: for `NPART = 11…16` the code jumps over the parton-luminosity call (`rm` 1087–1088, `GOTO 224`) — the PDFs, the scales
and the Sudakov factor are already inside the grid values. The PDF set of the main grid and of the Y grid must therefore be the same (stated in the file's own notes).

### 3.2 The grids

Both are text files: **15 header lines** (the last one starts with two spaces and `Q,qT,y`; `iHeadLen`, `rr` 4442) followed by rows `Q qT y values…` on a **full rectangular mesh** (Q slowest,
then y, qT fastest; at most 200 qT, 300 y, 100 Q points). The number of columns is detected (`Column`, `rr` 4529). `PreReadIn` (`rr` 4380) counts the mesh and `ReadIn` (`rr` 3730) fills the arrays.

**Main grid** (`YAS`, `YAA`): $L_0$ and $A_3$ of the piece selected by the header's `LTO`:

| `LTO` in the header | `NPART` | Piece |
|---|---|---|
| −1 | 14 | LO |
| 0 | 11 | CSS resummed $W$ |
| 1 | 13 | $\Delta\sigma$ |
| 2 | 12 | asymptotic $A$ |

(`rr` 3967–3980: `LTOpt` → `NPart`.) Columns 4 and 5 are read as $L_0$ and $A_3$ (`rr` 4008–4009).

**Y grid, `iYGrid = 2`** (`rr` 4040–4065): `Q qT y  Sing(L0) Sing(A3)  Pert(L0) Pert(A3)  r1 r2 r4 r0`, produced by `get_yk_new` and stored as

$$
Y_0=P_0-A_0^{\rm sing},\qquad Y_3=P_3-A_3^{\rm sing},\qquad
r_1=R_{A1}\frac{A_1^P}{L_0^P},\quad r_2=R_{A2}\frac{A_2^P}{L_0^P},\quad r_4=R_{A4}\frac{A_4^P}{L_0^P},\quad r_0=R_{A0}\frac{A_2^P}{L_0^P}
$$

*(Verified: `gy` 342–347; $r_0$ and $r_2$ come from the same perturbative column, consistent with Lam–Tung $A_0=A_2$ at $O(\alpha_s)$.)* With `order = NLO` all $R_{Ai}=1$; with `NNLO`
they come from an external table.

**Limits taken from the grids** (`rr` 4355–4366):

$$
q_T^{\max}\!=\!X_{1A}(i_{D1}),\qquad y_B^{\max}\!=\!X_{2A}(i_{D2})-\Delta y,\qquad Q\in[X_{3A}(0),X_{3A}(i_{D3})]
\quad(\text{main grid}),\qquad q_T^{\max,Y}=X_{1Y}(i_{DD1})\quad(\text{Y grid}),
$$

and `PRIMARY_CUTS` rejects any event with $q_T>q_T^{\max,Y}$, $|y|>y_B^{\max}$ or $Q$ outside the main grid (`rr` 2039–2051). So **the y and Q coverage comes from the main grid and the qT coverage from the Y grid**.

---

## 4. Reading, units and the header

`ReadIn` also reads from the main-grid header: `ECMC`, the beam, `LTO`, `iSet`, the non-perturbative choice, $C_1,C_2,C_3,C_4$, `KinCorr`, the masses used in the grid (`MW_GRID`, `MZ_GRID`) and the Sudakov
orders (`rr` 3850–3915). Consequences:

* the **boson type** (`Type_V`) is taken from the grid, not from `resbos.in`;
* for `W±` and `Z0` the grid values are multiplied by $(M_V/M_V^{\rm grid})^2$ when the mass of `resbos.in` differs (`rm` 3845–3866); for `DY` this is not done;
* a grid with a single Q value (`iOneQ`) is padded with ghost points 0.001 GeV apart and the weight gets $\frac{\pi}{2}\frac{\Gamma}{0.003}$, i.e. a narrow-width treatment (`rr` 4310–4350, `rm` 4651);
* `Y_ONE_SIDE` grids (only $y\ge0$) are mirrored using the signs of the odd pieces ($A_1$, $A_3$, $A_4$).

---

## 5. Matching: how the pieces become one cross section (`MatchGrids1`, `rr` 4899)

This is the step that decides the shape of the cross section above the peak. It runs once, before the Monte Carlo, only for `NPART = 11`, and only method 0 is allowed (`rr` 1029–1031, 1183).

### 5.1 Algorithm

For every node $(Q_i, y_j)$ of the **Y grid** and for $q_T$ increasing along the Y-grid nodes (`rr` 4985–5090):

1. interpolate the main (CSS) grid at the node (4-point polynomials in each variable, section 7): $W_0=L_0^{W}(q_T,y,Q)$, $W_3=A_3^{W}$;
2. build the two candidates

$$
T_{0}=W_0+Y_0 \;(=\,P_0+W_0-A_0^{\rm sing}),\qquad T_{3}=W_3+Y_3,\qquad\text{and}\qquad P_0,\;P_3\ \text{(Pert columns)};
$$

3. **crossings:** for $q_T>1.5$ GeV (`QTV_LOW_CUT`, `rr` 5033) count the sign changes of

$$
P_0-T_0 \;=\; A_0^{\rm sing}-W_0 \;=\; -(W_0-A_0^{\rm sing}),
$$

   $n_{\times}$ increases by one every time $(P_0-T_0)_{q_T}\,(P_0-T_0)_{q_T^{\rm prev}}\le0$ (`rr` 5049); the same for $L_0$ and $A_3$ separately;
4. store in the Y array (this is the grid that the Monte Carlo will interpolate)

$$
L_0^{M}(q_T)=\begin{cases}
W_0 & q_T<1.5\ \text{GeV}\\
W_0+Y_0 & q_T\ge1.5\ \text{GeV and } n_\times<2\\
P_0 & n_\times\ge2
\end{cases}
\qquad
A_3^{M}\ \text{likewise with }W_3,Y_3,P_3 .
$$

(`rr` 5069–5078.) The columns $r_1,r_2,r_4,r_0$ are left untouched. `iMatchOut = 1` writes the three candidates and $n_\times$ to `Matched.out`.

*Interpretation:* below the first crossing $W>A$ (the resummed result dominates), then $W-A$ turns over and a second crossing means that $W+Y$ has returned to $P$: from there the fixed
order is used. If $W-A$ never crosses (it stays $\ge0$) the matched cross section is $W+Y$ for all $q_T$, i.e.

$$
L_0^{M}=P_0+\big(W_0-A_0^{\rm sing}\big)\quad\text{at all }q_T,
$$

and it equals the perturbative result only as long as $W_0-A_0^{\rm sing}\to0$.

### 5.2 Why the *main-grid* qT mesh does not have to equal the Y-grid mesh
The matched array lives on the **Y-grid** nodes; the main grid is only interpolated at them. That is why the ResBos2 W grid of `COLLIDER_RESBOS2_W_WORKFLOW.md` (89 or 99 qT points) can replace a Legacy grid (153 points)
without touching the Y grid. Y-grid nodes with $q_T$ larger than the last main-grid node are skipped (`rr` 5005: `If (qTv.GT.X1A(iD1)) Goto 232`) and keep the unmatched Y values.

### 5.3 What each matched piece does for the lepton distributions
The matched $L_0^M,A_3^M$ multiply the angular functions (section 6.2), so the resummation shapes both the boson spectrum and the lepton spectra; the ratios $r_i$ give the $\phi^*$-dependent
terms only from the fixed-order piece, which is why $p_T^\ell$ and $\eta^\ell$ distributions are most sensitive to the matching at moderate/large $q_T$.

### 5.4 Worked example: the Legacy W grid is zero for qT ≥ 2Q
`codes/legacy/res.for` sets the CSS function to 0 for $q_T\ge 2Q$ (`if(QT_V .ge. 2.0*Q_V) fresum=0`, line ~2102). On the E253 grids (ZU, $Q=50$ GeV, $y=0$; $L_0$ in grid units):

| $q_T$ [GeV] | $W$ Legacy | $W$ ResBos2 | $A$ (asymptotic) | $W-A$ Legacy | $W-A$ ResBos2 |
|---|---|---|---|---|---|
| 30 | 591.6 | 595.2 | 318.4 | +273.3 | +276.8 |
| 50 | 41.9 | 42.7 | 2.0 | +39.9 | +40.7 |
| 65 | −20.9 | −21.0 | −29.5 | +8.6 | +8.5 |
| 80 | −28.3 | −28.3 | −30.1 | +1.8 | +1.8 |
| 100 | −21.4 | −21.6 | −22.4 | +1.0 | +0.8 |
| 130 | **0** | −11.87 | −12.74 | **+12.7** | +0.87 |
| 170 | **0** | −5.33 | −6.20 | **+6.2** | +0.87 |
| 250 | **0** | −1.37 | −1.86 | **+1.9** | +0.49 |
| 400 | **0** | −0.21 | −0.36 | **+0.36** | +0.15 |

*(Verified: values from `legacy/…_ZU_main.out` and the ResBos2 grid; $A$ taken from the Legacy file, it is the same piece in both chains.)* Here $W-A\ge0$ everywhere, so there is **no crossing** and
$L_0^M=P_0+(W_0-A_0)$: with the Legacy grid the excess over the fixed order jumps from ~1 to ~13 grid units at $q_T=2Q$, with the ResBos2 grid it stays at ≲1. That excess is the origin of the
inflated $W321/NLO$ above $p_T\sim 2Q$ in the E253 46–66 GeV window.

---

## 6. The event weight

### 6.1 Phase space (`WRESPH`, `rm` 4998; called from `MAKE_EVENT`, `rm` 759)

One point is $(Q,q_T,y,\cos\theta^*,\phi^*)$ — `NDIM = 5` for the resummed case with a Y piece, 4 without it ($\phi^*$ is then random), 3 for the LO and $\Delta\sigma$ runs (`rm` 266–290).
Each variable is mapped from the unit hypercube $u_k$ with an importance-sampling function whose inverse Jacobian is multiplied into the weight:

| Variable | Mapping | Weight |
|---|---|---|
| $Q^2$ (W, Z, DY: Breit–Wigner, `rm` 5199–5210) | $Q^2=M^2+M\Gamma\tan\xi$, $\xi=\arctan x_{\max}\,u+(1-u)\arctan x_{\min}$, $x=\frac{Q^2-M^2}{M\Gamma}$ | $\dfrac{M\Gamma\,(\arctan x_{\max}-\arctan x_{\min})}{\cos^2\xi}$ |
| $q_T^2$ (`rm` 5215–5240) | $q_T^2=-\frac1b\ln\!\big[e^{-bq_{\min}^2}-(e^{-bq_{\min}^2}-e^{-bq_{\max}^2})u\big]$, $b=\dfrac{5.9-1.2}{q_{T,\max Y}^2-0.1}$ | $\dfrac{e^{-bq_{\min}^2}-e^{-bq_{\max}^2}}{b\,e^{-bq_T^2}}$ |
| $y$ | uniform in $[-y_{\max},y_{\max}]$, $y_{\max}=\operatorname{arccosh}\dfrac{s+Q^2}{2\sqrt s\sqrt{Q^2+q_T^2}}$ (`YMAXIMUM`, `rm` 5597) limited by the grid | $2y_{\max}$ |
| $\cos\theta^*,\phi^*$ | uniform | $2$ and $2\pi$ |

with $q_{T,\max}^2=\min(q_{T,\max Y}^2,\,q_{T,\rm cut}^2)$ for the resummed case with a Y piece. The $q_T$ density is a fit to the W⁺ spectrum at 1.8 TeV (`rm` comment), an importance function only: the *result* does not depend on it, the
*variance* does. The remaining factors applied by the code are $\pi/2$ (the `d^4(Q)` factor of its comment), the two-body decay phase space $\beta/[8(2\pi)^3]$ per solid angle, $1/(\pi q_T)$ and $1/(2Q^2)$ (`rm` 5331–5365); I did not rederive how they combine. The lepton four-momenta are built in the
Collins–Soper frame and boosted to the lab (`rm` 5370–5500), which is what the cuts see.

### 6.2 The matrix-element weight (`WPRES`, `rm` 3429)

`WPRES` interpolates the matched grid at $(q_T,y,Q)$ (`ThreeYInterp`; `SigS = 0` in this branch because the CSS piece is already inside the matched array, `rm` 3703) and builds

$$
\mathcal W_{\rm ME}=F\Big[\mathcal C^{E}(Q)\,\mathcal A^{E}+s\,\mathcal C^{O}(Q)\,\mathcal A^{O}\Big],\qquad F=\frac{16\pi}{3},\quad s=+1
$$

(for `DY`, `F` is written as $2\cdot\frac{\pi}{3}\cdot(4\cdot2)$, `rm` 4511–4515)
and, because `iYGrid = 2` forces `KFAC_ANGFUNC = 2` (`rr` 3944; formulas `rm` 4483–4500),

$$
\mathcal A^{E}=L_0^{M}\Big[(1+\cos^2\theta^*)+\tfrac12(1-3\cos^2\theta^*)\,r_0+\sin2\theta^*\cos\phi^*\,r_1+\tfrac12\sin^2\theta^*\cos2\phi^*\,r_2\Big],\qquad
\mathcal A^{O}=2\cos\theta^*\,A_3^{M}+\sin\theta^*\cos\phi^*\,L_0^{M}\,r_4 .
$$

So $A_{0,1,2,4}=r_{0,1,2,4}\,L_0^{M}$: the angular ratios of the O($\alpha_s$) perturbative piece are applied to the **matched** $L_0$, at every $q_T$. For $W^\pm$ and $Z_0$ the same structure appears with $4Q^4/\text{Propagator}$ and
$(f_L^2+f_R^2)$, $\pm(f_L^2-f_R^2)$ (`rm` 4576–4600, $s=-1$ for $W^-$).

The event weight is then (`WEIGHT = PHASE_WT * WTME`, `rm` 1179; $\Phi$ is the phase-space weight of 6.1)

$$
w \;=\; \Phi(Q,q_T,y,\theta^*,\phi^*)\;\mathcal W_{\rm ME},
\qquad
\sigma=\int_{[0,1]^5}\! d^5u\;w(u)\;\simeq\;\frac1N\sum_{i=1}^{N}\frac{w(u_i)}{p_{\rm VEGAS}(u_i)},
$$

where $p_{\rm VEGAS}$ is the adaptive sampling density of VEGAS ($1/p_{\rm VEGAS}$ is the importance weight $\omega_{\rm VEGAS}$ below). Note the weight **can be negative** (the matched $L_0$ can be, and NLO pieces are not positive definite).

### 6.3 VEGAS and the stored points
`FXN` (`rm` 3154) returns $w$ to VEGAS (`rm` 6595). In the warm-up (`ITMX1`) VEGAS only adapts its grid; in the main round each point is written with $w\,\omega_{\rm VEGAS}/\text{ITMX2}$ (`FXN`, `PASSER`), so the **sum of the stored weights is the cross
section averaged over iterations** and each weight is a small piece of it. With `IWGT = 0` there is no unweighting. The ntuple stores the weight multiplied by the luminosity (`WEIGHT = WT*YLUMI`).

---

## 7. Interpolation

Everywhere a grid is read, `ThreeDInterp` / `ThreeYInterp` (`rm` 5652 / 5953) use **4 points in each of $q_T$, $y$ and $Q$** (`N_QT_INTP = N_Y_INTP = N_Q_INTP = 4`, `rm` 3651, `rr` 4949) in a nested Neville polynomial (`Polin3`, `rm` 6942):
first one variable, then the next, then the third. With a polynomial of degree 3 the mesh should have at least 4 points in every direction (a grid with a single Q is padded with ghost points, section 4; the behaviour with 2 or 3 Q nodes was not tested); near the edges
the window is shifted so that it always has 4 points. *Interpretation:* anything that changes sharply between neighbouring nodes — for instance the Legacy cut at $q_T=2Q$ — is interpolated *through*, which can distort the values over the four neighbouring nodes.

---

## 8. Cuts and the output

* `PRIMARY_CUTS` (`rr` 1880): boson window $Q_{\min..\max}$ (`YM12MIN/MAX`), $q_T\in[q_{T,\min},q_{T,\max}]$, $y_{\min..\max}$, plus the hard-wired grid limits of section 3.2. For `Z0`, `A0`, `DY` the lepton cuts are applied to **both**
  leptons: $p_T^{\ell}\in[p_{T,\min},p_{T,\max}]$ and $\eta^\ell\in[y_{\min},y_{\max}]$ (`rr` 2113–2125); for `W±` the charged lepton gets $|\eta|\in[y_{\min},y_{\max}]$ and the neutrino a missing-$E_T$ cut. Then $\Delta R_{34}$ and the
  leptonic transverse mass $M_T=\sqrt{2p_T^\ell p_T^\nu(1-\cos\Delta\phi)}$.
* In the production runs of this repository the lepton cuts are **open** (`0.0, -10, 0.0, 15000.0, 99.0`) and the cuts of each measurement are applied afterwards to the ntuple.
* Output: a ROOT tree `h10` with, among others, `pT_d1, pT_d2, y_d1, y_d2, pT_B, y_B, M_B, D_phi, cos_the_, phi_sta, DelR34` and `WT00` (`rr` ~5455–5545; documented in `KineticCuts/E253.yml` of the analysis project).
  $\sum_i \text{WT00}_i\,[\text{pb}]$ over the selected points is the cross section and $\sqrt{\sum_i \text{WT00}_i^2}$ its Monte Carlo error.

---

## 9. NLO and LO modes

| Run | Main grid | Y grid | `NDIM` | Result |
|---|---|---|---|---|
| `resNLO` (`NPART=11`) | $W$ (`LTO=0`) | `Yk` | 5 | $L_0^M$ as in 5.1 |
| `nloasy` (`NPART=12`) | $A$ (`LTO=2`) | `Yk` | 5 | $q_T>q_{T,\rm sep}$: $A+(P-A)=P$ |
| `nlodsi` (`NPART=13`) | $\Delta\sigma$ (`LTO=1`) | – | 3 | $q_T=q_{T,\rm sep}$ fixed |
| LO (`NPART=14`) | LO (`LTO=-1`) | – | 3 | $q_T=0$ |

$$
\sigma_{\rm NLO}=\sigma[\Delta\sigma]_{q_T=q_{T,\rm sep}}+\sigma[A+Y]_{q_T>q_{T,\rm sep}},
$$

the sum being formed by adding the weights of the two ntuples (that is what the `hadd` of `nloasy` and `nlodsi` does in the campaigns). *(Verified: `submit_all.sh` makes `nloasy` depend on the `asy` and `Y` grids and `nlodsi` only on the `dsi` grid; `rr` 990–1000
describes `NPART`.)*

---

## 10. Practical consequences

1. **The shape above the peak is decided by $W-A$ in `MatchGrids1`.** Any W grid must continue smoothly to $A$ at high $q_T$; a grid that is cut to zero there (Legacy at $q_T\ge2Q$) leaves $P+(−A)$.
2. **Coverage:** $Q$ and $y$ are limited by the main grid, $q_T$ by the Y grid; events outside are dropped without a message. A main-grid $q_T$ range that ends before the Y grid (as with ResBos2 `qtMax = 600`) loses events near the end (the E253 test lost the 66–116 GeV bins above ~543 GeV; the line of code responsible was not traced).
3. **The Y grid carries the angular information** ($r_i$); with `order = NLO` and $R_{Ai}=1$ they are the O($\alpha_s$) perturbative ratios.
4. **PDFs, $\alpha_s$, scales, non-perturbative parameters and the Sudakov orders are fixed by the grids**; `resbos_root` cannot change them. Changing the PDF means re-running Legacy/`w_pert`/`w_asym` (and the ResBos2 grid, if used).
5. **A negative weight is not an error;** the number of events is not the statistical power, the sum of squared weights is.

---

## 11. Not covered / not verified

* The diphoton (`AA`, `AG`), `ZZ`, `ZG` and Higgs branches, the radiative-decay options (`NPART = 15, 16`) and the unweighting (`IWGT = 1`) and reweighting (`IWGT = −1, −2`) modes were not read.
* `MatchGrids2` (`iMatchMethod = 1`) exists but is disabled by the code.
* `ThreeKInterp` and the `iKFacP/iKFacY = 1` K-factor files (`rr` 4570) were not used (`0, 0` in the production inputs).
* The matching rule of section 5.1 was read in `MatchGrids1`; it was not checked line by line against a real `Matched.out` (the campaigns write one with `iMatchOut = 1`, columns `Q qT y CSS CSS+Y Pert Matched iCross`).
* The exact reason why the E253 test with a ResBos2 grid ending at $q_T=600$ GeV lost the events above ~543 GeV is not traced.
* The statements marked *interpretation* are my reading of the physics; they are consistent with the numbers checked but are not documented in the source.

## 12. Index of routines

| Routine | File : line | Role |
|---|---|---|
| `Program ResBos` / `YUAN_MAIN` | `rr` 681 / 759 | reads `resbos.in`, grids, runs VEGAS, writes output |
| `PreReadIn`, `iHeadLen`, `Column`, `Sample` | `rr` 4380, 4442, 4529, 4476 | detect header length, columns and mesh size |
| `ReadIn` | `rr` 3730 | header, masses, orders, fills `YAS`/`YAA`/`YAY`, grid limits |
| `MatchGrids1` | `rr` 4899 | CSS + Y → matched grid (section 5) |
| `GENERATOR` | `rm` 36 | sets `NDIM`, calls VEGAS |
| `FXN` | `rm` 3154 | function integrated by VEGAS, passes events to the output |
| `MAKE_EVENT` | `rm` 759 | phase space, cuts, weight |
| `WRESPH` | `rm` 4998 | phase-space generation for resummed/NLO (Q, qT, y, θ\*, φ\*; boost) |
| `YMAXIMUM` | `rm` 5597 | kinematic limit of $y$ |
| `WPRES` | `rm` 3429 | interpolation of the matched grid, couplings, propagator, angular functions |
| `ThreeDInterp`, `ThreeYInterp`, `Polin3` | `rm` 5652, 5953, 6942 | 4-point polynomial interpolation |
| `VEGAS` | `rm` 6595 | adaptive Monte Carlo integration |
| `PRIMARY_CUTS`, `SECONDARY_CUTS` | `rr` 1880, 2989 | cuts |
| `PASS_Output` | `rr` 2998 | weight × luminosity and ntuple filling |
| `get_yk_new` (separate code) | `gy` | builds the Y grid and the ratios $r_i$ |
