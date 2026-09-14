#!/usr/bin/env bash
# DISABLED 2026-09-10 by decision: the 7x5 matrix at N=40 was dropped from the chain.
#
# WHY. N=40 does not resolve differences of the size we are chasing. Measured on this harness:
# standoff220 read bo3 2.15 at N=40 and 1.53 at N=100, while the control read 1.80 at N=40 and
# 1.60 at N=100 -- sampling alone moves bo3 by 0.2-0.6, which is larger than every candidate
# delta observed so far. The matrix would have cost ~5.8 h to produce 35 cells no single one of
# which could be trusted, and its per-candidate mean, while more stable, is a broad screen we do
# not currently need: the candidate set is already narrow.
#
# That time goes to N=100 on the arms that matter instead (see run_confirm_n100.sh).
#
# The original script is preserved as run_matrix.sh.disabled. Restore it if a broad screen is
# ever wanted again -- but run it at N>=100, or not at all.
#
# The sentinel below is deliberate: the confirmation pass is chained to this log line, so
# emitting it hands control straight on rather than stalling the queue.
echo "[matrix] SKIPPED at N=40 by decision 2026-09-10; see run_matrix.sh.disabled"
echo "[matrix] done"
