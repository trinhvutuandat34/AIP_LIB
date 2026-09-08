# AIP TGC 2026 — Competition Rules, Scoring, and Constraints

> Extracted from `Day_1_Lecture_Materials/2026 AI Pilot Top Gun Challenge.pptx` (the kickoff
> deck — this is where the actual rules live), cross-checked against the training
> environment's source code. The Day 2 deck (`AIP_경진대회_매뉴얼_rev7.pptx`, "competition
> manual" in name only) and both `.docx` manuals turned out to be **technical workflow
> guides** (how to run training/YAML/dashboard), not rules documents — confirmed by reading
> them in full. The HTML RL manual (`2026_aip_rl_manual_rev8.html`) is a training-metrics
> guide, same story. So this file is built almost entirely from the Day 1 deck, with one
> explicit code cross-check noted in §7.
>
> See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) for where things live on disk (including a
> note that the Day 1/Day 2 source materials cited above aren't present in this checkout),
> [PROJECT_ANALYSIS.md](PROJECT_ANALYSIS.md) for how the training system works internally, and
> [COMPETITION_PLAN.md](COMPETITION_PLAN.md) for the current strategy/execution plan.
>
> **The deck states explicitly: "대회 규칙 및 일정은 대회 사정에 의해 변경될 수 있습니다"
> — competition rules and schedule may change.** Treat anything here as the latest known
> state, not a guarantee.

## 1. What this competition actually is

Built on REALTIMEVISUAL's "AI Pilot" project (2020–2023, with Korea's Agency for Defense
Development/ADD) — conceptually the domestic counterpart to DARPA's AlphaDogFight Trials.
That original project's AI (rule-based, supervised, and RL variants) reportedly beat veteran
Air Force pilots and flight-school instructors with a 90% win rate in first evaluation and
100% in the final evaluation. **Students are given a deliberately degraded/reduced subset of
that same toolset** ("제공하는 AI 개발환경은 일정 부분이 열화, 제거된 상태로 제공") — this
independently confirms the `MyTrainEnv` vs `Release/` split already noted in
[PROJECT_ANALYSIS.md](PROJECT_ANALYSIS.md) §8.

**288 teams** registered for this run of the competition.

## 2. Awards

| Award | Awarded by | Prize (만원 = 10K KRW) | Who gets it |
|---|---|---:|---|
| 대상 (Grand Prize) | Minister of Science & ICT + President of Korea Aerospace University | 1,000 | Champion |
| 최우수상 (Excellence) | Air Force Chief of Staff | 500 | Runner-up |
| 우수상 (Merit) | Defense Acquisition Program Administration head + KASA head | 200 | 3rd–4th place |
| 학술상 (Academic) | Korean Air President | 200 | Best academic-presentation-session team |
| 장려상 (Encouragement) | KAI, Hanwha Systems, Hyundai Rotem, LIG D&A Presidents | 100 | Round-of-8 teams |
| 본선진출상 (Finals qualifier) | Korea Aerospace University SW-centered Univ. project lead | 50 | Any team that reaches the finals |

## 3. Schedule

| Stage | Format |
|---|---|
| **Cutoff** | Beat an operating-committee-designated baseline aircraft to advance. (As of the deck, the exact cutoff mechanism was still being decided — see §9.) |
| **Prelims (예선)** | Swiss-league format, single matches (단판), minimum 3 engagements. Selects **8 top teams + 4 wildcard teams**. Wildcards restricted to teams whose school isn't already represented, max 1 team/university. |
| **Finals group round (본선 조별 라운드)** | Split into four groups of 3 (3:3:3:3), best-of-3 (3판 2선승제), round-robin within group. Top 2 per group advance. |
| **Finals (본선)** | Round-of-8 single-elimination tournament, **best-of-5** (5판 3선승제). |

**Timeline mentioned:** prelims at end of August (2026), championship tournament mid-September (2026).

## 4. Core engagement rules

