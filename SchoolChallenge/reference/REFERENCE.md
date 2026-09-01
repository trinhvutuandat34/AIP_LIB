<!-- 자동 생성 — 수정 금지 (scripts/gen_references.py). 코드가 단일 진실 -->

# 어휘 레퍼런스

## 조건 (Condition)

`condition: 이름` 또는 `condition: {name: 이름, 임계값: 값}`. 아래 파라미터가 전부 — 다른 키는 즉시 오류.

| 조건 | 파라미터(기본값) | 의미 |
|---|---|---|
| `foe_threat` | `aspect_deg=120` | 적이 내 정면(헤드온)에서 조준 중 — 방어 국면. (aspect≈180 = 적 12시에 나) |
| `overshoot_risk` | `closure_fps=150, range_ft=2000` | 빠른 접근 + 근거리 → 추월 위험. lag/요요로 물러서야 함(4.4.7.2). |
| `foe_extending` | `closure_fps=0, range_ft=6000` | 적이 멀어지며 거리 벌림 → max-G 리드 추격(4.4.8.2.1). |
| `in_gun_envelope` | `range_ft=3000, ata_deg=30` | 건 사거리 + 조준각 근접 → pure/추적. |
| `nose_far` | `ata_deg=60` | 기수가 적에서 크게 벗어남 → 리드로 기수 당김. |
| `energy_advantage` | `min_ft=0` | 비에너지 우세 → 공세 유지 가능. |
| `low_altitude` | `floor_ft=4000, lookahead_s=0` | 하드덱(1,000ft) 근접 — 즉시 회복 필요. 급강하 관성 때문에 대응이 늦으면 회복해도 하드덱을 뚫는다 → floor_ft 는 넉넉한 여유를 둔다(기본 4,000ft). lookahead_s 를 주면 현재 고도 대신 그만큼 뒤의 예상 고도로 판정한다(기본 0=현재 고도). 고도만 보면 강하각에 따라 여유가 달라진다 — 730fps 강하에서 4,500ft 는 6초뿐인데 60° 강하 회복에는 4,500ft 가 든다. lookahead_s 는 침하율에 비례해 트리거를 앞당기므로 수평비행에서는 기본과 동일하게 동작한다. |
| `foe_above` | `min_ft=500` | 적이 나보다 위 — 수직 분리 판정(4.4.10). alt_gap_ft 양수=적이 위. |
| `foe_below` | `min_ft=500` | 적이 나보다 아래 — 요요 정점(재강하 시점) 판정(4.4.6.2.3). |
| `behind_foe` | `aspect_deg=60` | 적 후방 반구(control zone) 점유 — 공세 국면 판정(4.4.6). |
| `in_control_zone` | `range_lo_ft=2000, range_hi_ft=3000, aspect_deg=30, hca_deg=30` | BEM control zone 점유 — 후방 2~3 kft + AA≈0 + HCA 정렬(4.4.6). ATA 20~30°는 조건이 아니라 lag 추격의 결과(존 유지 기동이 만드는 기하). |
| `merged` | `range_ft=1500` | merge 통과(초근접) — 넥타이/교차 직후 국면(4.4.4). |
| `one_circle` | `—` | 1-circle flow — 양 기체가 **반대 수평 선회방향**으로 원 하나를 공유(radius fight). 한쪽이라도 직선이면 False. BEM 4.4.4 flow 정의 — 구 순간 HCA<90 프록시에서 2026-07-17 교범 정합 전환. 2-circle 은 two_circle 조건(inverter 아님 — 직선 포함 문제). |
| `two_circle` | `—` | 2-circle flow — 양 기체가 **같은 수평 회전방향**(노즈-투-노즈 rate fight). 한쪽이라도 직선이면 False. BEM 4.4.4. ¬one_circle 과 다름 — inverter 는 둘 다 직선인 접근 국면까지 참이 되므로 flow 판별에는 이 조건을 쓸 것. |
| `closing` | `min_fps=100` | 유의미한 접근율 — 요요 국면 전환(진입/정점) 판정. |
| `below_fighting_speed` | `kcas=교리연동` | 파이팅 속도 하한 미만 — 에너지 회복 필요(4.4.6.2.2). 기본값=교리 fighting_kts_lo. |
| `above_fighting_speed` | `kcas=교리연동` | 파이팅 속도 상한 초과 — 에너지 여유(전환 기동 가능)(4.4.6.2.2). 기본값=교리 fighting_kts_hi. |
| `low_health` | `hp=40` | 내 잔여 HP 가 임계 미만 — 손상 국면 전환(방어 전환·이탈 판단) 판정. |
| `vel_nose_far` | `vel_ata_deg=60` | 내 속도벡터가 적에서 크게 벗어남 — nose_far 의 속도벡터판. 기수는 표적을 물었는데 비행경로가 흘러나가는 고AoA 드리프트 감지. |
| `foe_path_threat` | `vel_aa_deg=120` | 적 속도벡터(비행경로)가 나를 향함 — foe_threat 의 속도벡터판. 기수 조준(aspect)보다 실제 접근 경로 기반의 위협 판정. |
| `is_head_on` | `hca_deg=150` | HABFM — 종축이 대향(HCA 고, BEM Angle-Off): 머지/헤드온 국면(4.4.4). 안정 노즈온 추적 대상. |
| `is_offensive` | `aspect_deg=60` | OBFM — 내가 적 후미(aspect 낮음): 공세 국면(4.4.6). control zone 유지 대상. |
| `is_defensive` | `aspect_deg=120` | DBFM — 적이 내 후미(aspect 높음): 방어 국면(4.4.9). 브레이크/역전 대상. |
| `in_overtime` | `—` | 오버타임 구간 — 정규 300초에 승자가 안 나온 현장 단판의 연장 120초. OT 에서는 Gun WEZ 가 완화된다(사거리 6,000 ft, 원뿔 45°). 이 조건으로 분기해 OT 전용 사격·추격 임계를 쓰라 — 예: {condition: in_overtime} + {condition: {name: in_gun_envelope, range_ft: 6000, ata_deg: 45}} 적용 범위는 현장 단판뿐이다(훈련센터·예선 풀리그는 항상 False). |

