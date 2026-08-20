# Cutoff Model Reference — What the Organizers' Baseline Is, and What We Score Against It

**What this file is for:** the single place to answer "what is the cutoff model, can we beat it,
and by how much". Written 2026-08-20, the day after the binary was distributed (2026-08-19). For
context elsewhere:

- **`COMPETITION_RULES.md` §3** — the gate itself ("Beat an operating-committee-designated
  baseline aircraft to advance"), and §5 for the 200 s / 1000 ft floor this file's adjudication
  argument turns on.
- **`BT_GATE_STRUCTURE_REFERENCE.md`** — our own tree. The cutoff's tree is a *different fork*
  of the same framework and shares almost none of its node vocabulary; see §2 below.
- **`COMPETITION_PLAN.md` §4.1** — the controller-defect history (D4, F1-BLIND) that explains
  why the flag identified in §5 had never been measured.
- **`LIVE_INFERENCE_FRAME_BUGS.md`** — read this too, not just as a reference. Every number in
  this file was measured on a code path that cannot exercise two confirmed, fixed-but-unverified
  bugs in live wire handling. §11 here explains why that doesn't invalidate this file, but does
  mean "beats the cutoff locally" and "will fly correctly live" are not yet the same claim.

---

## ⚠ Read before §4/§8/§9: what "alpha" actually varies

The `alpha_deg` column in every table below is **not an angle** in `match_base` mode, despite the
name. `scripts/eval_v5_vs_bt.py` (~line 935) reuses the alpha schedule as a deterministic sweep
across the **609.6-914.4 m separation band** (`_frac = (alpha_deg % 180) / 180`), because
`match_base`'s actual LOS angle is fixed by the scenario mode itself
(`MATCH_LOS_DEG = 90.0`, i.e. **beam merge**, unless `--match-los-deg` overrides it). Consequence:
`alpha=0` and `alpha=180` map to the **identical** separation (609.6 m) — they are not opposite
ends of anything; heading and left/right side are independently randomised per episode regardless
of alpha, so even identical-separation episodes are not reproductions of each other. Every result
in §4/§8/§9 was run at **90° LOS (beam) throughout** — none of it is a tail-to-tail measurement.
§10 adds the actual tail-to-tail (`--match-los-deg 180`) results — the geometry a 2026-08-20
kickoff-deck slide shows for the cutoff round (two aircraft spawned tails-facing, 2000-3000 ft
apart, same setup as prelim rounds 1-3), which `COMPETITION_RULES.md` §5.1 already flagged as an
open reading of the slide art (beam vs. tails-facing were both plausible before this).

---

## 1. The bar, in the organizers' own words

Stated 2026-08-19:

> 컷오프 모델 돌려보았을때 10번 중에 2~3번 정도는 추락하는 경우가 있을 수 있는데, 이를 감안해도
> 5할 이하의 승률을 보인다면 예선 참가를 재고해보아야 한다 정도로 이해하면 되겠습니다.

Two things follow. The threshold is **>50% win rate**, and the cutoff's own crashes (~2-3 in 10)
are **counted in our favour**. A draw does not clear the bar.

**Result: we clear it outright.** The shipping configuration scores 13.3%. Two changes — both
single CLI flags on `vptrack`, neither touching the tree or the DLL — take it to **100/100 wins at
N=100**:

```
--ownship-vptrack-throttle 1 --ownship-vptrack-range-m 6000 --ownship-vptrack-los-deg 90
```

100% wins, 95% CI [96.3%, 100%]; **98% on the strictest reading** (only wins where we drove the
target's health to zero, discarding every self-crash), CI [93.0%, 99.4%]. Zero losses, zero draws,
all ten alpha cells 10/10. §5 covers the throttle flag, §8-9 the envelope.

---

## 2. What the binary actually is

`unreal_bt_client.exe`, 1.92 MB, PE32+ x86-64 console, built 2026-08-18 12:58:42 UTC with
**MinGW-w64 / GCC 13** (not MSVC), no PDB. Statically analysed; the tree was recovered from
`.rdata` in full (414 lines, Korean comments intact).

**It is a C++ port of `run_unreal_inference.py --mode bt`.** Identical CLI surface (all 14 flags,
same names, same defaults including `--action-repeat 6`), same UDP protocol on 9999, and one of
its log strings — `[bt] fighter id reused with different force side: id=%d prev=%d cur=%d` — is a
literal translation of `bt_action_provider.py:45`. The organizers shipped their baseline as a
standalone binary so teams can run it without the Python environment.

**There is no learned component.** Zero ONNX/Torch/tensor symbols. `--ai-type rl|sl|fusion` only
changes an integer in the heartbeat; it does not change behaviour.

**Its node vocabulary is a different fork from ours.** It uses 42 custom node types, of which
**28 do not exist in this project's node library at all** (`SelectEFSF`, `MergeTurn`,
`DECO_SBFMCheck`, `Support_OBFM`, `WeaponSelect`, `LunchMSL`, `Split`, `Superior`, ...). Ours are
`Task_*`-prefixed; its are bare (`Pure`, `Lead`, `Lag`, `Turn`). Roughly 13 overlap. **Consequence:
its tree cannot be loaded into `AIP_BASE_target.dll`, and rebuilding will not help** — the nodes
are absent from our source, not just our binary. The peer rig in `scripts/setup_peer_bt.py` cannot
be used to host it.

### Structural weaknesses in its tree

Read statically, not all confirmed in play:

- **No default action anywhere.** The root is a bare `<Sequence>` and all 22 `Fallback`s lack an
  unconditional final branch. Any non-exhaustive guard pair propagates FAILURE to the root, and no
  command is emitted for that tick.
- **A non-exhaustive Fallback in DETECTING** (recovered tree lines 260-271): branch 1 covers
  `dv < 0`, branch 2 covers `NOT(dv > 0)`. Nothing covers `dv > 0`. Holds under either operator
  convention. The correct complement pattern is used two blocks earlier in HABFM.
- **A dead band at 90° < LOS < 100°** in its SF/S_Others branch (line 379/384), where
  `DECO_LOSCheck` is inclusive on both sides.
- **No altitude protection of any kind.** `DECO_TargetAltDifCheck` is dead code and there is no
  climb-to-safe-altitude node in the active tree. This is why it flies itself into the floor.
- **No defensive layer.** `DECO_EnemyWEZCheck` is fully implemented with real thresholds
  (`LOS <= 140 and LOS >= 45 and Distance <= 900 and AO >= 70`) and **nothing calls it**;
  `DefenceTurn`, `JinkingTurn`, `JinkingTurnSelector` and `DECO_JinkingCoolTimeCheck` form a
  complete unused cluster. Its DBFM branch is three nodes ending in `Pure` — when it is
  defensive, it answers with pure pursuit and never breaks, jinks or flares.

17 of its 59 implemented action classes are never reached by the active tree.

---

## 3. How to run it

**Against a live viewer (visual, one match at a time).** Start
`Windows/BattleServer_V0.2/DogFightViewer.exe`, then connect the cutoff and our client as opposite
sides. **`--ownship-force-side` / `--target-force-side` must be flipped between the two clients
and nothing will tell you if they are not**: `my_force_side` is taken straight from the CLI flag
(`unreal/policies.py:219`) and is never checked against the `force_side` byte in the incoming
`PlaneInfo`. Both clients default to `1`/`2`, so launching both on defaults gives two aircraft that
each believe they are Red. Ownship identity itself comes from the server's `SetPlaneID`
(`unreal/client.py:340`), which the flag does not affect.

**Headless, scoreable, at N episodes** — added by this work:

| file | role |
|---|---|
| `scripts/cutoff_provider.py` | implements the **server** half of the Unreal wire protocol on loopback, so the binary becomes an ordinary `ActionProvider` |
| `scripts/eval_vs_cutoff.py` | adds `--target-backend cutoff` to `eval_v5_vs_bt.py` by patching its factory; no existing file is edited |
| `scripts/sweep_vs_cutoff.py` | parallel sweep across ownship backends and controller variants |
| `scripts/summarize_cutoff.py` | ranking, with the adjudication correction of §6 |

```powershell
python scripts/eval_vs_cutoff.py --ownship-backend vptrack --ownship-vptrack-throttle 1 `
  --target-backend cutoff --scenario-mode match_base --episodes 100 `
  --out-csv artifacts/eval/cutoff_N100_throttle.csv
```

**Fidelity.** `plane_info_to_state()` maps PlaneInfo pos/rot/vel onto `state[0:9]`, and the local
sim's `state[0:9]` is (N,E,D metres / roll,pitch,yaw degrees / body u,v,w m/s). The provider is the
exact inverse, so the bytes the binary receives are the bytes it receives from Unreal. Handshake,
frame indexing and CMD decoding were verified against a captured real-server session
(`logs/unreal_packets/rx_packets_20260514_155232_15208.jsonl`). The binary is restarted per
episode, mirroring `_recycle_native_bts()`, because its tree carries state.

---

## 4. Results

**N=100, `match_base`, cutoff at its competition default `--action-repeat 6`:**

| config | N | W | D | L | win% | 95% CI | earned% | 95% CI | dmg dealt | dmg taken |
|---|---|---|---|---|---|---|---|---|---|---|
| **throttle + 6000/90** | 100 | **100** | 0 | 0 | **100%** | [96.3, 100] | **98.0%** | [93.0, 99.4] | 1.118 | 0.002 |
| throttle + 4000/45 | 100 | 100 | 0 | 0 | 100% | [96.3, 100] | 94.0% | [87.5, 97.2] | 0.935 | 0.000 |
| vptrack + throttle (2500/45) | 100 | 81 | 19 | 0 | 81.0% | [72.2, 87.5] | 75.0% | [65.7, 82.5] | 0.945 | 0.000 |
| vptrack + throttle + defensive | 100 | 80 | 20 | 0 | 80.0% | [71.1, 86.7] | 74.0% | [64.6, 81.6] | 0.945 | 0.000 |

The two 2500/45 rows saw identical seeded scenarios, so their 81-vs-80 delta comes only from how
each played the 36 clock-ending episodes; `ownship_health` was 1.0 in all 200 of those episodes.
Both widened configs win **10/10 in every alpha cell**.

**N=30 screening sweep, 17 configs, 510 episodes** (ordered by win%):

| config | win% | earned% | note |
|---|---|---|---|
| vptrack + throttle (+ any of defensive / corner) | 66.7% | 53.3-60.0% | all statistically identical |
| vptrack + corner | 66.7% | 53.3% | `corner_hold` preempts `throttle_control` in `_tracking_stick` — it *is* a throttle mode |
| vptrack + throttle @2000/45 | 56.7% | 50.0% | narrowing the envelope hurts |
| vptrack + throttle @2200/35 | 50.0% | 43.3% | narrowing further hurts more |
| **vptrack (shipping config)** | **13.3%** | 13.3% | |
| vptrack + defensive | 13.3% | 13.3% | bit-identical to baseline |
| hybrid_gated (v10) | 10.0% | 10.0% | 21/30 losses are our own crashes |
| vptrack @2000/45, @2200/35 | 6.7% | 6.7% | |
| **bt** | **0.0%** | 0.0% | 30/30 draws, zero contact |
| rl / hybrid / hybrid_vptrack (v10) | 0.0% | 0.0% | 24/30, 24/30, 19/30 losses are our own crashes |

---

## 5. What decided it: one flag that had never been reachable

**`--ownship-vptrack-throttle 1` is the entire result: 13.3% → 81%.** Same behaviour tree, same
everything else. Mean damage dealt goes 0.140 → 0.945.

It had never been measured because it never *could* be. `controller_providers.py:286` records that
`throttle_control` was popped from `kwargs` **after** `super().__init__()`, so passing it as a
kwarg raised `TypeError`; it had only ever been settable via the `DOGFIGHT_VPTRACK_THROTTLE` env
var, and the per-side CLI that made it reachable is recent. The shipping config has it **off**.

Mechanically it is `_range_throttle()` (`controller_providers.py:336`), which drives range to the
~220 m high-damage point of the 152.4-914.4 m band instead of passing the BT's hardcoded constant
through. Its own docstring records the defect it was written for: 3 of 8 draws had the angle gate
satisfied and the range wrong *at the same instant*. Against the cutoff that is the whole fight.

---

## 6. A scoring asymmetry in our own eval

`_classify_outcome` (`envs/single_agent_env.py:404-413`) returns **`"crash"`** when *our* aircraft
drops below the altitude floor, but falls through to **`"draw"`** when the *target* does, because
the target still has health. `COMPETITION_RULES.md` §5 says dropping below 1000 ft "is processed as
a crash/loss" — so under competition rules those episodes are **wins**.

This matters exactly where the organizers told us it would: it is their stated ~2-3-in-10
allowance, and our pipeline was booking every instance of it as a draw. `summarize_cutoff.py`
reports both (`rule%` re-adjudicated, `env%` as the pipeline sees it today).

**It does not change the verdict.** Even on the unmodified `env%` counting, the N=100 result is
75.0%. The correction widens the margin (75.0% → 81.0%); it does not create it.

---

## 7. What these numbers cannot tell you

**Nothing here measures defence.** The cutoff scored zero damage in the first 710 episodes across
every configuration, and our health was untouched in all 200 of the 2500/45 N=100 episodes. The
only exceptions are the two widened-envelope runs (0.001 and 0.002 total) — see §9.
`defensive_break` therefore benchmarks as a no-op — which means **untested, not useless**. The real
objective is other teams' models, which will shoot back. The peer rig (`scripts/setup_peer_bt.py`,
our own tuned BT on both sides) is the only opponent we have that does, and it is the right
instrument for that half of the problem.

