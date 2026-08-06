# AIP Official Slides — Model Architecture & Behavior Tree Tutorial

Transcription of five official kickoff-deck slides, saved 2026-08-06, with the mapping to this
codebase. **Source of truth for architecture choices.**

Scope note — this file covers only the *architecture* and *BT tutorial* slides. The engagement /
damage-rule slides are already captured in `COMPETITION_RULES.md` §6 (cone phases, `d_wez`
formula, hard deck) and are not repeated here. The findings derived *from* these slides live in
`COMPETITION_PLAN.md` §4.1 categories **C** (Behavior Tree) and **D** (System architecture); this
file is the raw reference those rows cite.

---

## 1. `Advanced 모델 예시` — the four sanctioned architectures

Four permitted compositions, drawn left to right on the slide:

| # | Chain | Notes |
|---|---|---|
| **1** | `Behavior Tree (전술 판단)` → `Reinforcement Learning AI (전투기 조종)` → `JSBSIM` | **No `JSBSIM Controller` box.** BT decides tactics; RL *flies the aircraft* |
| **2** | `Behavior Tree (전술 판단 1)` + `RL AI (전술판단 2)` → `JSBSIM Controller` → `JSBSIM` | Both produce tactical judgment; merge happens **before** the controller |
| **3** | `RL AI (전술판단)` → `JSBSIM Controller` → `JSBSIM` | Pure RL tactics, hand controller retained |
| **4** | `Behavior Tree (전술판단 1)` → `JSBSIM Controller` → `JSBSIM`, **and** `Behavior Tree` → `RL AI (Throttle 관리)` → `JSBSIM` | BT flies via the controller; RL manages **throttle** separately. Merge happens **after** the controller, at the JSBSIM input |

Verbatim closing text:

> 여러 조합의 방법을 사용 가능, 무슨 수를 써서라도 접속기에 붙이기만 하면 됩니다.
> 참가팀 여러분의 익숙한 AI 방식, 생각하기에 좋아 보이는 방향성 등
> 가장 성능 좋을 것 같은 방향으로 준비하세요

("Any combination of methods may be used; whatever it takes, as long as it attaches to the
connector. Prepare in whichever direction you think will perform best.")

**→ The rules impose no architectural preference. Nothing obliges keeping `Controller_CY` in the
loop** — architecture #1 removes it outright. That matters because `Controller_CY` is this
project's measured bottleneck (`COMPETITION_PLAN.md` §4.1 rows D1, E1-gap, E1c-null).

### Where this project actually sits

**Submission path** (`my_submission.py` / `run_unreal_inference.py`) ≈ **#4, generalized**:

```
BT 전술판단 ──► Controller_CY ──► stick ──┐
                                          ├──► + ──► JSBSIM
RL policy ──────────────────► ×0.35 ──────┘
```

Closest to #4 because the merge is **after** the controller, at the JSBSIM input — but the
slide's RL handles only throttle, whereas `StudentHybridProvider` residual corrects **all four
axes**. Not #2 (that merges *before* the controller, at the tactical/VP level), not #1 (the
controller is still present), not #3.

**Training path** (`train_curriculum.py` / `train_rllib.py`) = **§2 below / #3**: the learner flies
**solo**. Confirmed by grep — neither trainer references `ownship_action_provider`, and the env
field defaults to `None`, so the raw RL action goes straight through `_to_sim_action`.

> ⚠️ **TRAIN/DEPLOY MISMATCH.** The policy is optimised as an *absolute* controller flying alone,
> then deployed as a **0.35-scaled additive delta** on top of BT commands it never saw in
> training. Nothing in its training distribution resembles its inference role. `COMPETITION_PLAN.md`
> §3 assumes "RL only has to learn the delta", but **no current training path trains a delta.**
> Open decision as of 2026-08-06: (a) train with the BT in the loop, or (b) move to architecture
> #1 and let RL replace `Controller_CY`.

---

## 2. `학습 기반 모델의 구조` — the pure-RL reference

```
        상대 비행기의 위치, 자세, 속도
                    │
                    ▼
   ┌────────────────────────────┐
   │             AI             │◄──── 내 위치, 자세, 속도 (feedback)
   └────────────────────────────┘
                    │  조종값(CMD): Roll, Pitch, Yaw, Throttle
                    ▼
   ┌────────────────────────────┐
   │           JSBSIM           │
   └────────────────────────────┘
```

- **AI** — 자신의 정보와 상대의 정보를 입력하여 최적의 조종값을 생성.
  Inputs: own aircraft state + opponent aircraft state. Output: `조종값 (Roll, Pitch, Yaw, Throttle)`.
- **동역학 (JSBSIM)** — 조종값을 입력받아 비행 역학을 시뮬레이션.
  Inputs: Roll/Pitch/Yaw commands + throttle. Outputs: position, attitude, speed, etc.

