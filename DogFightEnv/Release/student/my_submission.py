"""
[학생 작성 파일] 경진대회 제출 — Unreal 서버 연결
=====================================================
학습한 모델을 경진대회 서버에 연결합니다.
BUNDLE_DIR 경로와 팀 이름을 설정한 뒤 이 파일을 실행하세요.

RETARGETED 2026-07-16 (real_eagle): TEAM_NAME/BUNDLE_DIR/MODE below now point at this team's
actual v4 bundle instead of the generic team01/v1 placeholder, and build_action_provider() now
uses RemappedRLProvider/StudentHybridProvider (student/inference_providers.py) instead of the
stock RLActionProvider/HybridActionProvider -- the same fix originally landed 2026-07-14 (see
memory/project_hybrid_inference_fixes_2026_07_14.md), lost in the 2026-07-15 accidental revert
along with everything else in this file, and restored here. Using the stock providers directly
reproduces the exact bug that fix was for: RL throttle never gets remapped from the policy's
[-1,1] training convention to the sim/wire's [0,1], flooring every negative raw output to
engine-idle. run_unreal_inference.py and run_local_dogfight.py got the same fix restored in the
same pass, so local validation via run_local_dogfight.py actually exercises what this file does.

커맨드라인으로 직접 실행하는 방법 (권장)
-------------------------------------------
  # RL 모델 사용
  python run_unreal_inference.py --mode rl \\
      --bundle-dir <검증된_bundle_경로> \\
      --observation-mode custom --observation-module student.my_observation_v2 \\
      --team-name real_eagle \\
      --server-ip <서버IP> --server-port 9999

  # BT만 사용 (모델 없이)
  python run_unreal_inference.py --mode bt \\
      --bt-dll AIP_BASE.dll \\
      --bt-rule-xml Rule_forTraining.xml \\
      --team-name real_eagle \\
      --server-ip <서버IP>

  # RL + BT 하이브리드 (팀 확정 전략)
  python run_unreal_inference.py --mode hybrid \\
      --bundle-dir <검증된_bundle_경로> \\
      --observation-mode custom --observation-module student.my_observation_v2 \\
      --bt-dll AIP_BASE.dll \\
      --bt-rule-xml Rule_forTraining.xml \\
      --hybrid-mode residual --residual-scale 0.35 \\
      --team-name real_eagle \\
      --server-ip <서버IP>

이 파일에서 직접 실행하려면
----------------------------
  python student/my_submission.py

아래 설정을 수정한 뒤 실행하면 됩니다.
"""
from __future__ import annotations

import json
import os
import sys

# Force UTF-8 on stdout/stderr (2026-08-06). THIS FILE IS THE COMPETITION ENTRY POINT and it
# prints Korean status text on every start-up path. When stdout is a UTF-8 console that is fine,
# but when it is REDIRECTED TO A FILE -- which is how an unattended competition run is launched --
# Python falls back to the Windows ANSI codepage (cp1252) and the very first status print raises
# UnicodeEncodeError, killing the process BEFORE supervise_client's reconnect loop is ever armed.
# A submission that dies at start-up never connects, and not connecting is a DQ path
# (COMPETITION_RULES Sec 8). Demonstrated 2026-08-06 by running build_action_provider() with
# output redirected: UnicodeEncodeError on the mode-selection print.
import io as _io
for _stream in ("stdout", "stderr"):
    try:
        getattr(sys, _stream).reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, _io.UnsupportedOperation):
        pass

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for p in (ROOT, SRC):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from dogfight.ai.bt_action_provider import BTActionProvider
from dogfight.ai.bt_rule_manager import activate_rule_xml
from dogfight.ai.rllib_utils import build_algorithm_from_bundle
from dogfight.ai.student_hooks import load_observation_hook
from dogfight.unreal import AIType, ProviderCommandPolicy, UnrealAIPilotUDPClient