**Our side gets more information locally than it would on the wire.** The local BT path receives
the full 51-float FDM (`AIPilot.Step`); over UDP it would receive only position, attitude, speed
magnitude and force side (`AIPilot.StepWithPlaneData`). These numbers flatter us.

**Their environment may differ from ours.** Local cutoff self-crash rate is 6 in 100; the
organizers quote 2-3 in 10.

**Do not over-read small per-alpha cells.** At N=30 — 3 episodes per alpha — alpha 80 and 180 read
0/3 with zero damage and looked like a structural blind spot. At N=100 (10 per cell) they are 7/10
and 7/10, i.e. unremarkable. **Any per-alpha claim needs ≥10 episodes per cell.**

---

## 8. The remaining conversion gap

At N=100 the per-alpha win rate is not flat:

| alpha° | 0 | 20 | 40 | 60 | 80 | 100 | 120 | 140 | 160 | 180 |
|---|---|---|---|---|---|---|---|---|---|---|
| wins | 10/10 | **6/10** | 7/10 | **6/10** | 7/10 | 10/10 | 10/10 | 9/10 | 9/10 | 7/10 |

**Every draw is a failure to close, not a failure to shoot.** Splitting the weak cells:

| | n | min distance | min ATA | steps ≤2° | WEZ steps | damage |
|---|---|---|---|---|---|---|
| wins (20°/60°) | 12 | 349.8 m | 0.09° | 1401 | 402 | 1.28 |
| **draws (20°/60°)** | 8 | **677.5 m** | 0.56° | 298 | **0** | **0.00** |
| wins (0/100/120°) | 30 | 302.6 m | 0.04° | 1443 | 342 | 1.14 |

