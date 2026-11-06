#!/bin/bash
# run_getnlo.sh -- NLO of every point of one fixed-target table with Yao's ROOT macro (getnlo.C / getnlo_nojac.C), as ~/InstallSources/YaoRepro/run_getnlo_gen.sh.
#
#   run_getnlo.sh <macro.C> <ecm> <npoints> <nqt> <workdir>
#
# <workdir> holds lto3.txt (Legacy LTO=3, 3 lines per qT and point) and lto1.txt (LTO=1, 1 line per qT and point), both with the 15 header lines removed and the
# points in table order; <nqt> is the number of qT values per point (138). For each point it cuts its lines into nlo_y.log / nlo_delsig.log / nlo_asy.log (the
# macro reads these names; asy = delsig as Yao does), runs `root -l -b -q "<macro>(<ecm>)"` and keeps the first "only_pert  NLO" line (qT_sep = 0.01).
# Writes <workdir>/getnlo_results.txt: "i only_pert NLO" per point (already converted to Q^3 dsigma/dQ/d{y|xF}). Needs ROOT in the PATH. Exit 1 if a point fails.
set -u
MACRO=$1; ECM=$2; N=$3; NQT=$4; W=$(cd "$5" 2>/dev/null && pwd) || { echo "ERROR: folder $5 not found"; exit 1; }   # absolute: the loop changes directory
[ -s "$W/lto3.txt" ] && [ -s "$W/lto1.txt" ] || { echo "ERROR: $W/lto3.txt or lto1.txt missing"; exit 1; }
command -v root >/dev/null || { echo "ERROR: root not in PATH (source thisroot.sh)"; exit 1; }
[ "$(wc -l < "$W/lto3.txt")" = "$((3*NQT*N))" ] || { echo "ERROR: lto3.txt has $(wc -l < "$W/lto3.txt") lines, expected $((3*NQT*N))"; exit 1; }
[ "$(wc -l < "$W/lto1.txt")" = "$((NQT*N))" ] || { echo "ERROR: lto1.txt has $(wc -l < "$W/lto1.txt") lines, expected $((NQT*N))"; exit 1; }
: > "$W/getnlo_results.txt"
for ((i=1;i<=N;i++)); do
  P=$(mktemp -d "$W/pt.XXXXXX"); cd "$P" || exit 1
  sed -n "$(( (i-1)*3*NQT + 1 )),$(( i*3*NQT ))p" "$W/lto3.txt" > nlo_y.log
  sed -n "$(( (i-1)*NQT + 1 )),$(( i*NQT ))p" "$W/lto1.txt" > nlo_delsig.log
  cp nlo_delsig.log nlo_asy.log
  root -l -b -q "$MACRO($ECM)" 2>/dev/null | grep -E '^[0-9.eE+-]+  [0-9.eE+-]+$' | head -1 | awk -v i=$i '{print i, $1, $2}' >> "$W/getnlo_results.txt"
  cd "$W" && rm -rf "$P"
done
n=$(wc -l < "$W/getnlo_results.txt")
[ "$n" = "$N" ] || { echo "ERROR: getnlo gave $n results for $N points"; exit 1; }
echo "getnlo: $n points -> $W/getnlo_results.txt"
