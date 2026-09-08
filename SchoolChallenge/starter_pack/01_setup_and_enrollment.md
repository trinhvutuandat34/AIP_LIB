# 1. 참가 준비 — 자격·계정·환경 설치

[← 목차로](README.md) · 다음: [2. 대회 구조와 규칙 핵심](02_rulebook_essentials.md)

## 1.1 이 대회가 뭔가 (30초 요약)

**F-16 한 대 대 한 대, 총(건)만 쓰는 근접 공중전.** 참가자가 만드는 건 조종
실력이 아니라 **행동트리(YAML 파일 하나)** — "이런 상황이면 이렇게 움직여라"는
규칙의 묶음이다. 비행기 성능·G 조절·에너지 관리 같은 저수준 조종은 전 참가자가
공유하는 공통 엔진(BEM 교리 계층)이 대신 해준다. 승부는 **전술 판단**에서만
갈린다.

- 엔진: `ai-combat-core2` (JSBSim 기반 F-16 6자유도 물리, 120 Hz)
- 제출물: **행동트리 YAML 파일 하나** — 코드도 DLL도 아니다

> ⚠️ **다른 대회와 헷갈리지 말 것.** 이 저장소의 `AIP_DCS/`·`DogFightEnv/`는
> 완전히 다른 대회(전국 규모 "AIP TGC 2026", Unreal 서버에 컴파일된 DLL을
> 제출하는 방식)를 겨냥한다. 엔진도 제출 형식도 이 대회(교내 AI Pilot
> 경진대회, `ai-combat-core2`)와 전혀 다르다.

## 1.2 자격·계정

- **`@afa.ac.kr` 메일 보유자만** 참가 가능
- **팀당 계정 1개** — 계정 공유·타인 계정 사용은 몰수·실격 대상이다(룰북 §12)
- 제출 페이지: **https://ai-pilot.boramae.club/submit**
- 정확한 가입/등록 절차는 위 사이트에서 직접 확인할 것

## 1.3 SDK 설치 (Windows, Python 3.14 · 64-bit 전용)

엔진이 `cp314-win_amd64`로 컴파일되어 배포된다 — **Python 3.14 64-bit Windows
환경이 아니면 아예 import가 안 된다.** Mac/Linux에서는 로컬 검증이 불가능하다
(왜 그런지, 그런데도 무엇까지는 할 수 있는지는
[06장](06_lessons_from_the_trenches.md#로그-1--엔진-없이-일하기-2026-09-01-오전)
참고 — 실제로 이 프로젝트 초기 개발이 그 상황에서 진행됐다).

```bat
py -3.14 -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
python tools\selfcheck.py
```

`py -3.14`가 없다는 오류가 뜨면 Python 3.14를 먼저 설치해야 한다
([python.org](https://www.python.org/downloads/)에서 3.14 64-bit, 설치 시
"Add py.exe to PATH" 옵션 확인).

**Conda를 쓴다면** 버전 태그에 주의할 것 — `conda search "python=3.14"`를
해보면 빌드가 두 종류 나온다:

```
3.14.7 h7ce57fb_101_cp314     <- 이거 (표준 ABI, .pyd 파일과 일치)
3.14.7 h1e93aee_1_cp314t      <- 이거 아님 (free-threaded 빌드, ABI가 다름)
```

`cp314t`(무료-threaded/no-GIL 빌드)는 이름이 비슷해 보이지만 **다른 ABI**라서
엔진의 `.cp314-win_amd64.pyd` 파일들을 import하지 못한다. 반드시 `cp314`
(t 없는 쪽) 빌드를 지정해서 설치할 것:

```bat
conda create -n aicombat -c defaults "python=3.14.7=h7ce57fb_101_cp314"
conda activate aicombat
pip install -r requirements.txt
python tools\selfcheck.py
```

(정확한 빌드 문자열은 시점에 따라 바뀔 수 있다 — `conda search "python=3.14"`로
그때그때 `cp314`로 끝나는(`cp314t` 아닌) 최신 버전을 골라 쓰면 된다.)

`selfcheck.py`가 마지막에 **`PASS`**를 출력하면 끝 — 로컬 환경이 서버와 완전히
같은 방식으로 매치를 돌릴 준비가 된 것이다(같은 엔진 소스, 같은 의존성 버전이
핀 고정되어 있어 **로컬 결과 = 서버 결과**, 룰북 §9).

> **알아두면 당황 안 하는 것**: `selfcheck.py`가
> `examples/textbook.yaml`을 찾다가 `FileNotFoundError`를 낼 수 있다 — SDK가
> 배포한 예제 파일의 실제 이름은 `examples/textbook_headon.yaml`이라, 도구
> 자체의 하드코딩된 경로가 틀린 것이다. 내 설치가 잘못된 게 아니니 당황하지
> 말 것. `tools/validate_agent.py`와 `scripts/run_match.py`는 이 버그와
> 무관하게 정상 동작한다 — 아래 1.4절로 바로 진행해도 된다.

## 1.4 첫 매치 (5분)

```bat
copy examples\starter.yaml my_agents\my_agent.yaml
python tools\validate_agent.py my_agents\my_agent.yaml
python scripts\run_match.py --scenario headon --seed 1 ^
  --blue my_agents\my_agent.yaml --red examples\energy_fighter.yaml --analyze
```

`replays/*.acmi`가 생성된다. [Tacview](https://www.tacview.net/)(무료)로 열어
복기하는 게 표준 워크플로다 — `ActiveNode`가 그 순간 내 트리에서 활성화된
분기 이름이라, 트리가 의도대로 움직였는지 눈으로 바로 확인된다. Tacview가 없으면
`--view` 플래그로 SDK 내장 브라우저 뷰어로도 볼 수 있다.

## 1.5 제출은 이렇게 굴러간다

대회는 **훈련센터 / 예선 라운드 / 결선 진출 풀리그** 3계층이다(자세한 건
[02장](02_rulebook_essentials.md) 참고). 제출 관점에서 알아둘 것만:

- 훈련센터: **재제출 무제한**(최소 간격만 있음). 재제출하면 이전 훈련센터
  기록은 초기화되고 새 파일이 평가 대상이 된다. **같은 파일 재제출 = 같은
  결과**(초기조건 재추첨 없음, 룰북 §9) — 그러니 졌다고 그냥 다시 내지 말고,
  반드시 리플레이를 열어 원인을 찾고 트리를 바꾼 다음 재제출할 것.
- 예선 라운드: 라운드 마감 시각의 제출물이 확정본. 마감 후 재제출해도 그
  라운드 결과는 안 바뀐다.
- 제출 전 **항상** `python tools/validate_agent.py`로 검증할 것 — 통과하면
  제출물 오류로 인한 실격(`disqualified`)을 피할 수 있다(룰북 §7.4).
- 정확한 제출 간격 등 현행 수치는 대회 공지·부록을 확인할 것(룰북이 숫자를
  못박지 않고 "공지 따름"으로 열어둔 항목들이 있다).

---

다음: [2. 대회 구조와 규칙 핵심](02_rulebook_essentials.md)