The draws' mean minimum distance, 677.5 m, **equals the initial separation of 677.4 m** — closest
approach was the starting instant and the pair never re-merged. Pointing is not the problem
(0.56° min ATA); the fight simply never develops.

The mechanism is structural. `_tracking_stick` (`controller_providers.py:397`) returns `None` —
deferring entirely to the BT — whenever `rng > engage_range_m or los_deg > engage_los_deg`
(2500 m / 45° by default). A non-closing fight is spent *outside* that envelope, so it is flown by
the native BT, which `EnvelopeGatedHybridProvider`'s docstring already records as the component
that "loses the neutral merge" (1/30 on `two_circle_headon` vs 12/30 on the advantaged OBFM start).

That narrowing the envelope measured strictly worse (2500/45 → 2000/45 → 2200/35 gives
66.7% → 56.7% → 50.0%) says the gradient points at **widening** it. **§9 confirms this: widening
to 6000 m / 90° closes the gap completely, 100/100 at N=100.**

---

## 9. Envelope-widening experiment — the gap closes completely

**2026-08-20, N=30 screen, all with `--ownship-vptrack-throttle 1`:**

| config | engage_range_m | engage_los_deg | win% | earned% | dmg dealt |
|---|---|---|---|---|---|
| baseline | 2500 | 45 | 66.7% | 56.7% | 0.715 |
| `env_r2500_l90` | 2500 | **90** | 83.3% | 70.0% | 0.697 |
| `env_r4000_l45` | **4000** | 45 | **100%** | 93.3% | 0.933 |
| `env_r4000_l60` | **4000** | 60 | **100%** | 93.3% | 0.988 |
| `env_r6000_l90` | **6000** | **90** | **100%** | **100%** | 1.129 |