- **Perfect State Information**: no sensor error, detection delay, noise, or visibility limits. Your AI receives the opponent's exact real-time position/attitude/speed directly from the simulator. This is explicitly so the competition tests **situational-awareness → aircraft-control performance only**, not perception/sensing.
- **60 Hz**: the engagement server sends battlefield state to your client at 60 Hz (Δt = 1/60s ≈ 0.016666s); your client must answer with a control command at 60 Hz too.
- **Response-time penalty**: your own AI's *computation* time (not network latency) is penalized if it exceeds **0.1667s (= 1/6 second = 6 frames at 60Hz)** for a single decision. **CORRECTED 2026-08-20** (re-read the source slide directly, `LIVE_INFERENCE_FRAME_BUGS.md` §7): this is a latency *budget* per decision, not a mandate to decide at 10 Hz. The deck's own side-note is explicit — *"AI doesn't need to decide every 1/60s, but the control command must answer battlefield info at 60Hz"* — i.e. the 60 Hz answer-rate (line above) and this 0.1667s compute-latency cap are two separate rules, and neither requires `--action-repeat 6`. `ProviderCommandPolicy.compute_command` already sends a CMD every tick regardless of action-repeat (cached or freshly computed), satisfying the 60 Hz rule structurally. `step_ratio: 6`/`--action-repeat 6` exists to match RL **training** dynamics (a train/inference consistency argument for a *trained* policy), not to satisfy this rule — measured live, `VPTrackingProvider.compute_action` runs worst-of-5000 in 0.611 ms, ~272× inside the 166.7 ms budget, at any action-repeat value. `vptrack` was never trained, so `--action-repeat 1` is valid and is what should ship for it; a trained RL/hybrid mode should keep `--action-repeat 6` to match its own training `step_ratio`, as a per-mode choice, not a global rules requirement.
- **Guns only** — extreme close-range gun engagement (no missiles), with a "roughly probabilistic" simulated gun cone. Win by dealing more damage or shooting down the opponent within the time limit.

## 5. Engagement space & duration

- **Engagement duration: 200 seconds.** Whoever has dealt more damage / has more health when time runs out wins.
- **Minimum altitude: 1000 ft (≈300 m).** Dropping below this is processed as a crash/loss.

### 5.1 Starting geometry — REWRITTEN 2026-09-03 from the 본선 운영 안내

**Source of record: the organizing committee's 본선 운영 안내 (2026-09-03).** It supersedes the
kickoff-deck scenario slides ("개요: 교전 시나리오 룰(예선)" / "…(본선)", transcribed 2026-08-06)
wherever the two disagree. The slides said the exact 시작거리/고도/속력 were "차후 공개"; this is
that release.

| Item | Official value |
|---|---|
| **초기 고도 / 속도** | **RANDOM, every game.** The band is not published. |
| **시작 상대거리** | Cycles with the **game index**: 1경기 **2,000 ft** → 2경기 **2,500 ft** → 3경기 **3,000 ft** → 4경기 **2,000 ft** → 5경기 **2,500 ft** … |
| **Blue / Red** | Alternates every game. Game 1: the bracket's **left-hand team is Blue**. |
| **Head-On 모드** | A **draw-triggered mode in the knockout rounds**, not a round number — see §5.2. |
| Everything else | "그 외 기본 경기규정은 예선 규정을 동일하게 적용" — the prelim rules (200 s clock, 1000 ft floor, guns-only, the §6.2 phased WEZ) carry over unchanged. |

**Two things this KILLS.** Both were load-bearing:

1. **There is no "round 4 at 10,000 ft".** The slide-derived row — *"Finals round 4+: tie-break,
   entered only if 3 rounds are level, 10000ft 이상, 서로 마주본 상태에서 정면 교전 수행"* — is
   **superseded**. Game 4 starts at **2,000 ft** like game 1. The head-on GEOMETRY survives as
   Head-On 모드; the 10,000 ft separation and the round number do not.
