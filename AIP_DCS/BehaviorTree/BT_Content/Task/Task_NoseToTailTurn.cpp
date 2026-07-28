#include "Task_NoseToTailTurn.h"

namespace Action
{
	// Gate 4 offensive sibling: already 20-45deg off the target's six at a matched-turn range
	// (AA convention verified against AspectAngleUpdate.cpp: 180=dead six, so "20-45deg off six"
	// = AA in [135,160]) -- bank-match rather than aim straight at a point, to hold position
	// instead of overshooting past the target.
	static const float NTT_AA_MIN_DEG = 135.0f;
	static const float NTT_AA_MAX_DEG = 160.0f;
	static const float NTT_RANGE_MIN_M = 1000.0f;
	static const float NTT_RANGE_MAX_M = 4000.0f;
	static const float NTT_SPEED_ADVANTAGE_MS = 13.0f;  // guide: +25-50kt, using the low end

	PortsList Task_NoseToTailTurn::providedPorts()
	{
		return {
				InputPort<CPPBlackBoard*>("BB")
		};
	}

	NodeStatus Task_NoseToTailTurn::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");

		float aa = (*BB)->MyAspectAngle_Degree;
		if (aa < NTT_AA_MIN_DEG || aa > NTT_AA_MAX_DEG
			|| (*BB)->Distance < NTT_RANGE_MIN_M || (*BB)->Distance > NTT_RANGE_MAX_M)
		{
			// Not "already 20-45deg off the target's six" at a matched-turn range -- fail so
			// the parent Fallback moves on to Task_OneCircleFight/Task_LagPursuit.
			return NodeStatus::FAILURE;
		}

		// Bank-match the target's own roll direction (hold position in the turn rather than
		// aiming straight at a point), converging toward the guide's 1000-2000m separation band,
		// with a speed-advantage throttle bias so the turn doesn't bleed down to parity.
		Vector3 towardTarget = (*BB)->TargetLocaion_Cartesian - (*BB)->MyLocation_Cartesian;
		double bankSide = ((*BB)->TargetRotation_EDegree.Roll > 0.0) ? 800.0 : -800.0;
		Vector3 bankMatchOffset = (*BB)->TargetRightVector * bankSide;
		(*BB)->VP_Cartesian = (*BB)->MyLocation_Cartesian + towardTarget + bankMatchOffset;
		(*BB)->Throttle = ((*BB)->MySpeed_MS < (*BB)->TargetSpeed_MS + NTT_SPEED_ADVANTAGE_MS) ? 0.9f : 0.6f;

		return NodeStatus::SUCCESS;
	}
}