**Confirmed at N=100:** `6000/90` → **100/100 wins, 98/100 earned**, CI [96.3%, 100%] and
[93.0%, 99.4%]; `4000/45` → 100/100 wins, 94/100 earned. Both win **10/10 in every alpha cell**,
including the 20°/60° cells that were 6/10 at 2500/45.

**Both axes help and range dominates** — 4000/45 alone reaches 100% while 2500/90 alone reaches
only 83.3%. Mean minimum distance falls 677 m → 446 m and episodes end in ~4,500 steps instead of
11,999: it now closes and finishes instead of orbiting to the clock. This is exactly the mechanism
§8 predicted.

### What this says about the architecture

At 6000 m / 90° the override is engaged essentially all the time, so **the hand-written tracking
law is flying almost the entire engagement and the BT's tactical layer is bypassed**. Against this
opponent the BT was not merely unhelpful, it was the component losing the draws — consistent with
`bt` alone scoring 0/30 and with `EnvelopeGatedHybridProvider`'s 1/30-on-`two_circle_headon` note.
This is a stronger claim than F1-BLIND ever established, and it was only measurable once a
non-symmetric opponent existed.

### Do not generalise this past the cutoff

Three reasons to hold the wide envelope as a *cutoff-gate* setting rather than a general one:

1. `env_r4000_l60` recorded `taken = 0.001` and the N=100 `6000/90` run recorded `taken = 0.002` —
   the **first non-zero damage against us in 740 prior episodes**. Trivial in size, but it is the
   first evidence that widening exposes us at all, and it happened against the one opponent that
   essentially never shoots.