2. **Fixed altitude/speed is no longer a defensible assumption.** Every local measurement to date
   was taken at one spawn preset (4572 m / 200 m/s). With both randomized per game, a
   single-preset number is a point sample. This compounds F38: real server packets showed
   altitudes of 0–1067 m (median 604 m), and `Task_ClimbToSafeAltitude` (Gate 0) fires below
   914 m and starves every tactical gate under it. Local eval has never spawned low enough to see
   it. **Randomized altitude makes that a recurring match condition, not a one-capture anomaly.**

**What SURVIVES the change:** the separation band is still 2,000–3,000 ft, and the merge geometry
is still a **BEAM merge, not a head-on**. Both diagrams draw the two
aircraft pointing in **opposite directions** with the separation arrow **between** them:
headings antiparallel, LOS running across them, i.e. ~90° off each aircraft's own nose.
Only the round-4 slide says "정면". This matters because it invalidates two of the three
scenarios this project had been evaluating against:

- `obfm_offensive` / `obfm_defensive` stage a **six-o'clock advantage the rules never grant**.
- `two_circle_headon` is neutral but spawns at **1,497–5,379 m** against a real **610–914 m**.

Modelled in `student/match_scenario_wrapper.py` as `match_base` / `match_tiebreak`; prefer
those for any result meant to predict match performance. `los_deg` is left a parameter because
the slide art also admits a 180° (tail-to-tail) reading — measured, not assumed.

> **Caveat added 2026-09-03.** `match_base` samples separation **uniformly** over 610–914 m,
> whereas the real thing is the three-value cycle above; and `match_tiebreak` keeps its 3,048 m
> separation, which is now an **assumption** (see §5.2), not a citation. `MATCH_SEPARATION_SET_M`
> in that module holds the real set. The uniform sampling was left in place deliberately so the
> existing F56/F58/F59 numbers stay comparable — re-measure against the discrete set as its own
> pass rather than changing the distribution underneath them.

### 5.2 Head-On 모드 — draw-triggered, geometry known, distance NOT known

From the same announcement (§5, 무승부 및 Head-On 모드):

- Applies in the **결선라운드** (knockout: 8강/4강/결승, all BO5). The group stage is BO3 with
  draws scored at 1 point, and the announcement does not extend the mode to it — **asked, not
  confirmed**.
- Trigger: **if games 1 AND 2 are both draws**, every subsequent game of that match is played in
  Head-On mode.
- A team may **optionally switch to a separately submitted 헤드온 모델** at that point. The switch
  is **one-way for the rest of that match**; the next match starts from the main model again.
- If everything is still level at the end: **one 연장전 game**, then a **coin toss**.

**What is not published: the separation and the exact geometry of Head-On mode.** "정면 교전"
gives us LOS ≈ 0° and that is all. The project's `match_tiebreak` proxy uses 3,048 m purely
because that was the old round-4 number — **if Head-On mode instead reuses the 2,000/2,500/3,000
ft cycle, every F58/F59 head-on measurement was taken at 3.3–5× the real range and does not
transfer.** Sweep it via `DOGFIGHT_HEADON_SEPARATION_M` until the organizers answer.

**Strategic consequence.** A draw is no longer merely a lost point — in the knockout it is the
event that *hands the opponent the option to change models mid-match*. Our own peer league runs
draw-heavy (F59: 18 draws in 50). Reducing the draw rate is now worth points in the group stage
**and** denies that option in the knockout.

**Cutoff (§3) — updated from the same slide.** Too many teams applied (`예상보다 너무 많은
참여팀이 지원`), and the mechanism is still under discussion between two proposals:
**제1안** only teams that beat an operating-committee model advance; **제2안** the model is
distributed to every team and each decides for itself whether to enter. Both hinge on a
reference model of "적당한 성능". **Under 제1안 a draw does not advance** — which is the
modal outcome against a capable opponent (see COMPETITION_PLAN.md §4.1 D1-SELFPLAY).

## 6. Damage model — two versions, don't confuse them

