// Fill out your copyright notice in the Description page of Project Settings.


#include "CPPBehaviorTree.h"
#include <windows.h>

// Resolves to the directory this DLL physically lives in (DogFightEnv/Release), independent of
// the calling process's current working directory. JSBSim's own init appears to chdir() away
// from the launch directory before CreateBehaviorTree() runs, so a plain relative path or the
// caller's cwd can't be trusted here -- this is immune to that.
static std::string GetThisModuleDirectory()
{
	HMODULE hModule = nullptr;
	GetModuleHandleExA(
		GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
		reinterpret_cast<LPCSTR>(&GetThisModuleDirectory),
		&hModule);

	char path[MAX_PATH] = { 0 };
	GetModuleFileNameA(hModule, path, MAX_PATH);

	std::string full(path);
	size_t pos = full.find_last_of("\\/");
	return (pos == std::string::npos) ? std::string() : full.substr(0, pos + 1);
}


Vector3 UCPPBehaviorTree::LLAtoCartesian(Vector3 LLA, Vector3 BaseLLA)
{
	double eccentricitysquare, N, M;
	eccentricitysquare = 1.0 - pow(6356752.3142, 2) / pow(6378137.0, 2);
	N = 6378137.0 / sqrt(1.0 - eccentricitysquare * pow(sin(BaseLLA.X * PI / 180.0), 2)); // prime vertical radius of curvature
	M = 6378137.0 * (1.0 - eccentricitysquare) / pow(1 - eccentricitysquare * pow(sin(BaseLLA.X * PI / 180.0), 2), 3 / 2);

	double dlat, dlon;
	dlat = LLA.X - BaseLLA.X;
	dlon = LLA.Y - BaseLLA.Y;

	double dN, dE, dD;
	dN = (M + BaseLLA.Z) * dlat * PI / 180.0;
	dE = (N + BaseLLA.Z) * cos(BaseLLA.X * PI / 180.0) * dlon * PI / 180.0;
	dD = (LLA.Z - BaseLLA.Z);
	Vector3 res(dN, dE, dD);
	return res;
}

// Sets default values for this component's properties
UCPPBehaviorTree::UCPPBehaviorTree()
{

	f2m = 3.28084;
	EQ_R = 6.378137E+6;
	P_R = 6.3567523142E+6;
	fr = 298.257223563;
	Req = 6.378137E+6;
	d2r = 3.1415926535897931 / 180.0;
	m2f = 3.28084;


	elev0 = 0.2;
	aile0 = 0.0;
	eccen = 1.0 - P_R * P_R / (EQ_R * EQ_R);

	BB = new CPPBlackBoard();

	//std::cout << "Behavior Tree Version : 2022.07.11" << std::endl;
}


UCPPBehaviorTree::~UCPPBehaviorTree()
{
	delete BB;
}


