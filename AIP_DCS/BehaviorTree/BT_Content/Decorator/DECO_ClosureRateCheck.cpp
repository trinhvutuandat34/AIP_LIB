#include "DECO_ClosureRateCheck.h"

namespace Action
{
	// Factors out the closure convention Task_HighYoYoUp already established (MySpeed_MS -
	// TargetSpeed_MS, a velocity differential in m/s) into a reusable decorator instead of
	// repeating the one-liner in each new maneuver that needs it.
	PortsList DECO_ClosureRateCheck::providedPorts()
	{
		return {
			InputPort<CPPBlackBoard*>("BB"),
			InputPort<std::string>("UpDown"),
			InputPort<std::string>("Closure")
		};
	}

	NodeStatus DECO_ClosureRateCheck::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");
		Optional<std::string> UpOrDown = getInput<std::string>("UpDown");
		Optional<std::string> Val = getInput<std::string>("Closure");

		float CurrentClosure = (*BB)->MySpeed_MS - (*BB)->TargetSpeed_MS;
		std::string UD = UpOrDown.value();
		float InputClosure = std::stof(Val.value());

		if (UD == "Greater")
		{
			if (CurrentClosure >= InputClosure)
			{
				return NodeStatus::SUCCESS;
			}
			else
				return NodeStatus::FAILURE;
		}
		else if (UD == "Less")
		{
			if (CurrentClosure <= InputClosure)
			{
				return NodeStatus::SUCCESS;
			}
			else
				return NodeStatus::FAILURE;
		}
		else
		{
			return NodeStatus::FAILURE;
		}
	}
}
