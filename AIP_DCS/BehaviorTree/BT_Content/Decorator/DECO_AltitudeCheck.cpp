#include "DECO_AltitudeCheck.h"

namespace Action
{
	// Own altitude only (MyLocation_Cartesian.Z, meters - LLAtoCartesian passes altitude
	// straight through, see Task_ClimbToSafeAltitude.cpp). Nearly every new maneuver has a
	// "X+ ft AGL" precondition from AERIAL_COMBAT_BT_GUIDE_DETAILED.md.
	PortsList DECO_AltitudeCheck::providedPorts()
	{
		return {
			InputPort<CPPBlackBoard*>("BB"),
			InputPort<std::string>("UpDown"),
			InputPort<std::string>("Altitude")
		};
	}

	NodeStatus DECO_AltitudeCheck::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");
		Optional<std::string> UpOrDown = getInput<std::string>("UpDown");
		Optional<std::string> Val = getInput<std::string>("Altitude");

		float CurrentAltitude = (*BB)->MyLocation_Cartesian.Z;
		std::string UD = UpOrDown.value();
		float InputAltitude = std::stof(Val.value());

		if (UD == "Greater")
		{
			if (CurrentAltitude >= InputAltitude)
			{
				return NodeStatus::SUCCESS;
			}
			else
				return NodeStatus::FAILURE;
		}
		else if (UD == "Less")
		{
			if (CurrentAltitude <= InputAltitude)
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