2. A controller with **no tactics** flying the whole engagement is the configuration most likely to
   be brittle against an opponent that manoeuvres to deny a solution rather than flying into one.
3. The setting was tuned against a single, deliberately simplified opponent. Nothing here shows it
   transfers, and §7's warning about defence applies with more force at a wide envelope, not less.

The peer rig (`scripts/setup_peer_bt.py`) is the instrument for testing whether it holds up against
something that shoots back.

---

## 9b. Full re-sweep post Gate1-fix (2026-08-20, later): gate still solidly passed, one new side effect

`COMPETITION_PLAN.md` F37-GATE1-DEFENSIVE-FIX added an own-ATA≥90° carve-out to Gate 1 (see that
doc). All 19 `sweep_vs_cutoff.py` configs plus the plain `vptrack` baseline re-run at N=30,
`match_base`, `MATCH_ALTITUDE_M=4572 m` (default — this table is what applies if the real prelim
altitude turns out to be ~15,000 ft, per the organizers' deck saying it is TBD).

**Champion/widened configs: bit-identical, zero self-crashes.** `env_r6000_l90` still 100%/100%
earned/0 taken; `env_r4000_l45`/`env_r4000_l60` still 100%/93.3%; `env_r2500_l90` still
83.3%/70.0%. These barely touch native-BT control (the hand-written law is engaged almost the
whole match), so Gate 1's change has essentially nothing to act on here.

**Narrower/BT-heavy configs: mostly improved win%, but each picked up 1-2 self-crashes per 30
episodes that were not there before**, including the 2500/45+throttle general-play default
(66.7%→56.7%, 1 self-crash) and plain shipping `vptrack` (13.3%→23.3%, 2 self-crashes). Native
`bt` alone went from a flat 0.0% to 6.7% (3.3% earned) — the tactical layer doing something,
finally, without any override. RL/hybrid-v10 family unchanged (bit-identical W/D/L in three of
four cases), still non-viable.

**This does not threaten the gate** — the shipping/champion configs are unaffected — but it is a
real, new finding, not noise: the self-crash pattern is `ownship altitude below min`, i.e. flying
into the ground, not being shot down (`taken=0.000` in every case). It did **not** appear anywhere
in the same day's peer-rig verification against a real shooting opponent (`match_base`,
`obfm_defensive` — both 0 self-crashes at N=30, throttle-on). Plausible mechanism, not confirmed:
narrower-envelope configs let the native BT fly more of the match against the cutoff specifically,
where own-ATA can cross 90° repeatedly in ways a real, actively-maneuvering peer doesn't produce —
worth a gate-trace investigation, not urgent given the shipping path is clean.

