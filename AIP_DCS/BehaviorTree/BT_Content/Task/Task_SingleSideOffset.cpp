#include "Task_SingleSideOffset.h"

namespace Action
{
	// Guide's Single Side Offset: a pre-merge approach pattern that avoids flying a straight-line
	// giveaway toward a not-yet-tracking target. 4 sub-phases via BB-timestamp (SyncActionNode
	// forbids RUNNING, same pattern as every other phased node in this tree): assess (0-1s) ->
	// lateral offset (1-3s) -> close (aim shifts to intercept as Distance drops through
	// 2000-3000m) -> release once Distance<2000m, handing off to Gate 4/Tail.
	//
	// Deliberately wired as a BARE node (no wrapping XML Sequence/DECO_DistanceCheck) even though
	// the plan's tree sketch showed one: a Range-3000-5000 XML decorator would cut this node off
	// exactly when Distance drops below 3000m mid-maneuver -- before it ever reaches its own
	// "close" phase, which needs to keep running from 3000m down to the 2000m handoff. Every other
	// phased node with a distance-based entry gate in this tree (Task_HighYoYoUp, Task_LowYoYo,
	// Task_Evade/TheBreak) checks its entry distance internally, only on a fresh (!active) claim,
	// for exactly this reason -- this node follows that same established idiom instead.
	static const float SSO_RANGE_MIN_M = 3000.0f;
	static const float SSO_RANGE_MAX_M = 5000.0f;
	static const float SSO_CLOSE_RANGE_M = 3000.0f;    // enters the "close" sub-phase once inside this
	static const float SSO_HANDOFF_RANGE_M = 2000.0f;  // releases once inside this
	static const float SSO_ATA_MAX_DEG = 30.0f;
	static const double SSO_ASSESS_PHASE_S = 1.0;
	static const double SSO_OFFSET_PHASE_S = 3.0;
	// Unconditional release cap. Found in review: unlike every other converging Gate 4 maneuver
	// (Task_HighYoYoUp/Task_LowYoYo/Task_BarrelRollAttack, each of which has its own unconditional
	// elapsed>*_TOTAL_MAX_S guard), this node's only release condition was Distance<2000m -- not
	// guaranteed against an opponent that never lets Distance close that far, and
	// ClaimManeuverPhase's stale-claim self-heal (Functions.h) resets elapsed back to 0 every
	// SSO_STALE_S rather than forcing a release, so it could cycle indefinitely and monopolize
	// this Fallback slot instead of yielding to plain Task_LeadPursuit/Task_Pure.
	static const double SSO_TOTAL_MAX_S = 15.0;
	static const double SSO_STALE_S = 20.0;
	static const double SSO_LATERAL_OFFSET_M = 2200.0;  // guide: ~30-45deg-equivalent

	PortsList Task_SingleSideOffset::providedPorts()
	{
		return {
				InputPort<CPPBlackBoard*>("BB")
		};
	}

	NodeStatus Task_SingleSideOffset::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");

		bool active = (*BB)->ActiveManeuverID == Maneuver_SingleSideOffset;

		if ((*BB)->Distance < SSO_HANDOFF_RANGE_M)
		{
			// Close enough for Gate 4/Tail's own pursuit nodes to take over.
			if (active)
			{
				BTFunc::ReleaseManeuverPhase(*BB, Maneuver_SingleSideOffset);
			}
			return NodeStatus::FAILURE;
		}

		// Entry gate only applies to a FRESH claim -- once active, Distance is expected to keep
		// shrinking as the approach works, so re-checking the full entry band every tick would
		// abort the maneuver right as it starts converging.
		if (!active
			&& ((*BB)->Distance < SSO_RANGE_MIN_M || (*BB)->Distance > SSO_RANGE_MAX_M
				|| (*BB)->EnemyInSight_Target || (*BB)->Los_Degree > SSO_ATA_MAX_DEG))
		{
			// Not the guide's "not yet tracked, mid-range approach" geometry -- fail so
			// Task_LeadPursuit (Tail, >2000m) handles it directly.
			return NodeStatus::FAILURE;
		}

		double elapsed = BTFunc::ClaimManeuverPhase(*BB, Maneuver_SingleSideOffset, SSO_STALE_S);

		if (elapsed > SSO_TOTAL_MAX_S)
		{
			// Guide's own approach-pattern duration exhausted without ever closing inside
			// SSO_HANDOFF_RANGE_M -- release unconditionally rather than holding the close-phase
			// intercept aim indefinitely against a target that isn't letting range close.
			BTFunc::ReleaseManeuverPhase(*BB, Maneuver_SingleSideOffset);
			return NodeStatus::FAILURE;
		}

		bool closePhase = elapsed >= SSO_OFFSET_PHASE_S || (*BB)->Distance <= SSO_CLOSE_RANGE_M;

		if (closePhase)
		{
			// Close: shift onto a predicted-intercept lead-pursuit point as range drops through
			// 2000-3000m, converging for Gate 4/Tail to take over below SSO_HANDOFF_RANGE_M.
			(*BB)->VP_Cartesian = (*BB)->TargetLocaion_Cartesian + BTFunc::PredictedTargetTravel(*BB);
			(*BB)->Throttle = 1.0f;
		}
		else if (elapsed < SSO_ASSESS_PHASE_S)
		{
			// Assess: hold plain pursuit aim while the phase timer starts, no offset yet.
			(*BB)->VP_Cartesian = (*BB)->TargetLocaion_Cartesian;
			(*BB)->Throttle = 0.7f;
		}
		else
		{
			// Lateral offset: bias the aim point to the side so the approach isn't a
			// straight-line giveaway (same technique Task_Notch/Task_TheBreak use).
			Vector3 offsetDir = BTFunc::ShorterTurnDirection(*BB);
			(*BB)->VP_Cartesian = (*BB)->TargetLocaion_Cartesian + offsetDir * SSO_LATERAL_OFFSET_M;
			(*BB)->Throttle = 0.8f;
		}

		return NodeStatus::SUCCESS;
	}
}
