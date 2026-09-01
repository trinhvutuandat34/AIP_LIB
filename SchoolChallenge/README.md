# SchoolChallenge — 교내 AI Pilot 경진대회 (ai-combat-core2)

이 디렉터리는 `ai-pilot.boramae.club` 이 운영하는 **교내(공사) AI Pilot 경진대회**용
제출물이다. 저장소 나머지(`AIP_DCS/`, `DogFightEnv/`)는 완전히 다른 대회
("AIP TGC 2026", 288팀 규모의 전국 대회 — DLL+XML 을 Unreal 서버에 제출하는
방식)를 겨냥하고 있어서, 엔진도 제출 형식도 이 대회와 겹치지 않는다. **둘을
섞지 말 것** — 이 대회는 YAML 행동트리 파일 하나만 제출한다(코드 없음, DLL 없음).

## 이 대회가 다른 이유

| | AIP TGC 2026 (`AIP_DCS/`, `DogFightEnv/`) | 교내 AI Pilot (여기) |
|---|---|---|
| 제출물 | 컴파일된 C++ DLL + XML 트리 | **YAML 행동트리 파일 하나** |
| 엔진 | JSBSim + Unreal(`DogFightViewer.exe`) | `ai-combat-core2` (JSBSim 단독, 120Hz) |
| 참가 자격 | 전국 대학 288팀 | `@afa.ac.kr` 메일 보유자만, 팀당 계정 1개 |
| 규모 | 국가 후원(장관상 등) | 학교 내부 |

## 파일 구성

```
SchoolChallenge/
├── README.md                      — 이 문서
├── agents/
│   └── agent.yaml                 — 제출용 행동트리 (agent_name: Boramae1)
├── reference/                     — 사용자가 전달한 SDK 파일 사본(팀 참고용)
│   ├── RULEBOOK.md                — 공식 룰북 (단일 진실)
│   ├── REFERENCE.md               — 조건/액션/교리 어휘 레퍼런스
│   ├── MEASURED_BEHAVIOR.md       — 액션→거동 실측표
│   ├── agent.schema.json          — 에디터 자동완성/검증용 JSON Schema
│   ├── examples/
│   │   ├── doctrine_regulator.yaml — doctrine 블록 시연(교리 스윕 근거 포함)
│   │   ├── energy_fighter.yaml     — 에너지 보존형 아키타입(commit/cooldown 시연)
│   │   ├── starter.yaml            — 최소 문법 예제(4분기)
│   │   └── textbook_headon.yaml    — stable/control_zone 모드 시연, SOO 우선순위 교훈
│   ├── scripts/
│   │   ├── run_match.py            — 공식 매치 러너(자가대전·로스터 배치 채점)
│   │   └── analyze_wez.py          — .acmi 리플레이 분석(WEZ·에너지·전술 그래프)
│   └── config/
│       ├── sim.yaml                 — 엔진 타이밍 상수(물리 120Hz, 트리 20Hz 등)
│       └── tactics.yaml             — 엔진 기본 트리(DEFAULT_SPEC 미러, 최소 베이스라인)
└── tools/
    └── validate_local.py          — 로컬 사전 점검(공식 검증기 아님, 아래 참고)
```

## `agent.yaml` 설계 요약

우선순위(selector, 위에서부터):

1. **안전** — 하드덱 회피 → 즉각 방어 브레이크(코앞 위협/경로 위협) → 부상
   이탈 → 실속 가드. 룰북 §5 의 판정 우선순위(하드덱·실속이 HP 우세보다
   우선)를 그대로 반영했다.
2. **국면별 전술** — High Yo-Yo(과접근 관리, commit 2국면) · Low Yo-Yo(각도
   열세 회수, commit 2국면) · 1서클/2서클 반경·rate 구분 · 오버타임 완화
   WEZ 압박 · 좁은 ATA 사격창 · 컨트롤존 유지/진입 · 이탈 추격 · 공세 압박 ·
   경로/기수 재정렬 · 일반 에너지 회복 · 헤드온 안정.
3. **기본** — 위 어디에도 안 걸리면 순정 추격.

총 20개 분기(`selector` 직계). 각 분기의 상세 근거(왜 이 조건 임계값·이
액션 파라미터인지)는 `agent.yaml` 안의 주석에 있다. 원 출처는 두 갈래다:

