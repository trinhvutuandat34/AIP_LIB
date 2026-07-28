#include "Task_EnergyTactics.h"

namespace Action
{
	// Energy-inferior branch of AERIAL_COMBAT_BT_GUIDE_DETAILED.md's Energy-State Decision
	// Algorithm (EnergyRatio<0.8, gated by Gate 3's DECO_EnergyRatioCheck). Also folds in the
	// guide's Pump maneuver, which is functionally the same "hold, turn away, reassess at
	// T+10s" behavior under a different name.
	static const double ENERGY_REASSESS_S = 10.0;
	// Late-match: a marginal shot not taken now may never happen again (COMPETITION_RULES.md's
	// WEZ phases only get easier as t->200s) -- bias toward re-engaging instead of extending.
	static const double ENERGY_LATE_MATCH_S = 180.0;
	static const float ENERGY_CONTINUE_DISTANCE_M = 3000.0f;
	// Guide: "never drop below 300kt (154 m/s) in a turning fight."
	static const float ENERGY_SPEED_FLOOR_MS = 154.0f;
	static const double ENERGY_STALE_S = 20.0;
	static const double ENERGY_LATERAL_OFFSET_M = 400.0;
	static const float ENERGY_THROTTLE = 0.3f;

	PortsList Task_EnergyTactics::providedPorts()
	{
		return {
				InputPort<CPPBlackBoard*>("BB")
		};
	}

	NodeStatus Task_EnergyTactics::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");

		double elapsed = BTFunc::ClaimManeuverPhase(*BB, Maneuver_EnergyTactics, ENERGY_STALE_S);
		bool lateMatch = (*BB)->RunningTime > ENERGY_LATE_MATCH_S;

		if (elapsed > ENERGY_REASSESS_S || lateMatch)
		{
			if ((*BB)->Distance > ENERGY_CONTINUE_DISTANCE_M && !lateMatch)
			{
				// Still far and clear -- keep the evasion going, restart the reassess window.
				(*BB)->ActiveManeuverStartTime = (*BB)->RunningTime;
			}
			else
			{
				// Close again, or late in the match -- release back to the offensive branches
				// instead of continuing to extend.
				BTFunc::ReleaseManeuverPhase(*BB, Maneuver_EnergyTactics);
				return NodeStatus::FAILURE;
			}
		}

		// Gentle turn away from the target -- preserve energy rather than out-turn a
		// superior-energy opponent.
		Vector3 awayFromTarget = (*BB)->MyLocation_Cartesian - (*BB)->TargetLocaion_Cartesian;
		Vector3 lateral = (*BB)->MyRightVector * ENERGY_LATERAL_OFFSET_M;
		(*BB)->VP_Cartesian = (*BB)->MyLocation_Cartesian + awayFromTarget + lateral;

		if ((*BB)->MySpeed_MS < ENERGY_SPEED_FLOOR_MS)
		{
			// Clamp throttle up to protect the speed floor even mid-evasion.
			(*BB)->Throttle = 1.0f;
		}
		else
		{
			(*BB)->Throttle = ENERGY_THROTTLE;
		}

		return NodeStatus::SUCCESS;
	}
}