### 6.1 Base rule (the original AIP/AlphaDogFight damage model)

- Damage occurs when the opponent's aircraft center is inside your forward attack cone.
- Damage scales with proximity (closer = more damage).
- Cone: **LOS ≤ 1°, distance 500–3000 ft.**

### 6.2 Actual competition rule — eased, and it changes over the match

The live competition **widens the cone in phases as the 200s clock runs down**, explicitly
to reduce draws ("어떻게든 여러분의 전투기가 공격을 하고 무승부가 안나게 하기 위한 조치"):

| Phase | Time window | Cone | Damage coefficient |
|---|---|---|---:|
| 1 | 0–100s | LOS < 1°, 500–3000 ft | 1.0 |
| 2 | 100–150s | LOS < 2°, 500–3500 ft | 0.3 |
| 3 | 150–200s | LOS < 3°, 500–4000 ft | 0.1 |

Cone radii scale roughly `1 : 2.72 : 5.34`, cone volumes `1 : 6.36 : 21.37`. **If the enemy
sits inside a *narrower* phase's cone even during a later time window, the narrower phase's
(higher) damage coefficient applies** — e.g. at t=160s (nominally Phase 3), landing a
Phase-1-quality shot still pays Phase-1 damage, not the discounted Phase-3 rate
(*"하위 Phase에 적이 위치하는 경우 하위 phase의 대미지 적용"*).

**Exact per-phase damage formulas** (transcribed 2026-08-06 from the `통합 픽셀 데미지 맵`
slide — each phase has its OWN divisor; these were previously absent from this file and are what
any local phased-scoring estimate must use). `r` = forward range in **feet**, `θ` = LOS angle in
degrees. Evaluated in priority order, first match wins (*내부 Phase가 외부 Phase를 덮어씀*):

```
1) Phase 1 (최우선)  500 <= r <= 3000  AND  |θ| < 1°   ->  Damage = 1.0 × (3000 − r) / 2500
2) Phase 2 (그 다음)  500 <= r <= 3500  AND  |θ| < 2°   ->  Damage = 0.3 × (3500 − r) / 3000
3) Phase 3 (그 다음)  500 <= r <= 4000  AND  |θ| < 3°   ->  Damage = 0.1 × (4000 − r) / 3500
4) 그 외            r < 500  OR  |θ| >= 3°            ->  Damage = 0
```

Pixel/greyscale rendering on the slide: `Gray = round(255 × Damage)` → 0/26/77/255 for
Damage 0 / 0.10 / 0.30 / 1.00.

> **Two consequences this project measured (2026-08-05/06), both in `COMPETITION_PLAN.md` §4.1:**
> 1. **Damage is maximal at 500 ft and exactly ZERO at 3000 ft** (row A2). `Task_GunTrack` was
>    parking at ~1830 ft → coefficient 0.47, discarding ~2.1–2.3× of the available damage per
>    scoring step. It had no range term at all until this was fixed.
> 2. **`r < 500 ft` is a zero-damage dead zone** (row A5) — Gate 2.5's floor was 150 m = 492 ft,
>    an 8 ft sliver where the BT believed it was in the band and scored nothing. Now 152.4 m.
>
> Scoring the BT's existing traces under this full 3-phase model still yielded **exactly 0
> damage**, because range and alignment are never simultaneously satisfied (row A4) — so
> implementing Phase 2/3 locally would not change the local result, and is deprioritized.

### 6.3 Cross-check against the training code — this matters for your strategy

