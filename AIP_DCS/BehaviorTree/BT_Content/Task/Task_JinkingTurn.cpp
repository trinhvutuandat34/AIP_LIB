#include "Task_JinkingTurn.h"
#include <cmath>

namespace Action
{
	// Jinking is for when a break-away (Task_Evade) can't outrun the shot -- close range,
	// still threatened. DECO_DistanceCheck elsewhere in the tree already uses 2000m as the
	// close/far boundary; reused here for consistency.
	static const float JINK_RANGE_TRIGGER_M = 2000.0f;
	// Full lateral oscillation period. A few seconds is fast enough to spoil a tracking
	// solution without exceeding realistic roll/turn-rate limits.
	static const float JINK_PERIOD_S = 4.0f;
	static const float JINK_LATERAL_OFFSET_M = 600.0f;
	static const float TWO_PI = 6.28318530718f;

	PortsList Task_JinkingTurn::providedPorts()
	{
		return {
				InputPort<CPPBlackBoard*>("BB")
		};
	}

	NodeStatus Task_JinkingTurn::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");

		if (!(*BB)->EnemyInSight_Target || (*BB)->Distance > JINK_RANGE_TRIGGER_M)
		{
			// Not threatened, or threatened but still far enough out that a plain break-away
			// (Task_Evade) can work -- fail so the parent Fallback moves on.
			return NodeStatus::FAILURE;
		}

		// Same "extend away from the threat" baseline as Task_Evade, with a lateral
		// oscillation layered on top (MyRightVector * sin(time)) so the flight path isn't a
		// straight, predictable line -- the actual "jink". RunningTime is a free-running match
		// clock (CPPBehaviorTree.cpp), so this naturally cycles for as long as the threat lasts.
		Vector3 awayFromTarget = (*BB)->MyLocation_Cartesian - (*BB)->TargetLocaion_Cartesian;
		float phase = sinf((*BB)->RunningTime * (TWO_PI / JINK_PERIOD_S));
		Vector3 lateralOffset = (*BB)->MyRightVector * (phase * JINK_LATERAL_OFFSET_M);

		(*BB)->VP_Cartesian = (*BB)->MyLocation_Cartesian + awayFromTarget + lateralOffset;
		(*BB)->Throttle = 1.0f;

		return NodeStatus::SUCCESS;
	}
}