from student.inference_providers import (
    RemappedRLProvider,
    StudentHybridProvider,
    require_healthy_bundle,
    verify_bundle_observation,
)
# DQ hardening (2026-08-05): reconnect supervisor + never-throw provider wrapper. Guards the two
# no-edit-client fragilities that risk a competition-day disconnect/DQ (COMPETITION_RULES Sec8).
from student.controller_providers import (
    EnvelopeGatedHybridProvider,
    GLimitedProvider,
    VPTrackingProvider,
)
from student.g_limiter import G_LIMIT
from student.live_frame_fix import LiveVerticalFrameProvider
from student.submission_resilience import (
    ResilientActionProvider,
    run_with_setup_retry,
    supervise_client,
)


# =============================================================================
# TODO: 아래 설정을 팀에 맞게 수정하세요.
# =============================================================================

TEAM_NAME = os.environ.get("DOGFIGHT_TEAM_NAME", "real_eagle")

# ⚑ 제출본은 월요일에 잠기고 재제출이 없다(4.1 F39-ONE-SHOT-SUBMISSION). 그런데 공식 서버
# 주소는 아직 공개되지 않았고(4.1 F27), 기록에 남은 후보 IP는 전부 팀원 개인 장비다. 즉
# **주소가 제출 마감 이후에 공지될 수 있는데, 그때 이 파일은 이미 잠겨 있다.**
# 그래서 상수를 그대로 두되 환경변수로 덮어쓸 수 있게 한다 -- 잠긴 제출본을 수정하지 않고도
# 실행 시점에 올바른 주소를 넣을 수 있다. 환경변수가 없으면 동작은 종전과 100% 동일하다.
#
#     set DOGFIGHT_SERVER_IP=<공지된 IP>
#     set DOGFIGHT_SERVER_PORT=<공지된 포트>
#     python student\my_submission.py
#
# 포트도 같이 덮어써야 한다: 9999는 COMPETITION_RULES.md에 근거가 없고, 실제로 기록된 연결
# 테스트 2건은 모두 6666을 썼다(4.1 F27).
# 주소가 틀리면 조용히 실패한다 -- 소켓은 열리고 하트비트도 나가지만 프레임이 0장이다.
# 2026-08-21 실측(4.1 F40-SILENCE-BLIND). 이제 최소한 경고는 뜬다.
SERVER_IP = os.environ.get("DOGFIGHT_SERVER_IP", "221.151.77.208")
SERVER_PORT = int(os.environ.get("DOGFIGHT_SERVER_PORT", "9999"))

# 사용할 백엔드 모드 선택: "rl" | "bt" | "vptrack" | "hybrid" | "hybrid_vptrack" | "hybrid_gated"
#
# TEMP SAFE DEFAULT (2026-08-05): forced to "bt" until a bundle is validated (via
# eval_matchup.py, beats pure BT). At the time, BUNDLE_DIR still pointed at the v4 stage_3
# bundle, documented below as a 100%-crash policy. The health gate only catches NaN/Inf weights,
# not this (finite-but-degenerate), so "hybrid" would blend that crash behavior into the BT floor
# every match. Team-confirmed target strategy is still Hybrid(residual) -- flip back once
# BUNDLE_DIR points at a bundle that actually beats BT-alone.
#
# UPDATE 2026-08-11: BUNDLE_DIR is now None rather than a placeholder path, so an rl/hybrid* mode
# can no longer silently arm that crash policy -- it raises instead. See the BUNDLE_DIR block.
#
# UPGRADED 2026-08-06: "bt" -> "vptrack". This does NOT weaken the safety argument above --
# it strengthens it. "vptrack" loads NO RL bundle at all (see build_action_provider), so every
# concern in the paragraph above about a finite-but-degenerate policy is structurally absent,
# exactly as with "bt". What changes is only the flight-control law: the native BT still owns
# all tactics and throttle, and the student-space controller replaces Controller_CY's VP->stick
# law during terminal tracking only.
#
# Measured N=30, OBFM_offensive (the confirmed main-match preset), identical seeds, vs the
# same BT opponent:
#                        wins     WEZ-contact eps   damage dealt/taken   median min-ATA
#     MODE="bt"           0/30          0/30           0.00 / 0.000        4.08-4.45 deg
#     MODE="vptrack"     12/30         30/30          15.59 / 0.000        0.024 deg
# Zero self-crashes, ownship health 1.0 in every episode, and 49.6 us per decision (0.03% of
# the 166.7 ms six-frame compute budget). See COMPETITION_PLAN.md 4.1 D1-DONE / D3-FLOOR.
#
# KNOWN LIMIT (4.1 D1-LIMIT): on the neutral two_circle_headon merge -- the round-4 tie-break
# analogue, NOT rounds 1-3 -- vptrack scores 1/30, because it only takes the stick inside a
# <=1200 m / <=20 deg terminal envelope and the native BT still loses the neutral merge that
# would put it there. It converts an offensive position into a kill; it does not create one.
#
# Hybrid is NOT selected: every residual configuration measured is <= vptrack alone with the
# current (0-win) v6 policy. "hybrid_gated" is the upgrade path the moment a bundle exists
# that is worth composing -- it is safe at full residual scale where plain residual is not.
MODE = "vptrack"   # was "bt" (2026-08-05), was "hybrid" -- see notes above

