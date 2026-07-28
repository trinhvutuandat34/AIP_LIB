# AIP 경진대회 매뉴얼 (rev7)

## Slide 1

2026 AI Pilot Top Gun Challenge

나만의 AI Pilot을
실험하는 방법

## Slide 2

1. 접근법

이 매뉴얼의 목적

RLLib 기반 실험 공통 플랫폼 사용 가이드

●  학생은 보상, 관측, 커리큘럼, YAML 조건을 자유롭게 설계합니다.
●  공통 코드는 실행 계약과 기록 방식을 제공합니다.
●  아이디어는 작게 돌리고, 로그로 읽고, 다음 가설로 이어가는 방식을 권장합니다.

핵심 규칙 3개

1

실행 위치와 런타임 자산

2

관측 mode/module 일치

3

bundle과 관측 차원 호환성

## Slide 3

1. 접근법

좋은 실험은 작은 루프입니다

가설

→

YAML 기록

→

짧은 학습

→

로그 확인

→

수정

작게
● 가설 1개
● 조건 1개만 변경

기록되게
● YAML로 조건 보존
● output.name + tag

읽히게
● dashboard에서 비교
● config.json까지 같이

## Slide 4

1. 접근법

관찰 가능한 지표는 결과의 이유를 읽습니다

reward_mean
에피소드 평균 reward
추세로 학습 안정성 확인

crash_rate
추락 발생률
보상 과격도와 함께 봄

ep_min_distance
에피소드 내 최소 접근
접근/회피 행동 진단

ep_wez_steps
WEZ 안에서 머문 step
교전 점유 시간

승률 하나로 판단하지 않습니다. 왜 그렇게 됐는지를 metric으로 같이 봅니다.

## Slide 5

2. 실행 준비

Release 폴더를 루트로 사용합니다

Release/
├ src/dogfight/        공통 플랫폼
├ student/             학생 작성 템플릿
├ experiments/         YAML 실험 템플릿
├ train_rllib.py       단일 학습
├ train_curriculum.py  커리큘럼 학습
├ run_local_dogfight.py
├ run_unreal_inference.py
└ DLL / Rule XML / aircraft / engine / scripts