---

## 10. Confirmed via the peer rig (2026-08-20): stay scoped to the cutoff

§9's caution was correct. Scored through `scripts/setup_peer_bt.py` (peer = F25-fixed tree, no
Gate 1 own-ATA carve-out — see `COMPETITION_PLAN.md` 4.1 F37-GATE1-DEFENSIVE-FIX for that change),
N=30 seed 0, `--ownship-vptrack-throttle 1 --ownship-vptrack-range-m 6000
--ownship-vptrack-los-deg 90`:

| scenario | 6000/90 | 2500/45 (champion) |
|---|---|---|
| `match_base` | 13W/8D/9L (43.3%), damage 0.428/**0.478** | 13W/11D/6L (43.3%), damage 0.342/**0.230** |
| `obfm_defensive` | 10W/3D/17L (33.3%), damage 0.360/0.577 | 7W/4D/19L (23.3%), damage 0.054/0.550 |

On `match_base` — the confirmed prelim geometry — the two configs are statistically tied on win
rate, but 6000/90 takes **more than double the damage** and is the first config measured on this
scenario to show a self-crash on either side (1 free, 1 ours; champion is 0/0). `obfm_defensive`
actually favours the wide envelope on win rate, recorded here rather than cherry-picked away, but
damage taken is statistically the same either way, so it isn't evidence of it being *safer* —
only that it wins more of a fight it still gets hurt in equally. Net: **6000/90 stays a
cutoff-only setting.** Use `2500m/45°/throttle-on` as the general-purpose and match-day default;
they solve different problems (the cutoff never manoeuvres to deny a solution, a real opponent
does), not competing champions for the same job.

---

## 10. Tail-to-tail (`--match-los-deg 180`) — the leader stays undefeated

Real geometry this time: `los_deg=180` in `apply_match_scenario` (`student/match_scenario_wrapper.py:81`)
places both aircraft heading directly **away** from each other (`own_heading = h+180`,
`target_heading = h+360=h`, both ATA=180°) — confirmed analytically from the heading-assignment
math, not assumed. Both start at 200 m/s flying apart, so separation grows ~400 m/s and blows past
any 2500 m default envelope within ~5 seconds — the entire opening reversal is spent outside a
narrow gate.

**N=30, `--match-los-deg 180`:**

| config | W | D | L | win% | earned% | dmg dealt | dmg taken | note |
|---|---|---|---|---|---|---|---|---|
| **throttle + 6000/90** | 30 | 0 | 0 | **100%** | **100%** | 0.839 | 0.000 | zero self-crashes needed |
| throttle + 4000/45 | 28 | 2 | 0 | 93.3% | 90.0% | 0.178 | 0.005 | |
| baseline (no throttle) | 27 | 3 | 0 | 90.0% | 90.0% | 0.423 | 0.000 | |
| throttle only (2500/45) | 26 | 3 | **1** | 86.7% | 83.3% | 0.086 | 0.006 | first loss anywhere in this project |

**`throttle + 6000/90` is 30/0/0 at tail-to-tail, same as at beam.** Combined with §9's N=100 beam
result: **60/60 across both tested geometries, zero losses, zero draws.** This reverses a
mechanical prediction made before running it — a wide envelope was expected to struggle when
nobody starts pointed at anybody, since both aircraft separate before any solution exists.
Instead it wins for that exact reason: a narrow gate misses the reversal phase entirely and hands
the whole thing to the native BT (§9's "no tactics" component); a wide gate stays engaged through
the separation and lets the tracking law fly the merge itself. §6 of
`LIVE_INFERENCE_FRAME_BUGS.md` measures directly how much of this the native BT actually flies —
35-51% of a tail-to-tail match by wall-clock time, which is precisely why this geometry is the
one where the horizontal-frame bug matters most.

`throttle only (2500/45)` recorded this project's first loss anywhere — 1 in 1,570+ prior
episodes at the time it happened. Not investigated; not the config being shipped, so low priority,
but worth a look before dismissing as noise.

**These N=30 tail-to-tail numbers, like every other number in this file, were measured before the
live-frame fixes existed** — see §11.

---

## 11. Every number in this file predates the live-wire frame fixes — read `LIVE_INFERENCE_FRAME_BUGS.md`

Two bugs were found and fixed the same day this file's numbers were produced, in
`src/dogfight/unreal/policies.py`'s live boundary: a vertical-sign inversion in
`VPTrackingProvider`'s own tracking law, and a horizontal-frame corruption (raw Unreal metres fed
to a function expecting lat/lon degrees) in the native BT's geometry, active whenever
`_tracking_stick` defers outside its envelope. Full derivation, proof, and fix in
`LIVE_INFERENCE_FRAME_BUGS.md`.

**Neither bug can be exercised by `CutoffProvider`** (`scripts/cutoff_provider.py`) — it feeds
`ownship_state`/`target_state` directly, structurally bypassing `plane_info_to_state()` and the
native-BT plane-data path both bugs live in. So every win-rate number in this file — the N=30
sweep, the N=100 confirmations, the tail-to-tail results in §10 — is a valid **local**
measurement, produced on the code path that has never been broken. None of them confirm what the
now-patched live code actually does against a real connection. `LIVE_INFERENCE_FRAME_BUGS.md` §6
measures that the affected code path flies 17-51% of a real match depending on geometry, so this
is not a small caveat.

Treat this file's numbers as "what beats the cutoff, measured correctly, in the environment that
has always been available" and `LIVE_INFERENCE_FRAME_BUGS.md` as "the reason those numbers are not
yet a live-match prediction."

---

## 12. Handoff — open items, roughly in priority order

1. **Validate the live-frame fix against a real connection.** `LIVE_INFERENCE_FRAME_BUGS.md` §5.
   Nothing else here matters if this doesn't hold up.
2. **Re-confirm the shipping config's win rate live**, once #1 passes — these local numbers are
   the best available estimate, not a substitute for a live measurement.
3. **N=100 the tail-to-tail leader** (`throttle + 6000/90`, currently N=30/30/0/0) to get a real
   confidence interval, matching what was done for beam in §4.
4. **Peer-rig test** (`scripts/setup_peer_bt.py`) — run the winning config against your own tuned
   BT, which has both real offense and real defense (`Task_Evade`, `Task_JinkingTurn`, etc.). This
   is the nearest available proxy for "a complete opponent" and the only way to get real data on
   §7's untested defensive question. A prior (pre-throttle-fix, pre-frame-fix) self-play run
   scored 46.7% win / 46.7% draw / 6.7% loss against this same BT — a useful anchor, not a
   substitute for re-running it on the current build.
5. **Investigate the `throttle only (2500/45)` tail-to-tail loss** (§10) — first loss in the
   project's history at N≈1,570+. Low priority since it isn't the shipping config.
6. **Build a wire-faithful local harness** so the frame bugs (and any future ones like them) are
   catchable without a live connection — `LIVE_INFERENCE_FRAME_BUGS.md` §5, item 3.
7. **Do not ship any RL or hybrid mode** without first fixing `context.observation`'s uncorrected
   vertical frame (`LIVE_INFERENCE_FRAME_BUGS.md` §5, item 2) — irrelevant while shipping
   `vptrack`, which doesn't read `observation`.