# RL 모드 설정
# =========================================================================
# !!! BUNDLE_DIR = None (2026-08-11). 현재 경진대회에 쓸 수 있는 RL bundle이 하나도
#     없습니다. 실제 학습 아티팩트를 직접 확인한 결과:
#       - v4/stage_3   = 최종 crash_rate 100%, reward -1.001,
#                        접근 실패(min-distance 4.8 km) -- 100% 추락 정책
#       - v4/stage_4~7 = SAC가 stage 4 iter 248에서 NaN 발산 -> 가중치 손상
#       - v4/stage_0~2 = loiter/고정 표적만 상대(실전 교전 미학습)
#       - v5           = 100% 자기추락(20/20), v6 = 18/20 추락, 0승, WEZ 0
#       - v7           = 2026-08-11 학습 진행 중
#
#     2026-08-11 이전에는 여기에 v4/stage_3 경로가 "자리표시자"로 남아 있었습니다.
#     그것이 위험한 이유: 아래 건전성 게이트(require_healthy_bundle)는 NaN/Inf 가중치만
#     잡아내는데, 그 번들은 "유한하지만 망가진(finite-but-degenerate)" 상태라 게이트를
#     그대로 통과합니다. 즉 MODE를 rl / hybrid* 로 바꾸는 순간 100% 추락 정책이 아무런
#     경고 없이 실전 경로에 실립니다. None으로 두면 그 경로가 조용히 무장되는 대신
#     즉시 큰 소리로 실패합니다(_build_action_provider_raw의 가드 참고).
#
# 조치: 검증된 bundle -- 즉 "vptrack 단독보다 낫다"가 측정으로 확인된 bundle -- 이
#     나오면 아래를 그 경로 문자열로 교체하세요. 그때까지 안전한 제출은
#     MODE="vptrack"이며, 이것은 RL bundle을 전혀 로드하지 않습니다.
# =========================================================================
BUNDLE_DIR = None   # 검증된 bundle이 생기면 경로 문자열로 교체 (위 설명 참고)
OBSERVATION_MODE = "real_eagle15"                  # student.my_observation_v2의 OBSERVATION_MODE
OBSERVATION_MODULE = "student.my_observation_v2"   # 학습 시 사용한 custom 관측 모듈

# BT 모드 설정
# - 기본 배포 Rule은 Rule_forTraining.xml입니다 (2026-07-15 20종 기동 전부 재구성+재배포됨).
# - 팀별 BT DLL/XML을 제출하는 경우 파일을 Release 루트에 두고 아래 이름을 바꾸세요.
BT_DLL = "AIP_BASE.dll"
BT_RULE_XML = "Rule_forTraining.xml"  # BT 튜닝은 이 파일에서 직접 진행

