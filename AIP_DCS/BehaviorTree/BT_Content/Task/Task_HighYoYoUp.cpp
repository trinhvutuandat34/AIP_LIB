#include "Task_HighYoYoUp.h"

namespace Action
{
	// Same close/far boundary DECO_DistanceCheck uses elsewhere in the tree.
	static const float YOYO_RANGE_TRIGGER_M = 2000.0f;
	// Excess closure (own speed over target speed) that signals real overshoot risk.
	static const float YOYO_CLOSURE_TRIGGER_MS = 40.0f;
	// Guide's own abort conditions: altitude/speed margin required to safely pull up.
	static const float YOYO_ABORT_ALTITUDE_M = 1524.0f;   // 5000ft
	static const float YOYO_ABORT_SPEED_MS = 154.0f;      // 300kt
	static const double YOYO_CLIMB_PHASE_S = 6.0;         // guide: 4-8s climb/decel
	static const double YOYO_TOTAL_MAX_S = 10.0;          // guide: 6-8s total, +margin, then release
	static const double YOYO_STALE_S = 20.0;
	static const float YOYO_POSITION_BEHIND_M = 900.0f;   // guide: 2-3km behind, scaled to close range
	static const float YOYO_POSITION_BELOW_M = 230.0f;    // guide: 500-1000ft below

	PortsList Task_HighYoYoUp::providedPorts()
	{
		return {
				InputPort<CPPBlackBoard*>("BB")
		};
	}

	NodeStatus Task_HighYoYoUp::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");

		float closureRate = (*BB)->MySpeed_MS - (*BB)->TargetSpeed_MS;
		// Entry gate only applies to a FRESH claim -- the climb itself bleeds closure (and
		// distance may shift), so re-checking it every tick once active would abort the pull-up
		// partway through. The abort conditions below (altitude/speed floor) are what actually
		// terminates it early if needed.
		bool active = (*BB)->ActiveManeuverID == Maneuver_HighYoYo;
		if (!active && ((*BB)->Distance > YOYO_RANGE_TRIGGER_M || closureRate < YOYO_CLOSURE_TRIGGER_MS))
		{
			// Not closing fast enough to risk an overshoot right now -- fail so the parent
			// Fallback moves on to plain Task_LeadPursuit/Task_Pure.
			return NodeStatus::FAILURE;
		}

		float altitude = (*BB)->MyLocation_Cartesian.Z;
		if (altitude < YOYO_ABORT_ALTITUDE_M || (*BB)->MySpeed_MS < YOYO_ABORT_SPEED_MS)
		{
			BTFunc::ReleaseManeuverPhase(*BB, Maneuver_HighYoYo);
			return NodeStatus::FAILURE;
		}

		double elapsed = BTFunc::ClaimManeuverPhase(*BB, Maneuver_HighYoYo, YOYO_STALE_S);

		if (elapsed > YOYO_TOTAL_MAX_S)
		{
			// Guide's own maneuver duration exhausted -- release unconditionally rather than
			// holding the position-refine aim point indefinitely (same class of bug fixed in
			// Task_VerticalScissors: a phased maneuver must have an unconditional release path,
			// not just an abort floor).
			BTFunc::ReleaseManeuverPhase(*BB, Maneuver_HighYoYo);
			return NodeStatus::FAILURE;
		}

		if (elapsed < YOYO_CLIMB_PHASE_S)
		{
			// Pull-up phase: the same lead-pursuit point Task_LeadPursuit computes, pulled up in
			// world altitude -- trades some closure/lead accuracy for vertical separation, the
			// real "pull up and out of plane" technique for bleeding excess closure without
			// flying past the target. Bigger altitude offset early, tapering toward the
			// position-refine target as the climb phase ends.
			float pullUpFraction = 1.0f - (float)(elapsed / YOYO_CLIMB_PHASE_S);
			Vector3 yoyoPoint = (*BB)->TargetLocaion_Cartesian + BTFunc::PredictedTargetTravel(*BB);
			yoyoPoint.Z += 400.0f + 400.0f * pullUpFraction;
			(*BB)->VP_Cartesian = yoyoPoint;
			(*BB)->Throttle = 1.0f;
		}
		else
		{
			// Position-refine / nose-drop re-entry: settle behind and below the target once
			// the climb phase ends, aspect near 180 (behind), ready for the next engagement.
			Vector3 behindOffset = -(*BB)->TargetForwardVector * YOYO_POSITION_BEHIND_M;
			Vector3 refinePoint = (*BB)->TargetLocaion_Cartesian + behindOffset;
			refinePoint.Z -= YOYO_POSITION_BELOW_M;
			(*BB)->VP_Cartesian = refinePoint;
			(*BB)->Throttle = 0.7f;
		}

		return NodeStatus::SUCCESS;
	}
}
