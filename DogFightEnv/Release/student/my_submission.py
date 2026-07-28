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
    verify_bundle_observation,
)


# =============================================================================
# TODO: 아래 설정을 팀에 맞게 수정하세요.
# =============================================================================

TEAM_NAME = "real_eagle"
SERVER_IP = "221.151.77.208"   # TODO: 운영 공지로 최신 서버 IP 확정 필요 -- startup_command.txt의
                                # 10.185.16.247(사설/연습망으로 추정)과 다름; 최신 공지 전까지 확정 아님
SERVER_PORT = 9999

# 사용할 백엔드 모드 선택: "rl" | "bt" | "hybrid"
MODE = "hybrid"   # 팀 확정 전략: Hybrid(residual) -- BT가 안전망, RL이 그 위에 보정을 얹음

# RL 모드 설정
# v4 커리큘럼은 stage 4(obfm_offensive)에서 정지된 상태(진행 중인 프로세스 없음, final_bundle
# 없음) -- 현재 쓸 수 있는 가장 최신/완성된 bundle은 stage 3(autopilot_pursuit)의 final_bundle.
# 주의: 이 bundle은 추격(pursuit)까지만 학습되었고 실제 BT 상대 교전 학습은 아직 못 마쳤음 --
# 제출 전 v4를 stage 4 이후로 재개하는 것이 최우선 과제 (memory/project_v4_recovery 참고).
BUNDLE_DIR = "artifacts/curriculum/real_eagle/v4/stage_3_autopilot_pursuit/final_bundle"
OBSERVATION_MODE = "real_eagle15"                  # student.my_observation_v2의 OBSERVATION_MODE
OBSERVATION_MODULE = "student.my_observation_v2"   # 학습 시 사용한 custom 관측 모듈

# BT 모드 설정
# - 기본 배포 Rule은 Rule_forTraining.xml입니다 (2026-07-15 20종 기동 전부 재구성+재배포됨).
# - 팀별 BT DLL/XML을 제출하는 경우 파일을 Release 루트에 두고 아래 이름을 바꾸세요.
BT_DLL = "AIP_BASE.dll"
BT_RULE_XML = "Rule_forTraining.xml"  # 예: "Rule_real_eagle.xml" (아직 별도 파일 없음)

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

    print(f"[{TEAM_NAME}] RL 모델 로드: {bundle_path}")
    rl_provider = RemappedRLProvider(
        bundle_dir=str(bundle_path),
        algorithm_factory=build_algorithm_from_bundle,
    )

    if MODE == "rl":
        print(f"[{TEAM_NAME}] RL 전용 모드")
        return rl_provider

    # hybrid
    bt_provider = BTActionProvider(dll_name=BT_DLL)
    print(f"[{TEAM_NAME}] Hybrid 모드: {HYBRID_MODE} (scale={RESIDUAL_SCALE}, alpha={ALPHA})")
    return StudentHybridProvider(
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
        action_provider = build_action_provider()
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

        client = UnrealAIPilotUDPClient(
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
            client.run()
        finally:
            action_provider.close()
            print(f"[{TEAM_NAME}] 클라이언트 종료")


if __name__ == "__main__":
    main()
