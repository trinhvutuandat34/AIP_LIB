#include "Functions.h"

namespace BTFunc
{
	void AddNodeExcute(std::string * out, std::string input)
	{
		out->append(input);
		out->append("\n");
	}
	void SaveTextData(std::string * tempString, std::string * BT_Text)
	{
		if (tempString != nullptr && BT_Text != nullptr)
		{
			if (tempString->length() > 910)
				tempString->clear();

			BT_Text->clear();

			BT_Text->append((*tempString));
			tempString->clear();
		}
	}

	double ClaimManeuverPhase(CPPBlackBoard* BB, ManeuverID id, double staleAfterSeconds)
	{
		if (BB->ActiveManeuverID != id)
		{
			BB->ActiveManeuverID = id;
			BB->ActiveManeuverStartTime = BB->RunningTime;
			return 0.0;
		}

		double elapsed = BB->RunningTime - BB->ActiveManeuverStartTime;
		if (elapsed > staleAfterSeconds)
		{
			BB->ActiveManeuverStartTime = BB->RunningTime;
			return 0.0;
		}

		return elapsed;
	}

	void ReleaseManeuverPhase(CPPBlackBoard* BB, ManeuverID id)
	{
		if (BB->ActiveManeuverID == id)
		{
			BB->ActiveManeuverID = Maneuver_None;
		}
	}

	void ReleaseManeuverPhaseWithCooldown(CPPBlackBoard* BB, ManeuverID id, double cooldownSeconds)
	{
		ReleaseManeuverPhase(BB, id);
		if (id > Maneuver_None && id < Maneuver_Count)
		{
			BB->ManeuverCooldownUntil[id] = BB->RunningTime + cooldownSeconds;
		}
	}

	bool IsManeuverOnCooldown(CPPBlackBoard* BB, ManeuverID id)
	{
		if (id <= Maneuver_None || id >= Maneuver_Count)
		{
			return false;
		}
		return BB->RunningTime < BB->ManeuverCooldownUntil[id];
	}

	Vector3 PredictedTargetTravel(CPPBlackBoard* BB)
	{
		float leadTime = 0.0f;
		if (BB->MySpeed_MS > 1.0f)
		{
			leadTime = BB->Distance / BB->MySpeed_MS;
		}
		if (leadTime > 4.0f)
		{
			leadTime = 4.0f;
		}
		return BB->TargetForwardVector * BB->TargetSpeed_MS * leadTime;
	}

	Vector3 ShorterTurnDirection(CPPBlackBoard* BB)
	{
		Vector3 toTarget = BB->TargetLocaion_Cartesian - BB->MyLocation_Cartesian;
		Vector3 dir = BB->MyUpVector.cross(toTarget);
		if (dir.dot(BB->MyRightVector) < 0.0)
		{
			dir = -dir;
		}
		dir.normalize();
		return dir;
	}

}