**RESOLVED 2026-07-08, then REGRESSED 2026-07-15 and left that way deliberately — read the
2026-07-16 note before trusting the "implemented" claims below.** This §6.3 originally flagged
both as gaps; both were implemented 2026-07-08 and confirmed exact-match against the official
kickoff-deck slides 2026-07-11 (history below is accurate as of then). An accidental full-tree
revert on 2026-07-15 (see `PROJECT_STRUCTURE.md`'s dated "Current state" entry) reverted
`src/dogfight/config.py` and `single_agent_env.py` back to their pre-fix, single-phase state, and
— because neither has a plug-in hook a student file can reach, unlike `reward_module`/
`observation_module`/`stages_module` — the team **deliberately chose not to restore them** rather
than cross the `src/dogfight` hard boundary or edit the shared trainer scripts. As of 2026-07-16:

- **Phase 2/3 widening is NOT implemented in the platform right now.** `src/dogfight/config.py`
  has only a flat single cone (`angle_deg=2.0`, 500–3000 ft, implicit coefficient 1.0), and
  `single_agent_env.py::update_damage()` has no `_match_wez_phase()`/phase-iteration logic at all.
  The description below of how the (currently absent) phased version worked is kept for reference/
  if it's ever restored, not as a claim about current behavior:
  - `_WEZ_PHASES` carried all three phases (P1 `<1°`/500–3000 ft/coef 1.0, P2 `<2°`/500–3500 ft/
    coef 0.3, P3 `<3°`/500–4000 ft/coef 0.1), applied via the narrowest-qualifying-phase-wins rule
    (a Phase-1-quality shot pays Phase-1 damage even late). Every number and the damage formula
    matched the official slides exactly.
  - The pursuit-*shaping reward* (not the damage model) is still phase-aware today, in
    `student/my_reward.py` / `student/reward_lib.py`'s `WEZ_PHASES`/`wez_pursuit_multipliers()` —
    re-homed there 2026-07-15/16 after the platform copy was reverted. This affects what the RL
    policy is nudged toward, not what damage actually gets scored locally.
  - **2026-07-16, user-requested ("can we apply the real competition WEZ into the code"): the
    reward's *damage* term is now phase-aware too**, not just pursuit-shaping. New
    `student/reward_lib.py` functions `match_wez_phase()`/`wez_damage_estimate()` (reconstructed
    fresh from this section's own rule description — no bytecode of the platform's own
    phase-matching function survived the revert, unlike `WEZ_PHASES` itself) replace the flat
    `ownship_damage`/`target_damage` the platform hands `compute_reward()` with an estimate using
    the real 3-phase model. **This is a reward-only fix, not a damage-model fix**: investigated
    whether the platform's own number could be corrected from outside `src/dogfight` first, and it
    can't — `update_damage()` calls `self._sim.deduct_health()` on the closed FighterSim object the
    instant it computes a (wrong, flat-cone) damage value, before any student-space code ever sees
    the resulting state, and before `src/dogfight`'s own termination check reads that same value.
    Win/loss *timing* during local training therefore still runs on the flat cone, unfixably from
    student space. What's fixed is only what the policy is taught to optimize for. Also an
    approximation for a second reason: `update_damage()` accumulates true per-tick damage across
    `step_ratio` (6) physics ticks per env step, but `compute_reward()` only ever sees the
    end-of-block state — so the estimate treats the whole 6-tick block as one `delta_t` at the final
    geometry (`wez_step_ratio`/`wez_sim_hz` in `MY_REWARD_CONFIG`, default 6/60), not true per-tick
    accumulation. Verified via unit tests on every phase boundary (including the
    narrowest-qualifying-phase-wins rule) and a live `run_local_dogfight.py` rollout.
- **Episode length at the `full_dogfight` curriculum stage is 300s, not the competition's 200s**
  — corrected 2026-07-16, this section previously (wrongly) claimed 200s/`episode_step_limit:
  12000`. Verified directly against `src/dogfight/ai/curriculum.py`: the builtin `full_dogfight`
  stage is `episode_step_limit=18000` (60 Hz × 300s), and v4's override
  (`student/my_curriculum.py::_build_two_circle_v4`/`get_stages()`) only touches
  `max_iterations` (1000→1500) via `dataclasses.replace()`, leaving `episode_step_limit`
  untouched at 18000. Not a `DEFAULT_ENV_CONFIG` knob either way (the curriculum path doesn't
  forward `max_engage_time`/`episode_step_limit` from env_config — episode length is
  per-`CurriculumStage`). **Fixed 2026-07-16** (same day, user-approved): `student/my_curriculum.py`'s
  `full_dogfight_v4` override now also sets `episode_step_limit=12000` (both the normal
  `dataclasses.replace()` path and its defensive fallback branch), rather than only extending
  `max_iterations`. Zero retroactive impact — training hasn't reached this stage yet (v4 is
  stalled at stage 4/12, `obfm_offensive`; see the 2026-07-16 current-state entry above), so
  nothing was ever trained against the wrong horizon.

