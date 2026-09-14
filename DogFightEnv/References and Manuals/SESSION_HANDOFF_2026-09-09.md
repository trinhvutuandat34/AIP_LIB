# Session handoff - 2026-09-09

> ## ⚠️ SUPERSEDED IN PART — read this before acting on anything below (added 2026-09-11)
>
> This document is kept as the record of what the 2026-09-09 session knew. Three of its
> load-bearing claims are now false, and two of them cost real time on 2026-09-11 before being
> caught. **Verify against `SESSION_HANDOFF_2026-09-11.md` first.**
>
> 1. **Sec 4 item 2 — the standoff arm is NOT pending. It was run, and it LOST.** Fifteen
>    standoff CSVs exist. `confirm_standoff200_gated` at n=100 came back **bo3 +0.00,
>    win −1.0% (−0.14 SE)**, and `scripts/league.py:249` records that the ungated version
>    "lost its N=100 confirmation (bo3 1.53 vs 1.60) after looking strong at N=40."
>    `STANDOFF_M` ships OFF. The overshoot *geometry* is real; the aim-point lever does not
>    fix it. **Closed, negative.**
> 2. **Sec 2 — `deckttc_on` is NOT "the one never-measured knob."** It was measured the next
>    morning, 2026-09-10, n=25 across all five archetypes
>    (`artifacts/eval/league_match_base__deckttc_on__vs__*`). Result: a wash. Still ships OFF.
> 3. **Every number in this document was measured on the WRONG SPAWN BAND.** The organizers
>    confirmed on 2026-09-11 that the real band is 2,000–30,000 ft (609.6–9,144 m) at
>    200–300 m/s, not the 1,000–7,700 m / 150–280 m/s proxy every run here used. ~37% of the
>    real spawn space was never sampled, and the real floor (609.6 m) sits **below**
>    `SHIP_HARD_DECK_M` (1,000 m), a case the old band made impossible to observe.
>
> Sec 1 (the first gate trace) and Sec 3 (what was built) remain accurate.

**Extends `SESSION_HANDOFF_2026-09-08.md`.** Its Sec 5 priority list is still correct. This
session closed its item 3 (the knob sweep) with two negatives, took the first BT gate trace in
the project's history, and left one new lever measured-ready.

Git branch: `tgc/envelope-6000-90-round4-baseline`. **Nothing was committed.**

**5 days to the deadline: 2026-09-14 12:00 noon.**

---

## 0. One line

The defensive layer is **measured** dead rather than suspected dead, the two remaining
never-measured knobs are now **measured negatives**, and the overshoot (median closest approach
19.9 m against a 152.4 m zero-damage floor) is the one live explanation left, with the first
instrument for it built and unit-tested but not yet run.

## 1. The first gate trace ever taken

`GateTrace.h` has been compiled into the DLL for weeks and had never been switched on;
`scripts/audit_unreachable_nodes.py` had never been run. Both were, on the current DLL
(crc32 `1131281049`), 6 episodes of `match_base` self-play at the shipped 6000/120 config:

    set AIP_BT_GATE_TRACE=D:\aip_lib\DogFightEnv\Release\artifacts\gate\trace.csv
    set AIP_BT_GATE_TRACE_ALL=1      # the REJECTED gates are the evidence; without this only winners show
    set AIP_BT_GATE_TRACE_FIRST=1200
    python scripts/audit_unreachable_nodes.py artifacts/gate/trace.csv

**`Gate1_DefensiveSpiral` is reached 7,287 times and succeeds 0 times.** Both decorators pass;
the node itself refuses. NOT one dead constant. An earlier reading in this same session said the
154 m/s (~299 kt) speed line was unreachable and **that was wrong** - it came from episode MEANS.
Per-episode *minimum* TAS is median 305.3 kt and 9 of 20 episodes dip below it. What never
coincides is the three-way fresh-claim conjunction: only 15% of the reached ticks had
`Distance < 2000 m`, and the dips are brief. Fixing it needs the claim relaxed in TIME
("was slow recently"), which is real blackboard state and a DLL rebuild.

**Nothing breaks when we are being shot at.** On ticks where the bandit holds a gun solution on
us inside the scoring band: `Gun_Track` **61.5%**, `Gate2_NoseToNoseTurn` 15.4%,
`Gate4_LagPursuit` 12.8%, `Gate1_JinkingTurn` **7.7%**. 61.5% of those are the mutual case (our
own ATA also under 8 deg), which trips the `Gate1_*_NotGunSolution_OwnATA_Ge8` carve-out on
**every** Gate 1 branch. While we track, no defensive gate can fire, by construction.

**The gun branch barely gets the stick.** `Gun_DistGt152p4` 15,611 to `Gun_DistLt914` **1,056**
(6.8%) to `Gun_OwnATA_Lt8` **31** (2.9%) to `Gun_Track` **31 = 0.2% of ticks**. Range binds, not
angle.

Reading caveats: `Record` logs the first `FIRST` ticks per tree **plus only path changes**, so
read ratios not totals; the capture was self-play, so `Gate3_Ratio_Gt1_4` at 0/11,279 is symmetry
not a defect; the file carries a **repeated header** (one per tree init), so skip non-numeric
rows when parsing. Re-run against `cutoff` before generalising the threat table.

## 2. Two knobs measured, both rejected

N=40/cell against the N=100 shipped control in `artifacts/eval/ab_fixed_0908/`.

