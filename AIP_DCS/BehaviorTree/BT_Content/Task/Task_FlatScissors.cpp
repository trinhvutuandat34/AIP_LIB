#include "Task_FlatScissors.h"

namespace Action
{
	// The direct stalemate-breaker: AERIAL_COMBAT_BT_GUIDE_DETAILED.md's dedicated maneuver
	// for a neutral nose-to-nose/nose-to-tail fight that hasn't resolved -- exactly the
	// documented BT-vs-BT self-test outcome (both survive, no kill).
	static const double SCISSORS_NEUTRAL_MIN_S = 3.0;
	static const float SCISSORS_ALTITUDE_ABORT_M = 457.0f;
	static const double SCISSORS_BURST_S = 2.5;
	static const double SCISSORS_STALE_S = 20.0;
	static const double SCISSORS_LATERAL_OFFSET_M = 2500.0;
	static const double SCISSORS_FORWARD_OFFSET_M = 1000.0;

	PortsList Task_FlatScissors::providedPorts()
	{
		return {
				InputPort<CPPBlackBoard*>("BB")
		};
	}

	NodeStatus Task_FlatScissors::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");

		// Gate 2's shared Sequence (Rule_forTraining.xml) already confirmed close range and
		// mutual off-boresight (Distance<2000m, Los_Degree/Los_Degree_Target>45) before this
		// node is ever ticked -- see Task_pure/Task_LeadPursuit for the established convention
		// of trusting an XML-level Decorator gate instead of re-checking it here.
		if ((*BB)->NeutralEngagementStartTime < 0.0)
		{
			return NodeStatus::FAILURE;
		}
		double neutralElapsed = (*BB)->RunningTime - (*BB)->NeutralEngagementStartTime;
		if (neutralElapsed < SCISSORS_NEUTRAL_MIN_S)
		{
			// Just merged -- give Task_OneCircleFight (Gate 4) a moment before escalating to a
			// scissors. Fail so the parent Fallback moves on.
			return NodeStatus::FAILURE;
		}

		float altitude = (*BB)->MyLocation_Cartesian.Z;
		if (altitude < SCISSORS_ALTITUDE_ABORT_M)
		{
			// Unconditional abort regardless of phase -- fail so the Fallback rescans from
			// Task_ClimbToSafeAltitude next tick.
			BTFunc::ReleaseManeuverPhase(*BB, Maneuver_FlatScissors);
			return NodeStatus::FAILURE;
		}

		double elapsed = BTFunc::ClaimManeuverPhase(*BB, Maneuver_FlatScissors, SCISSORS_STALE_S);

		// Reverse cut direction every ~2.5s burst (guide: 2-3s bursts, ~10-15s cycle) -- denies
		// the opponent a predictable, repeating turn circle to settle into.
		long burstIndex = (long)(elapsed / SCISSORS_BURST_S);
		double sign = (burstIndex % 2 == 0) ? 1.0 : -1.0;

		Vector3 lateral = (*BB)->MyRightVector * (sign * SCISSORS_LATERAL_OFFSET_M);
		(*BB)->VP_Cartesian = (*BB)->MyLocation_Cartesian + (*BB)->MyForwardVector * SCISSORS_FORWARD_OFFSET_M + lateral;
		(*BB)->Throttle = 0.4f;

		return NodeStatus::SUCCESS;
	}
}
