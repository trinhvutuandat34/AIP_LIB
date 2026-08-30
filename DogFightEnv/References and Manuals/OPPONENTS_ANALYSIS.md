# Opponents Analysis

Scouting log for teams in the 2026 AI Pilot Top Gun Challenge. One entry per
opponent, added as match footage becomes available. Each entry is built by
reconstructing the opponent's engagements from broadcast/replay footage
(health-bar telemetry, WEZ-cone visuals, missile trails, battle-phase
markers, contrail geometry), not from their code or logs — treat findings as
hypotheses to validate in our own practice sims, not guarantees.

## Opponent Index

- [GoGoSSung](#gogossung) — scouted 2026-08-30, 5 matches, 5–0 record observed

---

## GoGoSSung

**Scouted:** 2026-08-30 · **Source:** 5 recorded matches (broadcast HUD footage) ·
**Record observed:** 5–0 (won every match analyzed, all by kill)

### Summary

Across five games GoGoSSung conceded meaningful damage exactly once and was
never brought to a draw or loss. Average health retained across the sample
is **96.5%**. It wins in two different modes depending on what the opponent
gives it: a fast decisive kill when it gets an early energy/position
advantage (59.5s, no damage taken), or a patient multi-pass grind lasting
150–207 seconds when it doesn't. The one match where an opponent actually
hurt it (Match 5) is the most useful data point in the set — see
[Vulnerabilities](#vulnerabilities).

### Match-by-Match Log

| # | Opponent | Side | Duration | GG health end | Hits taken by GG | Hits GG landed | Win method |
|---|---|---|---|---|---|---|---|
| 1 | 개쩌는유컨 | Red | 156s | 98.5% | 1 (graze) | 6 | 40s scoreless open → 6-pass whittle → terminal-phase missile kill (~t146s) |
| 2 | Physics2Chemistry2 | Red | 59.5s | 100% | 0 | 2 | High-to-low diving pass, hit despite target's break turn; fastest win in sample |
| 3 | VAlkyrie | Red | 156s | 100% | 0 | 5 | **96s scoreless** (61% of match) → low-to-high vertical missile (763–933m lock) → 4-hit closeout |
| 4 | MotherGoose | Blue | 202s | 100% | 0 | 8 | Immediate opening shot (t≈8s) off two-circle spawn → 80s + 40s lulls → vertical high-yo-yo → 3 hits in ~12s to finish |
| 5 | 봉희찬재광 | Red | 207.6s | **84.0%** | **1 (real, ~16%)** | 3 | Opponent hits GG in first ~10–12s (only hit anyone landed) → 136s scoreless → only rolling scissors in sample → 2 hits in ~2s → kill in final seconds of clock |

### Patterns & Style

- **Shot discipline.** Tolerates long scoreless stretches (80–136s, three of
  five games) rather than forcing a low-percentage shot. Do not read a quiet
  fight as a sign it has no plan.
- **Geometry-agnostic.** Confirmed kills from high-to-low (M2), low-to-high
  (M3), and off a vertical high-yo-yo reposition (M4) — no single blind
  angle to bait it into.
- **Finishing instinct.** Once it has an angle it fires more than once in
  quick succession rather than one-and-done: 3 hits in ~12s (M4), 2 hits in
  ~2s (M5).
- **Comfortable in the vertical.** Won the one high-yo-yo/vertical duel in
  the sample outright (M4).
- **Uses discrete "Battle Phase" gates** (in-HUD indicator, phases 1→3+);
  finishing shots in M1, M3, and M5 all landed during/after a Battle Phase 3
  transition.
- **Composure at the buzzer.** Its hardest fight (M5) still ended in a kill
  in the literal final seconds of the clock, not a points/time decision.

### Strengths

1. Excellent shot discipline / patience — won't force a bad shot.
2. No fixed preferred attack geometry — adapts to whatever altitude
   advantage is on offer.
3. Stacks follow-up shots once it has an angle instead of relaxing after
   one hit.
4. Performs well in vertical fights, not just flat turning ones.
5. Closes out contested matches under time pressure rather than fading.

### Vulnerabilities

1. **The opening window.** The only hit anyone landed on it (M5) came in
   the first ~10–12 seconds, before the match intro graphic even finished
   clearing. A fast, prepared first-look shot is the one thing that has
   worked.
2. **Forcing a scissors.** The only time it was pulled into a genuine
   close-in rolling scissors (M5), that same game produced its longest
   scoreless stretch (136s) and its closest final margin in the sample.
3. **Not literally unhittable.** 2 of 5 opponents (40%) drew blood — it can
   be hit, even though none has landed the kill on it yet.
4. **Punishes stillness, not maneuvering.** Every scoring hit against an
   opponent in the sample landed while that opponent was flying straight or
   already committed to an escape it couldn't complete — never while
   actively evading.

### Recommended Counter-Tactics (ranked by evidence strength)

1. **Drill a fast first-look shot at the merge.** The only tactic that has
   drawn blood in five games; it worked inside the first ~10 seconds.
   *(Evidence: M5, t≈10–12s)*
2. **Plan to fly the full clock.** Three of five wins ran 150–207s; build
   the game plan and energy/countermeasure budget around a full-length
   fight, not an early decision. *(Evidence: M1, M4, M5)*
3. **Force a close-in turning fight over a missile trade at range.** The
   one game that reached a real scissors also produced the longest
   scoreless stretch and tightest margin seen. *(Evidence: M5, t≈136–151s)*
4. **Never go static after beating a shot.** Keep maneuvering through any
   follow-up; every hit it landed found a target flying straight or
   mid-commitment to an unfinished maneuver. *(Evidence: M2, M4)*
5. **Brief for a follow-up salvo, not a single shot.** Assume a second/third
   shot is inbound once it has an angle. *(Evidence: M4 — 3 hits/12s; M5 —
   2 hits/2s)*
6. **Hold energy/countermeasures in reserve for the final 15 seconds.** It
   found a kill in the closing seconds in three of five games rather than
   accepting a decision. *(Evidence: M1, M4, M5)*

### Caveats / Confidence

- Sample is five GoGoSSung **wins** only — survivorship bias. No footage of
  it losing or absorbing sustained pressure beyond what M5 shows.
- All figures read from broadcast HUD telemetry (health bars, WEZ-cone
  visuals, missile trails, phase markers), cross-checked against
  timestamps — not raw sim logs or its actual control/policy inputs.
- Opponent skill varied across the five games; long scoreless openings may
  partly reflect a passive opponent rather than pure restraint by
  GoGoSSung.
- No visibility into countermeasure logic, sensor range, or missile
  loadout from video alone. Validate all recommendations above in our own
  practice sims before relying on them in a live match.
