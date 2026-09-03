"""Round-robin league: every candidate config against every opponent archetype.

WHY THIS EXISTS. Every configuration decision in this project has been taken against ONE
opponent at a time -- the cutoff binary, or a mirror of ourselves -- and that has misled us
twice. F37 rejected the wide envelope on the peer rig while the cutoff column liked it; F48
adopted hybrid_gated's ranking from a cutoff run that F54 then voided entirely. A config tuned
against a single benchmark is tuned against that benchmark's quirks.

WHAT IT MEASURES. The competition adjudicates a timeout on DAMAGE DIFFERENTIAL
(COMPETITION_RULES.md Sec 5), and draws are our modal outcome, so `dealt - taken` is the number
that decides matches -- not win rate, and not kills. This ranks on **mean differential across
the whole roster**, with **worst-case differential** as the tiebreak: a minimax pick, so we
ship the least exploitable config rather than the one that beats the cutoff hardest.

WHAT IT REUSES. Nothing here is new machinery:
  * parallel dispatch + failed-arm relaunch  -- the pattern from sweep_vs_cutoff.py
  * per-side controller config                -- eval_v5_vs_bt.py's --{side}-vptrack-* flags
  * scoring on the competition's own scale    -- summarize_h2h.py / summarize_cutoff.py

    python scripts/league.py --episodes 50 --jobs 6
    python scripts/league.py --summarize

CAVEAT ON THE ARCHETYPES. `sniper` is a GoGoSSung ANALOGUE built from broadcast footage of five
of its wins, not a replica -- see OPPONENTS_ANALYSIS.md. A row reading "beat sniper 60%" must
never be read as "beat GoGoSSung 60%".
"""
from __future__ import annotations

import argparse
import csv
import glob
import subprocess
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_PY = sys.executable
_OUT = _ROOT / "artifacts" / "eval"

# ---- Candidates: what we might ship. Ownship side. ------------------------------------
# Flags mirror the SHIP_* constants in student/controller_providers.py; `ship` is the current
# adopted config (F59) and is the control every other row is read against.
CANDIDATES: dict[str, list[str]] = {
    "ship_6000_120_deck": ["--ownship-vptrack-range-m", "6000", "--ownship-vptrack-los-deg", "120",
                           "--ownship-vptrack-throttle", "1", "--ownship-vptrack-hard-deck", "1000"],
    "alt_8000_90_deck":   ["--ownship-vptrack-range-m", "8000", "--ownship-vptrack-los-deg", "90",
                           "--ownship-vptrack-throttle", "1", "--ownship-vptrack-hard-deck", "1000"],
    "prev_6000_90":       ["--ownship-vptrack-range-m", "6000", "--ownship-vptrack-los-deg", "90",
                           "--ownship-vptrack-throttle", "1"],
}

# ---- Archetypes: who we might face. Target side. --------------------------------------
# See OPPONENTS_ANALYSIS.md "Archetype roster" for what each one represents and why these five
# span the axis that actually decides our matches: willingness to trade damage.
ARCHETYPES: dict[str, list[str]] = {
    # Extend-and-clock. The real independent opponent; declines the re-merge and banks the clock.
    # NOTE: `cutoff` is NOT a valid --target-backend on eval_v5_vs_bt.py (choices are rl/bt/
    # vptrack/hybrid*/fixed/autopilot/loiter) -- it is injected by the eval_vs_cutoff.py wrapper.
    # launch() dispatches this archetype there instead; passing it through the normal path exits
    # rc=2 on argparse before a single episode runs.
    "cutoff":    ["--cutoff-action-repeat", "6"],
    # A peer at our level -- the previously shipped config.
    "mirror":    ["--target-backend", "vptrack",
                  "--target-vptrack-range-m", "6000", "--target-vptrack-los-deg", "90",
                  "--target-vptrack-throttle", "1"],
    # GoGoSSung ANALOGUE (low confidence -- see module docstring). Narrow envelope reproduces
    # "engages rarely, retains health"; nothing we have reproduces its salvo behaviour.
    "sniper":    ["--target-backend", "vptrack",
                  "--target-vptrack-range-m", "2500", "--target-vptrack-los-deg", "45",
                  "--target-vptrack-throttle", "1"],
    # Forces decisive merges and trades freely. Deck guard on, or it just flies into the ground.
    "aggressor": ["--target-backend", "vptrack",
                  "--target-vptrack-range-m", "6000", "--target-vptrack-los-deg", "120",
                  "--target-vptrack-throttle", "1", "--target-vptrack-hard-deck", "1000"],
    # Rule-based floor. Never shoots (HANDOFF.md), so it is a sanity check, not a real opponent.
    "bt_only":   ["--target-backend", "bt"],
}