### 조건 쓰는 법 (예제)

```yaml
# ① 기본 임계값 그대로 — 문자열 하나
- condition: merged

# ② 임계값 오버라이드 — 위 표의 파라미터 이름만 쓸 수 있다(오타는 즉시 오류)
- condition: {name: low_altitude, floor_ft: 5000, lookahead_s: 6}

# ③ 교리 연동 — kcas 를 안 쓰면 doctrine.fighting_kts_lo 를 따라간다
- condition: below_fighting_speed                        # 교리값(기본 325)
- condition: {name: below_fighting_speed, kcas: 330}     # 330 고정 — 교리를 바꿔도 안 움직인다
```

**구간(밴드) 판정** — 상한·하한을 한 번에 주는 조건이 없으면 문턱값 두 개를 `inverter` 로 조합한다:

```yaml
# 1,500~3,000 ft 대역에서만 참
sequence:
  - condition: {name: merged, range_ft: 3000}                # 3,000 ft 보다 가깝고
  - inverter: {condition: {name: merged, range_ft: 1500}}    # 1,500 ft 보다는 멀다
  - action: {pursuit: pure, name: gun_band}
```

> **`inverter` 는 조건에만 씌운다.** 액션을 감싸면 명령을 세팅해 놓고 FAILURE 를
> 반환하므로 selector 가 다음 형제로 넘어가 그 명령을 덮어쓴다 — 쓴 대로 나가지 않는다.

> **부정은 반대말이 아니다.** `inverter(one_circle)` 은 `two_circle` 이 아니다 —
> 양쪽 다 직선인 접근 국면에서도 참이 되기 때문이다(위 표 참조). flow 판별에는
> 해당 조건을 직접 쓸 것.

