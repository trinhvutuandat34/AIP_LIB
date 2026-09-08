# Opponents Analysis

Scouting log for teams in the 2026 AI Pilot Top Gun Challenge. One entry per
opponent, added as match footage becomes available. Each entry is built by
reconstructing the opponent's engagements from broadcast/replay footage
(health-bar telemetry, WEZ-cone visuals, battle-phase markers, contrail
geometry), not from their code or logs — treat findings as hypotheses to
validate in our own practice sims, not guarantees.

> **Reading rule, added 2026-09-02.** Observations from footage are data;
> the mechanism attributed to them is interpretation, and interpretation must
> be checked against [COMPETITION_RULES.md](COMPETITION_RULES.md) before it is
> acted on. The first revision of this file failed that check twice — it read
> gun-WEZ damage events as missile shots in a **guns-only** competition (§4),
> and it credited the opponent with a "Battle Phase gate" that is actually the
> **competition's own WEZ widening on the match clock** (§6.2). Both errors
> pointed the counter-tactics at things that do not exist. Keep the telemetry
> columns and re-derive the mechanism.

## Opponent Index

- [GoGoSSung](#gogossung) — scouted 2026-08-30, 5 matches, 5–0 record observed
  (re-analyzed 2026-09-02 against the real rules)
- [HAnnamAir](#hannamair) — scouted 2026-09-08, 4 matches, 3–1 record observed
- [Fight's on!](#fights-on) — scouted 2026-09-08, 5 matches, 4–1 record observed

**All three A조 group opponents now have dossiers.** Remaining scouting
priority (see [Prelim standings — schedule-adjusted](#prelim-standings--schedule-adjusted-2026-09-03)
for the full 16-team field): **TrAI Everything** (our likely 8강 opponent) →
**불나방** (strongest team in the field, reachable only at 4강/결승).

---

## GoGoSSung

**Scouted:** 2026-08-30 · **Re-analyzed:** 2026-09-02 ·
**Source:** 5 recorded matches (broadcast HUD footage) ·
**Record observed:** 5–0 (won every match analyzed, all by kill)

### The two corrections that change everything

**1. There are no missiles.** `COMPETITION_RULES.md` §4: *"Guns only — extreme
close-range gun engagement (no missiles), with a roughly probabilistic
simulated gun cone."* There is no missile mechanic anywhere in the scoring,
damage, or flight-model code either (`CLAUDE.md`, `AIP_DCS` node inventory —
`LunchMSL`/`WeaponSelect` were confirmed dead and never implemented). So every
"missile kill", "missile trail" and "lock" in the original report is a **gun
WEZ damage event**. The tell is in the numbers the report itself recorded:
Match 3's "763–933 m lock" is 2,503–3,061 ft, which is the **gun cone's own
range band**, not a missile envelope.

**2. "Battle Phase 1→3" is the match clock, not their AI.** §6.2: the
competition widens the damage cone in three phases as the 200 s clock runs
down, explicitly to reduce draws.

| Phase | Window | Cone | Coef | Damage formula (`r` in ft, `θ` = LOS°) |
|---|---|---|---:|---|
| 1 | 0–100 s | θ<1°, 500–3000 ft | 1.0 | `1.0 × (3000 − r)/2500` |
| 2 | 100–150 s | θ<2°, 500–3500 ft | 0.3 | `0.3 × (3500 − r)/3000` |
| 3 | 150–200 s | θ<3°, 500–4000 ft | 0.1 | `0.1 × (4000 − r)/3500` |
| — | — | r<500 ft or θ≥3° | 0 | **hard zero-damage dead zone below 500 ft** |

Narrowest qualifying phase wins, so a Phase-1-quality shot still pays 1.0 even
at t=160 s. Every team gets these phases. "Its finishing shots landed during a
Battle Phase 3 transition" reduces to "they landed after t=150 s" — which is
what the widened cone predicts for *anyone*, and is not evidence of design.

### Match-by-Match Log

Telemetry columns are unchanged from the original observation. The right-hand
column is re-derived.

| # | Opponent | Side | Duration | GG health end | Hits taken | Hits landed | Re-derived scoring read |
|---|---|---|---|---|---|---|---|
| 1 | 개쩌는유컨 | Red | 156 s | 98.5% | 1 (graze) | 6 | 40 s scoreless → 6-pass whittle → kill ~t146 s = **Phase 2** (coef 0.3, θ<2°) |
| 2 | Physics2Chemistry2 | Red | 59.5 s | 100% | 0 | 2 | High-to-low diving pass inside t<100 s = **Phase 1 at full coef 1.0**. Fastest win in the sample, and the most damage-efficient |
| 3 | VAlkyrie | Red | 156 s | 100% | 0 | 5 | 96 s scoreless → shot at 763–933 m (2,503–3,061 ft) **straddling the P1/P2 boundary at t≈96–100 s** — 3,061 ft is outside P1's 3,000 ft but inside P2's 3,500 ft |
| 4 | MotherGoose | Blue | 202 s | 100% | 0 | 8 | Opening shot t≈8 s (**Phase 1**) → lulls → 3 hits in ~12 s at t≈190 s (**Phase 3**, coef 0.1) |
| 5 | 봉희찬재광 | Red | 207.6 s | **84.0%** | **1 (~16%)** | 3 | Took its only real hit at t≈10–12 s — **Phase 1, coef 1.0, which is why one hit cost 16%** → 136 s scoreless → 2 hits in ~2 s → kill in the final seconds (**Phase 3**) |

> **Clock caveat.** Matches 4 and 5 are logged at 202 s and 207.6 s against a
> 200 s engagement limit (§5). Broadcast footage evidently includes a few
> seconds of pre/post-roll, so **footage timestamps are not match-clock
> timestamps**. Every phase attribution above carries roughly ±8 s of
> uncertainty, which matters most at the 100 s and 150 s boundaries (M3 sits
> exactly on one).

### What the pattern actually is

Re-read through the phase model, "patience" is a less interesting explanation
than the scoring gradient:

- **Their damage is concentrated where the coefficient pays.** Either early at
  Phase 1 (M2, M4's opener, and the one hit they *took* in M5), or late once
  the cone is 6.4× (P2) to 21.4× (P3) larger by volume. The long scoreless
  middles are partly the model telling everyone to wait.
- **A Phase-1 hit is worth up to 10× a Phase-3 hit of identical geometry**
  (coef 1.0 vs 0.1). That single number explains M5's shape better than
  anything about their tactics: they took one Phase-1 hit and it cost 16% of
  their health, while their own three late hits took the whole clock to finish
  the job.
- **Shot discipline is still real, but it is cheap discipline.** Tolerating an
  80–136 s scoreless stretch costs little when the cone is about to widen and
  you are not being shot at. It is not evidence they can win a contested
  Phase-1 exchange — nothing in this sample tests that, because only one
  opponent ever put a gun on them.

Genuinely supported by the footage, and unchanged by the corrections:

- **Geometry-agnostic.** Kills from high-to-low (M2), low-to-high (M3), and
  off a vertical reposition (M4). No single blind angle to bait.
- **Stacks follow-up shots** once it has an angle: 3 hits in ~12 s (M4), 2
  hits in ~2 s (M5). Assume a salvo, not a single shot.
- **Comfortable in the vertical** (M4).
- **Closes out under time pressure** rather than accepting a decision.

### Vulnerabilities

1. **The opening window.** The only hit anyone landed on it (M5) came in the
   first ~10–12 s — Phase 1, coefficient 1.0, and it cost 16% health from a
   single event. See the finals geometry note below: rounds 1–3 start abeam at
   610–914 m, so each side needs only ~90° of turn to point. Whoever wins that
   quarter-turn gets first shot inside the highest-paying phase of the match.
2. **It can be hit.** 2 of 5 opponents (40%) drew blood.
3. **It punishes stillness, not maneuvering.** Every scoring hit it landed
   found a target flying straight or mid-commitment to an unfinished escape —
   never one actively maneuvering.
4. **Untested under sustained pressure.** No footage shows it absorbing more
   than the single M5 hit.

### Design requirements derived from this dossier — NOT deployable counters

> **Re-scoped 2026-09-03. Read this before the list.** The submission is
> **exactly two artifacts** — one main model, optionally one head-on model,
> both frozen at 2026-09-14 12:00 (`COMPETITION_PLAN.md` F61,
> `COMPETITION_RULES.md` §7.1). **A configuration aimed at one opponent cannot
> be shipped.** One binary plays every team in A조 and then whoever emerges
> from D조. So nothing below is a counter we deploy when we see GoGoSSung on
> the bracket — each item is only actionable if it is **good against the whole
> field**, and it earns its place in the single main model on that basis or
> not at all. They are tagged accordingly: **[UNIVERSAL]** = plausibly right
> against every archetype in the league roster; **[CHECK]** = derived from
> this opponent's profile and *not* obviously safe to generalise, so it needs
> its own measurement before it shapes the shipped config.

Ranked by evidence strength. Items 3 and 6 of the original list are **deleted**
— they briefed for a missile trade and a countermeasure reserve, neither of
which exists in this competition.

1. **[UNIVERSAL] Win the first 15 seconds.** It is the only thing that has
   ever worked against them, it pays at coefficient 1.0, and the start geometry
   hands it to whoever reverses faster. *(M5, t≈10–12 s)* — Generalises: the
   beam merge is played in **every game of every match**, and the opening is a
   ~90° pointing problem for both aircraft regardless of who is flying.
2. **[UNIVERSAL] Plan to fly the full clock.** Three of five wins ran
   150–207 s. Budget energy for a full-length fight, not an early decision.
   *(M1, M4, M5)* — Generalises: the 200 s clock is a property of the rules.
3. **[UNIVERSAL] Never go static after beating a shot.** Every hit it landed
   found a straight-flying or mid-commitment target. *(M2, M4)* — Generalises:
   nothing about it depends on the shooter's identity.
4. **[CHECK] Brief for a salvo.** Assume a second and third shot once it has an
   angle. *(M4 — 3 hits/12 s; M5 — 2 hits/2 s)* — This is an observation about
   **GoGoSSung's** persistence on a solution. Whether the disengagement posture
   it implies is right against a `cutoff`-type opponent that declines the
   re-merge is a separate question, and F58 says that opponent beats us on the
   clock, not on gunnery.
5. **[CHECK — and now suspect] Deny the late cone rather than racing it.** Its
   Phase 2/3 hits come from holding a solution on a predictable target, and a
   Phase-3 hit only pays 0.1. **But under F61's criterion this is a
   draw-generating posture**, and draws are now a ranked cost: they bleed
   세트득실차 in the group, and two of them in a knockout hand the opponent the
   option to switch to their 헤드온 모델. Against a passive opponent this item
   converts a winnable game into a timeout. **Do not adopt it into the shipped
   config without measuring its effect on draw rate across the whole roster.**
6. **[UNIVERSAL] Do not read a quiet fight as a won fight.** Three of five games
   had 80 s+ scoreless stretches and all three ended in a kill.

### Implications for our own build

The correction reframes two of our own open items:

- **Our local eval cannot see the lever they use.** `COMPETITION_RULES.md`
  §6.3: the Phase 2/3 widening is **not implemented** in
  `src/dogfight/config.py` — local scoring runs a flat single cone. So every
  local damage number systematically under-counts late-match scoring, which is
  exactly where GoGoSSung collects. `student/reward_lib.py` already has
  `match_wez_phase()` / `wez_damage_estimate()`; the eval harness could score
  the phased model post-hoc from logged geometry without touching the
  platform.
- **Their profile is the opponent our `defensive_break` was parked for.**
  F26-DEFENSIVE parked it with the words "worth re-testing against an opponent
  that out-shoots us." GoGoSSung out-shoots essentially everyone, and
  "punishes stillness" is a direct indictment of flying a steady tracking
  solution in front of them.

### Caveats / Confidence

- Sample is five GoGoSSung **wins** only — survivorship bias. No footage of it
  losing or under sustained pressure.
- All figures read from broadcast HUD telemetry, not raw sim logs or their
  control inputs. Footage timestamps ≠ match clock (see clock caveat).
- Opponent skill varied; long scoreless openings may reflect passive opponents
  as much as restraint.
- The phase attributions are re-derived by us from §6.2, not read off the HUD.
  The HUD phase marker was observed; the mapping from marker to coefficient is
  our inference.
- Validate everything here in our own practice sims before relying on it.

---

## HAnnamAir

**Scouted:** 2026-09-08 · **Source:** 4 recorded matches (broadcast HUD
footage, from HAnnamAir's own qualifying-stage matches — none of the four
opponents faced here are teams we will play) · **Record observed:** 3–1

Scoring-mechanism corrections carry over unchanged from the GoGoSSung dossier
above: guns-only, no missiles, and the three-phase WEZ cone widening (§6.2)
explains any "late-match" scoring the same way it does there — see that
section's phase table. Footage did not consistently expose a phase marker at
the moments read, so kill timing below is reported as raw footage-clock, not
phase-attributed.

### Match-by-Match Log

| # | Opponent | Side | Duration (footage) | HAnnamAir health end | Opponent health end | Outcome |
|---|---|---|---|---|---|---|
| 1 | 추락도락이다 (Churock_Is_Rock) | Red | 207.0 s | 0% (killed ~t199–201s) | 100% (untouched) | **Loss** — total shutout against us |
| 2 | INHA_VIPER | Blue | 197.0 s | 100% (untouched) | 0% (killed ~t185–189s) | Win — shutout |
| 3 | 대화 | Red | 203.1 s | 100% (untouched) | 0% (killed ~t201.9s) | Win — shutout |
| 4 | FalconAI | Red | 198.2 s | 95.7% (one hit, ~t118–154s) | 0% (killed ~t197s) | Win — near-shutout |

### What the pattern actually is

- **Bimodal, not competitive.** In all four matches, one side finishes at
  ≥95.7% and the other at 0%. Nothing here shows HAnnamAir in a genuine
  back-and-forth exchange — it either completely denies the opponent's gun or
  is completely denied itself.
- **Wins are slow grinds, not fast kills.** In all three wins, the opponent's
  health drops in a series of distinct steps over roughly 80–100 seconds
  (M2: 100→77.9→41.8→9.4, then stuck at 9.4% for ~70 more seconds before the
  kill; M3: 100→76→58→46→21→1→0 over ~80s; M4: 100→~78→41→23→0 over ~80s)
  rather than one or two decisive salvos. Contrast with Fight's on! below,
  which frequently kills in single-digit seconds once it starts.
- **The one loss is a complete inversion, not a close loss.** Against
  추락도락이다, HAnnamAir logged zero hits landed in 207 seconds while taking a
  slow grind of its own (chip damage from ~t90 to ~t180, then a finishing hit
  right at the death clock). Whatever 추락도락이다 did neutralized HAnnamAir's
  offense entirely, not just outscored it.

### Vulnerabilities

1. **Slow to close out a nearly-dead opponent.** M2's INHA_VIPER sat at 9.4%
   health for roughly 70 seconds before HAnnamAir finished it. An opponent
   capable of extending/evading at critical health may survive longer against
   HAnnamAir than its health bar suggests it should.
2. **[CHECK] Total-shutout losses look possible, and on this evidence look
   like complete outclassing rather than bad luck** — zero offense generated
   in the one loss sampled. Sample size is one; treat as a flag to watch for,
   not a confirmed weakness.
3. **No data on a contested, roughly-even fight against HAnnamAir.** Every
   match here was lopsided one way or the other (the same survivorship-bias
   caveat the GoGoSSung dossier flags for itself).

### Design requirements derived from this dossier — NOT deployable counters

Same re-scoping rule as the GoGoSSung dossier: one main model plays the whole
field, so anything below only earns a place in the shipped config if it
plausibly helps against every archetype, not just this one.

1. **[CHECK] Deny the merge / first exchange entirely if possible.** All three
   wins involved landing the *first* hit and never giving it back; the one
   loss involved landing no hits at all. No recovery arc is visible in this
   sample either way — small-sample, needs more footage before it shapes the
   shipped config.
2. **[UNIVERSAL] Don't assume a 5–10% health lead is safe.** HAnnamAir's own
   matches show it taking ~70s to finish an opponent parked at 9.4% health.
   Don't relax pursuit discipline just because the target's HP bar is nearly
   empty — this generalizes regardless of opponent identity.
3. **[CHECK] Whatever beat HAnnamAir in M1 is unknown** (추락도락이다 is a
   Group B team, out of scope for direct scouting) but looks like a complete
   win, not just an edge, if the mechanism can ever be identified. Flagged for
   future scouting only — not actionable today.

### Archetype mapping — tentative

**Confidence: low.** None of the five roster archetypes fit cleanly.
`sniper` (narrow envelope, retains health, engages rarely) matches the
defensive half of HAnnamAir's profile — it is essentially never hit in three
of four matches — but its wins involve extended, active pursuit rather than
restraint, which `sniper`'s "engages rarely" framing doesn't capture. If one
archetype must be picked for sparring, `sniper` is the least-wrong choice for
the defensive half of its game only; it does not model the "grinds a lead
into a kill over 80–100 seconds" offensive half. Treat any "beat `sniper` X%"
result as uninformative about HAnnamAir specifically.

### Caveats / Confidence

- All four matches are against opponents we will not face — this profiles
  HAnnamAir's own tendencies, not how it plays against a style it hasn't met,
  including ours.
- Sample is 4 matches split evenly into "total win" and "total loss" — no
  data point in between. The bimodal read is a clean pattern across all four
  samples, but four samples is still few.
- Read from broadcast HUD footage (health bars, name tags, on-screen
  distance/LOS callouts), not raw sim logs. Footage durations here run
  197–207s against a 200s engagement limit, consistent with a few seconds of
  pre/post-roll — same "footage timestamp ≠ match clock" caveat as the
  GoGoSSung dossier.
- The on-screen "Delay Count" readout in this footage is **not** the match
  clock — cross-checked across frames, it does not decrease monotonically
  with time (it holds constant for tens of seconds, then jumps), consistent
  with a network-delay/tick-lag telemetry readout. Do not use it for phase
  attribution.
- Kill geometry (vertical vs. flat) was not confidently readable at enough
  kill-moment frames to report per the observable table; qualitative
  impression leans toward flat/sustained-turn engagements rather than
  vertical finishes, but this is low confidence.

---

## Fight's on!

**Scouted:** 2026-09-08 · **Source:** 5 recorded matches (broadcast HUD
footage, from Fight's on!'s own qualifying-stage matches — none of the five
opponents faced here are teams we will play) · **Record observed:** 4–1

Same scoring-mechanism caveats as the HAnnamAir dossier above (guns-only, WEZ
phase widening, "Delay Count" is not the match clock).

### Match-by-Match Log

| # | Opponent | Side | Duration (footage) | Fight's on! health end | Opponent health end | Outcome |
|---|---|---|---|---|---|---|
| 1 | FalcoPilot | Blue (jester) | 150.9 s | 24.5% | 0% | Win — hard-fought, both sides took real damage |
| 2 | team737 (날아라칠암칠) | Red (jester) | 78.3 s | 100% | 0% | Win — shutout, fast |
| 3 | FDSA (이겨야 한다'딸깍') | Blue (jester) | 67.9 s | 100% | 0% | Win — shutout, fastest in sample |
| 4 | KAIST_FAIR | Red (jester) | 149.8 s | 100% | 0% | Win — shutout, slower grind |
| 5 | UFO (신원미상비행체) | Red (jester) | 147.1 s | 0% | ~12% (post-kill hit) | **Loss** |

### What the pattern actually is

- **First-strike dependent.** Three of five matches (M2, M3, M4) show Fight's
  on! taking zero damage the entire game. Two of those three (M2, M3) are
  also the shortest matches in the sample (78.3s, 67.9s) — a long scoreless
  opening (60–100s) followed by one abrupt, lethal multi-second burst that
  takes the opponent from ~100% to 0% almost immediately (M3: 96.8%→29.6%→
  8.4%→0% in about 5 seconds of footage). This is a "patient, then decisive"
  profile, not a "grind them down steadily" one — contrast with HAnnamAir
  above.
- **When it wins the first real exchange, it wins the match.** No comeback
  arcs appear in the four wins — once Fight's on! lands the opening damage,
  the opponent never claws back.
- **The one loss shows exactly the opposite: no comeback of its own.** In M5,
  both sides were scoreless until ~t102 of the footage. The merge that
  followed damaged both (jester 100→41%, UFO 100→96%→64%) — Fight's on! took
  far more damage than it dealt in that single exchange, and it was dead a
  few seconds later, with UFO's own health only dropping further (64%→12%)
  after jester's kill (likely follow-through fire, not a second Fight's on!
  shot). No recovery attempt is visible — the first bad exchange was the
  whole match.
- **M1 is the outlier and the closest look we get at it under pressure.**
  Against FalcoPilot, both sides traded real damage across several distinct
  exchanges (98.9%→~74%, then 74%→24.5%) and Fight's on! still closed it out
  at 24.5% health remaining — the only match in the sample where it
  demonstrably survived taking a real beating and still won.

### Vulnerabilities

1. **Losing the first real merge looks fatal.** M5 is the only loss in the
   sample and the only match where Fight's on! did not land the opening
   blow — and it lost decisively, not narrowly. If our aircraft can win the
   first exchange (or at minimum not lose it badly), this sample shows no
   established recovery pattern for Fight's on! to fall back on.
2. **High variance in how fast it finishes.** Two kills complete in
   single-digit seconds once damage starts; one (M4, KAIST_FAIR) takes ~100
   seconds of stepped damage instead. What determines which pattern applies
   is not yet clear from this sample.
3. **Untested at length under sustained, contested pressure.** Only M1 shows
   it taking damage across multiple exchanges rather than one; four of five
   matches are effectively decided by a single engagement.

### Design requirements derived from this dossier — NOT deployable counters

Same re-scoping rule as above — one main model plays the whole field.

1. **[UNIVERSAL] Winning the opening exchange matters against everyone, and
   doubly so here.** This is already item 1 of the GoGoSSung list; Fight's
   on!'s dossier reinforces it independently — its only loss in this sample
   is also the only match it didn't open with the first hit.
2. **[CHECK] Don't concede a clean first merge without a fight.** If forced
   into a defensive first exchange, M5 suggests damage taken there compounds
   fast (jester lost 59 points of health in one exchange, more than the
   opponent's 36). This is a data point on their opponent's finishing power,
   not ours — whether *our* aircraft is exposed the same way needs its own
   measurement, not an assumption transferred from this footage.
3. **[UNIVERSAL] Plan for a fast kill window once an opponent is hit hard.**
   Two of five matches went from ~100% to 0% in single-digit seconds once
   real damage landed. This matches "brief for a salvo" already in the
   GoGoSSung list (item 4) — evidence that stacking follow-up shots fast,
   once an angle is open, is generically rewarded by this scoring model, not
   just something GoGoSSung does.

### Archetype mapping — tentative

**Confidence: low.** The existing five-archetype roster doesn't have a clean
fit. Fight's on!'s profile — long scoreless patience *and* an aggressive,
high-damage finish once engaged — mixes `sniper`'s opening restraint with
`aggressor`'s commitment once merged. If forced to pick one for sparring,
`aggressor` is the closer analogue for the finishing behavior (the part that
actually decides its matches), but label it as an analogue only, per the same
rule used for GoGoSSung — a league row reading "beat `aggressor` X%" should
not be read as "beat Fight's on! X%".

### Caveats / Confidence

- All five matches are against opponents we will not face — this profiles
  Fight's on!'s own tendencies, not how it plays against a style it hasn't
  met, including ours.
- Sample is 5 matches with 4 wins skewed toward shutouts — likely some
  survivorship bias in what "typical" Fight's on! offense looks like; the one
  loss (M5) is the only look at what beats it, and it's one data point.
- Same footage/telemetry caveats as the HAnnamAir dossier: HUD-read, not raw
  logs. Match durations here (67.9–150.9s, none near the 200s cap) suggest
  these were often decided well before the clock, so the "footage timestamp ≠
  match clock" ambiguity matters less here than for full-length matches, but
  still applies to any absolute timing claim.
- Kill geometry: several kills (M2, M3) show steep-pitch pursuit in the
  frames immediately before the kill, suggestive of vertical/diving finishes,
  but this was not confirmed rigorously — medium-low confidence.

---

## Finals format — REWRITTEN 2026-09-03 from the 본선 운영 안내

**This section previously described a "Round 4+ tie-break at 10,000 ft".
That round does not exist.** The official 본선 운영 안내 (2026-09-03)
supersedes the team-supplied slide this block was built from on 2026-09-02.
Full detail in `COMPETITION_RULES.md` §5.1–5.2 and §7; the scouting-relevant
parts:

| | Every game | Head-On 모드 |
|---|---|---|
| When | all of them | knockout only, **after games 1 AND 2 both draw** |
| Separation | **cycles by game index**: 2,000 → 2,500 → 3,000 → 2,000 → 2,500 ft | **not published** (our 3,048 m proxy is an assumption) |
| Geometry | **Antiparallel and abeam** — the two aircraft travel in opposite directions on parallel tracks, tail-to-tail (diverging). Each one's LOS to the other runs ~90° across its own nose. | **Nose-to-nose head-on** (정면 교전) |
| Model | main model | optionally a separately submitted **헤드온 모델**, one-way for the rest of that match |

**Date/format:** 2026-09-17, 16 teams (12 direct + 4 wildcard). Group stage:
4 groups × 4 teams, round robin, **BO3**, 승 3 / 무 1 / 패 0, top 2 advance.
Knockout: **BO5** single elimination (8강 → 4강 → 결승).

**Our group — A조:** GoGoSSung (숭실대) · Fight's on! (연세대) ·
**진짜보라매 (공사, us)** · HAnnamAir (한남대).
**GoGoSSung is a group opponent**, not a hypothetical — the dossier above is
now scouting on a team we are guaranteed to play, at BO3.
8강 pairing if we top the group: **A1 vs D2**; if we finish second: **A2 vs D1**
(D조 = TrAI Everything · FNG · SSUPERSONIC · Check_six).

**Standings tiebreak: 승점 → 세트승수 → 세트득실차 → 승자승 → 코인토스.** Two
of the four keys are set-level, so *how* we win the BO3s matters, not just
whether — and drawn sets cost differential without costing a match.

**This confirms the reading the project already had.** `COMPETITION_RULES.md`
§5.1 called it "a BEAM merge, not a head-on… headings antiparallel, LOS running
across them, i.e. ~90° off each aircraft's own nose," and
`student/match_scenario_wrapper.py` encodes it as `MATCH_LOS_DEG = 90.0`. It
left `los_deg` a parameter because the slide art also admitted a 180°
(collinear tail-to-tail) reading. **The 90° reading is the correct one** —
"parallel to each other" excludes the collinear alternative. `match_base` has
been modelling the right geometry all along, and `Gate2_BeamMerge` (HCA > 120°,
own ATA 45–150°, dist < 2500 m) fires at it as designed.

**Three consequences that do still bite:**

1. **Spawn range sits inside the Phase-1 band, at its weak end.** 610–914 m is
   2,000–3,000 ft and Phase 1 pays from 500 ft, but the range term makes real
   damage **0.40 at 2,000 ft falling to zero at 3,000 ft**. Damage worth having
   is at 150–300 m (0.81–1.00). The opening matters because it is the front of
   a 100-second coefficient-1.0 window — not because spawn range is lucrative.
2. **It is a ~90° pointing problem, not a 180° reversal.** Each aircraft needs
   roughly a quarter-turn, not a half-turn, to bring guns to bear, so
   time-to-first-shot is short and the one-circle/two-circle choice is made
   almost immediately. That is the window in which GoGoSSung has been hit.
3. **Added 2026-09-03: the opening is no longer one condition, it is six.**
   Three start separations × randomized initial altitude and speed × Blue/Red
   alternating every game. Any scouted read of an opponent's opening — including
   GoGoSSung's "win the first 15 seconds" vulnerability — was observed at
   whatever conditions those matches ran, and may not hold at 3,000 ft or at a
   low-altitude spawn. Record the start conditions with every future
   observation; the per-team block below now has rows for them.

---

## Prelim standings — schedule-adjusted, 2026-09-03

**Source:** final prelim standings supplied by the team, 2026-09-03. Swiss format
with MTG-style tiebreakers: **OMW%** = opponents' match-win percentage (schedule
strength), **GW%** = our own game-win percentage, **OGW%** = opponents' game-win
percentage. Wildcards are the 4th seed of each group.

| 조 | Team | Record | OMW | GW | OGW |
|---|---|---|---|---|---|
| **A** | GoGoSSung (숭실대) | 5-0 | 54.7 | 100 | **48.0** |
| **A** | Fight's on! (연세대) | 5-1 | 55.6 | 83.3 | 53.9 |
| **A** | **진짜보라매 (공사, us)** | 5-1 | **50.0** | 83.3 | **48.3** |
| **A** | HAnnamAir (한남대) · wildcard | 4-2 | **69.4** | 66.7 | **69.4** |
| B | 추락도락이다 (아주대·서울대·포항공대) | 5-0 | 56.0 | 100 | 56.0 |
| B | 봉희찬재관 (한국항공대) | 5-1 | **69.4** | 83.3 | 68.9 |
| B | 궁댕이채찍 (인하대·한성대·상명대) | 5-2 | 58.5 | 71.4 | 56.6 |
| B | Yaksha (UNIST) · wildcard | 4-3 | 55.6 | 50.0 | 55.6 |
| C | 불나방 (서울대) | 5-0 | **68.0** | 100 | **66.0** |
| C | 구리인창 (공주대·한경국립대·상명대·경동대) | 5-1 | 52.8 | 83.3 | 52.8 |
| C | 에어프라이어 (한국항공대) | 5-1 | 56.7 | **80.0** | 56.7 |
| C | Dragon (경기대) · wildcard | 4-3 | 46.9 | 57.1 | 38.4 |
| **D** | TrAI Everything (한국항공대·KAIST·서강대) | 5-0 | **64.0** | 100 | **64.0** |
| **D** | FNG (공사) | 5-1 | 66.7 | 83.3 | 65.0 |
| **D** | SSUPERSONIC (숭실대) | 5-1 | 50.0 | 83.3 | 44.4 |
| **D** | Check_six (조선대) · wildcard | 4-2 | 55.6 | 66.7 | 50.0 |

### Four reads, and what each is worth

**1. Our own 5-1 is one of the least-tested records in the field.** OMW **50.0**
(tied second-lowest with SSUPERSONIC, above only Dragon's 46.9) and OGW **48.3**
(fourth-lowest). We beat a below-average schedule. **Consequence for this
project: prelim placing is weak evidence about us specifically**, and the league
matrix (F60) is the better basis for decisions than the tournament result. It
also means the assumption behind F56 — "the scouted field is stronger than we
are" — is *supported*, not contradicted, by our own good record.

**2. GoGoSSung is the softest-scheduled of the four undefeated teams.** It is
**the only 5-0 team whose opponents' game-win percentage is below .500**
(OGW 48.0):

| 5-0, GW 100% | OMW | OGW |
|---|---|---|
| 불나방 (C) | 68.0 | 66.0 |
| TrAI Everything (D) | 64.0 | 64.0 |
| 추락도락이다 (B) | 56.0 | 56.0 |
| **GoGoSSung (A)** | **54.7** | **48.0** |

This is doubly notable because **Swiss pairs winners against winners** — an
undefeated team's OMW should *rise* through the rounds. GoGoSSung's did not.
Its 5-0 is real and its GW 100% is real; the *field it was tested against* was
not. **The dossier above stands; the aura around it should shrink.** The two
genuinely strongest teams by this measure are **불나방** and **TrAI Everything**.

**3. HAnnamAir is not the soft fourth seed.** 4-2, labelled wildcard — and
**OMW 69.4 / OGW 69.4, tied with 봉희찬재관 for the hardest schedule in the
entire 16-team field.** It went 4-2 against the toughest pairings anyone drew.
The wildcard label is seeding, not strength. **Schedule-adjusted, A조 is
plausibly HAnnamAir ≈ GoGoSSung > Fight's on! ≥ us** — treating HAnnamAir as
the group's free win is the single most likely way to miss the top two.

**4. Winning A조 is worth a materially easier 8강.** The bracket is
**M1 = A1 vs D2** and **M4 = A2 vs D1**. D조's top seed is **TrAI Everything**
(5-0, OMW 64.0) — the second-strongest team in the tournament by schedule-
adjusted record. Finishing **second in A조 routes us straight into it**;
finishing **first** gives us FNG or SSUPERSONIC. Combined with the standings
tiebreakers (승점 → 세트승수 → 세트득실차, `COMPETITION_RULES.md` §7), this turns
"top 2 advances" from a threshold into a target, and it is the strongest
argument yet for F61's draw-rate tiebreak: drawn sets cost differential in
exactly the place where group order is decided.

### One anomaly worth an answer

Two GW% figures are inconsistent with one game per match: **에어프라이어** 5-1
shows **80.0%** (= 4/5, not the 83.3% a 5-1 record implies) and **Yaksha** 4-3
shows **50.0%** (= 4/8, not 4/7 = 57.1%). The 에어프라이어 figure is exactly
what a **bye or a forfeit win** produces — a match credited with no game played.
If a prelim match was decided by an opponent failing to connect, that is the
same failure mode our `.exe` packaging risk creates (`MATCH_DAY_RUNBOOK.md` §8),
and it would also be evidence about how the organizers handle draws. **Asked of
the team 2026-09-03.**

### Caveats

- OMW/OGW measure **who you were paired against**, not skill directly. In Swiss
  they are correlated with your own results, which is precisely why GoGoSSung's
  low OMW at 5-0 and HAnnamAir's high OMW at 4-2 are informative — both run
  against the expected direction.
- Samples are 5–7 matches. These are tiebreakers, not ratings.
- **None of this changes what we can ship** (F61: one main model). It changes
  the **weights on the league roster** and the **scouting order** — nothing else.

### Scouting priority, reordered by this table

1. **TrAI Everything** (D1 — our 8강 opponent if we finish second, and the
   strongest schedule-adjusted team we can actually meet)
2. **HAnnamAir** (guaranteed group opponent, most underrated by seed)
3. **Fight's on!** (guaranteed group opponent, directly ahead of us on tiebreak)
4. **불나방** (strongest in the field, but only reachable at 4강/결승)
5. GoGoSSung — dossier already exists; re-read it against read 2 above.

---

## Scouting intake — how a dossier becomes a sparring partner

Scouting is only worth the effort if it changes what we fly against. This
section is the pipeline: **observed telemetry → inferred behaviour → archetype
parameters → a config the league can actually run.** Fill the block below for
each new team; do not reason ad hoc.

### The per-team block

```
### <Team name>
**Scouted:** <date> · **Source:** <n> matches, <what kind of footage> ·
**Record observed:** <W-L-D, and note if the sample is wins only>

| Observable                  | Value | How read |
|---|---|---|
| **Start separation / game #** |     | 2,000 / 2,500 / 3,000 ft — from the game index |
| **Start altitude & speed**  |       | HUD at t=0; randomized per game, so log it every time |
| **Side (Blue/Red)**         |       | alternates every game |
| Mean health retained        |       | HUD health bar at match end |
| Time to first damage        |       | footage clock MINUS pre-roll (see clock caveat) |
| Longest scoreless stretch   |       |  |
| Hits per scoring window     |       | 1 = one-and-done, >1 = salvo |
| Engagement ranges observed  |       | convert to ft and check against the §6.2 band |
| Vertical vs flat kills      |       |  |

**Inferred behaviour:** <2-4 sentences>
**Archetype:** <roster row below> · **Confidence:** <high/med/low>
**Sparring parameters:** <the exact CLI flags>
```

> **Check the mechanism against `COMPETITION_RULES.md` before acting on it.**
> This is not boilerplate — the first revision of this file read gun-WEZ damage
> events as missile shots in a **guns-only** competition, and credited the
> opponent with a "Battle Phase" gate that is the competition's own clock-driven
> cone widening. Two of six counter-tactics briefed for things that do not
> exist. Telemetry is data; mechanism is interpretation.

### Archetype roster

Every archetype is parameterisation of code we already have — no new
controller. `mirror`/`sniper`/`aggressor` are built from `VPTrackingProvider`
via the per-side flags on `scripts/eval_v5_vs_bt.py`.

| Archetype | Represents | Built from |
|---|---|---|
| `cutoff` | the extend-and-clock type; refuses the re-merge and wins on accumulated damage | organizers' binary via `scripts/cutoff_provider.py` |
| `mirror` | a peer at our level | our own shipped config on the target side |
| `sniper` | patient, engages rarely, retains health | narrow envelope: `--target-vptrack-range-m 2500 --target-vptrack-los-deg 45 --target-vptrack-throttle 1` |
| `aggressor` | forces decisive merges, trades freely | wide envelope + deck guard: `--target-vptrack-range-m 6000 --target-vptrack-los-deg 120 --target-vptrack-hard-deck 1000` |
| `bt_only` | rule-based floor | `--target-backend bt` |

**Why these five.** They span the axis that actually decides our matches —
willingness to trade damage. `cutoff` sits at one end (declines trades, banks
the clock), `aggressor` at the other, `sniper` trades rarely but only on
favourable terms. A config tuned against one of these is not tuned against the
others, which is the whole reason for a roster rather than a single benchmark.

### GoGoSSung → `sniper` (worked example)

**Archetype:** `sniper` · **Confidence: low — this is a hypothesis, not a
replica.** Everything known about GoGoSSung comes from broadcast footage of
five of its wins. The mapping rests on three observations: 96.5% mean health
retained (it is rarely in a position to be shot), 80–136 s scoreless stretches
in three of five games (it declines low-percentage shots), and multi-hit
salvos once it has an angle (it commits fully when it does engage). A narrow
engagement envelope reproduces the first two; nothing we have reproduces the
third.

**Label it as an analogue in every results table.** A league row reading
"beat `sniper` 60%" must never be read as "beat GoGoSSung 60%".

**What would raise confidence:** any footage of GoGoSSung *losing* or under
sustained pressure. The current sample is five wins — pure survivorship bias,
and it tells us nothing about what happens when someone gets inside its
envelope early, which is the one thing that has worked (M5, t≈10–12 s).
