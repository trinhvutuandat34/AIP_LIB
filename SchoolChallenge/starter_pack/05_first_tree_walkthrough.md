# 5. 나의 첫 트리 — starter.yaml 한 줄씩 해설

[← 4. 공중전 기초](04_bfm_basics.md) · [목차](README.md) · 다음: [6. 개발하며 배운 것들](06_lessons_from_the_trenches.md)

`examples/starter.yaml` 전체(문법 학습용 최소 예제, 4줄짜리 selector):

```yaml
agent_name: Starter
selector:
  - sequence:
      - condition: {name: low_altitude, floor_ft: 4500}
      - action: {pursuit: pure, g_burst: 0.8, aim_above_ft: 4000, name: recover_altitude}
  - sequence:
      - condition: {name: in_gun_envelope, range_ft: 3000, ata_deg: 30}
      - action: {pursuit: pure, name: gun_track}
  - sequence:
      - condition: nose_far
      - action: {pursuit: lead, name: lead_pull}
  - action: {pursuit: pure, name: chase}
```

한 줄씩:

1. **`agent_name: Starter`** — 리플레이(Tacview)에 표시될 내 기체 이름. 안 써도
   되지만(기본 blue_1/red_1), 팀 이름으로 바꿔두면 리플레이 볼 때 편하다.
2. **규칙 1 (`low_altitude`)** — 고도가 4,500ft 이하면 무조건 회복부터. 하드덱
   (1,000ft)이 즉시 패이므로 트리 최상단에 둔다. `aim_above_ft: 4000`으로 조준점을
   위로 크게 던지고 `g_burst: 0.8`로 그 오차만큼 세게 당기게 한다(둘 다 있어야
   확실히 상승한다 — 4장의 요요 원리와 같다. **이 둘을 함께 써야 하는 이유**를
   [06장](06_lessons_from_the_trenches.md#로그-2--가장-중요한-곳에-정작-빠뜨린-것-2026-09-01-오전)에서
   실제 실패 사례로 볼 수 있다).
3. **규칙 2 (`in_gun_envelope`)** — 사거리 3,000ft 안, ATA 30° 안(=Gun WEZ 전체
   대역, [2.4절](02_rulebook_essentials.md#24-총gun-wez-판정--여기가-승부처))이면
   `pure`로 조준 사격. 여기가 "이기는" 분기다.
4. **규칙 3 (`nose_far`)** — 기수가 적에서 많이 벗어났으면(기본 60°) `lead`로
   미래점을 노려 기수를 빨리 당긴다.
5. **규칙 4 (기본)** — 위 어디에도 안 걸리면 그냥 `pure`로 추격.

**이 트리의 한계** (README·주석에 이미 명시됨): 방어 분기가 없다
([3.3절](03_behavior_trees_101.md#33-왜-조건마다-거리-게이트가-필요한가)에서
배운 "거리 게이트 있는 방어 분기"가 아예 없음) — 노련한 상대에겐 그냥 계속 쫓기기만
하다 진다. **문법 학습·베이스라인용이지 실전용이 아니다.** 이 다음엔
`examples/energy_fighter.yaml`(요요 2국면 시연)과 `examples/textbook_headon.yaml`
(컨트롤존 진입/유지 분리, "사격 기회가 존 유지를 이긴다"는 우선순위 교훈)을
읽어볼 것 — 실제로 방어·요요가 들어간 예제다. 이 프로젝트의 실제 제출 트리
[`../agents/agent.yaml`](../agents/agent.yaml)은 20개 분기까지 늘어난 버전인데,
그 각 분기가 왜 있는지, 어떻게 지금 값에 도달했는지가
[06장](06_lessons_from_the_trenches.md)의 내용이다.

## 검증하고 매치 돌려보기

### 검증 — 제출 전 항상

```bat
python tools\validate_agent.py my_agents\my_agent.yaml
```

`✅` 가 뜨면 통과. 스키마·범위·교리 lo>hi 역전까지 서버와 같은 방식으로 잡아준다.
**이걸 통과 못 한 파일을 제출하면 `disqualified`(실격패, 룰북 §5 #4)다** —
경기를 뛰어보지도 못하고 지는 것이니 제출 전 습관으로 만들 것.

### 자가대전(self-play)으로 검증

```bat
python scripts\run_match.py --scenario headon --seed 1 ^
  --blue my_agents\my_agent.yaml --red examples\energy_fighter.yaml --analyze
```

- `--scenario`: `headon`/`perch_offense`/`perch_defense`/`neutral` 4종을 **다**
  돌려볼 것 — 한 국면만 잘하는 트리는 순위를 얻지 못한다.
- `--seed`: 고정하면 결정론적으로 같은 결과가 나온다(비교용으로 필수).
- `--red`: 자기 트리끼리(예: `examples/energy_fighter.yaml`) 붙여보는 것.
  `scripted:{turn|straight|extend|break}` 로 단순 기동 상대와도 붙일 수 있다.
- `--analyze`: 매치 후 WEZ·에너지·전술 그래프(`*_wez.png` 등)를 자동 생성한다.
  요요·브레이크·컨트롤존 분기가 의도대로 발동하는지, G 여유를 못 쓰는 구간은
  없는지 그래프로 확인할 것.
- `--view`: Tacview 없이 SDK 내장 브라우저 뷰어로 3D 재생.

### 리플레이 읽는 법

`.acmi`를 Tacview로 열면:

- **`ActiveNode`** — 그 순간 내 트리에서 실행 중인 분기 이름(`action:`의
  `name:` 값). **디버깅의 핵심** — 원하는 분기가 원하는 타이밍에 켜지는지
  여기서 확인한다. 이 프로젝트가 트리를 고칠 때마다 실제로 본 게 바로 이
  필드다([06장](06_lessons_from_the_trenches.md) 전체가 이 필드를 근거로 쓰였다).
- **`GMode`/`PowerMode`/`AimAbove`** — 교리(BEM) 계층이 실제로 뭘 하고 있는지.
- **`Distance`/`ATA`/`AA`/`HCA`** — 조건 임계값을 튜닝할 실측 근거.

> ⚠️ **리플레이·매치 기록은 대회 참가자 외부로 반출·공개 금지**(룰북 §11) —
> 개인 SNS·외부 저장소 업로드는 몰수·실격 대상이다. 팀 내부·본인 학습용으로만
> 쓸 것.

---

이전: [4. 공중전 기초](04_bfm_basics.md) · 다음: [6. 개발하며 배운 것들](06_lessons_from_the_trenches.md)