void UCPPBehaviorTree::init()
{

	/*
	노드 입력 : 구현해둔 노드들을 Factory 객체에 입력해주는 과정
	
	새로 생성한 노드를 여기에 입력해주세요!!!!!!
	*/
	Factory.registerNodeType<Action::SelectTarget>("SelectTarget");
	Factory.registerNodeType<Action::DistanceUpdate>("DistanceUpdate");
	Factory.registerNodeType<Action::CheckSight>("CheckSight");
	Factory.registerNodeType<Action::AngleOffUpdate>("AngleOffUpdate");
	Factory.registerNodeType<Action::DirectionVectorUpdate>("DirectionVectorUpdate");
	Factory.registerNodeType<Action::AspectAngleUpdate>("AspectAngleUpdate");
	Factory.registerNodeType<Action::EnergyStateUpdate>("EnergyStateUpdate");
	Factory.registerNodeType<Action::DECO_BFMCheck>("DECO_BFMCheck");
	Factory.registerNodeType<Action::DECO_DistanceCheck>("DECO_DistanceCheck");
	Factory.registerNodeType<Action::DECO_LOSCheck>("DECO_LOSCheck");
	Factory.registerNodeType<Action::DECO_AngleOffCheck>("DECO_AngleOffCheck");
	Factory.registerNodeType<Action::DECO_AspectAngleCheck>("DECO_AspectAngleCheck");
	Factory.registerNodeType<Action::DECO_AltitudeCheck>("DECO_AltitudeCheck");
	Factory.registerNodeType<Action::DECO_SpeedCheck>("DECO_SpeedCheck");
	Factory.registerNodeType<Action::DECO_EnergyRatioCheck>("DECO_EnergyRatioCheck");
	Factory.registerNodeType<Action::DECO_ClosureRateCheck>("DECO_ClosureRateCheck");
	Factory.registerNodeType<Action::Task_Empty>("Task_Empty");
	Factory.registerNodeType<Action::Task_pure>("Task_Pure");
	Factory.registerNodeType<Action::Task_GunTrack>("Task_GunTrack");
	Factory.registerNodeType<Action::Task_LeadPursuit>("Task_LeadPursuit");
	Factory.registerNodeType<Action::Task_Evade>("Task_Evade");
	Factory.registerNodeType<Action::Task_ClimbToSafeAltitude>("Task_ClimbToSafeAltitude");
	Factory.registerNodeType<Action::Task_JinkingTurn>("Task_JinkingTurn");
	Factory.registerNodeType<Action::Task_HighYoYoUp>("Task_HighYoYoUp");
	Factory.registerNodeType<Action::Task_OneCircleFight>("Task_OneCircleFight");
	Factory.registerNodeType<Action::Task_LagPursuit>("Task_LagPursuit");
	Factory.registerNodeType<Action::Task_Notch>("Task_Notch");
	Factory.registerNodeType<Action::Task_FlatScissors>("Task_FlatScissors");
	Factory.registerNodeType<Action::Task_AnglesTactics>("Task_AnglesTactics");
	Factory.registerNodeType<Action::Task_EnergyTactics>("Task_EnergyTactics");
	Factory.registerNodeType<Action::Task_LowYoYo>("Task_LowYoYo");
	Factory.registerNodeType<Action::Task_VerticalScissors>("Task_VerticalScissors");
	Factory.registerNodeType<Action::Task_RollingScissors>("Task_RollingScissors");
	Factory.registerNodeType<Action::Task_NoseToTailTurn>("Task_NoseToTailTurn");
	Factory.registerNodeType<Action::Task_NoseToNoseTurn>("Task_NoseToNoseTurn");
	Factory.registerNodeType<Action::Task_LeadTurn>("Task_LeadTurn");
	Factory.registerNodeType<Action::Task_BarrelRollAttack>("Task_BarrelRollAttack");
	Factory.registerNodeType<Action::Task_LagDisplacementRoll>("Task_LagDisplacementRoll");
	Factory.registerNodeType<Action::Task_SingleSideOffset>("Task_SingleSideOffset");

	//파일로 트리 구조 정의
	//자신의 팀 이름으로	xml 파일 만들어서 입력해주세요!!!!!! (Rule_forTraining.xml은 예시입니다)
	// Resolved relative to this DLL's own location (see GetThisModuleDirectory above) so
	// bt_rule_manager.py's activate_rule_xml() actually controls which file this loads. Was
	// previously a hardcoded absolute path to one developer's Desktop checkout, which silently
	// ignored whatever Rule XML the Python side activated.
	//
	// createTreeFromFile() throws on a malformed/unrecognized-node XML. Caught here (rather than
	// left to cross the extern "C" DLL boundary in LibMain.cpp::CreateBehaviorTree(), which is
	// undefined behavior on Windows) so a bad Rule XML fails as a clean, loggable
	// bInitialized=false instead.
	try
	{
		tree = Factory.createTreeFromFile(GetThisModuleDirectory() + "Rule_forTraining.xml");
	}
	catch (const std::exception& e)
	{
		std::cout << "Behavior Tree Initialization Failed: " << e.what() << std::endl;
		bInitialized = false;
		return;
	}

	std::cout << "Behavior Tree Initialized" << std::endl;
	//블랙보드 연결 : 원래는 블랙보드 내에 있는 모든 변수를 하나하나 이런식으로 입력해줘야하는 미친 비효율을 보이는 방식이지만 커스텀 블랙보드를 만들어 해당 블랙보드를 입력시킴
	tree.rootBlackboard()->set<CPPBlackBoard*>("BB", BB);
	bInitialized = true;

}