## 노드·액션

트리 노드는 단일 키 dict. 미지 키는 즉시 오류.

| 노드 | 형식 | 의미 |
|---|---|---|
| selector | `selector: [자식, ...]` | 처음 성공하는 자식 채택 (우선순위) |
| sequence | `sequence: [자식, ...]` | 전부 성공해야 성공 (조건 게이트→액션) |
| inverter | `inverter: 자식` | 결과 반전 |
| commit | `commit: {name, duration_s, cooldown_s, child}` | 성공한 child 명령을 duration_s 유지, 만료 후 cooldown_s 재진입 차단 |
| cooldown | `cooldown: {wait_s, child}` | 성공 국면 종료 후 wait_s 재진입 차단 |

액션 `action:` 허용 키 — `aim_above_ft, cz_range_ft, g_burst, g_full_ata_deg, lag_dist_ft, lead_time_s, mode, name, pursuit, track_ata_deg, track_rng_ft`:

| 키 | 값 | 의미 |
|---|---|---|
| pursuit | lag / lead / pure | 추격 기하 — lead(앞 조준)/pure(현 위치)/lag(뒤) |
| mode | control_zone / stable | L2 가이드 국면 모드 — stable(헤드온 안정 노즈온 추적)/control_zone(존 유지·오버슈트 억제). 미지정=기본 조절 |
| name | 문자열 | Tacview `ActiveNode` 에 찍히는 전술명 |
| g_burst | 0 ~ 1 (기본 0) | **지속↔순간 봉투 보간.** 0=지속 봉투(Ps≥0 유지, 에너지 보존), 1=순간 봉투 전량(에너지 소모). 1 이어도 아래 ATA 조절은 통과한다 |
| g_full_ata_deg | 20 ~ 90 (기본 = 교리 `ata_target_hi`) | 명목 G 에 **포화하는 각도**. 지령 G 는 기수→**조준점** 각도에 비례한다(적까지의 ATA 가 아니다 — `aim_above_ft` 를 주면 그만큼 오차가 커져 더 세게 당긴다). 작을수록 공격적, 클수록 완만 |
| track_rng_ft / track_ata_deg | 1000 ~ 3000 / 10 ~ 30 (기본 2500 / 30) | 건 추적 하한 G 창. 이 창 안에서는 표적 LOS 회전율을 따라잡는 G 를 **순간 봉투까지** 쓴다 — `g_burst` 가 낮아도 사격 국면만 크게 당길 수 있다 |
| aim_above_ft | -5000 ~ 5000 | 조준점 수직 오프셋 (+위/−아래) — 요요의 재료 |
| lead_time_s / lag_dist_ft | 0 ~ 3 / 0 ~ 8000 (기본 1.5 / 1,500) | lead 예측시간·lag 후방거리 오버라이드 |
| cz_range_ft | 500 ~ 6000 (기본 2,500 — BEM 2,000~3,000 의 중앙) | control zone 목표 슬랜트 거리. **`mode: control_zone` 일 때만 효과**가 있다 |

숫자 키는 **범위 밖이면 제출이 거부**된다(조용히 클램프하지 않는다). 생략하면 위 기본값이
적용되는데, 기본값은 의도적으로 "무난하지만 최적은 아닌" 값이다 — 튜닝이 설계의 일부다.

> **lead 는 시간, lag 는 거리인 이유**: lead 조준점 = 적 미래위치(적속도×시간)라 **시간**이
> 자연 파라미터(리드 거리가 적 속도에 자동 비례). lag 조준점 = 적 뒤 고정 **거리**(트레일·존)라
> 적 속도와 무관한 공간 상수 — 그래서 단위가 비대칭이다.

