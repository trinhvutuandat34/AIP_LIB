#include "Task_pure.h"

PortsList Action::Task_pure::providedPorts()
{
	return {
			InputPort<CPPBlackBoard*>("BB")
	};
}

NodeStatus Action::Task_pure::tick()
{
	Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");

	// Pure pursuit: aim directly at the target's current position (SelectTarget keeps
	// TargetLocaion_Cartesian up to date every tick) instead of a fixed point ahead of our
	// own nose. Controller_CY's existing GetStick() steers toward whatever VP_Cartesian is.
	(*BB)->VP_Cartesian = (*BB)->TargetLocaion_Cartesian;

	// This branch only runs at close range (<2000m, see Rule_forTraining.xml). Throttle back
	// from full burner to reduce overshoot risk on the tighter turns this range calls for.
	(*BB)->Throttle = 0.7f;

	return NodeStatus::SUCCESS;
}
