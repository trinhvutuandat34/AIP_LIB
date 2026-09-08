# 스타터 팩 — AI Pilot 경진대회 신입 참가자용

> BT(행동트리) 문법도, BFM(공중전) 용어도 처음인 신입 팀원을 기준으로 쓴
> 문서 묶음이다. 다 읽고 나면 SDK 원본 문서(`reference/`)를 바로 읽을 수 있는
> 정도를 목표로 한다.
>
> **규칙의 단일 진실은 항상 [`../reference/RULEBOOK.md`](../reference/RULEBOOK.md)다.**
> 여기 요약과 룰북이 어긋나면 룰북이 맞다(대회 공지로 개정될 수 있다).

## 이 폴더가 일반 SDK 문서와 다른 점

`../reference/` 는 주최측이 배포한 원본 자료(룰북·어휘 레퍼런스·실측 표)의
사본이다. **이 폴더(`starter_pack/`)는 그걸 신입이 읽을 수 있는 순서·설명으로
풀어쓴 것 + 이 팀이 실제로 트리를 만들고 40경기를 돌려보며 얻은 실전 경험**이다.
후자는 원본 어디에도 없는, 이 프로젝트를 직접 겪어야만 알 수 있는 내용이다 —
특히 [`06_lessons_from_the_trenches.md`](06_lessons_from_the_trenches.md)를
꼭 읽을 것.

## 읽는 순서

| # | 문서 | 언제 읽나 |
|---|---|---|
| 1 | [01_setup_and_enrollment.md](01_setup_and_enrollment.md) | 참가 자격 확인 → SDK 설치 → 첫 매치 실행까지 |
| 2 | [02_rulebook_essentials.md](02_rulebook_essentials.md) | 대회 구조·매치 규칙·판정 기준의 핵심 요약 |
| 3 | [03_behavior_trees_101.md](03_behavior_trees_101.md) | BT 문법을 처음부터(selector/sequence/commit 등) |
| 4 | [04_bfm_basics.md](04_bfm_basics.md) | 공중전 용어(ATA/AA/HCA, 1서클/2서클, 요요 등) |
| 5 | [05_first_tree_walkthrough.md](05_first_tree_walkthrough.md) | `starter.yaml` 한 줄씩 해설 + 검증/실행 실습 |
| 6 | **[06_lessons_from_the_trenches.md](06_lessons_from_the_trenches.md)** | **이 팀이 실제로 트리를 만들며 겪은 일 — 뭘 틀렸고, 어떻게 알아챘고, 뭘 배웠나** |
| 7 | [07_common_mistakes_checklist.md](07_common_mistakes_checklist.md) | 제출 전 마지막 점검 체크리스트 |
| 8 | [08_glossary_and_resources.md](08_glossary_and_resources.md) | 용어 사전 + 외부 참고 링크 |
| 9 | [09_sample_red_opponent.md](09_sample_red_opponent.md) | 스파링용 기본 상대(RedBasic) — BT 그림, 분기 설명, 실측 3경기 |

처음이라면 1→5까지 순서대로, 그다음 6번을 반드시 읽고, 7번을 제출 전 습관으로
삼을 것. 8번은 필요할 때마다 찾아보는 참조용이다.

## 5분 안에 첫 매치까지 (바쁘면 이것만)

```bat
py -3.14 -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
python tools\selfcheck.py

copy examples\starter.yaml my_agents\my_agent.yaml
python tools\validate_agent.py my_agents\my_agent.yaml
python scripts\run_match.py --scenario headon --seed 1 ^
  --blue my_agents\my_agent.yaml --red examples\energy_fighter.yaml --analyze
```

자세한 설명은 [01_setup_and_enrollment.md](01_setup_and_enrollment.md) 참고.

## 이 프로젝트의 실제 결과물

- [`../agents/agent.yaml`](../agents/agent.yaml) — 실제 제출 트리("Boramae1"),
  20개 분기. 모든 분기 옆에 왜 이 값인지 주석이 달려 있다 — 튜닝 근거를
  읽는 연습으로 좋다.
- [`../MATCH_LOG.md`](../MATCH_LOG.md) — 실측 기반 튜닝 기록 원문(라운드 1·2).
  [06_lessons_from_the_trenches.md](06_lessons_from_the_trenches.md)는 이걸
  신입이 배울 수 있는 형태로 재구성한 것이지, 대체하는 게 아니다 — 원문이
  더 자세하다.

---

*이 스타터 팩은 `reference/RULEBOOK.md`(2026-08-24 개정 반영본)·
`reference/REFERENCE.md`·`reference/MEASURED_BEHAVIOR.md`·`agents/agent.yaml`·
`MATCH_LOG.md`·이 프로젝트의 git 이력을 근거로 작성됐다. 규칙이 개정되면 이
문서들도 갱신이 필요하다 — 룰북과 어긋나면 룰북이 맞다.*