# Hybrid 모드 설정 (MODE="hybrid" 일 때만 사용)
HYBRID_MODE = "residual"   # "residual" | "blend" | "switch"
RESIDUAL_SCALE = 0.35      # residual 모드 강도 (0~1, 클수록 RL 비중 증가)
ALPHA = 0.5                # blend 모드 비율 (alpha × RL + (1-alpha) × BT) -- residual에서는 미사용

# 연결 설정
AI_TYPE = AIType.Fusion    # MODE="hybrid"이므로 RL 단일이 아닌 Fusion으로 신고
HEARTBEAT_SEC = 1.0
COMMAND_DELAY_SEC = 0.0
RECV_TIMEOUT_SEC = 0.2
ACTION_REPEAT = 1          # 2026-08-20 6->1. 규칙의 60Hz 응답/0.1667s 패널티는 "판단 주기"가
# 아니라 "판단 1회당 연산 시간" 제한이며(대회 룰 슬라이드 자체 각주: "1/60초로 판단 안 내려도
# 되지만 조종명령은 꼭 60Hz로 답해야 함"), ProviderCommandPolicy.compute_command는 action-repeat
# 값과 무관하게 매 tick CMD를 보낸다(캐시든 신규 계산이든). 6은 RL 학습 step_ratio=6과 맞추기
# 위한 값이었는데, MODE="vptrack"은 학습된 적이 없으므로 맞출 대상이 없다. 실측
# VPTrackingProvider.compute_action worst-of-5000 = 0.611ms, 166.7ms 예산의 1/272 -- 어떤
# action-repeat 값에서도 여유. RL/hybrid 번들을 다시 실을 경우 그 모드는 자기 학습
# step_ratio에 맞춰 6으로 되돌릴 것 (모드별 결정, 전역 규칙 아님). See
# LIVE_INFERENCE_FRAME_BUGS.md Sec7, COMPETITION_RULES.md Sec4.
DEBUG_ACTION_REPEAT = False

# 번들 건전성 게이트 (2026-08-01 추가): RL 번들 가중치에 NaN/Inf가 있으면 실전에 내보내지
# 않습니다 (v4 stage 4~7의 NaN 발산이 정확히 이 경우). False = 비정상 번들이면 경고 후
# BT 전용으로 자동 강등(연결 실패 대신 BT 바닥으로 교전 진행). True = 즉시 예외 발생
# (제출 전 로컬 점검용 -- 문제를 크게 알리고 멈춤).
STRICT_BUNDLE_HEALTH = False


# =============================================================================
# 예시: 학습 결과 확인 (로컬 테스트용 백엔드)
# =============================================================================
# 경진대회 제출 전 로컬에서 결과 확인:
#   python run_local_dogfight.py \\
#       --ownship-backend vptrack \\
#       --target-backend bt \\
#       --save-log
#
# hybrid 계열을 확인하려면 --ownship-bundle-dir에 *검증된* bundle 경로를 넣으세요.
# v4/stage_3은 예시로도 쓰지 마세요 -- 100% 추락 정책입니다 (위 BUNDLE_DIR 설명 참고).


# =============================================================================
# 실행 로직 (수정 불필요)
# =============================================================================


def build_action_provider():
    """실제 제출 경로. 아래 _build_action_provider_raw()의 결과를 10 G 리미터로 감싼다.

    시뮬레이터에는 구조 한계가 없다: 전개된 측정(scripts/g_limit_check.py)에서 full pitch가
    550 kt에서 14.86 G까지 나온다(F-16 정격 9 G). 로컬에서 15 G를 활용하도록 학습/튜닝된
    기체는 G를 제한하는 실제 서버에서 다르게 움직이며, 그 차이는 로컬 평가가 아니라 경기
    당일에 드러난다. student/g_limiter.py 참고.
    """
    # Unreal은 state[2]를 위쪽이 양수인 고도로 보내지만 모든 소비자는 이를 NED Down으로
    # 읽는다. LiveVerticalFrameProvider가 리미터 안쪽에서 그 부호를 바로잡는다.
    # student/live_frame_fix.py 참고.
    return GLimitedProvider(
        LiveVerticalFrameProvider(_build_action_provider_raw()), limit_g=G_LIMIT
    )

