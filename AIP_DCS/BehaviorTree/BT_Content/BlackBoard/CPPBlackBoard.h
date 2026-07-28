#pragma once
#include "../../../Geometry/Vector3.h"
#include "../../../Geometry/EulerAngle.h"
#include <vector>

using namespace BT_Geometry;

enum BFM_Mode
{
	OBFM,
	HABFM,
	DBFM,
	DETECTING,
	SCISSORS,
	NONE

};

enum ACM_Mode
{
	EF,
	SF
};

enum TeamColor
{
	BLUE,
	RED,
	UNKNOWN
};

enum S_BFM_Mode
{
	S_OBFM,
	S_HABFM,
	S_DBFM,
	S_Others
};

enum WeaponMode
{
	Gun,
	Missile
};

// BT tactics-expansion phase tracker (AERIAL_COMBAT_BT_GUIDE_DETAILED.md). SyncActionNode
// forbids returning RUNNING (action_node.cpp: "SyncActionNode MUST never return RUNNING"), so
// multi-second phased maneuvers track their own elapsed time via BB->ActiveManeuverStartTime
// instead -- see Functions.h's ClaimManeuverPhase/ReleaseManeuverPhase.
enum ManeuverID
{
	Maneuver_None,
	Maneuver_TheBreak,
	Maneuver_Notch,
	Maneuver_FlatScissors,
	Maneuver_VerticalScissors,
	Maneuver_RollingScissors,
	Maneuver_NoseToNoseTurn,
	Maneuver_LeadTurn,
	Maneuver_HighYoYo,
	Maneuver_LowYoYo,
	Maneuver_BarrelRollAttack,
	Maneuver_NoseToTailTurn,
	Maneuver_LagDisplacementRoll,
	Maneuver_SingleSideOffset,
	Maneuver_AnglesTactics,
	Maneuver_EnergyTactics
};

/*
비행기들 객체 정보
자세, 위치, 속도, 팀, resv0(리눅스에서 ID), Resv1(비행기의 HP), Resv2(유인기/무인기)
*/
struct PlaneInfo
{
public:
	
	Vector3			Location;	//LLA Alt : Meter, 비헤비어트리로 입력할때는 LLA로 입력하지만 내부에서 사용할때는 Cartesian으로 사용
	
	EulerAngle		Rotation;	//Degree
	Vector3			AngleAcceleration;	//PQR
	
	float			Speed;		//m/s
	
	int				Team;		// 0 , 1
	float			Resv0;		//리눅스에서 ID로 쓰고있음
	float			Resv1;		//HP
	float			Resv2;		//유인기인지 무인기인지 판단용 0 : AI, 1 : Human

	PlaneInfo()
	{
		Location = Vector3(0, 0, 0);
		Rotation = EulerAngle(0, 0, 0);
		Speed = 0;
		Team = 0;
		Resv0 = 0;
		Resv1 = 0;
		Resv2 = 0;
	}
};

struct MissileTarget
{
public:
	int ListIndex;
	int DISID;
};

/*
그지같은 구조의 트리&블랙보드 구조를 개선해보기 위하여 만든 블랙보드 객체
비헤비어트리의 블랙보드 값을 여기에 선언-정의하고 이 블랙보드를 노드에서 호출하여 사용
모든 자세는 Degree이고 평면기준 자세를 기본으로 함

트리뿐만이 아니고 블랙보드의 변수들도 최대 2대 2까지만 상정하고 변수를 생성해둠
*/
class CPPBlackBoard
{
public:
	CPPBlackBoard();
	~CPPBlackBoard();

public:
	double RunningTime;										//해당 시뮬레이션 실행시간
	double DeltaSecond;										//비헤비어트리 작동 틱 판단 및 시간 계산용

	std::vector<PlaneInfo> Friendly;						//아군기들 정보 Array
	std::vector<PlaneInfo> Enemy;							//적기들 정보 Array

	Vector3 MyLocation_Cartesian;							//내 위치 정보 Cartesian
	Vector3 TargetLocaion_Cartesian;						//타겟 적기 위치 정보 Cartesian
	Vector3 VP_Cartesian;									//추적점 위치 정보 Cartesian

