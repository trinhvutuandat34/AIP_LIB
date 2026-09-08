# 8. 다음 단계, 용어 사전, 참고 자료

[← 7. 흔한 실수 체크리스트](07_common_mistakes_checklist.md) · [목차](README.md)

## 8.1 다음 단계 — 여기서부터 실력을 늘리는 법

1. **예제 4종을 전부 읽고 자가대전으로 붙여볼 것**: `starter`(문법 기초) →
   `energy_fighter`(요요 2국면 실전 예) → `textbook_headon`(컨트롤존 진입/유지
   분리, 우선순위 설계 교훈) → `doctrine_regulator`(교리 파라미터 스윕 근거).
2. **[`../reference/REFERENCE.md`](../reference/REFERENCE.md)를 정독할 것** —
   조건·액션 키 전체와 기본값·허용 범위가 여기 다 있다(자동 생성 문서라 엔진과
   항상 일치한다).
3. **[`../reference/MEASURED_BEHAVIOR.md`](../reference/MEASURED_BEHAVIOR.md)로
   액션의 실제 물리 반응을 확인할 것** — "이 값을 주면 선회율이 몇 도/초 나오는지"가
   실측되어 있다. 감으로 튜닝하지 말고 이 표로 시작할 것.
4. **훈련센터 배터리로 자가진단할 것**: 훈련센터에 제출하면 대항군 5종 ×
   시나리오 4종 × 시드 2개 = 40경기가 자동으로 돌아간다. 진 경기부터 리플레이를
   열어 `ActiveNode`가 뭘 하고 있었는지 확인 → 원인 가설 → 트리 수정 → 재제출 →
   재확인, 이 사이클을 반복하는 게 가장 빠른 성장 경로다 — 이 프로젝트가
   실제로 두 라운드 반복한 기록이 [6장](06_lessons_from_the_trenches.md)이다.
5. **시나리오별로 따로 튜닝할 것** — 한 트리가 4국면을 다 잘하려면 각 국면에서
   실제로 어떤 분기가 활성화되는지 리플레이로 개별 확인해야 한다.
6. **가설은 실측으로 검증할 것.** "이 조건이 왜 안 걸리지?"라는 의문이 들면,
   추측으로 값을 바꾸기 전에 최소 트리(조건 하나만 있는 트리)를 만들어 실제
   엔진 값과 대조해볼 것 — 이 프로젝트가 그런 진단용 트리를 만들어 둔 예가
   [`../reference/diag_below_fighting_speed.yaml`](../reference/diag_below_fighting_speed.yaml)이다.
7. **`../MATCH_LOG.md`를 계속 이어 쓸 것.** 이 프로젝트의 실측 기반 튜닝
   기록이다 — 새로 발견한 것, 시도한 수정, 그 결과를 같은 형식으로 계속
   남기면 팀 전체의 학습 곡선이 빨라진다. [6장](06_lessons_from_the_trenches.md)이
   그 기록을 신입용으로 재구성한 것이듯, 이 문서 자체도 계속 갱신될 수 있다.

## 8.2 용어 사전 (빠른 참조)

