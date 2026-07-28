#include "Task_OneCircleFight.h"

namespace Action
{
	// Same close-range boundary DECO_DistanceCheck uses elsewhere in the tree.
	static const float OCF_RANGE_TRIGGER_M = 2000.0f;
	// Los_Degree (CheckSight.cpp) is true ATA - angle between my own nose and the LOS to the
	// target. Genuinely off-boresight at close range means the merge has happened and this is
	// now a turning fight, not a clean pursuit setup.
	static const float OCF_ATA_TRIGGER_DEG = 45.0f;
	// Below Task_Pure's 0.7 -- turn radius shrinks with speed, and winning a one-circle fight
	// is entirely about out-turning the opponent, not closing distance.
	static const float OCF_THROTTLE = 0.5f;

	PortsList Task_OneCircleFight::providedPorts()
	{
		return {
				InputPort<CPPBlackBoard*>("BB")
		};
	}

	NodeStatus Task_OneCircleFight::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");

		if ((*BB)->Distance > OCF_RANGE_TRIGGER_M || (*BB)->Los_Degree < OCF_ATA_TRIGGER_DEG)
		{
			// Too far to be a merged turning fight, or already tracking well enough that
			// Task_LagPursuit/Task_Pure are the better choice -- fail so the parent Fallback
			// moves on.
			return NodeStatus::FAILURE;
		}

		// Aim at the target's CURRENT position, not a lead point -- over-leading in a tight
		// turn is exactly what causes an overshoot past the target (the same risk
		// Task_LeadPursuit's own comment flags at long range, just sharper up close). Cutting
		// the turn radius via reduced throttle, not via a smarter aim point, is the actual
		// one-circle-fight mechanism.
		(*BB)->VP_Cartesian = (*BB)->TargetLocaion_Cartesian;
		(*BB)->Throttle = OCF_THROTTLE;

		return NodeStatus::SUCCESS;
	}
}
