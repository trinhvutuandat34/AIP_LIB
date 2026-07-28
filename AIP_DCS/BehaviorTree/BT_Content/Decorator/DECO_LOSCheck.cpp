#include "DECO_LOSCheck.h"

namespace Action
{
	PortsList DECO_LOSCheck::providedPorts()
	{
		return {
			InputPort<CPPBlackBoard*>("BB"),
			InputPort<std::string>("UpDown"),
			InputPort<std::string>("InputLOS"),
			// "Own" (default, Los_Degree - my ATA to the target) or "Target" (Los_Degree_Target -
			// the target's own ATA to me). Needed for Gate 2's symmetric merge/neutral-fight checks.
			InputPort<std::string>("Which")
		};
	}

	NodeStatus DECO_LOSCheck::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");
		Optional<std::string> UpOrDown = getInput<std::string>("UpDown");
		Optional<std::string> Dist = getInput<std::string>("InputLOS");
		Optional<std::string> Which = getInput<std::string>("Which");

		std::string WhichLOS = Which.value();
		float CurrentLOS = (WhichLOS == "Target") ? (*BB)->Los_Degree_Target : (*BB)->Los_Degree;
		std::string UD = UpOrDown.value();
		float InputLOS = std::stof(Dist.value());

		if (UD == "Greater")
		{
			if (CurrentLOS >= InputLOS)
			{

				return NodeStatus::SUCCESS;
			}
			else
			{
				return NodeStatus::FAILURE;
			}
		}
		else if (UD == "Less")
		{
			if (CurrentLOS <= InputLOS)
			{

				return NodeStatus::SUCCESS;
			}
			else
				return NodeStatus::FAILURE;
		}
		else
		{
			//UpDown 입력 문자열이 오타난건 아닌지 확인 필요!!!! Greater 나 Less 가 아님
			return NodeStatus::FAILURE;
		}
	}
}