수정 중심
● student/
● experiments/*.yaml

공통 플랫폼
● src/dogfight/
● 실행 계약을 제공
● 기본적으로 직접 수정하지 않음

런타임 자산
● DLL, XML, aircraft, engine, scripts
● 이름 변경과 이동 금지

## Slide 6

2. 실행 준비

python 가상환경을 먼저 설치합니다

Anaconda 설치 시 체크박스

## Slide 7

2. 실행 준비

python 가상환경을 먼저 설치합니다

cd DogFightEnv\Release
python -m pip install -r requirements.txt
python scripts\run_experiment.py experiments\student_sac_mlp.yaml --dry-run

python -c "import JSBSimWrapper; print('OK')"

● python을 설치합니다.
● command prompt에서 진행하길 권장합니다.
● Anaconda 가상환경 Python 3.11.x를 사용합니다.
● 설치 직후에는 학습보다 import와 dry-run부터 확인합니다.
● Ray/Torch 문제는 가상환경과 버전 충돌을 먼저 봅니다.

conda create –n aip python=3.11
conda activate aip

cd DogFightEnv\Release
python RLLibLstm\tools\apply_rllib_sac_lstm_patch.py C:\Users\USER\anaconda3\envs\aip --dry-run

## Slide 8

2. 실행 준비

런타임 자산은 반드시 지켜져야 하는 실행 계약입니다

종류

파일/폴더

주의

JSBSim

JSBSimAIPLib.dll

Release 루트

BT DLL

AIP_BASE.dll
AIP_BASE_target.dll

기본/target DLL 구분
팀 DLL은 인자로 지정

Rule XML

Rule_forTraining.xml
Rule_팀이름.xml

기본 Rule 유지
팀별 Rule은 --bt-rule-xml

Aircraft/Engine

aircraft/, engine/

폴더 이동 금지

JSBSim scripts

scripts/

초기 실행 자산

## Slide 9

2. 실행 준비

실패 원인은 다음 부분들부터 확인합니다

DLL을 찾지 못함
Release 루트에서 실행 중인지 확인
파일명 일치 확인

import 실패
가상환경 활성화
requirements 설치 상태 확인

모델 로드 실패
metadata.json / policy_weights.pkl.gz
BUNDLE_DIR 경로 확인

관측 차원 오류
학습과 추론의 mode/module 일치
OBSERVATION_SIZE 확인

## Slide 10

3. 환경 계약

환경은 네 개의 계약으로 움직입니다

Observation
정책 입력 벡터
mode/module/shape 일치

Action
4차원 연속 제어
throttle은 내부에서 [0,1]로 변환

Reward
float reward + components
분석 가능한 이름으로 기록

Termination / Info
종료 사유
로그와 metric 해석 근거

## Slide 11

3. 환경 계약

관측 모드 : 기본 4종과 custom

classic12
기본 비교용
12차원

relative14
상대 위치 중심
14차원

tactical16
기본 제공 예시
16차원

legacy37
37차원

custom
student/my_observation.py
OBSERVATION_SIZE 직접 선언

--observation-mode custom --observation-module student.my_observation

tactical16은 기본 제공 예시입니다. 학생 설계의 정답으로 고정하지 않습니다.

## Slide 12

3. 환경 계약

custom observation 작성 계약 : my_observation.py

OBSERVATION_MODE = "student8"
OBSERVATION_SIZE = 8
def build_observation(ownship_state, target_state, geo_info, wez_config=None):
    return np.asarray(obs, dtype=np.float32)

shape
반환 vector shape == OBSERVATION_SIZE

dtype
float32 1-D vector 권장

일관성
학습 / 로컬 / Unreal 모두 같은 module path

## Slide 13

3. 환경 계약

액션과 종료는 결과 해석의 기준입니다

축

의미

범위

0

roll

[-1, 1]

1

pitch

[-1, 1]

2

rudder/yaw

[-1, 1]

3

throttle

[-1,1]->[0,1]

승패보다 종료 사유부터 봅니다. 종료 조건은 정답이 아니라 분석 기준입니다.

Health
ownship/target HP 0 이하

Altitude
최저 고도 미만

Time / Step
max_engage_time
episode_step_limit

FDM / Guard
FDM 오류, NaN
연구용 guard

액션 공간

종료 조건

## Slide 14

4. 학생 작성

학생 수정 영역은 분리되어 있습니다

student/my_reward.py
보상 아이디어
compute_reward() 반환 계약

student/my_observation.py
관측 아이디어
OBSERVATION_SIZE와 shape 계약

student/my_curriculum.py
단계 아이디어
get_stages()로 stage 목록 제공

Experiments/*.yaml
실험 조건 기록
output/env/algo/runtime을 파일로 보존

공통 학습 루프를 담은 본체의 수정은 지양합니다.

## Slide 15

4. 학생 작성

my_reward.py: 공식보다 반환 계약

MY_REWARD_CONFIG = { ... }
def compute_reward(...):
    components = {}
    total = ...
    return float(total), components

반환 계약
float total
dict components

components 이름
ep_reward_<name>으로 기록
metric 분석에 사용

정답 회피
전술 로직 예시는 답안처럼 보이지 않게 최소화

## Slide 16

4. 학생 작성

my_observation.py: 커스텀 관측공간

필수
OBSERVATION_SIZE
build_observation(...)

선택
OBSERVATION_MODE
OBSERVATION_LOW/HIGH
describe_observation()

차원 변경 위험
기존 checkpoint/bundle과 호환 불가

기록 위치
YAML env.observation_module
metadata.json observation_module
my_submission.py OBSERVATION_MODULE

## Slide 17

4. 학생 작성

my_curriculum.py: get_stages() 계약

from dogfight.ai.curriculum import CurriculumStage
def get_stages() -> list[CurriculumStage]:
    return [
        CurriculumStage(
            name=...,
            initial_scenario=..., ...),
        ...
    ]

기본 curriculum 참고
Stage 0~3: survival / pursuit / WEZ / autopilot
Stage 4~13: two_circle_headon a000~a180
Stage 14: full_dogfight

실행
--stages-module student.my_curriculum

기본 stage는 출발점이 아니라 계약 확인용 참고입니다.

## Slide 18

4. 학생 작성

my_train.py는 wrapper · train_rllib.py가 본체

my_train.py (학생)
TRAINING_CONFIG
ENV_CONFIG
RL_CONFIG
공통 trainer 호출 wrapper

train_rllib.py (본체)
학습 루프, Ray 초기화
checkpoint / bundle 저장
logging / dashboard / record

python train_rllib.py --algorithm sac
  --reward-module student.my_reward
  --output-name team01 --output-tag v1

공통 학습 루프를 담은 본체의 수정은 지양합니다.

## Slide 19

5. 실험 관리

YAML 템플릿 6종: 실험 조건을 보존합니다

템플릿

용도

주요 키

student_sac_mlp.yaml
student_ppo_mlp.yaml

일반 학생 시작점
MLP baseline

algo.mlp
reward/observation module

student_sac_lstm.yaml
student_ppo_lstm.yaml

LSTM 경로
SAC는 RLLibLstm 패치 필요

algo.lstm
algo.network

student_mixed_initial_sac_mlp.yaml

BT/loiter target 혼합
MLP 예시

env_config.initial_scenario

student_mixed_initial_sac_lstm.yaml

mixed initial + SAC LSTM
고급 예시

RLLibLstm
initial_scenario

## Slide 20

5. 실험 관리

dry-run으로 실제 명령을 먼저 봅니다

python scripts\run_experiment.py experiments\student_sac_mlp.yaml --dry-run

dry-run이 보여주는 것
YAML → CLI 변환 결과
output.name / tag
선택된 module path
env_config nested 설정

바로 다음 단계
짧은 iterations로 smoke
관측 shape / reward 반환 확인
bundle 저장 확인

YAML은 조건을 기록하고, Python 아이디어는 module로 주입합니다.

## Slide 21

5. 실험 관리

두 실험을 비교할 때는 숫자와 조건을 함께 봅니다

Run A · sac_mlp_v1
YAML: student_sac_mlp.yaml
config.json observation_module 확인
metrics.jsonl reward_mean, crash_rate

vs

Run B · mixed_initial_sac_mlp_v1
YAML: student_mixed_initial_sac_mlp.yaml
initial_scenario 분포 확인
metrics.jsonl win_rate, ep_min_distance

metrics.jsonl
reward_mean 추세
crash_rate, win_rate

config.json
YAML/CLI 설정
reward / observation module

metadata.json
obs_mode / observation_module
bundle 해석 기준

## Slide 22

5. 실험 관리

모델 bundle은 학습 모델의 제출 단위입니다

artifacts/models/<team>/<tag>/
├ metadata.json
└ policy_weights.pkl.gz

metadata.json 확인 키
algorithm
obs_mode / observation_module
reward_module

policy_weights.pkl.gz
경량 정책 weight
Native checkpoint와 분리

bundle 사용 위치
로컬 검증 / Unreal 제출

## Slide 23

6. 학습 실행

PPO와 SAC는 선택 가능한 도구입니다

PPO
정책 업데이트 폭 제한
비교적 안정적인 baseline
clip-param, gae-lambda

SAC
entropy 기반 탐색
연속 제어 실험에 적합
tau, target-entropy
LSTM/RNNSAC는 RLlib 패치 필요

## Slide 24

6. 학습 실행

처음에는 짧게, 의존성부터 확인합니다

python train_rllib.py --algorithm sac --iterations 1 --output-name team01 --output-tag smoke

python student\my_train.py --iterations 1

초기 목표
좋은 reward가 아니라 실행 가능성 확인

Ray/RLlib 의존성
짧은 smoke로 빌드/import 확인
긴 Ray 실행은 본 학습에서만

이후 확대
관측 shape, reward 반환, bundle 저장을 먼저
안정화 후 iterations와 batch를 키운다

ray stop –force

## Slide 25

6. 학습 실행

재개 방식 3종: 보존 상태가 다릅니다

Native checkpoint
옵션: --restore-checkpoint
보존: policy + optimizer + replay buffer
쓰임: 중단된 학습을 그대로 재개

Lightweight bundle
옵션: --init-bundle
보존: policy weight only
쓰임: 좋은 정책을 시드로 새 실험 시작

Curriculum resume
옵션: --resume
기준: curriculum_state.json
쓰임: 중단된 stage/iteration 이어가기

주의: 관측 변경
OBSERVATION_SIZE 또는 module이 바뀌면 기존 checkpoint/bundle과 호환되지 않습니다.

주의: LSTM bundle
LSTM bundle은 metatdata의 use_lstm_sac, lstm_scope, max_seq_len 확인 필요

주의: 한 줄 원칙
--restore-checkpoint`와 `--init-bundle`은 동시에 쓰지 않는다. weight-only 재시작을 checkpoint 재개처럼 해석하면 optimizer/replay 상태가 달라져 결과 비교가 흔들린다.

## Slide 26

7. 로컬 검증

로컬 검증은 제출 전 안전 점검입니다

bundle 선택

→

backend 조합

→

교전 실행

→

종료 사유 확인

→

다음 실험

python run_local_dogfight.py --ownship-backend rl --ownship-bundle-dir artifacts\models\team01\v1 --target-backend bt --save-log

## Slide 27

7. 로컬 검증

먼저 볼 것은 승률보다 실패 원인입니다

Crash / Altitude
비행 안정성 실패
액션 과격도, 초기 조건 확인

FDM / NaN
시뮬레이터 상태 오류
로그와 상태값 확인

Observation mismatch
mode/module 불일치
bundle metadata와 제출 설정 비교

Distance / WEZ
접근과 기하 흐름
정답 보상이 아닌 관찰 지표

## Slide 28

7. 로컬 검증

custom 관측 policy는 같은 module로 검증합니다

python run_local_dogfight.py
  --ownship-backend rl
  --ownship-bundle-dir artifacts\models\team01\observation_v1
  --target-backend bt
  --observation-mode custom
  --observation-module student.my_observation

같은 module path
학습 때 쓴 module을 그대로 사용

판단 기준
로그 근거로 다음 실험을 고른다

## Slide 29

8. Unreal 제출

Unreal 접속도 같은 입력 계약을 씁니다

PlaneInfo

→

Observation

→

Policy/BT

→

CMD

→

Unreal step

입력 계약 일치
로컬 / 학습 / Unreal 동일 module path

서버 정보
IP / Port / 팀명
운영 공지 기준

MODE 선택
rl / bt / hybrid
rl/hybrid는 BUNDLE_DIR 필요

## Slide 30

8. Unreal 제출

student/my_submission.py 수정 지점

설정

의미

확인

TEAM_NAME

팀 표시 이름

등록명과 일치

SERVER_IP / PORT

Unreal 서버 주소

운영 공지 기준

MODE

rl / bt / hybrid

실험 의도와 일치

BUNDLE_DIR

제출 policy 경로

metadata와 weights 확인

OBSERVATION_MODE / MODULE

policy 입력 계약

학습 설정과 일치

## Slide 31

9. 최종 점검

최종 체크리스트와 운영 원칙

실행 위치
Release

실험 기록
YAML
output.name/tag
dashboard config.json

모델 파일
metadata.json
policy_weights.pkl.gz
bundle path

제출 계약
student/*
artifacts/models/<output team>/<output tag >

## Slide 32

Appendix A

오류 FAQ

증상

먼저 확인

조치

DLL 오류

Release 루트와 파일명

위치/이름 확인

import 실패

Python/venv/requirements

환경 재확인

모델 로드 실패

BUNDLE_DIR와 파일 2개

metadata/weights 확인

관측 오류

mode/module/shape

학습 설정과 제출 설정 비교

서버 무응답

IP/port/방화벽

운영 공지와 네트워크 확인

## Slide 33

Appendix B

로그는 다음 가설의 근거입니다

로그

볼 것

사용

training_log.csv

reward, crash, win, WEZ, distance

학습 추세

metrics.jsonl

dashboard scalar

시각 비교

config.json

YAML/CLI/module 설정

조건 비교

Tacview CSV

위치, 자세, health

로컬 교전 복기

summary.json

end_condition, outcome

종료 사유

## Slide 34

Appendix C

긴 CLI 명령 모음

YAML dry-run
python scripts\run_experiment.py experiments\student_sac_mlp.yaml --dry-run

단일 학습
python scripts\run_experiment.py experiments\student_sac_mlp.yaml

custom 관측 학습
student_sac_mlp.yaml에서 observation_mode: custom,
observation_module: student.my_observation 활성화

## Slide 35

Appendix C

긴 CLI 명령 모음

Native checkpoint 재개
python train_rllib.py --algorithm sac --iterations 50 `
  --restore-checkpoint artifacts\checkpoints\team01\v1 `
  --output-name team01 --output-tag v1_resume

Lightweight bundle 재시작
python train_rllib.py --algorithm sac --iterations 50 `
  --init-bundle artifacts\models\team01\v1 `
  --output-name team01 --output-tag bundle_restart_v1

SAC LSTM YAML smoke
ray stop --force
python scripts\run_experiment.py experiments\student_sac_lstm.yaml --dry-run
python scripts\run_experiment.py experiments\student_sac_lstm.yaml

## Slide 36

Appendix D

Unreal 접속 명령

python run_unreal_inference.py --mode rl
  --bundle-dir artifacts\models\team01\sac_mlp_v1
  --team-name team01 --server-ip <IP> --server-port 9999
  --action-repeat 6

python run_unreal_inference.py --mode rl
  --bundle-dir artifacts\models\team01\observation_v1
  --observation-mode custom --observation-module student.my_observation
  --team-name team01 --server-ip <IP> --server-port 9999
  --action-repeat 6

python run_unreal_inference.py --mode hybrid
  --bundle-dir artifacts\models\team01\sac_mlp_v1
  --bt-dll AIP_BASE.dll --bt-rule-xml Rule_팀이름.xml
  --team-name team01 --server-ip <IP> --server-port 9999
또는 python student\my_submission.py

## Slide 37

Appendix E

관측 일관성

YAML

→

train

→

metadata

→

local

→

submission

위치

확인할 값

불일치 위험

YAML

env.observation_mode / observation_module

학습 조건 기록 오류

train_rllib.py

--observation-mode / --observation-module

학습 입력 차원 불일치

metadata.json

obs_mode / observation_module

bundle 해석 오류

run_local_dogfight

--observation-mode / --observation-module

로컬 성능 왜곡

my_submission.py / CLI

OBSERVATION_MODE / OBSERVATION_MODULE
BT_RULE_XML / ACTION_REPEAT

제출 추론 입력 또는 BT 자산 불일치

## Slide 38

Appendix F

SAC LSTM 패치 적용

기본 경로
student_sac_mlp.yaml
student_ppo_mlp.yaml
mixed initial은 별도 예시

패치 적용
RLLibLstm/tools/apply_rllib_sac_lstm_patch.py
Ray 2.54.0 site-packages 확인 후 적용

RNNSAC
`actor_only`: actor LSTM+MLP Q
`actor_critic`: recurrent Q/twin/target Q
`sequence_v1`: YAML layer sequence