> **pursuit 선택과 조준각(ATA)** — 데미지는 거리 대역이 아니라 **ATA 계단**으로 결정된다
> (룰북 §4). 그래서 "사거리 안에 있다"와 "맞고 있다"는 다른 사건이다.
> `pure` 는 적의 **현재 위치**를 겨눈다 — 표적이 선회 중이면 겨눈 지점에서 계속 벗어나므로
> ATA 가 벌어진 채 유지되고, 사거리 안에 오래 머물러도 계수 0 구간(ATA≥30°)에서 벗어나지
> 못할 수 있다. `lead` 는 적의 **미래 위치**를 겨눠 그 격차를 메우고, `g_burst`·
> `g_full_ata_deg` 는 기수를 표적으로 얹는 속도를 높인다(대가는 에너지).
> 어느 국면에 무엇을 쓸지는 참가자의 설계 영역이다 —
> 리플레이에서 `range_ft` 뿐 아니라 `ata_deg` 를 함께 보면 판단에 도움이 된다.

### 최상위 필드 (선택)

트리 루트 옆에 둘 수 있는 최상위 키:

| 키 | 값 | 의미 |
|---|---|---|
| `agent_name` | 문자열 | 리플레이(ACMI CallSign)·Tacview 에 찍히는 표시용 에이전트 이름 |
| `doctrine` | 매핑 | 교리 setpoint 오버라이드 (개방 시에만; 아래 교리 표 참조) |
| `dwell_s` | 수 ≥ 0 | 명령 히스테리시스 최소 유지시간 [s] (기본 0.3). 전술이 **바뀔 때만** 적용된다 — 이 시간이 지나기 전엔 새 전술을 채택하지 않는다. 0 이면 매 tick 즉시 전환. 12팀 528경기 실측에서 0.0/0.3 간 승자 변경은 7.2%, 순위 상위 4팀은 불변이었다 — 승부를 가르는 노브가 아니다 |

```yaml
agent_name: MyViper
selector:
  - action: {pursuit: pure, name: chase}
```

### 노드 형식 예제 (학습용)

```yaml
# ① 액션 하나면 트리다
action: {pursuit: pure, name: chase}
```

```yaml
# ② 조건 게이트로 국면을 나누고, 데코레이터로 관성을 준다
selector:                                  # 위에서부터 먼저 참인 분기 채택
  - sequence:                              # 조건(모두 참) → 액션
      - condition: {name: is_defensive, aspect_deg: 150}
      - condition: {name: merged, range_ft: 6000}
      - action: {pursuit: lag, g_burst: 0.8, name: break}
  - commit:                                # 성공 분기를 duration_s 동안 래치(국면 안정화)
      name: hold_zone
      duration_s: 3.0
      cooldown_s: 2.0
      child:
        sequence:
          - condition: {name: is_offensive, aspect_deg: 45}
          - action: {pursuit: lag, mode: control_zone, cz_range_ft: 2200, name: hold}   # 존 목표거리
  - inverter: {condition: {name: closing, min_fps: 250}}   # 결과 반전(과속접근 아닐 때)
  - action: {pursuit: pure, name: default}
```

```yaml
# ③ high yo-yo — aim_above_ft 로 조준점을 수직으로 옮겨 국면을 만든다
#    (BEM 4.4.6.2.3 / 4.4.7.2. 과접근을 수직으로 소산하고 정점에서 재강하 공격)
commit:
  name: high_yoyo
  duration_s: 4.0        # 요요 1회 예산 — 4~5s 를 넘기면 에너지 소산이 과하다
  cooldown_s: 3.0        # 연속 요요(chattering) 방지
  child:
    selector:
      # 국면2 — 정점: 후방 + 적이 아래 + 접근율 정리됨 → 리드로 재강하 공격
      - sequence:
          - condition: {name: behind_foe, aspect_deg: 90}
          - condition: {name: foe_below, min_ft: 800}
          - inverter:
              condition: {name: closing, min_fps: 60}
          - action: {pursuit: lead, name: yoyo_down, aim_above_ft: -300, lead_time_s: 1.5}
      # 국면1 — 상승: 후방 추적 중 과접근 → 조준점을 위로(수직 소산)
      - sequence:
          - condition: {name: behind_foe, aspect_deg: 90}
          - condition: {name: overshoot_risk, closure_fps: 160, range_ft: 2200}
          - action: {pursuit: lag, name: yoyo_up, aim_above_ft: 750, lag_dist_ft: 2000}
```