This is exactly what v5/v6 train. v5 failed at 100 % self-crash (20/20 into the ground) — pure RL
must learn tactics *and* flight control simultaneously, which is why §3 chose residual instead.

---

## 3. `C++ Behavior Tree의 구성`

Library reference given on the slide: **https://www.behaviortree.dev/**

| Element | Slide definition |
|---|---|
| **Tree** | XML, 사고 회로 ("thought circuit") |
| **BlackBoard** | Behavior Tree 가 정보를 저장하는 공간 |
| **Fallback** | Unreal BT 의 Selector 노드. 자손 노드중 성공한 노드를 실행 — `if / else` |
| **Sequence** | 자손 노드를 모두 실행 — `if, if, if` |
| **Decorator Node** | 트리의 조건문. 자식 노드의 실행 결과값을 판단 및 변환하는 노드 |
| **Task Node** + **Service Node** → **Action Node** | **서비스 노드와 같은 역할 구분이 사라짐.** 트리의 말단 부분, 객체의 행위 자체를 구현하는 부분 |

**→ The Task/Service collapse is why every `DECO_*` and every `Service/` class in `AIP_DCS`
inherits `SyncActionNode` rather than `ConditionNode`.** That is the official convention, not
drift — do **not** "fix" it (`COMPETITION_PLAN.md` §4.1 row C4).

---

## 4. `Unreal Engine Behavior Tree의 구성` — node semantics

| Element | Slide definition |
|---|---|
| **Tree** | Unreal Engine 이 제공하는 BT 제작 툴, **사고 회로** |
| **BlackBoard** | 정보를 저장하는 공간, 모든 노드에서 접근 가능, **기억** |
| **Selector** | 성공한 노드를 실행 — `if else`. 왼(위)쪽부터 차례대로 검사하여 **하나라도 성공하면 더 이상 진행하지 않음** |
| **Sequence** | 자손 노드를 모두 실행 — `if, if, if`. 왼(위)쪽부터 검사하여 **하나라도 실패하면 더 이상 진행하지 않음** |
| **Task Node** | 객체의 행위 자체를 수행하는 노드. **이 프로젝트에서는 VP를 생성하는 역할** |
| **Decorator Node** | 다른 노드들에 붙어서 실행 조건을 확인하는 노드, `if` 문의 조건 |
| **Service Node** | 트리가 지나가는 경로 도중에 실행되는 노드, 주로 상태 업데이트를 위해 씀 |

> ⚠️ **ARCHITECTURAL CEILING.** "Task Node = VP를 생성하는 역할" is load-bearing: Task nodes emit
> **only an aim point**. `Controller_CY::GetStick` is the sole VP→stick converter. Therefore **no
> BT-side change can fix terminal pointing error except by displacing VP** — which is precisely
> the lead-feedforward experiment already tried and reverted (see `Task_GunTrack.cpp`'s note).
> This bounds what any further BT work can achieve. (`COMPETITION_PLAN.md` §4.1 row C3.)

BlackBoard described as **기억** (memory) reachable from every node — the sanctioned home for
fight-state, if the deferred Tier-2 fight-state memory is ever revisited (row C5).

---

## 5. Reference tree from the tutorial

```
Root
 └─ Update Distance   (Service) ──► BlackBoard   e.g. Distance : 650 m
    Update LOS        (Service) ──► BlackBoard   e.g. LOS      : 4.3
    └─ Selector
       ├─ Distance <  1000 m
       │   └─ Selector
       │      ├─ LOS <= 1  ──► Pure Pursuit
       │      └─ LOS >  1  ──► Lag Pursuit
       └─ Distance >= 1000 m ──► Lag Pursuit
```

**Four leaves.** Two Services write the blackboard each tick; a Selector chain reads it.

### Two observations this project should not lose

1. **The reference gates Pure Pursuit on `LOS <= 1` — the Phase-1 scoring criterion itself**
   (`COMPETITION_RULES.md` §6.2: LOS < 1°). Our equivalent, Gate 2.5, fires at **ATA < 8°**, and
   the tail `Task_Pure` has **no angle gate at all** (`dist < 2000 m` only). The official design
   aims *at what scores*; ours aims at a proxy and hopes to converge inside it.
   (`COMPETITION_PLAN.md` §4.1 row C1 — and this is the same defect as row A4 seen from the other
   side.)

2. **Complexity has not bought performance.** Reference = 4 leaves. `Rule_forTraining.xml` = ~25
   nodes across 6 gates, backed by 23 `Task_*` classes → **0 WEZ steps in every configuration
   tested** (BT-vs-BT mirror, tightened gate, non-maneuvering target, all three damage phases).
   Not an argument to revert the expansion, but a strong argument that the next move is
   *simplification toward the scoring condition*, not more tactical layers. (Row C2 — this is what
   killed the fight-state-memory Tier 2.)