**Practical effect**: local training/eval currently scores damage against a flatter, non-widening
model than the real competition uses. This is a training-fidelity gap, not a competition-legality
one — the live Unreal server scores independently of this codebase's local `update_damage()`.

One open caveat on the damage model: the slides present `d_wez` as an instantaneous intensity
∈[0,1] (gray-value map); the code integrates it as `d_wez × delta_t × coef` into health per step.
The formula *structure* matches exactly, but the exact health-depletion rate / kill-time depends on
competition constants the deck says are "차후 공개 (released later)" — worth reconfirming when they
publish them.

## 7. Match scenario format — UPDATED 2026-09-03 (본선 운영 안내)

Finals: **2026-09-17**, 16 teams (12 direct + 4 wildcard), 4 groups of 4.

| Stage | Format | Starting distance | Advancement |
|---|---|---|---|
| Prelims | 1 round, single match | 2000–3000 ft | — |
| **조별라운드** | 4 groups × 4 teams, **round robin, BO3** | per-game cycle 2,000 / 2,500 / 3,000 ft | **top 2 of each group** (8 teams) |
| **결선라운드** | **8강 / 4강 / 결승, BO5, single elimination** | same cycle, extended: game 4 = 2,000 ft, game 5 = 2,500 ft | winner advances |

**Group scoring:** 승 3 / 무 1 / 패 0. Standings tiebreak order: **승점 → 세트승수 → 세트득실차
→ 승자승 → 코인토스**. Note the second and third keys are *set*-level — a 2:0 sweep and a 2:1 grind
are worth the same points but not the same set differential, and drawn sets bleed it.

**8강 bracket:** M1 = A1–D2 · M2 = B1–C2 · M3 = C1–B2 · M4 = D1–A2. 4강 = M1/M2 winners and
M3/M4 winners.

**Our group (A조):** GoGoSSung (숭실대) · Fight's on! (연세대) · **진짜보라매 (공사, us)** ·
HAnnamAir (한남대). GoGoSSung already has a dossier in
[OPPONENTS_ANALYSIS.md](OPPONENTS_ANALYSIS.md) — it is a group opponent, not a hypothetical.

**Tie-break:** there is no separate long-range tie-break round. Draws are resolved by Head-On 모드
(§5.2), then 연장전 1경기, then a coin toss. The training curriculum's α-sweep
(`two_circle_headon_a000`…`a180`, see [PROJECT_ANALYSIS.md](PROJECT_ANALYSIS.md) §4) was built for
the old 10,000 ft head-on round; it is the right *family* for Head-On mode — **and, since the
organizers confirmed Head-On separation as 3,048 m / 10,000 ft on 2026-09-05, the right
*separation* too.** (This sentence previously ended "…but its separations were chosen for a
scenario that no longer exists." That is now wrong: the scenario changed, the distance did not.
See §4.1 F72 and `student/match_scenario_wrapper.py` for the provenance.)

### 7.1 Submission — CHANGED 2026-09-03

| | Prelim (what we did) | Finals (required) |
|---|---|---|
| Artifact | ZIP of Python sources + DLLs, launched as `python student\my_submission.py` (`scripts/package_release.py`) | **실행파일 (.exe)** |
| Environment | `aip` conda env on the operations PC | must run **without installing any library**, immediately, on the same operations PC |
| Count | one | **main model (required) + head-on model (optional)** |
| Deadline | — | **2026-09-14 (Mon) 12:00 noon.** No modification, replacement, or resubmission afterwards. |

