#include "Task_LeadPursuit.h"

namespace Action
{
	PortsList Task_LeadPursuit::providedPorts()
	{
		return {
				InputPort<CPPBlackBoard*>("BB")
		};
	}

	NodeStatus Task_LeadPursuit::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");

		// Lead pursuit: aim at the target's PREDICTED position (current position + its own
		// velocity times an estimated closing time) instead of where it is right now. Pure
		// pursuit (Task_pure) always lags behind a moving target and produces a tail-chase
		// curve that two equally-matched aircraft never close out of. Leading the target lets
		// this aircraft cut the corner instead of just following it.
		(*BB)->VP_Cartesian = (*BB)->TargetLocaion_Cartesian + BTFunc::PredictedTargetTravel(*BB);

		// This branch only runs beyond 2000m (see Rule_forTraining.xml) -- full burner to
		// close the distance as fast as possible.
		(*BB)->Throttle = 1.0f;

		return NodeStatus::SUCCESS;
	}
}