def _csv_path(cand: str, arch: str, scenario: str) -> Path:
    return _OUT / f"league_{scenario}__{cand}__vs__{arch}.csv"


def run(args: argparse.Namespace) -> None:
    _OUT.mkdir(parents=True, exist_ok=True)
    cands = args.candidates or list(CANDIDATES)
    archs = args.archetypes or list(ARCHETYPES)
    pairs = [(c, a) for c in cands for a in archs if c in CANDIDATES and a in ARCHETYPES]
    if args.skip_existing:
        pairs = [(c, a) for c, a in pairs
                 if not _csv_path(c, a, args.scenario_mode).exists()]
    print(f"[league] {len(pairs)} pairs, scenario={args.scenario_mode}, "
          f"episodes={args.episodes}, jobs={args.jobs}", flush=True)

    queue = list(pairs)
    running: list[tuple[tuple[str, str], subprocess.Popen, object]] = []
    started: dict[tuple[str, str], float] = {}
    relaunched: set[tuple[str, str]] = set()
    done: list[tuple[str, str, int, float]] = []

    def launch(pair: tuple[str, str]) -> None:
        cand, arch = pair
        out = _csv_path(cand, arch, args.scenario_mode)
        # The cutoff opponent lives behind its own wrapper (see ARCHETYPES["cutoff"]).
        entry = "eval_vs_cutoff.py" if arch == "cutoff" else "eval_v5_vs_bt.py"
        cmd = [
            _PY, str(_HERE / entry),
            "--ownship-backend", "vptrack",
        ] + (["--target-backend", "cutoff"] if arch == "cutoff" else []) + [
            "--scenario-mode", args.scenario_mode,
            "--episodes", str(args.episodes),
            "--seed", str(args.seed),
            "--out-csv", str(out.relative_to(_ROOT)),
        ] + CANDIDATES[cand] + ARCHETYPES[arch]
        log = out.with_suffix(".log").open("w", encoding="utf-8")
        proc = subprocess.Popen(cmd, cwd=str(_ROOT), stdout=log, stderr=subprocess.STDOUT)
        started[pair] = time.time()
        running.append((pair, proc, log))
        print(f"[league] start {cand} vs {arch}", flush=True)

    while queue or running:
        while queue and len(running) < args.jobs:
            launch(queue.pop(0))
        time.sleep(5)
        for entry in list(running):
            pair, proc, log = entry
            if proc.poll() is None:
                continue
            running.remove(entry)
            log.close()
            el = time.time() - started[pair]
            # Relaunch once: a crashed arm otherwise vanishes from the matrix with only a
            # non-zero rc in a log tail (this is how env_r8000_l90 became a 6-episode row).
            if proc.returncode != 0 and pair not in relaunched:
                relaunched.add(pair)
                print(f"[league] FAILED {pair[0]} vs {pair[1]} rc={proc.returncode} "
                      f"-- relaunching once", flush=True)
                queue.append(pair)
                continue
            done.append((pair[0], pair[1], proc.returncode, el))
            print(f"[league] done  {pair[0]} vs {pair[1]} rc={proc.returncode} "
                  f"in {el/60:.1f} min", flush=True)

    print("\n[league] all finished")
    for c, a, rc, el in done:
        print(f"  {c:<22} vs {a:<10} rc={rc} {el/60:>6.1f} min")
    bad = [(c, a) for c, a, rc, _ in done if rc != 0]
    if bad:
        print(f"\n  !! {len(bad)} pair(s) still failing after one relaunch: {bad}")
        print("     Treat a non-zero rc as a real result to investigate, not noise.")


