#include "Task_NoseToNoseTurn.h"

namespace Action
{
	// Primary handler for the head-on merge (Gate 2's merge-check Sequence in
	// Rule_forTraining.xml already confirmed HCA>150, both ATA<20, Distance 500-10000m) --
	// NOTE: that floor was 3000m when this comment was first written; lowered to 500m on
	// 2026-07-16 because 3000m excluded the entire real Prelims starting range (2000-3000ft =
	// ~610-914m), so this node could only ever fire for the rare Finals tie-break. Comment
	// corrected 2026-08-05; check Rule_forTraining.xml, not this line, for the live values --
	// this is also the Finals tie-break scenario (10,000+ft, face-to-face restart) and what the
	// curriculum's two_circle_headon_a000..a180 alpha-sweep trains against.
	static const double NTN_PHASE1_S = 1.5;
	static const double NTN_PHASE3_MAX_S = 7.0;   // guide: 5-7s total duration
	static const float NTN_VERTICAL_ALT_MIN_M = 1524.0f;
	static const float NTN_VERTICAL_SPEED_MIN_MS = 115.0f;
	static const double NTN_STALE_S = 20.0;

	PortsList Task_NoseToNoseTurn::providedPorts()
	{
		return {
				InputPort<CPPBlackBoard*>("BB")
		};
	}

	NodeStatus Task_NoseToNoseTurn::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");

		double elapsed = BTFunc::ClaimManeuverPhase(*BB, Maneuver_NoseToNoseTurn, NTN_STALE_S);

		if (elapsed > NTN_PHASE3_MAX_S)
		{
			// Guide's own duration exhausted -- release so the Fallback reassesses (typically
			// into the offensive branches once the merge has resolved into a close-range fight).
			BTFunc::ReleaseManeuverPhase(*BB, Maneuver_NoseToNoseTurn);
			return NodeStatus::FAILURE;
		}

		// Turn intensity ramps from ~60deg-equivalent (phase1) to ~85-90deg-equivalent
		// (phase2-3), biased toward whichever side is the shorter turn from current heading --
		// same technique as Task_Notch/Task_TheBreak.
		double lateralMagnitude = (elapsed < NTN_PHASE1_S) ? 1500.0 : 2800.0;

		Vector3 turnDir = BTFunc::ShorterTurnDirection(*BB);
		Vector3 turnPoint = (*BB)->MyLocation_Cartesian + turnDir * lateralMagnitude;

		// Vertical variant: enough altitude buffer and speed on both sides to trade some of the
		// turn into the vertical plane instead of pure-lateral.
		bool verticalVariant = (*BB)->MyLocation_Cartesian.Z > NTN_VERTICAL_ALT_MIN_M
			&& (*BB)->MySpeed_MS > NTN_VERTICAL_SPEED_MIN_MS
			&& (*BB)->TargetSpeed_MS > NTN_VERTICAL_SPEED_MIN_MS;
		if (verticalVariant)
		{
			turnPoint = turnPoint + (*BB)->MyUpVector * 1200.0;
		}

		(*BB)->VP_Cartesian = turnPoint;
		(*BB)->Throttle = 1.0f;

		return NodeStatus::SUCCESS;
	}
}
