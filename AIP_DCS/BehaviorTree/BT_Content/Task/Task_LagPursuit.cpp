#include "Task_LagPursuit.h"

namespace Action
{
	static const float LAG_RANGE_TRIGGER_M = 2000.0f;
	// Los_Degree (true ATA) already small -- already tracking the target well. Mirrors
	// Task_OneCircleFight's trigger from the other side: that one fires when ATA is bad and a
	// turn is needed, this one fires when ATA is already good and overshoot is the real risk.
	static const float LAG_ATA_TRIGGER_DEG = 20.0f;
	static const float LAG_THROTTLE = 0.6f;

	PortsList Task_LagPursuit::providedPorts()
	{
		return {
				InputPort<CPPBlackBoard*>("BB")
		};
	}

	NodeStatus Task_LagPursuit::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");

		if ((*BB)->Distance > LAG_RANGE_TRIGGER_M || (*BB)->Los_Degree > LAG_ATA_TRIGGER_DEG)
		{
			// Too far, or ATA not good enough yet for lag pursuit to make sense -- fail so the
			// parent Fallback moves on to Task_OneCircleFight/Task_Pure.
			return NodeStatus::FAILURE;
		}

		// Mirror of Task_LeadPursuit, subtracting the predicted-motion offset instead of adding
		// it -- aim BEHIND the target's predicted point instead of ahead of it. Trades tracking
		// precision for closure control: already well-aligned, so the risk now is closing too
		// fast and blowing through the target rather than needing to cut a corner.
		(*BB)->VP_Cartesian = (*BB)->TargetLocaion_Cartesian - BTFunc::PredictedTargetTravel(*BB);
		(*BB)->Throttle = LAG_THROTTLE;

		return NodeStatus::SUCCESS;
	}
}
