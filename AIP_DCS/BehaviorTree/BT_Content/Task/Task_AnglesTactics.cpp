#include "Task_AnglesTactics.h"

namespace Action
{
	// Energy-superior branch of AERIAL_COMBAT_BT_GUIDE_DETAILED.md's Energy-State Decision
	// Algorithm (EnergyRatio>1.2, gated by Gate 3's DECO_EnergyRatioCheck in
	// Rule_forTraining.xml). Objective: press raw turning advantage while it lasts.
	static const double ANGLES_MATCH_CHECK_S = 3.0;
	static const float ANGLES_MATCHED_LOS_TARGET_DEG = 30.0f;
	static const double ANGLES_STALE_S = 20.0;
	static const float ANGLES_THROTTLE = 0.45f;

	PortsList Task_AnglesTactics::providedPorts()
	{
		return {
				InputPort<CPPBlackBoard*>("BB")
		};
	}

	NodeStatus Task_AnglesTactics::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");

		double elapsed = BTFunc::ClaimManeuverPhase(*BB, Maneuver_AnglesTactics, ANGLES_STALE_S);

		// Guide's own transition trigger: opponent matching/beating our turn rate for 3+
		// consecutive seconds -> fall through to Energy Tactics instead of continuing to press.
		// Los_Degree_Target (the enemy's own ATA to us, computed symmetrically by
		// CheckSight.cpp) staying low is a proxy for "they're still tracking us well despite
		// the aggressive turn" -- i.e. matched, not winning.
		if (elapsed > ANGLES_MATCH_CHECK_S && (*BB)->Los_Degree_Target < ANGLES_MATCHED_LOS_TARGET_DEG)
		{
			BTFunc::ReleaseManeuverPhase(*BB, Maneuver_AnglesTactics);
			return NodeStatus::FAILURE;
		}

		// Steep turn straight at the target's current position -- angles tactics is spent
		// turning advantage, not lead prediction (that's what an energy-superior aircraft can
		// afford). Reduced throttle tightens turn radius, matching Task_OneCircleFight's
		// established convention for turn-rate-focused maneuvers.
		(*BB)->VP_Cartesian = (*BB)->TargetLocaion_Cartesian;
		(*BB)->Throttle = ANGLES_THROTTLE;

		return NodeStatus::SUCCESS;
	}
}
