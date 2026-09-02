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

### Recommended counter-tactics

Ranked by evidence strength. Items 3 and 6 of the original list are **deleted**
— they briefed for a missile trade and a countermeasure reserve, neither of
which exists in this competition.

1. **Win the first 15 seconds.** It is the only thing that has ever worked
   against them, it pays at coefficient 1.0, and the finals start geometry
   hands it to whoever reverses faster. *(M5, t≈10–12 s)*
2. **Plan to fly the full clock.** Three of five wins ran 150–207 s. Budget
   energy for a full-length fight, not an early decision. *(M1, M4, M5)*
3. **Never go static after beating a shot.** Every hit it landed found a
   straight-flying or mid-commitment target. *(M2, M4)*
4. **Brief for a salvo.** Assume a second and third shot once it has an angle.
   *(M4 — 3 hits/12 s; M5 — 2 hits/2 s)*
5. **Deny the late cone rather than racing it.** Its Phase 2/3 hits come from
   holding a solution on a predictable target. Late-match unpredictability is
   worth more than late-match aggression, because a Phase-3 hit only pays 0.1.
6. **Do not read a quiet fight as a won fight.** Three of five games had 80 s+
   scoreless stretches and all three ended in a kill.

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

## Finals format — confirmed 2026-09-02 (team-supplied organizer slide)

Supersedes the "slide art admits two readings" ambiguity in
`COMPETITION_RULES.md` §5.1 and in `student/match_scenario_wrapper.py`'s
docstring.

| | Rounds 1–3 | Round 4+ (tie-break) |
|---|---|---|
| Separation | **2,000–3,000 ft (610–914 m)** | **10,000 ft+ (3,048 m+)** |
| Geometry | **Antiparallel and abeam** — the two aircraft travel in opposite directions on parallel tracks, tail-to-tail (diverging). Each one's LOS to the other runs ~90° across its own nose. | **Nose-to-nose head-on** (정면 교전) |
| Method | AlphaDogFight engagement rules | Winner-take-all |

**Date/format:** 2026-09-17, 16 teams, 4 groups, **BO3** (first to 2 wins
advances); a 4th round is played if still level after 3.

**This confirms the reading the project already had.** `COMPETITION_RULES.md`
§5.1 called it "a BEAM merge, not a head-on… headings antiparallel, LOS running
across them, i.e. ~90° off each aircraft's own nose," and
`student/match_scenario_wrapper.py` encodes it as `MATCH_LOS_DEG = 90.0`. It
left `los_deg` a parameter because the slide art also admitted a 180°
(collinear tail-to-tail) reading. **The 90° reading is the correct one** —
"parallel to each other" excludes the collinear alternative. `match_base` has
been modelling the right geometry all along, and `Gate2_BeamMerge` (HCA > 120°,
own ATA 45–150°, dist < 2500 m) fires at it as designed.

**Two consequences that do still bite:**

1. **Spawn range sits inside the Phase-1 band, at its weak end.** 610–914 m is
   2,000–3,000 ft and Phase 1 pays from 500 ft, but the range term makes real
   damage **0.40 at 2,000 ft falling to zero at 3,000 ft**. Damage worth having
   is at 150–300 m (0.81–1.00). The opening matters because it is the front of
   a 100-second coefficient-1.0 window — not because spawn range is lucrative.
2. **It is a ~90° pointing problem, not a 180° reversal.** Each aircraft needs
   roughly a quarter-turn, not a half-turn, to bring guns to bear, so
   time-to-first-shot is short and the one-circle/two-circle choice is made
   almost immediately. That is the window in which GoGoSSung has been hit.