def _build_action_provider_raw():
    if MODE == "bt":
        print(f"[{TEAM_NAME}] BT 백엔드 사용: {BT_DLL}")
        return BTActionProvider(dll_name=BT_DLL)

    # vptrack: 네이티브 BT가 전술/스로틀을 담당하고, 종말 조준(터미널 트래킹)만
    # student 쪽 제어 법칙이 가져간다. 2026-08-06 측정(N=30, OBFM, 동일 시드):
    # 승률 0/30 -> 12/30, WEZ 접촉 0/30 -> 30/30, 자기추락 0. RL 번들이 전혀 필요 없으므로
    # 번들 상태와 무관하게 안전하다 -- 즉 MODE="bt"보다 강한 새로운 안전 바닥이다.
    # THROTTLE_CONTROL=True 명시 (2026-08-13, 4.1 F29-THROTTLE-CONFIRMED). 이전에는
    # controller_providers.THROTTLE_CONTROL 기본값(off)에 의존했습니다. 두 가지 이유로 여기서
    # 명시적으로 켭니다.
    #   (1) 측정 결과가 뒤집혔습니다. F2-CHAMPION은 "null", F14는 "harmful"로 기록했지만
    #       그 측정들은 전술 계층이 죽어 있던 트리(F25 이전)에서 나온 것입니다. 살아 있는
    #       트리에 대해 peer rig로 3개 시드 N=30씩 재측정한 결과, 패배율이 매 시드마다
    #       감소했습니다(8 -> 5/5/4), 피해량도 8.31 -> 5.37/4.64/3.21. 통합 N=90에서
    #       패배율 26.7% -> 15.6%.
    #   (2) 환경변수(DOGFIGHT_VPTRACK_THROTTLE)에 의존하면 경기 당일 셸에 그 변수가
    #       설정되지 않았을 때 조용히 예전 동작으로 되돌아갑니다. 제출 경로에서는 추측이
    #       아니라 코드가 값을 정해야 합니다.
    # 되돌리려면: throttle_control=False (또는 이 인자를 제거).
    if MODE == "vptrack":
        # ENGAGEMENT ENVELOPE WIDENED TO 4000m/60deg (2026-08-20). This is a single, LOCKED
        # submission used for both the mandatory >50% cutoff gate AND every prelim match --
        # there is no separate resubmission window, so this one config has to serve both.
        #
        # The 50% cutoff bar is a hard, one-shot, unappealable gate (missing it means not
        # advancing at all), so it gets weighted more heavily than a marginal prelim edge.
        # Measured, cutoff N=100: standard 2500m/45deg = 76% win / 73% earned (CI ~[67,83]);
        # 4000m/60deg = 100% win / 95% earned (CI ~[96,100]) -- a materially larger safety
        # margin against a gate we cannot retry.
        #
        # Verified this does NOT cost real-match performance, via the peer rig (never trust
        # a symmetric measurement): match_base win rate matches or slightly exceeds the
        # standard config on two independent seeds (43.3/46.7% vs 43.3%, both seed 0 and
        # seed 1000), and obfm_defensive win rate is IDENTICAL (23.3% both) with damage
        # taken barely moving (0.577 vs 0.550). The real cost is confined to match_base
        # specifically: damage taken roughly doubles there (~0.48-0.53 vs 0.23) because the
        # wider envelope holds the terminal law engaged longer -- it does not change whether
        # we win, only the margin. See COMPETITION_PLAN.md 4.1 (envelope-margin analysis,
        # 2026-08-20) for the full numbers before changing this again.
        #
        # Revert: drop engage_range_m/engage_los_deg to return to 2500m/45deg.
        print(f"[{TEAM_NAME}] VP 트래킹 백엔드 사용 (RL 없음): {BT_DLL} "
              f"(throttle_control=True, engage=4000m/60deg)")
        return VPTrackingProvider(
            dll_name=BT_DLL, throttle_control=True,
            engage_range_m=4000.0, engage_los_deg=60.0,
        )

    # BUNDLE_DIR 가드 (2026-08-11): 여기 도달했다는 것은 MODE가 rl/hybrid* 계열이라는
    # 뜻이고, 그러려면 RL 번들이 반드시 있어야 합니다. 예전처럼 자리표시자 경로를 남겨두면
    # 건전성 게이트가 "유한하지만 망가진" 번들을 통과시켜 100% 추락 정책이 조용히 실립니다.
    # 조용히 무장되는 대신 여기서 멈춥니다.
    if BUNDLE_DIR is None:
        raise RuntimeError(
            f"MODE={MODE!r}는 RL 번들을 요구하지만 BUNDLE_DIR이 None입니다.\n"
            f"현재 검증된 RL bundle이 없습니다(v4 stage_3=100% 추락, v4 stage_4~7=NaN, "
            f"v5=100% 자기추락, v6=0승).\n"
            f"안전한 제출은 MODE=\"vptrack\"입니다 (RL 번들 불필요, 측정 12/30 승).\n"
            f"vptrack 단독보다 낫다고 측정된 bundle이 생기면 BUNDLE_DIR을 그 경로로 설정하세요."
        )

    bundle_path = ROOT / BUNDLE_DIR
    if not bundle_path.exists():
        raise FileNotFoundError(
            f"모델 번들을 찾을 수 없습니다: {bundle_path}\n"
            f"먼저 학습을 완료하고 BUNDLE_DIR 경로를 확인하세요."
        )

    metadata_path = bundle_path / "metadata.json"
    if metadata_path.exists():
        bundle_payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        verify_bundle_observation(bundle_payload, OBSERVATION_MODE, OBSERVATION_MODULE)

    # 번들 건전성 게이트: NaN/Inf 가중치면 실전 투입 거부. residual hybrid에서 NaN RL은
    # BT 베이스까지 함께 망가뜨리므로(전체 action -> 0 -> idle stall) MODE와 무관하게
    # 비정상이면 BT 전용으로 강등한다. strict=True면 여기서 예외를 던진다.
    if not require_healthy_bundle(str(bundle_path), strict=STRICT_BUNDLE_HEALTH):
        print(f"[{TEAM_NAME}] 번들 비정상 -> BT 전용으로 강등 (안전 바닥): {BT_DLL}")
        return BTActionProvider(dll_name=BT_DLL)

    print(f"[{TEAM_NAME}] RL 모델 로드: {bundle_path}")
    rl_provider = RemappedRLProvider(
        bundle_dir=str(bundle_path),
        algorithm_factory=build_algorithm_from_bundle,
    )

    if MODE == "rl":
        print(f"[{TEAM_NAME}] RL 전용 모드")
        return rl_provider

    # hybrid / hybrid_vptrack / hybrid_gated
    #
    # RESIDUAL_SCALE 경고 (2026-08-06 측정, N=30, OBFM): 고정된 제어 바닥 위에서
    # scale 0.35는 승률을 12/30 -> 0/30으로 무너뜨린다. 채점 게이트가 <=1.0도인데
    # 바닥은 0.024도로 수렴하므로, 0.35 보정은 지키려는 정밀도보다 훨씬 크다.
    # 측정된 절벽: 0.02 -> 12/30, 0.10 -> 13/30, 0.35 -> 0/30. 0.10 이하를 쓸 것.
    if MODE == "hybrid_gated":
        # 접근 단계에서만 잔차를 적용하고, 발사 해법(터미널 트래킹) 중에는 바닥을
        # 그대로 통과시킨다 -- 잔차가 조준 해법을 망칠 수 없는 구조.
        secondary = VPTrackingProvider(dll_name=BT_DLL)
        hybrid_cls = EnvelopeGatedHybridProvider
    elif MODE == "hybrid_vptrack":
        secondary = VPTrackingProvider(dll_name=BT_DLL)
        hybrid_cls = StudentHybridProvider
    else:
        secondary = BTActionProvider(dll_name=BT_DLL)
        hybrid_cls = StudentHybridProvider
    bt_provider = secondary
    print(f"[{TEAM_NAME}] Hybrid 모드: {MODE}/{HYBRID_MODE} (scale={RESIDUAL_SCALE}, alpha={ALPHA})")
    return hybrid_cls(
        primary_provider=rl_provider,
        secondary_provider=bt_provider,
        mode=HYBRID_MODE,
        alpha=ALPHA,
        residual_scale=RESIDUAL_SCALE,
    )