def _load(path: Path) -> dict | None:
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    if not rows:
        return None
    n = len(rows)
    w = l = d = kills = 0
    dealt = taken = 0.0
    for r in rows:
        ph = (r.get("phased_outcome") or "").strip().lower()
        dealt += float(r.get("ep_damage_dealt") or 0)
        taken += float(r.get("ep_damage_taken") or 0)
        if (r.get("end_condition") or "").strip() == "target destroyed":
            kills += 1
        if ph == "win":
            w += 1
        elif ph == "loss":
            l += 1
        else:
            d += 1
    return {"n": n, "w": w, "d": d, "l": l, "kills": kills,
            "dealt": dealt / n, "taken": taken / n, "diff": (dealt - taken) / n}


def summarize(args: argparse.Namespace) -> None:
    archs = list(ARCHETYPES)
    rows: dict[str, dict[str, dict]] = {}
    for path in sorted(_OUT.glob(f"league_{args.scenario_mode}__*.csv")):
        stem = path.stem[len(f"league_{args.scenario_mode}__"):]
        if "__vs__" not in stem:
            continue
        cand, arch = stem.split("__vs__", 1)
        got = _load(path)
        if got:
            rows.setdefault(cand, {})[arch] = got

    if not rows:
        print("no league CSVs found -- run without --summarize first")
        return

    present = [a for a in archs if any(a in v for v in rows.values())]
    head = f"{'candidate':<22}" + "".join(f"{a:>13}" for a in present) + f"{'MEAN':>9}{'WORST':>9}"
    print(f"\nDAMAGE DIFFERENTIAL (dealt - taken, per episode) -- scenario={args.scenario_mode}")
    print(head)
    print("-" * len(head))
    ranked = []
    for cand, per in rows.items():
        diffs = [per[a]["diff"] for a in present if a in per]
        mean = sum(diffs) / len(diffs) if diffs else float("nan")
        worst = min(diffs) if diffs else float("nan")
        ranked.append((mean, worst, cand, per))
    for mean, worst, cand, per in sorted(ranked, reverse=True):
        line = f"{cand:<22}"
        for a in present:
            line += f"{per[a]['diff']:>+13.3f}" if a in per else f"{'--':>13}"
        print(line + f"{mean:>+9.3f}{worst:>+9.3f}")
    print("-" * len(head))
    print("Ranked on MEAN differential; WORST is the minimax tiebreak (least exploitable).")

    print(f"\nW/D/L and kills")
    for _, _, cand, per in sorted(ranked, reverse=True):
        parts = [f"{a}: {per[a]['w']}/{per[a]['d']}/{per[a]['l']} ({per[a]['kills']}k)"
                 for a in present if a in per]
        print(f"  {cand:<22} " + "  ".join(parts))
    print("\nNOTE: `sniper` is a GoGoSSung ANALOGUE, not a replica -- do not read these rows "
          "as results against GoGoSSung.")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--episodes", type=int, default=50)
    p.add_argument("--jobs", type=int, default=6)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--scenario-mode", default="match_base",
                   choices=["match_base", "match_tiebreak"])
    p.add_argument("--candidates", nargs="*", default=None)
    p.add_argument("--archetypes", nargs="*", default=None)
    p.add_argument("--skip-existing", action="store_true",
                   help="Skip pairs whose CSV already exists.")
    p.add_argument("--summarize", action="store_true")
    args = p.parse_args()
    summarize(args) if args.summarize else run(args)


if __name__ == "__main__":
    main()