StickValue UCPPBehaviorTree::Step(PlaneInfo MyInfo, int NumofOtherPlane, PlaneInfo* OthersInfo, Vector3 & VP, float & Throttle)
{
	/*LLA 좌표를 Cartesian 좌표로 변경
			
	굳이 리눅스의 기준 좌표 37, 127로 맞출 필요 없음
	*/
	Vector3 Mylocation_Cartesian = LLAtoCartesian(MyInfo.Location, Vector3(OriLAT, OriLOn, 0));
	//std::cout << "Pitch : " << MyInfo.Rotation.Pitch <<  std::endl;
	//Cartesiam 좌표계로 위치 정보를 바꾼 내 비행기 정보
	PlaneInfo Myinfo;
	Myinfo.Location = Mylocation_Cartesian;
	//Myinfo.Location = MyInfo.Location;
	Myinfo.Rotation = EulerAngle(MyInfo.Rotation.Yaw, MyInfo.Rotation.Pitch, MyInfo.Rotation.Roll);
	Myinfo.AngleAcceleration = MyInfo.AngleAcceleration;
	Myinfo.Speed = MyInfo.Speed;
	Myinfo.Team = MyInfo.Team;
	Myinfo.Resv0 = MyInfo.Resv0;		//ID
	Myinfo.Resv1 = MyInfo.Resv1;		//HP
	Myinfo.Resv2 = MyInfo.Resv2;		//OperationMode

	
	//HP가 0이하가 되면 자유 낙하하도록 설정
	if (Myinfo.Resv1 <= 0)
	{
		StickValue R;

		BB->VP_Cartesian = Vector3(BB->MyLocation_Cartesian.X, BB->MyLocation_Cartesian.Y, 0);
		R = Controller.GetStick(
			BB->MyLocation_Cartesian,
			Vector3(BB->MyRotation_EDegree.Roll*DEG2RAD,
				BB->MyRotation_EDegree.Pitch*DEG2RAD,
				BB->MyRotation_EDegree.Yaw*DEG2RAD),
			BB->VP_Cartesian);
		BB->Throttle = 0;
		R.RudderCMD = 100;

		std::cout << " HP : 0 !!!!!!!!!" << std::endl;
		return R;
	}

	//HP가 0이상일때
	else
	{
		//다른 비행기들 위치 좌표계 변환
		PlaneInfo others[4];
		for (int i = 0; i < NumofOtherPlane; i++)
		{
			// Was a raw LLA passthrough (LLAtoCartesian call commented out) while MyInfo below
			// used the properly-converted value -- meant Distance/AA/LOS mixed lat/lon degrees
			// with altitude meters for the enemy side. Restored to match MyInfo's conversion.
			Vector3 Enemylocation_Cartesian = LLAtoCartesian(OthersInfo[i].Location, Vector3(OriLAT, OriLOn, 0));
			others[i].Location = Enemylocation_Cartesian;
			others[i].Rotation = EulerAngle(OthersInfo[i].Rotation.Yaw, OthersInfo[i].Rotation.Pitch, OthersInfo[i].Rotation.Roll);
			others[i].Speed = OthersInfo[i].Speed;
			others[i].Team = OthersInfo[i].Team;
			others[i].Resv0 = OthersInfo[i].Resv0;
			others[i].Resv1 = OthersInfo[i].Resv1;
			others[i].Resv2 = OthersInfo[i].Resv2;
			
			
		}

		//블랙보드의 아군기, 적군기 List 초기화
		BB->Friendly.clear();
		BB->Enemy.clear();

		//블랙보드에 내 정보(위치, 자세, 속력, 팀) 업데이트
		// Was "= MyInfo.Location" (the raw, uncoverted LLA parameter -- note capital-I MyInfo
		// vs the lowercase-i Myinfo computed just above) instead of the properly LLA-to-
		// Cartesian-converted Mylocation_Cartesian. Meant BB->MyLocation_Cartesian silently held
		// (lat_deg, lon_deg, alt_m) instead of true local Cartesian meters, so any distance/AA/
		// LOS math built on top of it mixed degrees and meters in one Euclidean calculation.
		BB->MyLocation_Cartesian = Mylocation_Cartesian;
		BB->MyRotation_EDegree = EulerAngle(Myinfo.Rotation.Yaw, Myinfo.Rotation.Pitch, Myinfo.Rotation.Roll);
		BB->MyAngleAcceleration = Myinfo.AngleAcceleration;
		BB->MySpeed_MS = Myinfo.Speed;
		BB->Team = (TeamColor)Myinfo.Team;

		//아군기 리스트에 내 정보 추가. Friendly의 index 0번은 무조건 나 자신
		BB->Friendly.push_back(Myinfo);

		//생존중인 비행기들의 적아 구분
		for (int i = 0; i < NumofOtherPlane; i++)
		{
			if (others[i].Resv1 > 0)
			{
				if (others[i].Team == Myinfo.Team)
				{
					BB->Friendly.push_back(others[i]);
				}
				else
				{
					BB->Enemy.push_back(others[i]);
				}
			}
			else
			{

			}
		}


		// Initialized 2026-08-05: was declared uninitialized, passed by reference into RunCPPBT()
		// (which never writes it), and never read afterward -- an uninitialized read that only
		// stayed harmless by accident. Pairs with BB->IsAimmingMode, which had the same gap.
		bool AimmingMode = false;

		StickValue R;

		//블랙보드에 입력된 정보를 바탕으로 비헤비어트리 Run
		RunCPPBT(VP, Throttle, AimmingMode);


		R = Controller.GetStick(
			BB->MyLocation_Cartesian,
			Vector3(BB->MyRotation_EDegree.Roll * DEG2RAD,
				BB->MyRotation_EDegree.Pitch * DEG2RAD,
				BB->MyRotation_EDegree.Yaw * DEG2RAD),
			VP);
		
		return R;
	}
}

Vector3 UCPPBehaviorTree::GetVP()
{
	Vector3 Vp = (*BB).VP_Cartesian;
	return Vp;
}



 void UCPPBehaviorTree::RunCPPBT(Vector3& VP, float& Throttle, bool& AimmingMode)
{

	BB->RunningTime += BB->DeltaSecond;	//시뮬레이선 타임에 따른 델타 타임 설정
	tree.tickRoot(); //트리 작동

	VP = BB->VP_Cartesian;	// VP 값

	// Was hardcoded to 1.0f unconditionally (see CPPBlackBoard.h's Throttle field, which
	// existed but nothing wrote to it). Task nodes now set BB->Throttle each tick; every
	// current Fallback branch (Evade/LeadPursuit/Pure) does so, so this is always fresh.
	Throttle = BB->Throttle;
}

 void UCPPBehaviorTree::SetDeltaTime(double DT)
 {
	 BB->DeltaSecond = DT;
 }