> `behind_foe` 게이트가 없으면 헤드온 머지마다 오발동해 사격 창을 잠식한다.
> `commit` 없이 조건만 쓰면 임계값 근처에서 국면1↔국면2 가 매 tick 뒤집혀 요요가
> 성립하지 않는다 — **수직 기동은 래치가 있어야 기동이 된다.**

```yaml
# ④ cooldown — 회복 브랜치가 임계값 근처에서 붙었다 떨어졌다 하는 것을 막는다
selector:
  - cooldown:
      name: regain
      wait_s: 8.0                # 회복이 끝난 뒤 8초는 이 분기를 아예 건너뛴다
      child:
        sequence:
          - condition: below_fighting_speed
          - action: {pursuit: lag, name: regain_energy}
  - action: {pursuit: pure, name: chase}
```

> **`commit` 과 `cooldown` 은 서로 반대편을 막는다.** commit 은 *들어간 뒤* duration_s
> 동안 붙잡아 둔다(중간에 조건이 풀려도 기동을 마치게 한다). cooldown 은 *끝난 뒤*
> wait_s 동안 다시 못 들어가게 한다. 요요처럼 완주해야 하는 기동은 commit,
> 에너지 회복처럼 경계에서 재진입이 잦은 분기는 cooldown 이다.


## 관측값

트리는 조건을 통해서만 상황을 본다. **적 HP·피해량은 비노출**(정보 정책) — 기하로 추정하라.

> **부호 규약**: 적 상대위치 계열(`alt_gap_ft`=적−아군, +면 적이 위)과 내 우위 margin 계열(`energy_diff_ft`=아군−적, +면 내가 우세)은 기준이 다르다 — 각각 `foe_above`(적 어디 있나)·`energy_advantage`(내가 유리한가) 조건이 부호 그대로 자연스럽게 읽히도록 최적화한 것.

| 필드 | 설명 |
|---|---|
| `ata_deg` | 내 기수(종축)→적 각도. 0°=정조준 (BEM ATA) |
| `aspect_deg` | 적 종축(꼬리) 기준 내 위치각. 0°=내가 적 6시, 180°=적이 나를 정면 조준 (BEM AA) |
| `range_ft` | 상대 거리 [ft] |
| `closure_fps` | 접근율 [ft/s]. +접근 / −이탈 |
| `kcas` | 내 보정대기속도 [kts] |
| `energy_diff_ft` | 비에너지 차(아군−적) [ft]. +우세 |
| `alt_gap_ft` | 고도 차(적−아군) [ft]. +적이 위 |
| `alt_ft` | 내 절대고도(MSL ft) — 하드덱(1,000ft) 회피 판단 |
| `my_health` | 내 잔여 HP (적 HP 는 비노출 — 기하로 추정) |
| `hca_deg` | 종축 교차각(BEM Angle-Off). 0°=동방향, 180°=헤드온 |
| `my_turn_dir` | 내 수평 선회방향 (+1 우/−1 좌/0 직선) — 1/2-circle flow 판별 |
| `foe_turn_dir` | 적 수평 선회방향 (+1 우/−1 좌/0 직선) — one_circle/two_circle 조건 |
| `vel_ata_deg` | 내 속도벡터→적 각도. 0°=비행경로가 적을 향함 (기수 기준은 ata_deg) |
| `vel_aa_deg` | 적 속도벡터→나 각도. 180°=적 비행경로가 나를 향함 (기수 기준은 aspect_deg) |
| `overtime` | 오버타임 구간인가 (조건 in_overtime). 경과 시간은 관측되지 않으므로 OT 인지 경로는 이것뿐이다 — 현장 단판 외에는 항상 False |
| `t_s` | 트리 자체 시계 [s] (Commit/Cooldown 용) |
| `dt_s` | 트리 tick 간격 [s] (20Hz) |