**`corner_on` - rejected, and its mechanism refuted.** The stale-premise correction was real:
`controller_providers.py` cited 339.6 kt from 2026-08-07, and the current DLL measures
**506.4 kt** mean, so `CORNER_KT = 440` now *decelerates*. It still lost - WEZ-entry cutoff
60.0 to 47.5%, aggressor 72.0 to 65.0%, sniper 91.0 to **65.0% (z = -3.75)**; damage differential
vs cutoff -0.078 to -0.191. **And the radius story does not survive its own test:** below-floor
moved only 80.0 to 82.5% vs the cutoff, and against `sniper`, the archetype we do *not* overshoot
into, slowing made the overshoot **worse** (median min range 242 to 102 m). Speed is not what
puts us at 20 m.

**`defensive_on` - rejected; F26-DEFENSIVE is now closed rather than parked.** It was kept off
pending "an opponent that out-shoots us, e.g. the cutoff". That opponent rejected it: wins
38% to **15%**, dealt 0.471 to 0.301, and damage **taken went UP**, 0.549 to 0.605; differential
-0.078 to -0.304. Against the cutoff the break does not even deny damage, it only spoils our own
solution - consistent with its own blind spot, `_losing_gun_duel()` requiring `152.4 <= rng`
while the median closest approach is ~20 m.

`deckttc_on` remains the one never-measured pre-existing knob.

## 3. What was built, all default-OFF

- **`STANDOFF_M`** (`student/controller_providers.py`) plus `--{side}-vptrack-standoff-m`,
  plumbed through `eval_v5_vs_bt.py` and `run_local_dogfight.py`. Inside the radius the aim point
  slides toward the target's six by `(standoff - rng)`, **capped at the range**. First thing in
  this stack to bias the AIM POINT; both existing range mechanisms are throttle-only and throttle
  cannot arrest a merge. League candidates `standoff220_deck` / `standoff400_deck` added.
- **`scripts/test_standoff_aimpoint.py`** - and it earned its keep twice. An uncapped lag puts
  the aim point *behind us* at 30 m, pushing `los_deg` past the 120 deg cone so `_tracking_stick`
  silently returns `None` and hands the aircraft to the BT: the knob would have disabled the
  controller in exactly the geometry it was built for. It also pins a known null - in a
  co-aligned stern chase the standoff cannot move the stick at all, because this law's roll is a
  function of error DIRECTION only, not magnitude.
- **`experiments/rule_variants/gate1_threat_break.xml`** - a Gate-1 branch above the carve-outs,
  firing when their ATA <= 4 deg and ours >= 4 deg inside 152.4-914.4 m. `DECO_LOSCheck` already
  reads `Los_Degree_Target`, so **no C++ and no DLL rebuild**. Shipped XML untouched. UNVALIDATED
  against the runtime - see Sec 4.

## 4. Do this next, in order

1. **Validate the XML variant before trusting any run of it.** Per F70 a failed Rule-XML load is
   caught in C++, printed to stdout, and turned into an all-zero `ControlValue` that still
   handshakes at 60 Hz - a dead tree and a healthy one are indistinguishable from outside. And
   **these files cannot be linted with a standards parser**: all three shipped Rule XMLs contain
   a double hyphen inside comments, so `xml.etree` rejects them while tinyxml2 accepts them. Run
   one episode, assert `Behavior Tree Initialized` appears, and confirm `Gate1_ThreatBreak` shows
   up in a gate trace.

2. **The standoff arm** - the one live explanation for the overshoot:

       python scripts/league.py --candidates standoff220_deck standoff400_deck --archetypes cutoff aggressor sniper --episodes 40 --chunk-episodes 40 --jobs 3 --seed 20260909

   Screen on **WEZ-entry rate and `ep_min_distance`**, and check `ep_damage_dealt` alongside:
   `corner_on` is the cautionary case where a knob moved min range the right way and still lost.

3. **The threat-break A/B**, ours-only because the cutoff runs its own binary:

       python scripts/eval_vs_cutoff.py --ownship-backend vptrack --target-backend cutoff --scenario-mode match_base --episodes 40 --seed 20260909 --bt-rule-xml experiments/rule_variants/gate1_threat_break.xml --ownship-vptrack-range-m 6000 --ownship-vptrack-los-deg 120 --ownship-vptrack-throttle 1 --ownship-vptrack-hard-deck 1000 --out-csv artifacts/eval/threatbreak_vs_cutoff.csv

   Do **not** pass `--bt-rule-xml` in a self-play arm: both aircraft read one global Rule XML, so
   it is symmetric there and cancels exactly.

4. **Still open from 2026-09-08 and untouched today:** the `ab_head_0908` control arm holds only
   **17 of 100** episodes per cell, so "the fixed tree cleared its A/B" is still not established.

5. **`python scripts/spawn_preset_guard.py --restore`** - `aircraft/f16/f16_init.xml` drifted
   15,000 to 20,045 ft during today's evals (expected, F57).

6. **Rebuild before packaging.** The exe (2026-09-08 21:32) is now older than
   `student/controller_providers.py`. Every change today is default-OFF so the shipped behaviour
   is unchanged, but `package_release.py` will refuse until rebuilt, which is the correct gate.

## 5. Do NOT re-do these

- `corner_on` and `defensive_on` - see Sec 2. Two independent measurements now reject corner
  speed from opposite sides of the band.
- Do not revive "above corner, wide radius, therefore overshoot". Its own arm refutes it.
- Everything in `SESSION_HANDOFF_2026-09-08.md` Sec 6 still stands.
