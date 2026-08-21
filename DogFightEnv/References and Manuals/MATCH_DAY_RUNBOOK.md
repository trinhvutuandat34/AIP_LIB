# 경기 당일 운영 절차 (real_eagle) — 2026-08-21

**제출본은 단 하나이고 월요일에 잠긴다.** 컷오프 심사와 예선 전 경기에 같은 파일이 쓰이며
재제출 창구는 없다(§4.1 F39-ONE-SHOT-SUBMISSION). 그래서 이 문서는 "무엇을 아는가"가 아니라
**"그 순간 무엇을 누르는가"**만 적는다. 판단이 필요한 부분은 전부 미리 결정해 두었다.

---

## 0. 한 줄 요약

```powershell
cd <압축 푼 폴더>
$env:DOGFIGHT_SERVER_IP  = "<공지된 IP>"
$env:DOGFIGHT_SERVER_PORT = "<공지된 포트>"
python student\my_submission.py
```

`python`은 **`aip` conda 환경**이어야 한다
(`C:\Users\Administrator\anaconda3\envs\aip\python.exe`). 기본 `python`은 anaconda3 base라
`pymap3d`가 없어 즉시 죽는다.

---

## 1. 접속 전 확인 (2분)

| 확인 | 방법 | 기대값 |
|---|---|---|
| 압축 해제 완료 | `dir` | 최상위에 `AIP_BASE.dll`, `student\`, `src\` |
| 파이썬 환경 | `python -c "import pymap3d, torch; print('ok')"` | `ok` |
| IP/포트 확정 | 운영 공지 | **추측 금지** — §2 참고 |

**작업 디렉터리는 신경 쓰지 않아도 된다.** 진입점은 자기 위치 기준으로 경로를 푼다
(`C:\`에서 절대경로로 띄워도 정상 동작함을 실측). 다만 위 명령은 압축 푼 폴더에서 실행하는
것을 기본으로 한다.

---

## 2. IP와 포트 — 절대 추측하지 말 것

코드 기본값은 `221.151.77.208:9999`이지만 **이 값은 공식이 아니다.** 기록에 남은 주소는 전부
팀원 개인 장비이고, 포트도 `COMPETITION_RULES.md`에 명시가 없다 — 실제로 기록된 연결 테스트
2건은 모두 **6666**을 썼다(§4.1 F27).

**따라서 공지된 값을 환경변수로 넣는다.** 파일을 수정할 필요 없다(제출본은 잠겨 있다):

```powershell
$env:DOGFIGHT_SERVER_IP  = "<공지 IP>"
$env:DOGFIGHT_SERVER_PORT = "<공지 포트>"
```

이 환경변수 경로는 패키징된 사본에서 동작을 실측 확인했다.

---

## 3. 정상 동작의 모습

접속 후 수 초 내에 패킷 모니터의 카운터가 **올라가야 한다**:

```
RX: MT_PlaneInfo=2490, MT_SetPlaneID=1
TX: MT_SimState=22, MT_CMD=1245, MT_ClientInfo=22
own_plane.valid=True   enemy_plane.valid=True
```

- `MT_CMD` ≈ `MT_PlaneInfo` / 2 이면 정상(자기/적 한 쌍당 명령 1회, `ACTION_REPEAT=1`).
- `own_plane.valid=True` 이고 `plane_id`가 `-1`이 아니어야 한다.

---

## 4. 증상별 대응

### 4.1 `WARNING: no frames from server yet` 가 반복된다
소켓은 열렸고 하트비트도 나가지만 **한 장도 못 받은 상태**다. 거의 항상 **IP/포트가 틀렸거나
경기가 아직 시작 안 된 것**이다.

- 먼저 **기다린다.** 경기 시작 전이면 정상이다.
- 계속되면 **IP/포트를 재확인**한다. 이 경고가 없다면 이 상태는 경기가 끝날 때까지
  오류처럼 보이지 않는다 — 경고 자체가 F40에서 추가된 것이다.
- **클라이언트를 죽이지 말 것.** 하트비트는 계속 나가고 있어서, 서버가 열리는 순간 붙는다.

### 4.2 `WARNING: server silent for N.Ns after M frames`
받다가 끊긴 상태다. 자동 재접속은 **꺼져 있다**(경고만) — 정상적인 라운드 간 대기와 구분할
기준이 없고, 불필요한 재접속은 규정 8절의 "네트워크 불안정"으로 집계될 수 있기 때문이다
(운영측 컷오프 클라이언트도 경고만 한다).

- 짧으면 무시한다.
- **길고, 경기가 진행 중인 게 확실하면** 재접속을 켜서 다시 띄운다:
  ```powershell
  python run_unreal_inference.py --mode vptrack --team-name real_eagle `
    --server-ip <IP> --server-port <포트> --action-repeat 1 `
    --server-silence-reconnect-sec 30
  ```

### 4.3 `SETUP FAILED on attempt N` 이 반복된다
DLL/Rule XML/관측 모듈 로드에 실패하는 중이다. **프로세스는 죽지 않고 계속 재시도한다**(F42).

- 메시지에 적힌 원인 파일을 확인한다(대개 경로 문제이거나 백신이 방금 푼 DLL을 잠근 경우).
- **고치면 자동으로 복구된다.** 다시 띄울 필요 없다.

### 4.4 즉시 종료된다
`argparse` 오류(잘못된 CLI 플래그)는 **일부러** 즉시 실패한다. 메시지를 읽고 플래그를 고친다.

---

## 5. 하지 말아야 할 것

- **Rule XML을 만지지 말 것.** 현재 트리는 F25/F37/F41 검증을 통과한 상태다
  (명명 노드 60개 중 57개가 실제 실행됨). md5 `F49BACF8C91DD06A6AE65143182EA1B2`.
- **RL/hybrid 모드로 바꾸지 말 것.** 12개 캠페인 전부 쓸 만한 bundle을 내지 못했고,
  hybrid는 아무것도 안 하는 것보다 나쁘다고 실측됐다(§4.1 F36-HYBRID-VERDICT).
  `MODE="vptrack"`, `BUNDLE_DIR=None`이 정답이다.
- **컨트롤러 파라미터를 바꾸지 말 것.** 4000 m / 60° + throttle은 컷오프 게이트를
  N=100에서 100% 통과한 설정이다(F39-ENVELOPE-MARGIN).
- **네트워크가 불안하다고 재접속을 반복하지 말 것.** 2회 불안정이 실격이다.

---

## 6. 아직 검증 못 한 것 (정직하게)

**실서버 대상 리허설은 한 번도 못 했다.** 이 장비에서 `DogFightViewer.exe`가 D3D11 스왑체인
생성에 실패해 실행되지 않는다(§4.1 F40-VIEWER-D3D11). 위의 모든 수치는 **실제 캡처된 Unreal
프레임을 재생하는 루프백 서버** 기준이며, 프로토콜·프레임 보정·재접속 경로는 실측했지만
**실제 경기 서버와의 연결은 미검증**이다.

가능하면 경기 전에 연습 서버 접속 기회를 요청할 것 —
`ORGANIZER_QUESTIONS_20260821.md` Q4.

---

*근거: §4.1 F27(IP/포트), F36(모드 선택), F39(엔벨로프·단일 제출), F40(침묵 경고·뷰어 블로커),
F41(노드 감사), F42(셋업 재시도·패키지 스모크 테스트). 패키징: `scripts/package_release.py`.*
