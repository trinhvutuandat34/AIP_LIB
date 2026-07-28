#include "DECO_EnergyRatioCheck.h"

namespace Action
{
	// BB->EnergyRatio (own specific energy / target specific energy), written every tick by
	// the EnergyStateUpdate service. Gate 3's energy-ratio guard: >1.2 -> Angles Tactics,
	// <0.8 -> Energy Tactics (AERIAL_COMBAT_BT_GUIDE_DETAILED.md's Energy-State Decision
	// Algorithm), scoped narrowly in front of the offensive branches only.
	PortsList DECO_EnergyRatioCheck::providedPorts()
	{
		return {
			InputPort<CPPBlackBoard*>("BB"),
			InputPort<std::string>("UpDown"),
			InputPort<std::string>("Ratio")
		};
	}

	NodeStatus DECO_EnergyRatioCheck::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");
		Optional<std::string> UpOrDown = getInput<std::string>("UpDown");
		Optional<std::string> Val = getInput<std::string>("Ratio");

		float CurrentRatio = (*BB)->EnergyRatio;
		std::string UD = UpOrDown.value();
		float InputRatio = std::stof(Val.value());

		if (UD == "Greater")
		{
			if (CurrentRatio >= InputRatio)
			{
				return NodeStatus::SUCCESS;
			}
			else
				return NodeStatus::FAILURE;
		}
		else if (UD == "Less")
		{
			if (CurrentRatio <= InputRatio)
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
