#include "DECO_AspectAngleCheck.h"

namespace Action
{
	// Checks MyAspectAngle_Degree (180=ownship at target's dead six, 0=ownship at target's
	// nose - verified against AspectAngleUpdate.cpp's vector math). "Range" checks (e.g.
	// 30-90) are done by chaining two instances (Greater X, Less Y) in an XML Sequence, same
	// as every other DECO_*Check in this tree - no separate Range port.
	PortsList DECO_AspectAngleCheck::providedPorts()
	{
		return {
			InputPort<CPPBlackBoard*>("BB"),
			InputPort<std::string>("UpDown"),
			InputPort<std::string>("AA")
		};
	}

	NodeStatus DECO_AspectAngleCheck::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");
		Optional<std::string> UpOrDown = getInput<std::string>("UpDown");
		Optional<std::string> Val = getInput<std::string>("AA");

		float CurrentAA = (*BB)->MyAspectAngle_Degree;
		std::string UD = UpOrDown.value();
		float InputAA = std::stof(Val.value());

		if (UD == "Greater")
		{
			if (CurrentAA >= InputAA)
			{
				return NodeStatus::SUCCESS;
			}
			else
				return NodeStatus::FAILURE;
		}
		else if (UD == "Less")
		{
			if (CurrentAA <= InputAA)
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