| 용어 | 뜻 |
|---|---|
| BT | Behavior Tree, 행동트리 — 이 대회의 유일한 제출물 형식 |
| BFM | Basic Fighter Maneuvers, 기본 공중전 기동 — 이 대회 전술의 이론적 배경 |
| ATA | 내 기수→적 각도(0°=정조준). Gun WEZ 데미지를 결정하는 핵심 각 |
| AA (Aspect) | 적 꼬리 기준 내 위치각(0°=내가 적 뒤, 180°=적이 나를 정면 조준) |
| HCA | 두 기체 종축 교차각(180°=정면 대향) |
| HABFM/OBFM/DBFM | 대등/공세/수세 국면 |
| WEZ | Weapon Engagement Zone, 무장 유효 판정 구역 |
| 하드덱 | 고도 하한(1,000ft) — 위반 즉시 패 |
| 컨트롤존 | 공세 시 유지하려는 적 후방 2~3kft 존 |
| 요요(Yo-Yo) | 수직을 써서 과접근/각도열세를 해결하는 기동(하이/로우) |
| 1서클/2서클 | 반대/같은 방향 선회 — 반경/기수지향률 승부 |
| `selector`/`sequence` | 우선순위 선택 / 전체 성공 필요 노드 |
| `commit`/`cooldown` | 기동 완주 보장 / 재진입 방지 |
| 교리(doctrine) | 에이전트 전역에 적용되는 L2 setpoint(개방된 튜닝 파라미터) |
| `pure`/`lead`/`lag` | 현재 위치/미래 예측점/후방 오프셋 조준 기하 |
| `ActiveNode` | 리플레이(ACMI)에 찍히는, 그 순간 실행 중이던 내 트리 분기 이름 — 디버깅 핵심 |
| chattering | 조건이 경계값 근처에서 매 tick 참/거짓을 오가며 분기가 뒤집히는 현상 |

## 8.3 외부 참고 자료

이 대회 문서 밖에서 개념을 더 깊이 이해하고 싶을 때 참고할 만한 자료. 전부
대회 SDK와 무관한 일반 자료이며, 대회 규칙·수치는 항상
[`../reference/RULEBOOK.md`](../reference/RULEBOOK.md)가 우선한다.

**행동트리(BT) 일반**

- [Behavior Trees in Robotics and AI: An Introduction](https://arxiv.org/abs/1709.00084)
  (Colledanchise & Ögren) — 행동트리 개념 자체를 다루는 표준적인 입문 논문.
  로보틱스/게임 AI 분야에서 널리 인용된다. `selector`/`sequence`/`decorator`
  같은 용어의 일반적인 정의를 이 대회 SDK의 어휘와 비교하며 읽으면 좋다.

**YAML 문법**

- [YAML 공식 스펙](https://yaml.org/spec/) — 정확한 문법이 궁금할 때.
- [yamllint](https://www.yamllint.com/) — 온라인 YAML 문법 검사기. 들여쓰기
  실수로 `validate_agent.py`가 이상한 에러를 낼 때 먼저 여기서 문법만
  걸러내면 원인을 빨리 좁힐 수 있다.

**리플레이 뷰어**

- [Tacview](https://www.tacview.net/) — 이 대회 리플레이(.acmi) 표준 뷰어.
  무료 버전으로 충분하다.

**공중전(BFM) 배경 지식**

- 이 SDK의 교리 파라미터는 **RoKAF F-16C BEM(Basic Fighter Maneuvers) Vol.5
  (2005) 4장**을 근거로 설계됐다(`reference/REFERENCE.md` 교리 절 참고) —
  군 교범이라 온라인에 공개된 링크는 없지만, 이 문서명을 알아두면 학교나
  관련 자료에서 원문을 찾을 때 도움이 된다.
- Robert L. Shaw, *Fighter Combat: Tactics and Maneuvering* — BFM 분야의
  고전적인 대중서. 1서클/2서클, 요요, 컨트롤존 같은 개념을 그림과 함께
  설명한다(국문 번역본 유무는 학교/도서관에서 확인).

**Git·버전 관리** (팀 트리를 여러 명이 함께 수정한다면)

- [Pro Git (한국어)](https://git-scm.com/book/ko/v2) — 무료 온라인 책. 트리
  파일 하나를 여러 팀원이 반복 수정하는 워크플로에는 브랜치·커밋 이력 관리가
  꽤 도움이 된다 — 이 프로젝트도 `MATCH_LOG.md`와 git 커밋 메시지를 "왜 이
  값으로 바꿨는지"의 기록으로 같이 썼다.

---

이전: [7. 흔한 실수 체크리스트](07_common_mistakes_checklist.md) · [목차](README.md) · 다음: [9. 스파링용 기본 상대 — RedBasic](09_sample_red_opponent.md)