def main():
    print(f"=== {TEAM_NAME} 경진대회 클라이언트 시작 ===")
    print(f"서버: {SERVER_IP}:{SERVER_PORT}")
    print(f"모드: {MODE}")
    # 셋업(_run_once) 전체를 재시도로 감싼다 (2026-08-21, F42). supervise_client는 클라이언트가
    # 생긴 뒤부터만 보호한다 -- Rule XML 활성화/DLL 로드/관측 모듈 import는 그 앞에서 맨몸으로
    # 실행되고, 여기서 한 번 실패하면 프로세스가 그대로 종료되어 "접속 실패"(규정 8절 실격
    # 경로)가 된다. 갓 압축 해제한 DLL을 백신이 스캔하며 잠그는 상황이 대표적이며, 이런 실패는
    # 몇 초 뒤 재시도하면 성공하는 종류다. student/submission_resilience.py 참고.
    run_with_setup_retry(_run_once)


def _run_once():
    if MODE in {"bt", "hybrid"}:
        print(f"BT DLL/XML: {BT_DLL} / {BT_RULE_XML}")

    with activate_rule_xml(BT_RULE_XML, ROOT):
        # DQ hardening (2026-08-05): a never-throw provider wrapper + a reconnect supervisor so a
        # transient network error or a runtime hiccup self-heals instead of ending the session (a
        # disconnect = DQ risk, COMPETITION_RULES Sec8). See student/submission_resilience.py.
        action_provider = ResilientActionProvider(build_action_provider())
        observation_hook = (
            load_observation_hook(OBSERVATION_MODULE)
            if OBSERVATION_MODULE
            else None
        )
        command_policy = ProviderCommandPolicy(
            action_provider=action_provider,
            observation_mode=observation_hook["mode"] if observation_hook else OBSERVATION_MODE,
            observation_fn=observation_hook["build_observation"]
            if observation_hook
            else None,
            ownship_force_side=1,
            target_force_side=2,
            action_repeat=ACTION_REPEAT,
            debug_action_repeat=DEBUG_ACTION_REPEAT,
        )

        def make_client():
            return UnrealAIPilotUDPClient(
                command_policy=command_policy,
                server_ip=SERVER_IP,
                server_port=SERVER_PORT,
                team_name=TEAM_NAME,
                ai_type=AI_TYPE,
                heartbeat_interval_sec=HEARTBEAT_SEC,
                command_delay_sec=COMMAND_DELAY_SEC,
                recv_timeout_sec=RECV_TIMEOUT_SEC,
                enable_terminal_monitor=True,   # 패킷 모니터 표시
            )

        try:
            # activity= arms the server-silence watchdog (2026-08-21, F40). 경고만 하고
            # 재접속은 하지 않는다 (silence_reconnect_sec 기본 0.0) -- 주최측 기준
            # 클라이언트(unreal_bt_client.exe --server-timeout-sec)도 "Warn (log only)"이다.
            # 서버 침묵은 45초 실측에서 재접속도 경고도 없이 무시됐다. 근거는
            # student/submission_resilience.py의 _silence_watchdog 참고.
            supervise_client(make_client, activity=action_provider, silence_warn_sec=5.0)
        finally:
            action_provider.close()
            print(f"[{TEAM_NAME}] 클라이언트 종료")


if __name__ == "__main__":
    main()
