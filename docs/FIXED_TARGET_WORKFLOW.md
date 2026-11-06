# Fixed-target workflow: LO, NLO and resNLO (W321) as Yao computes them

This document describes how the $q_T$-integrated fixed-target Drell-Yan cross sections (E605, E866, E906) are obtained at **LO**, **NLO** and
**resNLO** (= W321 = NNLL+NLO), why they have to be **integrated in $q_T$**, and why **Legacy** is used for part of the calculation. Everything was
verified against Yao's files for E605 with his PDF (`pp830a016`); whatever could not be verified is marked as such.

Yao's sources this is based on: `New_kFactorCT25/FixedTarget_pp830a016_yao_09182026/` (`LO/`, `LegacyNLO/getnlo.cpp`, `fixedtarget.config`, `*_up2025*`) and
`New_kFactorCT25/YAORESBOS/resbos2/src/NonPertFit/FixedTarget.cc` (+ `GetFixed.cc`).

Since 2026-10-12 the whole chain is automated by `run_process.py` with `[campaign] mode = fixedtarget` (section 4.5, examples `Examples/FT_*_CT25NLO.ini`).
Sections 4.0–4.4 describe the same steps by hand, which is how they were first validated.
**The fixed-target chain runs its own Legacy binary, `bin/legacy_ft/main`, not `bin/legacy/main`; section 4.6 explains the difference and why.**

---

## 0. Summary: which variable is integrated in each experiment, and why

**In all four sets a single variable is integrated: $q_T$**, the transverse momentum of the Drell-Yan pair, from $0$ to $q_T^{\max}$.
The other variables of the measured point are **not integrated**: they are evaluated at the central value of the data table.

| | E605 (E201) | E866 pp (E204, `e866ppxf`) | E866 pd/pp (E203, `e866f`) | SeaQuest (E206, `e906aF`) |
|---|---|---|---|---|
| Collision | p + Cu, 800 GeV | p + p, 800 GeV | p + p and p + d, 800 GeV | p + p and p + d, 120 GeV |
| $\sqrt s$ per nucleon | 38.8 GeV | 38.75 GeV | 38.76 GeV | 15.07 GeV |
| Points | 119 $(y,Q)$ | 184 $(x_F,Q)$ | 15 bins in $x_2$ | 6 bins in $x_t=x_2$ |
| Measured observable | $Q^{3}\,d^{2}\sigma/(dQ\,dy)$ [nb GeV²/nucleon] | $Q^{3}\,d^{2}\sigma/(dQ\,dx_F)$ [nb GeV²/nucleon] | $\sigma_{pd}/2\sigma_{pp}$ | $\sigma_{pd}/2\sigma_{pp}$ |
| **Integrated variable** | **$q_T$** | **$q_T$** | **$q_T$** (in $pp$ and in $pd$) | **$q_T$** (in $pp$ and in $pd$) |
| Fixed at each point | $y$ and $Q$ | $x_F$ and $Q$ | $x_F$ and $Q$ | $x_F$ and $Q$ |
| $q_T$ range | $0$–$10$ GeV | $0$–$10$ GeV | $0$–$10$ GeV | $0$–$5$ GeV in `GetFixed`; $0$–$10$ GeV in `getnlo` (see 6) |
| Jacobian inside the integral | none | $dy/dx_F=\sqrt s/(2m_T\cosh y)$ | same | same |
| What is computed per point | one value | one value | $\sigma_{pp}$ and $\sigma_{pd}$ per nucleon; $\sigma_{pn}=2\sigma_{pd}-\sigma_{pp}$; the ratio $\sigma_{pd}/\sigma_{pp}$ | same |
| Legacy (`iBeam`, `FRACT_N`) | $0$, $0.54$ (Cu) | $1$, $0$ | pp: $1$, $0$; pd: $0$, $0.5$ | pp: $1$, $0$; pd: $0$, $0.5$ |

**Why $q_T$ and not the other variables:**

1. **The measurements are integrated over all $q_T$.** They are cross sections differential only in $(Q,y)$ or $(Q,x_F)$, corrected for acceptance: what the
   experiment publishes is $\int dq_T\,d\sigma/(dQ\,dy\,dq_T)$ (section 1). The theory has to sum over all $q_T$ to be comparable.
2. **The integral cannot be taken for granted at fixed order.** $P\sim\ln(Q^2/q_T^2)/q_T$ diverges at $q_T\to0$, and the divergence only cancels against the virtual
   term (at $q_T=0$). Hence the *slicing* with $\Delta\Sigma$ for the NLO (2.2). The LO sits at $q_T=0$ and is not integrated. In the resummed calculation $W$ vanishes
   at $q_T\to0$ because of the Sudakov factor and the integral converges (2.3).
3. **$Q$ and $y$ (or $x_F$) are not integrated because the table only gives the central value of each point.** There is no averaging over the bin width: for E605 the
   bin edges are not verified (`KineticCuts/E201.yml`) and for the others it would be an additional approximation. That is why the tables are point calculations.
4. **In E866 and E906 the point is at fixed $x_F$, not at fixed $y$.** With $q_T>0$ the rapidity changes, $y(q_T)<y_0$ (2.5), and the Jacobian depends on $q_T$, so it goes
   **inside** the integral. E605 is measured in $y$ and has no Jacobian. This is why `getnlo_nojac.C` (E605) and `getnlo.C` (the rest) are different macros.
5. **In E866f and E906 the measurement is a ratio**, and each target is integrated separately, with the same grid and the same cuts (section 2.6): the ratio of integrals,
   not the integral of a ratio.

Why the calculation is done at the measured points (one job per point) and not on a large grid covering the range, and why ResBos2 for W321: section 3b.

One conceptual exception: $\Delta\Sigma(q_{\rm sep})$ is not integrated numerically; it is the analytic cumulant of the asymptotic expansion up to $q_{\rm sep}$ and is added already converted.
Numerical methods: NLO with a cubic spline in $q_T$ and Simpson in $\ln q_T$ (1000 points); W321 with uniform Simpson (40 points for $W$ and $Y$ in $[10^{-4},q_T^c]$, 20 for $P$ in $[q_T^c,q_T^{\max}]$).

---

## 1. What is computed

The fixed-target measurements are cross sections **integrated over all $q_T$**:

$$
\text{E605:}\quad Q^{3}\,\frac{d^{2}\sigma}{dQ\,dy}\qquad
\text{E866/E906:}\quad Q^{3}\,\frac{d^{2}\sigma}{dQ\,dx_F}
\qquad [\mathrm{nb\,GeV^{2}/nucleon}]
$$

with

$$
\frac{d\sigma}{dQ\,dy}=\int_{0}^{q_T^{\max}(Q,y)} dq_T\;\frac{d\sigma}{dQ\,dy\,dq_T},
\qquad
q_T^{\max}\ \text{fixed by the kinematics}\ (x_{1,2}\le 1).
$$