	Vector3 MyForwardVector;								//내 전방 방향 벡터
	Vector3 MyUpVector;										//내 업 방향 벡터
	Vector3 MyRightVector;									//내 오른쪽 방향 벡터

	Vector3 TargetForwardVector;							//타겟 적기 전방 방향 벡터
	Vector3 TargetUpVector;									//타겟 적기 업 방향 벡터
	Vector3 TargetRightVector;								//타겟 적기 오른쪽 방향 벡터

	EulerAngle MyRotation_EDegree;							//내 자세, 평면 기준 자세 ,Degree
	EulerAngle TargetRotation_EDegree;						//타겟 적기 자세, 평면 기준 자세, Degree

	Vector3 MyAngleAcceleration;

	float MySpeed_MS;										//내 속도, meter/sec
	float TargetSpeed_MS;									//타겟 적기 속도. meter/sec

	float Distance;											//타겟 적기와의 거리, meter
	float Throttle;											//Throttle, 0~1
	

	float Los_Degree;										//타겟에 대한 LOS값
	float Los_Degree_Target;								//타겟이 나에 대한 LOS

	float MyAngleOff_Degree;								//타겟과의 기수 교차각
	float MyAspectAngle_Degree;								//타겟에 대한 AA값

	bool EnemyInSight;
	bool EnemyInSight_Target;

	BFM_Mode BFM;											//현재 BFM (OBFM, HABFM, DBFM, DETECTING, SCISSORS, NONE)
	ACM_Mode ACM;											//현재 ACM (EF, SF)


	TeamColor Team;											//팀 컬러 (BLUE, RED, UNKNOWN)


	float AltSpeed;											//고도 변화량 (m/s, +up) -- populated by EnergyStateUpdate; was declared but never written anywhere prior to the BT tactics expansion
	float PreviousAltitudeForRate;							//AltSpeed 계산용 이전 틱 고도, 최초 틱 감지용 sentinel(-1e6)


	bool IsAimmingMode;

	// BT tactics expansion (additive) -- see the ManeuverID comment above.
	ManeuverID ActiveManeuverID;							//현재 진행 중인 다단계 기동 (BB-timestamp 패턴, RUNNING 미사용)
	double ActiveManeuverStartTime;						//ActiveManeuverID가 (재)설정된 시점의 RunningTime
	double NeutralEngagementStartTime;						//근접 중립 교전(스치어스 트리거) 지속 시작 시점, -1이면 미진행

	float OwnSpecificEnergy;								//내 비행기 비에너지: E_s = V^2/2g + h
	float TargetSpecificEnergy;							//타겟 비행기 비에너지
	float EnergyRatio;										//OwnSpecificEnergy / TargetSpecificEnergy

	// Cooldown after Task_VerticalScissors releases (time-cap or altitude-abort) before it may
	// claim again. Found necessary in local testing: without it, the same geometry that
	// triggered one activation is usually still true immediately after release, so the node
	// re-claims and repeats the climb/dive cycle back-to-back, netting a persistent descent
	// over several cycles even though no single activation runs away indefinitely anymore.
	double VerticalScissorsCooldownUntil;

	// Same cooldown pattern for Task_Evade ("The Break"). Found in a recheck of the node, not
	// caught when it was first written: unlike VerticalScissors, this one had NO unconditional
	// elapsed-time release at all -- only EnemyInSight_Target going false, or Distance growing
	// past the 5km goal, released it. EnemyInSight_Target is a ~191-degree hemisphere check with
	// no range limit (CheckSight.cpp), so it stays true through most close engagements; without a
	// cap, ClaimManeuverPhase's own stale-claim self-heal (Functions.cpp) just resets elapsed back
	// to 0 every staleAfterSeconds instead of forcing a release, so the node could hold Gate 1's
	// slot indefinitely -- short-circuiting the outer Fallback before Gate 2/4 ever get evaluated.
	double TheBreakCooldownUntil;

};