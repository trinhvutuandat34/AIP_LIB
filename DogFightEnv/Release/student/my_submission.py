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
      --bundle-dir artifacts/curriculum/real_eagle/v4/stage_3_autopilot_pursuit/final_bundle \\
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
      --bundle-dir artifacts/curriculum/real_eagle/v4/stage_3_autopilot_pursuit/final_bundle \\
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
from student.controller_providers import EnvelopeGatedHybridProvider, VPTrackingProvider
from student.submission_resilience import ResilientActionProvider, supervise_client


# =============================================================================
# TODO: 아래 설정을 팀에 맞게 수정하세요.
# =============================================================================

TEAM_NAME = "real_eagle"
SERVER_IP = "221.151.77.208"   # TODO: 운영 공지로 최신 서버 IP 확정 필요 -- startup_command.txt의
                                # 10.185.16.247(사설/연습망으로 추정)과 다름; 최신 공지 전까지 확정 아님
SERVER_PORT = 9999

# 사용할 백엔드 모드 선택: "rl" | "bt" | "vptrack" | "hybrid" | "hybrid_vptrack" | "hybrid_gated"
#
# TEMP SAFE DEFAULT (2026-08-05): forced to "bt" until a bundle is validated (via
# eval_matchup.py, beats pure BT) -- BUNDLE_DIR below still points at the v4 stage_3 bundle,
# documented (below) as a 100%-crash policy. The health gate only catches NaN/Inf weights, not
# this (finite-but-degenerate), so "hybrid" would blend that crash behavior into the BT floor
# every match. Team-confirmed target strategy is still Hybrid(residual) -- flip back once
# BUNDLE_DIR points at a bundle that actually beats BT-alone.
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
# !!! 경고 (2026-08-01 검증): 아래 BUNDLE_DIR은 "고장난" 모델을 가리킵니다.
#     제출용이 아니라 자리표시자입니다. 실제 학습 아티팩트를 직접 확인한 결과:
#       - v4/stage_3 (아래 경로)  = 최종 crash_rate 100%, reward -1.001,
#                                   접근 실패(min-distance 4.8 km) -- 100% 추락 정책
#       - v4/stage_4~7            = SAC가 stage 4 iter 248에서 NaN 발산 -> 가중치 손상
#       - v4/stage_0~2            = loiter/고정 표적만 상대(실전 교전 미학습)
#     즉, 현재 경진대회에 쓸 수 있는 RL bundle이 하나도 없습니다.
#
# 조치: experiments/real_eagle_v5.yaml 로 안정화 재학습(grad_clip + reward guard)
#     을 돌린 뒤, full_dogfight 까지 통과한 안정적인 bundle 경로로 아래를 교체하세요.
#     v5 완료 전에 실전 슬롯이 온다면 MODE="bt"(순수 BT)가 유일하게 안전한 제출입니다
#     -- residual hybrid는 고장난 RL을 더해도 BT 베이스까지 함께 망가뜨립니다
#     (NaN -> clip_action이 전체 action을 0으로 -> idle stall).
# =========================================================================
BUNDLE_DIR = "artifacts/curriculum/real_eagle/v4/stage_3_autopilot_pursuit/final_bundle"  # TODO: v5 안정 bundle로 교체
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
ACTION_REPEAT = 6          # 학습 step_ratio=6과 맞춰 6개 PlaneInfo pair마다 새 policy 호출
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
#       --ownship-backend hybrid \\
#       --ownship-bundle-dir artifacts/curriculum/real_eagle/v4/stage_3_autopilot_pursuit/final_bundle \\
#       --observation-mode custom --observation-module student.my_observation_v2 \\
#       --target-backend bt \\
#       --save-log


# =============================================================================
# 실행 로직 (수정 불필요)
# =============================================================================

def build_action_provider():
    if MODE == "bt":
        print(f"[{TEAM_NAME}] BT 백엔드 사용: {BT_DLL}")
        return BTActionProvider(dll_name=BT_DLL)

    # vptrack: 네이티브 BT가 전술/스로틀을 담당하고, 종말 조준(터미널 트래킹)만
    # student 쪽 제어 법칙이 가져간다. 2026-08-06 측정(N=30, OBFM, 동일 시드):
    # 승률 0/30 -> 12/30, WEZ 접촉 0/30 -> 30/30, 자기추락 0. RL 번들이 전혀 필요 없으므로
    # 번들 상태와 무관하게 안전하다 -- 즉 MODE="bt"보다 강한 새로운 안전 바닥이다.
    if MODE == "vptrack":
        print(f"[{TEAM_NAME}] VP 트래킹 백엔드 사용 (RL 없음): {BT_DLL}")
        return VPTrackingProvider(dll_name=BT_DLL)

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
            supervise_client(make_client)
        finally:
            action_provider.close()
            print(f"[{TEAM_NAME}] 클라이언트 종료")


if __name__ == "__main__":
    main()