**The full submission spec arrived 2026-09-05 (§4.1 F75). It answers both open packaging
questions, and one answer reverses our plan — read this before building anything.**

| Item | Requirement |
|---|---|
| Archives | **two**, one per model: `팀명_APTGC2026_main.zip`, `팀명_APTGC2026_headon.zip` |
| ZIP contents | **exactly two files at the archive root, no subfolders**: `팀명.exe` (headon: `팀명_headon.exe`) + optional `config.json` |
| Explicitly banned | README, guide docs, source code, **라이브러리 폴더** — i.e. anything else at all |
| Exe filename | English if the team name is Korean — **this clause governs the FILENAME ONLY** |
| Displayed team name | **exactly** the registered team name; 임의의 식별자 / 테스트용 이름 / 축약형 forbidden. Head-on appends **`_HeadOn`** (suffix — `HeadOn_X` is explicitly rejected) |
| Network | from `config.json`, **fixed**: IP `127.0.0.1`, port `9999` — the server is on **loopback** |
| Packaging | single `.exe`; no separate install, no extra dependency install |
| Verification PC | **same spec as the prelim** (⇒ the debug CRTs are present — F73/F75) |
| Deadline | **2026-09-14 (Mon) 12:00 noon**, no resubmission |
| 개인정보동의서 | separate `팀명_개인정보수집및활용동의서.zip`, one signed PDF/HWP per member |

**Consequence: a PyInstaller `onedir` bundle is NON-COMPLIANT.** The three protected DLLs,
`aircraft/`, `engine/` and the Rule XMLs must all be embedded **inside** the executable —
`onefile` is mandatory. Our earlier reasoning (that §8's no-rename/no-move rule is easier to
audit when the assets sit visible beside the exe) is moot: the organizers have ruled.

**Two live defects this exposes in our code**, both on the submission path:
`student/my_submission.py:115` ships `TEAM_NAME = "real_eagle"` (our registered team is
**진짜보라매** — see F75, this is a DQ risk), and `:131` defaults `SERVER_IP` to
`221.151.77.208` rather than `127.0.0.1`. **No `config.json` reader exists anywhere.**

## 8. Hard constraints / disqualification risks

