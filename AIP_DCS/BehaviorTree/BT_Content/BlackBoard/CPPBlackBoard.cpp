#include "CPPBlackBoard.h"

CPPBlackBoard::CPPBlackBoard()
{
	RunningTime = 0;
	DeltaSecond = 0.0166666;

	MyLocation_Cartesian		= Vector3(0,0,0);
	TargetLocaion_Cartesian		= Vector3(0, 0, 0);
	VP_Cartesian				= Vector3(0, 0, 0);

	MyForwardVector = Vector3(0, 0, 0);
	MyUpVector		= Vector3(0, 0, 0);
	MyRightVector	= Vector3(0, 0, 0);

	TargetForwardVector = Vector3(0, 0, 0);
	TargetUpVector		= Vector3(0, 0, 0);
	TargetRightVector	= Vector3(0, 0, 0);

	MyRotation_EDegree		= EulerAngle(0,0,0);
	TargetRotation_EDegree	= EulerAngle(0, 0, 0);

	MySpeed_MS		= 0;
	TargetSpeed_MS	= 0;

	Distance = 0;
	Throttle = 0;


	Los_Degree = 0;
	Los_Degree_Target = 0;

	MyAngleOff_Degree = 0;
	MyAspectAngle_Degree = 0;

	BFM = NONE;
	ACM = EF;

	Team = UNKNOWN;

	AltSpeed = 0;
	PreviousAltitudeForRate = -1000000.0f;

	// Was the ONE field this constructor missed -- every other member is initialized here, so an
	// uninitialized read was live (harmless only because nothing currently reads it).
	IsAimmingMode = false;

	ActiveManeuverID = Maneuver_None;
	ActiveManeuverStartTime = 0.0;
	NeutralEngagementStartTime = -1.0;

	OwnSpecificEnergy = 0;
	TargetSpecificEnergy = 0;
	EnergyRatio = 1.0f;

	// -1 == "never cooled down", matching the two scalar fields this array replaced.
	for (int i = 0; i < Maneuver_Count; ++i)
	{
		ManeuverCooldownUntil[i] = -1.0;
	}


}

CPPBlackBoard::~CPPBlackBoard()
{
}
