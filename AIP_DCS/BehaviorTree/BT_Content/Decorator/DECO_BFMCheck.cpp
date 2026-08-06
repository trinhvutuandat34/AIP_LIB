// DELIBERATELY INERT -- do not wire this into a Rule XML expecting it to work.
//
// This node gates on BB->BFM, but nothing anywhere assigns BB->BFM away from its constructor
// default of NONE: no situational BFM classifier exists, and per COMPETITION_PLAN.md's standing
// decision none is planned -- maneuvers get concrete per-node Decorator guards (distance / LOS /
// aspect / energy-ratio) instead of a classifier layer, because a classifier would be a second
// source of truth able to disagree with the per-node gates it sits above. It therefore has no
// caller in Rule_forTraining.xml and is registered only so the tree still parses if one is added.
//
// Consequence, with the 2026-08-05 fix below in place: EVERY CheckBFM value now returns FAILURE
// (correct spellings mismatch the permanent NONE; unrecognized ones hit the BFM_Unknown sentinel).
// That is the intended, safe behavior for a node whose input is never populated. To actually
// revive this you must first write a classifier that sets BB->BFM each tick -- probably a Service
// alongside EnergyStateUpdate -- and revisit the standing decision above.
#include "DECO_BFMCheck.h"

namespace Action
{
	PortsList DECO_BFMCheck::providedPorts()
	{
		return {
			InputPort<CPPBlackBoard*>("BB"),
			InputPort<std::string>("CheckBFM")
		};
	}

	NodeStatus DECO_BFMCheck::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");
		Optional<std::string> CheckBFM = getInput<std::string>("CheckBFM");

		BFM_Mode CurrentBFM = (*BB)->BFM;
		BFM_Mode InputBFM;

		std::string str = CheckBFM.value();
		if(str == "OBFM")
		{
			InputBFM = OBFM;
		}
		else if (str == "DBFM")
		{
			InputBFM = DBFM;
		}
		else if (str == "HABFM")
		{
			InputBFM = HABFM;
		}
		else if (str == "SCISSORS")
		{
			InputBFM = SCISSORS;
		}
		else if (str == "DETECTING")
		{
			InputBFM = DETECTING;
		}
		else
		{
			//CheckBFM 입력 문자열이 오타난건 아닌지 확인 필요!!!! OBFM,DBFM, HABFM, SCISSORS, DETECTING 가 아님
			// Fails CLOSED. This was `NONE` until 2026-08-05, which was the exact value BB->BFM
			// permanently holds -- so a typo'd CheckBFM MATCHED and returned SUCCESS, while a
			// correctly-spelled one returned FAILURE. See BFM_Unknown in CPPBlackBoard.h.
			InputBFM = BFM_Unknown;
		}

		if (CurrentBFM == InputBFM)
		{
			return NodeStatus::SUCCESS;
		}
		else
			return NodeStatus::FAILURE;
	}

}