- **Network instability is a DQ risk**: showing instability 2+ times on competition day, or being unable to connect at all, results in elimination ("탈락 처리"). This is explicit and severe — test your connector thoroughly beforehand.
- You **may** write your own engagement-server connector/client instead of using the provided one, **as long as you preserve the network protocol** (`src/dogfight/unreal/protocol.py`'s struct-packed message types). Don't reinvent the wire format.
- Runtime assets (DLL, Rule XML, `aircraft/`, `engine/`, `scripts/`) must not be renamed, moved, or deleted — stated identically in the Day 1 deck, the Day 2 deck, and `README.md`. This is the one rule repeated in literally every document.
  - **This is about file identity (name/location), not content** — overwriting a DLL's compiled
    content or editing an XML's contents in place, while keeping the same filename in the same
    folder, is compliant. It's the intended customization surface for the rule-based approach in
    §10, not something the rule is trying to prevent.
  - **Concrete mapping in this checkout** (`DogFightEnv/Release/`, verified 2026-07-07):
    `AIP_BASE.dll` / `AIP_BASE_target.dll` / `JSBSimAIPLib.dll` ("DLL"); `Rule_forTraining.xml` /
    `Rule.xml` and any `Rule_real_eagle.xml`-style file you add ("Rule XML"); `aircraft/` (f15/f16/
    fa50 configs); `engine/` (JSBSim engine configs); `scripts/f15_cruise.xml`, `f16_cruise.xml`,
    `f16_cruise`, `fa50_cruise.xml` specifically ("scripts/" = JSBSim flight-plan XML).
  - **Naming collision to watch for**: `scripts/run_experiment.py` lives in that same `scripts/`
    folder alongside the protected cruise-script XML, but it's an ordinary Python CLI tool, not
    a runtime asset the rule is about — freely editable, not covered by this rule at all.
  - **Not covered by this rule at all** (source, not a runtime asset): `AIP_DCS/`'s C++ source
    and `.vcxproj`/`.vcxproj.filters` — only the *compiled* DLL is named in the rule, not the
    code that builds it. Same reasoning for editing Rule XML *contents* (node graphs,
    thresholds) — the rule protects the file's name/location, not what's inside it.
  - See `CLAUDE.md`'s "Editing boundaries" section for the full categorized reference.

## 9. Still unresolved / explicitly called out as pending in the deck

- **Cutoff method**: as of the deck, two options were on the table — (1) only teams beating an operating-committee model advance, or (2) every team gets that model and self-selects whether to enter prelims. The speaker notes say option 2 was "거의 결정됨" (nearly decided) but this wasn't yet final in the deck itself.
- **Exact prelim starting parameters** (precise distance/altitude/speed) — stated as "to be released later."
- A competition Discord was mentioned for fast notices about server/environment changes and team scrimmages (`https://discord.gg/RagK27Av`) — the speaker notes say this invite link expires in about a week from when the deck was presented, so **treat it as likely expired** rather than assuming it's current.

## 10. AI approach — anything goes, explicitly

The deck explicitly endorses any combination of approaches and frames their relative
strengths for *this specific competition* (not as general ML wisdom):

| Approach | Strengths (per the deck) | Weaknesses (per the deck) |
|---|---|---|
| Rule-based (BT) | Higher floor, faster to show results, easier dev difficulty — *for this competition* | Lower ceiling; needs real dogfighting domain knowledge |
| Reinforcement Learning | Higher ceiling; doesn't require domain knowledge (cites Heron's AlphaDogFight win as precedent) | May need a finished rule-based AI as a sparring partner; needs significant time/compute |
| Supervised Learning | Decent guaranteed performance with good data | Ends up as a copy/inferior version of whatever generated the training data; needs labeled data (suggests P3D/DCS flight-sim logs as a possible source) |
| Hybrid/Advanced | Mix freely — "however you do it, as long as it hooks into the connector" | — |

This matches the codebase's `HybridActionProvider` (residual/blend/switch modes) being a
first-class, not bolted-on, option.

## 11. Source documents checked

| Document | Contains rules/scoring? | What it actually is |
|---|---|---|
| `Day_1_Lecture_Materials/2026 AI Pilot Top Gun Challenge.pptx` | **Yes — primary source for this entire file** | Kickoff deck: background, awards, full rules, schedule, environment overview, BT tutorial |
| `Day_2_Lecture_Materials/AIP_경진대회_매뉴얼_rev7.pptx` | No | RLlib/YAML experiment workflow guide ("나만의 AI Pilot을 실험하는 방법") |
| `Day_2_Lecture_Materials/Release_매뉴얼.docx` | No | Release folder usage manual (README-equivalent) |
| `Day_2_Lecture_Materials/DogFightEnv_Log_Check_CLI_YAML_Guide.docx` | No | Logging/dashboard operational guide |
| `교전 뷰어 사용 메뉴얼.pdf` | No | `DogFightViewer.exe` UI controls (camera keys, scenario buttons) |
| `2026_aip_rl_manual_rev8.html` | No (checked previously) | Training-metrics interpretation guide |
| `student_manual.html` | No (checked previously) | `student/` file-authoring contracts |
| `reward_design_concept_slides.html` | No (checked previously) | Tactical reward-design concepts (LOS/ATA/AA/WEZ/etc.) |

Not yet checked: the two Day 1 videos (`ADF_Video.mp4`, `경진대회에서 사용할 교전환경.mp4`) —
these are video content, not text-extractable the way the documents above were. Mentioned in
the deck as showing actual AlphaDogFight footage and a demo of the engagement environment;
flag if you want these reviewed too.
