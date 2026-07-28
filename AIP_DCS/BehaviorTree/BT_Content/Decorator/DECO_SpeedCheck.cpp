#include "DECO_SpeedCheck.h"

namespace Action
{
	// MySpeed_MS / TargetSpeed_MS (m/s). "Which" defaults to "Own" if omitted from the XML tag.
	PortsList DECO_SpeedCheck::providedPorts()
	{
		return {
			InputPort<CPPBlackBoard*>("BB"),
			InputPort<std::string>("UpDown"),
			InputPort<std::string>("Speed"),
			InputPort<std::string>("Which")
		};
	}

	NodeStatus DECO_SpeedCheck::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");
		Optional<std::string> UpOrDown = getInput<std::string>("UpDown");
		Optional<std::string> Val = getInput<std::string>("Speed");
		Optional<std::string> Which = getInput<std::string>("Which");

		std::string WhichSpeed = Which ? Which.value() : "Own";
		float CurrentSpeed = (WhichSpeed == "Target") ? (*BB)->TargetSpeed_MS : (*BB)->MySpeed_MS;
		std::string UD = UpOrDown.value();
		float InputSpeed = std::stof(Val.value());

		if (UD == "Greater")
		{
			if (CurrentSpeed >= InputSpeed)
			{
				return NodeStatus::SUCCESS;
			}
			else
				return NodeStatus::FAILURE;
		}
		else if (UD == "Less")
		{
			if (CurrentSpeed <= InputSpeed)
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