- `AIP_DCS/BehaviorTree/BT_Content/Task/` 의 기존 BFM 노드(`Task_HighYoYoUp`,
  `Task_OneCircleFight`, `Task_LowYoYo`, `Task_LagPursuit`, `Task_LeadPursuit`,
  `Task_Evade`, `Task_ClimbToSafeAltitude`) — 그 프로젝트의 **코드는 재사용
  하지 않았다**(다른 엔진, 다른 언어, 다른 액션 계약). 재사용한 것은
  "언제 어떤 추격 기하를 쓰는가"라는 전술 판단 자체다.
- SDK 가 제공한 예제 3종(`energy_fighter.yaml` 의 low yo-yo 2국면 패턴,
  `textbook_headon.yaml` 의 CZ 진입/유지 분리와 "사격 기회가 존 유지를
  이긴다"는 순서 교훈) — 값은 그대로 베끼지 않고 우리 우선순위·게이트에
  맞춰 재조정했다(각 분기 주석에 출처 명시).

`doctrine:` 블록은 SDK 예제(`reference/examples/doctrine_regulator.yaml`)가
자체 스윕(1,368경기)에서 "단일 최선"이라 명시한 3필드(`g_min: 1.5`,
`energy_margin_lo: 75`, `lv_above_ft: 500`)만 채택했다. 그 예제의 나머지
4필드는 파일 자체가 "의도적으로 최적이 아닌 값"이라고 밝히고 있어 가져오지
않았고, 우리 트리에는 기본값을 둔다.

## 검증 상태 — 중요: 로컬 사전 점검일 뿐, 공식 검증 아님

`tools/validate_local.py` 는 `agent.schema.json` 을 그대로 로드해 `jsonschema`
로 구조/어휘/범위를 점검하고, 스키마가 못 잡는 교리 lo>hi 역전(룰북 §10.2)도
따로 체크한다. 이 환경에서 `agent.yaml` 을 돌려 통과를 확인했다:

```
$ python3 tools/validate_local.py ../agents/agent.yaml
[SCHEMA] OK — ../agents/agent.yaml matches agent.schema.json
[DOCTRINE] all lo/hi bands consistent
OK
```

**하지만 이 스크립트는 공식 검증기가 아니다.** `reference/scripts/run_match.py`
는 받았지만, 그것이 import 하는 실제 엔진 패키지(`aircombat.engine.*`,
`aircombat.tactics.*`, `aircombat.geometry.*`, `aircombat.control.*`,
`aircombat.debrief.*` — `load_policy`/`make_pilot`/`Match`/`SCENARIOS` 등을
담은 소스)는 이 세션에 없다. 즉 **CLI 래퍼는 있지만 그 래퍼가 돌리는 엔진
본체가 없어서, 이 세션에서 실제 매치를 실행할 수는 없다.** `tools/validate_agent.py`
도 마찬가지로 아직 못 받았다. 그래서:

- **제출 전 반드시** 로컬 SDK(엔진 패키지가 설치된 실제 환경)에서
  `python tools/validate_agent.py agent.yaml` 로 공식 검증을 통과시킬 것.
- **반드시** `python scripts/run_match.py --scenario duel --seed 42 --blue agent.yaml --red reference/examples/energy_fighter.yaml`
  처럼 SDK 가 준 예제 아키타입들(`energy_fighter`/`textbook_headon`/`starter`)
  을 상대로 자체 대전을 돌려 실제 거동(특히 High/Low Yo-Yo·브레이크가
  의도대로 발동하는지, `--analyze` 로 WEZ·에너지 그래프까지)을 확인할 것 —
  스키마 통과는 "제출이 거부되지 않는다"는 뜻이지 "잘 싸운다"는 뜻이 아니다.
- 엔진 패키지(`aircombat/`) 소스를 이 세션에 전달할 수 있다면, 실제 매치를
  이 환경에서 직접 돌려 검증할 수 있다 — 필요하면 알려달라.

## 제출 방법 — 직접 업로드는 이 세션이 할 수 없다

`ai-pilot.boramae.club` 도메인은 이 세션의 네트워크 egress 프록시에서
차단되어 있어(허용 목록 밖) 이 세션이 직접 fetch 하거나 업로드할 수 없다.
`agents/agent.yaml` 을 다운로드해 [제출 페이지](https://ai-pilot.boramae.club/submit)
에서 직접 업로드해야 한다. 제출 최소 간격은 2시간이다(룰북 부록).