## 교리(Doctrine) 파라미터

L2 setpoint — 출처: RoKAF F-16C BEM Vol.5 (2005) Ch.4. 상태: **개방됨** — 아래 범위 안에서 `doctrine:` 블록으로 조정.

| 필드 | 기본값 | 허용 범위(교범 대역) |
|---|---|---|
| `corner_kcas_lo` | 330 | [330, 440] |
| `corner_kcas_hi` | 440 | [330, 440] |
| `fighting_kts_lo` | 325 | [325, 375] |
| `fighting_kts_hi` | 375 | [325, 375] |
| `energy_margin_lo` | 50 | [50, 75] |
| `energy_margin_hi` | 75 | [50, 75] |
| `slant_ft_lo` | 4000 | [4000, 6000] |
| `slant_ft_hi` | 6000 | [4000, 6000] |
| `ata_target_lo` | 35 | [35, 50] |
| `ata_target_hi` | 50 | [35, 50] |
| `entry_kcas` | 465 | [450, 480] |
| `lv_above_ft` | 750 | [500, 1000] |
| `initial_pull_g` | 7 | [6, 8] |
| `g_fraction` | 0.95 | [0.8, 0.95] |
| `g_min` | 1 | [1, 1.5] |
| `initial_pull_aspect_deg` | 120 | [90, 150] |
| `closure_saddle_ft` | 900 | [600, 1500] |
| `energy_backoff_floor` | 0.5 | [0.3, 0.8] |
| `cz_close_t_s` | 4 | [2, 8] |

### 교리 블록 쓰는 법 (예제)

```yaml
agent_name: MyViper
doctrine:
  fighting_kts_lo: 350     # 기본 325 (허용 325~375)
  fighting_kts_hi: 375
  lv_above_ft: 900          # 기본 750 (허용 500~1000)
selector:
  - sequence:
      - condition: below_fighting_speed   # 임계값이 325 → 350 로 함께 이동
      - action: {pursuit: lag, name: regain_energy}
  - action: {pursuit: pure, name: chase}
```

거부되는 예 — 전부 **제출 단계**에서 걸린다(`tools/validate_agent.py` 가 같은 메시지를 낸다):

| 쓴 값 | 거부 사유 |
|---|---|
| `fighting_kts_lo: 300` | 교범 허용 범위 [325, 375] 밖 |
| `fighting_kts_lo: 375` + `fighting_kts_hi: 325` | `fighting_kts: lo > hi` (대역이 뒤집힘) |
| `corner_speed: 400` | 미지 교리 필드 — 오타를 조용히 무시하지 않는다 |

> `doctrine:` 블록을 아예 안 쓰면 위 표의 기본값으로 동작한다. 조건에 임계값을 직접
> 쓰면(`condition: {name: below_fighting_speed, kcas: 330}`) 교리 연동이 끊기고
> 명시값이 이긴다.

## 에디터 자동완성 (JSON Schema)

`docs/agent.schema.json` — 이 문서와 동일 원천에서 자동 생성되는 어휘 스키마.
VS Code + YAML 확장([redhat.vscode-yaml](https://marketplace.visualstudio.com/items?itemName=redhat.vscode-yaml))이면
SDK 루트를 열 때 `.vscode/settings.json` 으로 자동 적용된다 — `my_agents/`·`examples/` 의
yaml 에서 조건·키 자동완성, 오타 밑줄, 임계값 기본값 힌트.

다른 에디터(yaml-language-server 지원)는 파일 첫 줄에 (my_agents/ 기준):

```yaml
# yaml-language-server: $schema=../docs/agent.schema.json
```

> 에디터 검증은 **보조 수단**이다 — 최종 판정은 `tools/validate_agent.py`(서버와 동일 파서).
> 제출 전 반드시 validate_agent 를 통과시킬 것.