For each measured point $(y,Q)$ three numbers are computed, and from them two ratios (K-factors):

| Symbol | Meaning | Program |
|---|---|---|
| $\sigma^{\rm LO}$ | Lowest order ($q_T=0$) | Legacy, `LTO = -1` |
| $\sigma^{\rm NLO}$ | Fixed order $\mathcal O(\alpha_s)$, integrated in $q_T$ | Legacy, `LTO = 3` and `LTO = 1` + integral |
| $\sigma^{\rm resNLO}$ | NNLL resummation ($A,B,C=3,2,1$) matched to fixed order | ResBos2 `GetFixed` |

$$
K_{\rm NLO}=\frac{\sigma^{\rm NLO}}{\sigma^{\rm LO}},\qquad
K_{\rm res}=\frac{\sigma^{\rm resNLO}}{\sigma^{\rm NLO}}
$$

(these are the `NLO/LO` and `w321/NLO` columns of Yao's `*_up2025_w321` files).

---

## 2. Physics: why one has to integrate in $q_T$

### 2.1 CSS decomposition

The differential cross section in $q_T$ is written as a resummed term plus a correction term:

$$
\frac{d\sigma}{dQ^{2}\,dy\,dq_T}\;=\;W(Q,q_T,y)\;+\;Y(Q,q_T,y),
\qquad
Y \equiv P - A .
$$

* **$W$ (resummed piece)**: Fourier–Bessel transform in impact-parameter space $b$,

$$
W \;\propto\; \int_{0}^{\infty} db\; b\, J_{0}(q_T b)\;\widetilde W(b_*,Q,x_1,x_2)\,e^{-S_{\rm NP}(b,Q,x_1,x_2)},
\qquad
b_*=\frac{b}{\sqrt{1+b^{2}/b_{\max}^{2}}},
$$

$$
\widetilde W(b,Q,x_1,x_2)=e^{-S(b,Q)}\,
\big[C\otimes f\big](x_1,\tfrac{b_0}{b})\,\big[C\otimes f\big](x_2,\tfrac{b_0}{b}),
\qquad b_0=2e^{-\gamma_E},
$$

$$
S(b,Q)=\int_{C_1^{2}/b^{2}}^{C_2^{2}Q^{2}}\frac{d\bar\mu^{2}}{\bar\mu^{2}}
\left[A\big(\alpha_s(\bar\mu)\big)\ln\frac{C_2^{2}Q^{2}}{\bar\mu^{2}}+B\big(\alpha_s(\bar\mu)\big)\right],
$$

with $A=\sum_n (\alpha_s/\pi)^n A^{(n)}$, and similarly for $B$ and $C$. The non-perturbative form used is BLNY,

$$
S_{\rm NP}=\Big[g_1+g_2\ln\frac{Q}{2Q_0}+g_1 g_3\ln(100\,x_1x_2)\Big]b^{2},
\qquad (g_1,g_2,g_3)=(0.21,\,0.68,\,-0.126),\ Q_0=1.6\ \mathrm{GeV},\ b_{\max}=0.5\ \mathrm{GeV^{-1}}.
$$

The factor $e^{-S}$ (Sudakov) makes $W\to 0$ when $q_T\to 0$, so **the integral of $W$ converges**.

* **$A$ (asymptotic piece)**: fixed-order expansion of $W$ for $q_T\ll Q$. At order $\alpha_s$,

$$
A(q_T)\;\sim\;\frac{\alpha_s}{\pi}\,\frac{1}{q_T}\Big[V_{12}\,L^{2}+V_{11}\,L+V_{10}\Big],
\qquad L\equiv\ln\frac{Q^{2}}{q_T^{2}},
$$

(the coefficients $V_{ij}$ involve the PDFs and the splitting functions; see `DeltaSigma::CalcTerms` in ResBos2).

* **$P$ (perturbative piece)**: fixed-order $\mathcal O(\alpha_s)$ calculation for $q_T>0$, valid at $q_T\sim Q$.
  When $q_T\to 0$, $P\to A$, and both diverge as $\ln(Q^2/q_T^2)/q_T$.

* **$Y=P-A$** is finite at $q_T\to0$ and corrects $W$ at large $q_T$. One has $W+Y\to P$ where $W\simeq A$.

### 2.2 The fixed-order problem and the *slicing*

Since $P\sim \ln(Q^2/q_T^2)/q_T$, the integral $\int_0 P\,dq_T$ **diverges**. In the real NLO calculation that divergence cancels against the
virtual term, which contributes at $q_T=0$ ($\delta(q_T)$). It is solved with *phase-space slicing*: the integral is split at $q_{\rm sep}$:

$$
\boxed{\;
\sigma^{\rm NLO}(Q,y)=\underbrace{\Delta\Sigma(q_{\rm sep})}_{0\le q_T\le q_{\rm sep}}
+\underbrace{\int_{q_{\rm sep}}^{q_T^{\max}} dq_T\;P(q_T)}_{q_T>q_{\rm sep}}\;}
$$

where $\Delta\Sigma(q_{\rm sep})$ is the **analytic cumulant** of the asymptotic expansion up to $q_{\rm sep}$ (it includes the zeroth-order term, the virtual part and the
integrated logarithms):

$$
\Delta\Sigma(q_{\rm sep})=\sigma^{(0)}+\frac{\alpha_s}{\pi}\Big[V_{12}\,L_{\rm sep}^{2}+V_{11}\,L_{\rm sep}+V_{10}\Big],
\qquad L_{\rm sep}=\ln\frac{Q^{2}}{q_{\rm sep}^{2}},
$$

with $\sigma^{(0)}$ the $q\bar q\to\gamma^*$ term (the LO). The result **must not depend on $q_{\rm sep}$**; Yao checks this by varying $q_{\rm sep}\in[0.01,0.1]$ GeV (the NLO changes by $0.07\,\%$ while the $\int P$ part alone changes from $1.02$ to $0.26$).

### 2.3 The matched resummation (resNLO / W321)

$W+Y$ describes the whole range, but at large $q_T$ $W$ starts to fail, and $W+Y\to P$ there. Yao integrates in two regions,
switching to pure $P$ at $q_T^{c}$, the point where $W=A$ (root of $W-A$, by Brent's method):

$$
\boxed{\;
\sigma^{\rm resNLO}(Q,y)=\int_{0}^{q_T^{c}}dq_T\,\big[W+Y\big]\;+\;\int_{q_T^{c}}^{q_T^{\max}}dq_T\;P
\;}
\qquad
W(q_T^{c})=A(q_T^{c})\ \Rightarrow\ W+Y=P\ \text{(continuity)}.
$$

`W321` = Sudakov orders $(A,B,C)=(3,2,1)$ ⇒ NNLL, matched with $Y$ at $\mathcal O(\alpha_s)$ (NLO). `W432` would be N$^3$LL+NNLO.
With `AsymOrder = 1` and `PertOrder = 1` the correction factor $y_k$ of the $Y$ piece is $1$ (it is only used in W432).

In Yao's code (`FixedTarget.cc`, `GetFixed`) the integration is uniform Simpson: 40 points in $[10^{-4},q_T^c]$ for $W$ and $Y$,
20 points in $[q_T^c,q_T^{\max}]$ for $P$, with $q_T^{\max}=10$ GeV (5 GeV in E906).

### 2.4 LO

$$
\frac{d\sigma^{\rm LO}}{dQ^{2}\,dy}\;\propto\;\sum_q e_q^{2}\,\big[f_q(x_1)\,f_{\bar q}(x_2)+f_{\bar q}(x_1)\,f_q(x_2)\big],
\qquad x_{1,2}=\frac{Q}{\sqrt s}\,e^{\pm y},
$$

with no $q_T$ dependence (everything at $q_T=0$). Therefore **$K_{\rm NLO}=\sigma^{\rm NLO}/\sigma^{\rm LO}$ only makes sense with the NLO already integrated**.

### 2.5 Unit conversions and Jacobians

Legacy delivers $d\sigma/dQ^{2}\,dy\,(\ldots)$ in pb. To get to $Q^{3}\,d\sigma/dQ\,dy$ in nb:

$$
Q^{3}\frac{d\sigma}{dQ\,dy}=\underbrace{\frac{Q^{3}}{1000}\,2Q}_{\text{pb}\to\text{nb},\ dQ^{2}=2Q\,dQ}\;\frac{d\sigma}{dQ^{2}\,dy}.
$$

For E866/E906 the observable is in $x_F$, and at fixed $m_T$ ($x_F=2m_T\sinh y/\sqrt s$):

$$
\frac{dy}{dx_F}=\frac{\sqrt s}{2\,m_T\cosh y},\qquad m_T=\sqrt{Q^{2}+q_T^{2}} .
$$

This Jacobian depends on $q_T$ and therefore goes **inside** the integral:

$$
\mathrm{conv}(Q,y,q_T)=\frac{Q^{3}}{1000}\,2Q\;\times\;
\begin{cases}
1 & \text{E605 (in } y)\\[4pt]
\dfrac{\sqrt s}{2\sqrt{Q^{2}+q_T^{2}}\,\cosh y} & \text{E866, E906 (in } x_F)
\end{cases}
$$

$$
\sigma^{\rm NLO}=\int_{q_{\rm sep}}^{q_T^{\max}}\!dq_T\,P\;\mathrm{conv}(Q,y,q_T)
+\Delta\Sigma(q_{\rm sep})\,\mathrm{conv}(Q,y,0).
$$

**Warning:** applying the Jacobian to E605 produces an error of $\approx-0.3\,\%$ in the NLO; E605 does not carry it.

#### Experiments in $x_F$: the rapidity depends on $q_T$ (finding with E866ppxf)

For E866/E906 the measured point is at **fixed $x_F$**, not at fixed $y$. With $q_T>0$,

$$
x_F=\frac{2\,m_T\sinh y}{\sqrt s}\;\Longrightarrow\;
y(q_T)=\operatorname{asinh}\!\Big(\frac{x_F\sqrt s}{2\sqrt{Q^{2}+q_T^{2}}}\Big)\;<\;y_0\equiv y(q_T{=}0),
$$

and the integrand has to be evaluated at that $y(q_T)$, not at the $y_0$ of the table:

$$
\sigma^{\rm NLO}=\int_{q_{\rm sep}}^{q_T^{\max}}\!dq_T\;P\big(q_T,\,y(q_T)\big)\,
\frac{Q^{3}}{1000}\,2Q\,\frac{\sqrt s}{2\,m_T\cosh y(q_T)}
+\Delta\Sigma(q_{\rm sep})\,\mathrm{conv}(Q,y_0,0).
$$

With $y$ fixed at $y_0$ (as `getnlo.cpp` does in its test point) the NLO of E866ppxf comes out $-0.86\,\%$ (RMS $1.3\,\%$, down to $-3.2\,\%$) below
the one implied by the `up2025` columns, with a strong correlation with $|y|$ ($-0.89$). Evaluating at $y(q_T)$ the bias drops to $-0.2\,\%$
and the RMS to $\approx0.5\,\%$. This requires running Legacy LTO=3 on a $y$ grid per point (10 values between $y(q_T{=}10)$ and $y_0$)
and interpolating in $y$ for each $q_T$ (interpolation of $\ln P$ with PCHIP). `KinCorr=0` does not change the result. **Not automated in `run_process.py`.**

### 2.6 Ratio measurements: E203 (E866f) and E206 (SeaQuest)

These two measurements are not a cross section but $R=\sigma_{pd}/2\sigma_{pp}$ in bins of $x_2$ ($x_t$ in SeaQuest). To compute it at each order, $\sigma_{pp}$ and
$\sigma_{pd}$ are integrated in $q_T$ **separately**, both per nucleon and in $Q^{3}\,d^{2}\sigma/(dQ\,dx_F)$ (same Jacobian in $x_F$, same $q_T$ grid, same $q_T^{\max}$):

* **pp:** Legacy with `iBeam=1`, `FRACT_N=0`.
* **pd:** Legacy with `iBeam=0`, `FRACT_N=0.5`. This gives the **per-nucleon average** of the deuteron, $\sigma_{pd}^{\rm (per\ nucleon)}=\tfrac12(\sigma_{pp}+\sigma_{pn})$, with no nuclear effects of the deuterium.
* **pn:** $\sigma_{pn}=2\,\sigma_{pd}^{\rm (per\ nucleon)}-\sigma_{pp}$, order by order (LO, NLO, W321). $\sigma_{pd}-\sigma_{pp}$ does not work, because $\sigma_{pd}$ is already per nucleon and
  $\sigma_{pd}-\sigma_{pp}=\tfrac12(\sigma_{pn}-\sigma_{pp})$, not $\sigma_{pn}$.
* **Ratio:** $R_{\rm order}=\sigma_{pd}^{\rm (per\ nucleon)}/\sigma_{pp}$ $\;(=\sigma_{pd}/2\sigma_{pp}$ with $\sigma_{pd}$ of the full deuteron$)$.

Two kinds of K-factor, which are not the same thing:

* **K per target** (what CTEQ's `*_up2025` files carry): $K_{\rm proton}=K_{pp}$ and $K_{\rm neutron}=K_{pn}$, each $\sigma^{\rm NLO}/\sigma^{\rm LO}$ and $\sigma^{\rm W321}/\sigma^{\rm NLO}$ of the corresponding target.
  These are the four columns `NLO/LO(neutron)`, `W321/NLO(neutron)`, `NLO/LO(proton)`, `W321/NLO(proton)`.
* **K of the ratio:** $K_R=R_{\rm W321}/R_{\rm NLO}$ (and $R_{\rm NLO}/R_{\rm LO}$). Neither $K_{pn}$ nor $K_{pn}/K_{pp}$ alone corrects the ratio (`KineticCuts/FIXED_TARGET_README.md`).
  With CT25NLO it comes out very close to 1 ($0.996$–$1.004$ for W321/NLO and $1.004$–$1.019$ for NLO/LO, E203 and E206 together): the order cancels between $pd$ and $pp$, and the ratio is mostly sensitive to the PDF's $\bar d/\bar u$.

---

## 3. Why Legacy

* **LO and NLO are not computed by `GetFixed`.** `FixedTarget.cc` (ResBos2) only implements the resummed total $\sigma^{\rm resNLO}$. Although ResBos2 contains the
  classes `DeltaSigma`, `Asymptotic` and `Perturbative` (with which the NLO could be assembled), that path is **not implemented in Yao's code**.
* **Legacy delivers each piece separately and per $q_T$ point** (according to the `LTO` field of `legacy.in`):

| `LTO` | Output | Use here |
|---|---|---|
| `-1` | LO | $\sigma^{\rm LO}$ |
| `0` | Full CSS, 4 columns | Not used (the resummation is done in ResBos2) |
| `1` | $\Delta\Sigma(q_T)$ | $q_T<q_{\rm sep}$ term of the NLO |
| `2` | $A(q_T)$ asymptotic | Check only |
| `3` | $Y$ and $P$ (3 lines per point) | $P$ = third number of the 2nd line |

* **Yao** combines the two tools: Legacy for LO and NLO (running `getnlo.cpp` on its outputs) and ResBos2 `GetFixed` for W321.
  Both use **the same PDF** (Yao's `pp830a016`), which is essential for the K-factors to be consistent.
* ResBos2 (`GetCalc(Q,pT,y)`) evaluates $W$, $A$ and $P$ at any $(Q,q_T,y)$, so it does not need a $q_T$ grid beforehand.
  Legacy, on the other hand, needs an explicit $q_T$ grid and interpolates it.

---

## 3b. Why compute at the experiments' points and not on a large grid

The measurements are **discrete points**: 119 $(y,Q)$ in E605, 184 $(x_F,Q)$ in E866 pp, 15 bins in $x_2$ in E866f and 6 in SeaQuest. Yao computes exactly those points, **one job per point**
(one task of a SLURM array with a single $y$ and a single $Q$ and the whole list of $q_T$), instead of a $(Q,q_T,y)$ grid covering the whole range. Which parts of what follows are
documented and which are reasoning is indicated in each case.

### 3b.1 Why a large grid is not convenient

*Documented (this repository's README, `LOG.md` of `KFactor_Raw_simulations`):*

1. **Almost everything that would be computed would not be used.** A rectangular $(Q,y)$ grid fills the whole rectangle and the data are a few points of it. With the unique values of the table,
   E866f (15 points) would give $15\times15=225$ grid points, 93 % wasted; E605 is the exception (119 points in $18\times7=126$, 6 % wasted) and that is why a grid **was** used there
   (the old `E201_e605_fine.ini`).
2. **A fine grid avoids the holes, but it is neither cheap nor clean.** On the rectangle that encloses the data, the kinematically valid fraction (LO limit, $|y|<\ln(\sqrt s/Q)$) is
   100 % in E605, 99 % in E906, 89 % in E866f and 71 % in E866 pp: the fine grid is **not** "almost all impossible" (an earlier statement of that kind was retracted, see `LOG.md` 8.6; the 93 % only
   applies to the unique-values grid). But the cost grows: the E605 fine-grid test was $40\ Q\times25\ y=1000$ combinations against 119 measured points, about 8 times more.
3. **The grid route goes through the Monte Carlo (`resbos`) and event binning**, which has its own problems here: the bin edges are not in the tables (those of E605 are not verified),
   there is Monte Carlo noise at high $Q$, $pd$ needs an asymmetric range in $y$ and the ratios need two campaigns on the same grid. The E605 grid campaign with `resbos`
   (`E201_e605_CT25NLO_resNLO_NLO.ini`, $40\ Q\times25\ y$) was **cancelled** because it does not reproduce Yao's K-factors (`LOG.md` 12.5).
4. **`resbos` requires a full rectangle.** Its `CheckSum` check demands $N_Q\times N_y\times N_{q_T}=$ number of rows of the Legacy main grid; a set of scattered points does not satisfy it,
   and unlike `R_Ai` those rows are physical values that cannot be padded with ones (README, section *ExpCustomGrid*).

*Reasoning (not measured):* a coarse grid forces **interpolation** in $Q$ and in $y$, and the calculation at the exact point has no such error. The reproduction of Yao's files (LO to $4\times10^{-5}$,
W321 with no difference) shows that the per-point chain is deterministic and reproducible.

### 3b.2 Advantages of the per-point calculation

* Only what was measured is computed.
* No interpolation between grid points and no Monte Carlo noise; the result is deterministic.
* Each point directly gives its K-factor, which is what the fit uses, with LO, NLO and W321 at **the same coordinates**.
* It does not depend on the bin edges.
* It parallelises trivially (119 independent jobs in E605).

Drawbacks: there are no events, so other cuts or other distributions cannot be obtained without new runs; many jobs have to be launched (SLURM limits a user to 1000 queued tasks,
and every task of an array counts); and every new data set needs its own run.

### 3b.3 Why ResBos2 for W321

`GetFixed` (`FixedTarget.cc`) calls `GetCalc(Q, pT, y)`, which evaluates $W$, $A$ and $P$ **at any point, without a $(Q,q_T,y)$ grid**. The only precomputed objects are the `ConvGrids`
(`C1`, `C1P1`, `C1P1P1`, `C1P2`, `C2`: PDF $\otimes$ coefficient convolutions). They depend only on the PDF and the scheme, not on the experiment's kinematics: they are generated **once per PDF** (the first
run of `GetFixed`, time not measured) and all experiments reuse them.

The integration is **adaptive in $q_T$** (2.3): it scans $q_T$ to locate the peak and the zero of $W$, obtains with Brent's method the root of $W-A$ (the $q_T^c$ where it switches to pure $P$) and only then integrates with
Simpson (40 points in $[10^{-4},q_T^c]$ and 20 in $[q_T^c,q_T^{\max}]$). With a fixed $q_T$ grid that crossing could only be obtained by interpolation, which is the reason already stated in section 3:
ResBos2 does not need a $q_T$ grid beforehand and Legacy does. *It is not documented why Yao chose ResBos2 beyond this*; Legacy can also run a single point, and in fact does so for LO and NLO.

### 3b.4 How it is done in Legacy

**Grid mode** (collider, `run_process.py` with `mode = collider`): a shared rectangular $(Q,q_T,y)$ grid of $80\times153\times143=1\,750\,320$ points (`inp/q_grid*.inp`, `qt_grid.inp`, `y_grid.inp`);
`w_pert`, `w_asym` and Legacy (`LTO=3` and `LTO=0`) run on the same grid, split in $Q$ in SLURM arrays; `get_yk_new` combines them and `resbos` interpolates them.

**Per-point mode** (Yao's, with his `run_points.sb` and `combine.sh`; in `run_process.py` it is `mode = fixedtarget`, section 4.5):

1. One array task per $(y,Q)$ point of the table, with its own `JOB<i>/` folder containing `main` and `legacy.in`.
2. `inp/` holds a single $Q$ (`q_grid_test.inp`), a single $y$ (`y_grid.inp`) and the complete list of $q_T$ (`qt_grid.inp`: 47 values in Yao's LO runs, 138 in the NLO runs, fine below $0.09$ GeV).
3. `./main` is run once per piece: `LTO=-1` (LO), `LTO=3` ($P$ and $Y$) and `LTO=1` ($\Delta\Sigma$), changing the `LTO` field of the second line of `legacy.in`.
4. `combine.sh` concatenates the `legacy.out` of all the `JOB<i>`, removing the 15 header lines; then `getnlo.C` integrates in $q_T$ (4.2).

```bash
sbatch --array=1-119%40 run_points.sb <workdir> <table>      # LO: one task per point, 40 at a time
sbatch --dependency=afterok:<ID> --wrap="bash combine.sh <workdir> 15 119 <output>"
```

Size comparison: the collider grid mode is 1.75 million shared $(Q,q_T,y)$ points; the E605 per-point mode is 119 points $\times$ 138 values of $q_T$ $=16\,422$ evaluations
per Legacy piece (`LTO=3`, `LTO=1`), each with its own exact $(y,Q)$.

---

## 4. Step-by-step workflow

Notation: `<exp>` ∈ {`e605`, `e866f_pp`, `e866f_pd`, `e866ppxf`, `e906aF_pp`, `e906aF_pd`}. The data table has $y$ in column 1, $Q$ in column 2 (and $x_F$ in column 3 for E866/E906);
the name `<exp>` fixes the beam and the ECM inside `GetFixed`.

### 4.0 Environment (HPCC)

* Dependencies: GCC 13.2, Yao's LHAPDF and HOPPET (`/mnt/home/fuyao3/GCC13/...`), ROOT 6.30.02 and `OpenSSL/1.1`. `setup.sb` builds ResBos2 against them (`ONLY=resbos2`).
* Connection: `ssh msu-dev` with `ControlMaster` (see `HPCC_CONNECTION.md`); open it with `ssh -fN msu-dev` and confirm with `ssh -O check msu-dev`.
* **PDF.** `pp830a016` in `~/InstallSources/LHAPDF` **is not** Yao's (1 member, MZ 91.1870 versus 3 members, MZ 91.1876).
  Use Yao's copy: `~/InstallSources/LHAPDF_YaoPDFs/` (locally: `New_kFactorCT25/PDFs_Yao/`). CT25NLO exists only in the user's LHAPDF.

### 4.1 LO — Legacy `LTO = -1`

One job per $(y,Q)$ point (SLURM array `1-N`), with Yao's `main` and his `legacy.in` (E605: line 1 `0,0.54d0,1,0`, line 2 `38.8,-1,0`):

```bash
sbatch --array=1-119%40 run_points.sb <workdir> <workdir>/<exp>        # JOB<i>/ with inp/q_grid_test.inp, y_grid.inp
sbatch --dependency=afterok:<ID> --wrap="bash combine.sh <workdir> 15 119 <exp>_LO.txt"
```

Output: `<exp>_LO.txt` (`Q  0  y  value  0`). $\sigma^{\rm LO}=\text{value}\times\mathrm{conv}(Q,y,0)$.

### 4.2 NLO — Legacy `LTO = 3` and `LTO = 1` + integral

1. Same scheme, with the 138-value $q_T$ grid `LegacyNLO/inp/qt_grid.inp` ($10^{-4}$ to $9.059$ GeV, fine at $q_T<0.09$).
   Two runs per point: `LTO = 3` (field 2 of line 2 of `legacy.in`) and `LTO = 1`.
2. Integration: **Yao's ROOT macro**, unchanged (`scripts/getnlo/getnlo.C`; `getnlo_nojac.C` for E605), run once per point by `scripts/run_getnlo.sh`:

```bash
source $ROOT/bin/thisroot.sh
bash scripts/run_getnlo.sh "$PWD/scripts/getnlo/getnlo_nojac.C" 38.8 119 138 work/e605    # macro, ECM, points, qT values per point, folder with lto3.txt and lto1.txt
```

`run_getnlo.sh` cuts the merged LTO=3 and LTO=1 outputs into the files the macro reads for one point (`nlo_y.log`, `nlo_delsig.log`, `nlo_asy.log`), calls `root -l -b -q "getnlo.C(ECM)"` and keeps the first line it prints
(qT_sep = 0.01); the result is `work/e605/getnlo_results.txt` (`i only_pert NLO`, already in $Q^3\,d\sigma/dQ/d\{y|x_F\}$). The macro is `getnlo.cpp` of Yao with two changes (standard ROOT includes instead of his private
`Figure.h`, and ECM as an argument): cubic spline (`TSpline3`) of $P(q_T)$ and of $\Delta\Sigma(q_T)$, Simpson in $\ln q_T$ with 1000 points from $q_{\rm sep}=0.01$ to $q_T^{\max}=10$ GeV, plus $\Delta\Sigma(q_{\rm sep})$.
`getnlo.C` applies the $x_F$ Jacobian $\sqrt s/(2m_T\cosh y)$ inside the integral and $\sqrt s/(2Q\cosh y)$ in the $\Delta\Sigma$ term (E866, E906); `getnlo_nojac.C` does not (E605). $q_{\rm sep}$ and $q_T^{\max}$ are fixed in the macro.
Until 2026-10-21 a Python port of this macro (`scripts/yao_nlo_integrate.py`) did this step; it was removed so that the integral is exactly Yao's code.

### 4.3 resNLO / W321 — ResBos2 `GetFixed`

Working directory with `fixedtarget.config`, `<exp>` (the data table behind 6 header lines), `<exp>_pert.txt` and the folders `Grids/` and `ConvGrids/`:

```bash
source bin/resbos2/env_getfixed.sh            # written by setup.sb (ONLY=resbos2); Yao's libraries and Yao's PDF folder first
mkdir -p Grids ConvGrids                      # the program does NOT create them on every write path
cp <Yao>/ConvGrids/<PDF>_0_Conv_*.out ConvGrids/   # if the PDF is Yao's; with another PDF they are generated in the first run
GetFixed <exp>                                # writes <exp>_ResBos2_w321.dat
```

Key parameters of `fixedtarget.config` (W321): `AOrder=3, BOrder=2, COrder=1`, `AsymOrder=1`, `PertOrder=1`, `Scale=MT`, `KinematicCorrection=true`,
`NonPert=BLNY`, `bMax=0.5`, `Q0=1.6`, `g=0.21, 0.68, -0.126`, `PDF=<set>`, `iSet=0`.

Output: `y  Q  data  total  ∫W  ∫Y  ∫pert`, with total $=\int W+\int Y+\int P_{\rm high}$ already multiplied by $\mathrm{conv}$.

> `GetFixed` ends with exit code 1 (`return 1` in `main`): SLURM marks it `FAILED` even if the result is valid.

### 4.4 K-factors and final table

$$
K_{\rm NLO}=\frac{\sigma^{\rm NLO}}{\sigma^{\rm LO}},\qquad
K_{\rm res}=\frac{\sigma^{\rm resNLO}}{\sigma^{\rm NLO}}\qquad(\text{columns }\texttt{NLO/LO},\ \texttt{w321/NLO}).
$$

Reference result: `hpcc_result/yao_repro_e605_pp830a016/e605_LO_NLO_W321_table.txt` (in the old repository `ResbosLegacy_v.2026.1`)
(`y Q data LO NLO W321 NLO/LO W321/NLO | NLO/LO and W321/NLO of up2025`).

### 4.5 Automated: `run_process.py` with `mode = fixedtarget`

Steps 4.1–4.4 are chained by `run_process.py`: `python3 run_process.py Examples/FT_<set>_CT25NLO.ini --submit`, with `<set>` ∈ {`e605`, `e866ppxf`, `e866f`, `e906aF`}.
For each target (pp, pd or the single one) it creates:

* a Legacy array with one task per point, which runs `LTO=-1`, `3` and `1` in the same folder (`legacy/<target>/points/pt<N>/`);
* a merge job (removes the 15 header lines and checks the row count: LO 1 per point, LTO=1 one per $q_T$, LTO=3 three per $q_T$);
* a `GetFixed` job (its output is validated by the number of rows, not by the exit code);
* a final job that sources ROOT, runs Yao's `getnlo` macro on every point (`run_getnlo.sh`) and then `make_fixedtarget_tables.py`, and writes `results/<set>_<PDF>_LO_NLO_W321.txt`.

The Legacy `.in` files come from the template `templates/FixedTarget/legacy/fixedtarget_legacy.in` (Yao's `legacy.in` from `LegacyNLO/`, with a 138-value $q_T$ grid); `GetFixed` uses
`templates/FixedTarget/resbos2/fixedtarget.config` with only the PDF rewritten. The data tables are in `templates/FixTargetTables/`. The first `GetFixed` job of a PDF generates the
`ConvGrids` and the other targets wait for it (`[fixedtarget] convgrids` reuses a finished set). Not included: the fixed-$x_F$ treatment (2.5) and W432.
The Legacy executable is `<bin>/legacy_ft/main` (section 4.6); `[executables] legacy = <file>` overrides it, e.g. with Yao's own `main`. To reproduce Yao's numbers exactly also use his PDF folder
(`[fixedtarget] lhapdf_data_path`) and his HOPPET.
**Status:** the four sets (`e605`, `e866ppxf`, `e866f`, `e906aF`) have run on the HPCC with `legacy_ft` and reproduce the tables of `KFactor_Raw_simulations` (4.6.4).

### 4.6 Which Legacy binary: `legacy_ft` and not `legacy`

#### 4.6.1 What is different

ResbosFlow builds two Legacy executables from two source folders that are identical except for three lines:

| | `bin/legacy/main` | `bin/legacy_ft/main` |
|---|---|---|
| Source | `codes/legacy/` | `codes/legacy_ft/` (a full copy of `codes/legacy/`) |
| Used by | collider chain (`mode = collider`: W±, Z0, ZU, ZD) | fixed-target chain (`mode = fixedtarget`) |
| `Type_V = 'A0'` normalisation override | **active** | **commented out** |

The three lines (`pert.for` twice, `res.for` once) are, in the `Type_V = 'A0'` branch (the virtual photon of Drell-Yan, which is what fixed target computes):

```fortran
          CONST=PI*ACOUPL*2.0/3.0 ! yfu test 2024.10.13 (override)      ! codes/legacy
c         CONST=PI*ACOUPL*2.0/3.0 ! yfu test 2024.10.13 (override)      ! codes/legacy_ft
```

To see it: `diff -r -x README.md codes/legacy codes/legacy_ft` (must print exactly those three lines). `setup.sb` builds both (`ONLY=resbos_legacy`, or `ONLY=legacy_ft` alone);
`run_process.py` in fixed-target mode reads `<[executables] dir>/legacy_ft/main` unless `[executables] legacy = <file>` is given. The collider mode is untouched.

#### 4.6.2 Why

Without the override, the `A0` branch sets the normalisation $\sigma_0$ of the photon with its decay into leptons,
$\sigma_0 = \pi^2\frac43\alpha(Q)\cdot\frac{\alpha(Q)}{3\pi Q^2} = \frac{4\pi\,\alpha(Q)^2}{9\,Q^2}$ (`alpha(Q)` = `PYALEM`, running). The override replaces it by $2\pi\,A_{\rm coupl}/3$, a constant with no
$\alpha(Q)^2/Q^2$. The result is that every Legacy output of the chain (LO, `LTO = 3` and `LTO = 1`, hence the NLO) is larger by the same factor

$$\frac{\sigma_0^{\rm override}}{\sigma_0}=\frac32\,\frac{A_{\rm coupl}\,Q^2}{\alpha(Q)^2}\sim 1250\,Q^2 ,\qquad A_{\rm coupl}=\sqrt2\,M_W^2 G_\mu\,2\sin^2\theta_W = 0.04734 .$$

* The ratio NLO/LO is **not** affected (the factor is common), so the K-factors $K_{NLO/LO}$ were right; the absolute LO and NLO were not, and $W321/NLO$ (ResBos2 over Legacy) was wrong by that factor.
* Yao's source (`legacy_final_version`, September 2026) has the line commented, with the note *"when comment out this line, the legacy direct output can be used for LO calculation, maybe adding this line, legacy grid can be used for events"*.
  `codes/legacy` has the line active (as the code was copied). Per Yao's note the override is for the case where the `A0` grid feeds event generation; no campaign here does that.
* W+, W−, Z0 take other branches (`WCOUPL`, `ZCOUPL`) and ZU/ZD set `NO_SIGMA0`, so the **collider results do not depend on this line** and the collider chain keeps `codes/legacy`.
* The `FT_*.ini` runs of 2026-10-14 used `bin/legacy/main` and produced the factor; the tables of `Simulations/` (E201, E203, E204, E206) were made on 2026-10-09 with Yao's own binaries
  (`~/InstallSources/YaoRepro`: his `LO_e605/main` and `NLO_e605/main`, his `getnlo.C` and the `GetFixed` of his build), which is why they never showed it.

Why a second source folder and not a patch inside `setup.sb`: a plain `diff -r` shows the difference at any time, the executable is built from files that exist in the repository, and nothing is edited at build time.
**Rule: a fix made in `codes/legacy/` must be copied to `codes/legacy_ft/`.**

#### 4.6.3 What is still different from Yao's chain

* `ACC_RERR` (relative accuracy of the integrals) is $10^{-7}$ in our Legacy (edit of 2026-10-08), $10^{-4}$ in Yao's. It is in both of our folders. It is the likely origin of the $10^{-5}$–$10^{-4}$ residual in the NLO (4.6.4); not isolated.
* HOPPET 1.3.0-devel (ours) versus 1.2.0 (Yao): `GetFixed` W321 differs by 0.13 % rms (section 5b). Legacy links HOPPET too; the agreement of LO and NLO to 5 digits with Yao's binaries (4.6.4) shows no visible effect in those pieces.
* The NLO is integrated with Yao's own ROOT macro (4.2); there is no difference in the integrator.
* The Legacy template and `fixedtarget.config` of `Examples/CT25NLOLegacy/templates/` are Yao's (git HEAD of 2026-10-12); those of `templates/` carry the mass alignment of 2026-10-14 (W 80.385, Z 91.1876, light quark masses and $m_t=172$ in `GetFixed`).

#### 4.6.4 Verification (E906/E206, 6 points, pp and pd)

1. First point ($Q = 4.791$ GeV, $y = 0.7717$, same `legacy.in`), raw `LTO = -1` output: Yao's `main` 0.076312362; **`legacy_ft` 0.076312362**; `legacy` 2203.1 (2211.2 with the later template masses).
2. The predicted factor above against the observed `bin/legacy` over Yao, at $Q$ = 4.79 … 6.46 GeV: 2.887·10⁴ / 2.898·10⁴ … 5.215·10⁴ / 5.228·10⁴ (0.2–0.4 %).
3. `FT_e906aF` run through the driver with Yao's `main` and then with `legacy_ft`, compared with `Simulations/` (ratio of the run to the table, 12 points):

| | LO | NLO | W321 |
|---|---|---|---|
| run / `Simulations` | 1.00000 | 0.99993 – 0.99999 | 0.9977 – 1.0026 |

   The W321 spread is the HOPPET version. The same campaign with commented templates (`Examples/CT25NLOLegacy/`) gives a bit-identical result table.

The other three sets were then run with the same `Examples/CT25NLOLegacy/FT_*_CT25NLO_Legacy.ini` (344 jobs, no failure), compared with `Simulations/` point by point (ratio of the run to the table):

| Set (experiment) | Points | LO | NLO (rms, min – max) | W321 (rms, min – max) |
|---|---|---|---|---|
| `e605` (E201) | 119 | 1.00000 | 5·10⁻⁵, 0.9998 – 1.0002 | 6·10⁻⁴, 0.9969 – 1.0027 |
| `e866ppxf` (E204) | 184 | 1.00000 | 1.5·10⁻⁴, 0.9990 – 1.0009 | 2.8·10⁻³, 0.9852 – 1.0175 |
| `e866f` (E203), pp and pd | 15 each | 1.00000 | 2·10⁻⁵, 0.99995 – 1.00002 | 6·10⁻⁴, 0.9985 – 1.0010 |

The LO is identical in every row. The NLO differs at the $10^{-5}$–$10^{-4}$ level. That is **not** the integrator: the same four sets re-integrated with Yao's own ROOT macro (`getnlo.C`, the chain's integrator since 2026-10-21) give the same NLO as the Python port that was used for the table above, to $4\times10^{-6}$ rms, and the ratios to `Simulations` do not change (E201 5·10⁻⁵, E204 1.5·10⁻⁴, E203 2·10⁻⁵, E206 4·10⁻⁵ rms). What is left is in the Legacy outputs (`ACC_RERR` $10^{-7}$ against Yao's $10^{-4}$ is the known difference; not isolated). The W321 differences are expected from the HOPPET version (1.3.0-devel against 1.2.0); the larger spread of E204 was not investigated.
The `FT_*` tables imported earlier into the HPCC workspace `KFactorsCT25R2` were made with the old binary and should be redone. `docs/CT25_COLLIDER_CAMPAIGNS_REPORT.md` section 4.7 records the original finding; `LOG.md` section 1j the investigation.

---

---

## 5. Validation performed (E605, Yao's PDF)

| Piece | Comparison | Result |
|---|---|---|
| LO | Yao's `e605_LO.txt` | **119/119 rows identical** |
| W321 | Yao's `e605_ResBos2_w321.dat` (total, ∫W, ∫Y, ∫pert) | **119/119 rows identical** (4 columns) |
| NLO integrator | Yao's logs of a single point ($q_{\rm sep}=0.01,0.05,0.09$) | agrees to 6 digits |
| $K_{\rm NLO}$ (E605) | `NLO/LO` column of `up2025` | median $-0.107\,\%$, RMS $0.13\,\%$, range $[-0.24,+0.15]\,\%$ |
| LO, W321 (E866ppxf, E866f pp/pd, E906aF pp/pd) | Yao's files | **identical** in the 5 sets |
| $K_{\rm NLO}$ (E866ppxf, $y$ fixed) | `up2025` | median $-0.86\,\%$, RMS $1.3\,\%$, range $[-3.2,0]\,\%$ |
| $K_{\rm NLO}$ (E866ppxf, $x_F$ fixed) | `up2025` | median $-0.2\,\%$, RMS $0.5\,\%$ |
| $K_{\rm NLO}$ (E866f, E906aF; $y$ fixed) | `up2025` | RMS $0.44$–$0.48\,\%$ and $0.03$–$0.05\,\%$ |
| $K_{\rm res}$ | `w321/NLO` column of `up2025` | median $+0.107\,\%$, RMS $0.13\,\%$ |

The $0.1\,\%$ residual in the NLO is **not explained**: it does not change with $q_{\rm sep}\in[0.01,0.03]$, with the integration rule (logarithmic or linear),
with the spline type, with the $\Delta\Sigma$ interpolation, with $q_T^{\max}\in[9,12]$ or with `DelSigOrder` 1 or 2 (identical results).
The script that produced the `up2025` columns is not in Yao's folder.

---

## 5b. Results with CT25NLO (same chain, Yao's integrator as is)

Computed with the same tools validated above (Legacy `main` and Yao's `getnlo.cpp`, `GetFixed`), changing only the PDF to `CT25NLO`
(`lha_CT25NLO` in each `legacy.in`, `PDF = CT25NLO` in `fixedtarget.config`). E605 uses `getnlo_nojac.C` (Yao's macro without the two factors
$\sqrt s/(2m_T\cosh y)$, as `FixedTarget.cc` does for `e605`; validated against the Python port to $6.5\times10^{-6}$; that port was removed on 2026-10-21, the chain now runs the macro itself).
Tables in `hpcc_result/ct25nlo_fixedtarget/` of the old repository (generated with `scripts/make_fixedtarget_tables.py`):
`e605`, `e866ppxf`, `e866f` (pp, pd, pn and ratio), `e906aF` (same), all with `LO`, `NLO`, `W321` and the K-factors.

| Set | points | $K_{\rm NLO}$ | $K_{\rm res}$ |
|---|---|---|---|
| E605 | 119 | 1.50 – 1.90 | 0.96 – 1.19 |
| E866ppxf | 184 | 1.42 – 2.06 | 0.65 – 1.14 |
| E866f | 15 | proton 1.50 – 1.66; neutron 1.51 – 1.69 | — |
| E906aF | 6 | proton 1.86 – 1.98; neutron 1.93 – 2.04 | — |

Compared with the K of `up2025` (PDF `pp830a016`): $K_{\rm NLO}$ changes ≲1–2 % (E605: median $+0.1\,\%$); $K_{\rm res}$ ≲ 1–5 %, except the points of
E866ppxf with $x_F\gtrsim0.67$ and $Q\approx4.5$–$5$ GeV, where CT25NLO's W321 is $20$–$30\,\%$ larger than that of `pp830a016`
(large-$x$ region, where the two PDFs are expected to differ; it was not verified that this is the only cause).
`ConvGrids/CT25NLO_*` are generated in the first run of `GetFixed` (5 files; the remaining 3 of Yao's PDF are only for W432).

**SLURM limit on the HPCC:** 1000 queued tasks per user (every task of an array counts); with 6 sets they have to be submitted in batches.

## 6. Pending items and warnings

* **CT25NLO:** done (section 5b). The `ConvGrids/CT25NLO_*` (5 files) were generated in the first `GetFixed` run.
* **Different $q_T^{\max}$ in E906:** `GetFixed` integrates W321 up to 5 GeV in E906 and `getnlo` integrates the NLO up to 10 GeV. $P$ is zero outside the phase space, but with $\sqrt s=15$ GeV
  the kinematic limit ($\approx6.8$ GeV at $y=0$, $Q\approx4.8$ GeV) lies above 5 GeV, so W321 might lose a small tail that the NLO does include. The effect on $W321/NLO$ of E906 has not been quantified.
* **No acceptance in E906:** the calculations are pointwise; folding with the $x_b$-dependent acceptance (Extended Data Table 3 of SeaQuest) is missing. There are also no nuclear corrections in E605 (Cu) or in the deuterium of E866 and E906.
* **E866f and E906aF are ratios** $\sigma(pd)/2\sigma(pp)$ and their `up2025` carry two pairs of K-factors. They are reproduced with
  $K_{\rm proton}=K_{pp}$ and $K_{\rm neutron}$ computed with $\sigma_{pn}=2\sigma_{pd}-\sigma_{pp}$ (applied separately to LO, NLO and W321);
  Legacy with `FRACT_N=0.5` gives the per-nucleon average, and $\sigma_{pd}-\sigma_{pp}$ does not work.
* **Fixed $x_F$** (see 2.5) tested only on E866ppxf; not yet applied to E866f and E906aF, and not automated in the driver.
* **W432** requires `<exp>_pert.txt` generated with `w_pert` (one job per point) for the $y_k$ factor; not covered here (the driver writes an empty `_pert.txt`, which is fine for W321).
* **PDF trap:** the name `pp830a016` exists in two different LHAPDF installs with different grids. With the wrong one W321 differs by up to $6\,\%$ from Yao's.
* **Modified Legacy:** `codes/legacy/{pert,pert_vj,res}.for` and `codes/resbos/resbosm.f` carry the resNLO-kinematics edits that were never committed in the old repository. The tables of sections 5 and 5b use
  Yao's binaries. The driver now runs `bin/legacy_ft/main` (section 4.6: same sources, `A0` override off); `bin/legacy/main` must not be used for fixed target (LO and NLO ~1250 $Q^2$ too large).
* **Units of $P$:** the integrator assumes the convention with which `getnlo.cpp` integrates directly in $q_T$ (`P·pT` in $\ln q_T$);
  it was not verified independently that $P$ is $d\sigma/dq_T$ and not $d\sigma/dq_T^{2}$, but the reproduction of Yao's numbers supports it.

---

## 7. How it enters the analysis project (`KFactor_Raw_simulations`)

The simulations are run on the HPCC with this chain; the analysis (tables, plots, final K-factors) lives in `KFactor_Raw_simulations`, which **does not run** simulations.
The results are copied to `Simulations/<generator>/` with the naming convention `{beam}_{ECM}{TeV|GeV}_{PDF}_{PROCESS}_{CUTS}_{ORDER}.txt`,
for example `pCu_38.8GeV_CT25NLO_DY_E201_NLO.txt` (ORDER = `LO`, `NLO` or `resNLO`, with `resNLO` = W321):

| Piece | `Simulations/` folder | Produced by (section) |
|---|---|---|
| LO and NLO | `ResbosLegacy/` | Legacy `LTO=-1`; Legacy `LTO=3` and `LTO=1` integrated with Yao's `getnlo.C` (4.1, 4.2) |
| W321 (`resNLO`) | `Resbos2/` | ResBos2 `GetFixed` (4.3) |
| Yao's results (PDF `pp830a016`) | `Yao/` | his files; **the NLO is derived**: LO $\times$ his `NLO/LO` of `*_up2025_w321` (there is no absolute NLO file). Before writing them it is checked that LO $\times K_{\rm NLO/LO}\times K_{\rm W321/NLO}=$ W321 to $10^{-5}$ in the four sets, which also validates the unit conversions |

An independent chain with Yao's PDF (E605) reproduces his LO to $4\times10^{-5}$, his W321 exactly and his NLO to $0.25\,\%$ (the residual of 5).
For E203 and E206 there is one file per beam (`pp_...` and `pd_...`); $\sigma_{pn}$ and the ratio are formed when reading (2.6).

```bash
python import_fixed_target.py                                   # HPCC tables and Yao's folder -> Simulations/ (checks coordinates and K before writing)
python extract_tables.py --only E201 E203 E204 E206 --Yao       # -> DataTablesFromResbos/ (LO, NLO, W321, K, statistics against the data in the header)
python plot_dcross.py --only E201 E203 E204 E206 --order NLO, resNLO --yao --kfactor --format both
python make_final_tables.py --only E201 E203 E204 E206          # -> KResults/: original data2025d table + KNLO/LO and KW321/NLO (per target in E203/E206)
```

The points are matched with the data table by $(y,Q)$, not by position. Details of the decisions and of what is pending: `KFactor_Raw_simulations/LOG.md` (sections 20 to 25).
