#include "Task_BarrelRollAttack.h"

namespace Action
{
	// Guide's Barrel Roll Attack: high-closure, high-energy approach where a straight pursuit
	// would overshoot -- pitch/roll up and around the target's flight path to bleed closure
	// without giving up the offensive position the way a plain lag pursuit roll would.
	static const float BARRELROLL_RANGE_MIN_M = 2000.0f;
	static const float BARRELROLL_RANGE_MAX_M = 3000.0f;
	static const float BARRELROLL_CLOSURE_TRIGGER_MS = 40.0f;
	static const float BARRELROLL_ALT_MIN_M = 1219.0f;    // 4000ft
	static const float BARRELROLL_SPEED_MIN_MS = 257.0f;  // 500kt
	static const double BARRELROLL_PITCHUP_PHASE_S = 2.0;  // guide: 0-2s pitch-up sweep
	static const double BARRELROLL_TOTAL_MAX_S = 6.0;
	static const double BARRELROLL_STALE_S = 20.0;
	static const float BARRELROLL_COMPLETION_THROTTLE = 0.35f;

	PortsList Task_BarrelRollAttack::providedPorts()
	{
		return {
				InputPort<CPPBlackBoard*>("BB")
		};
	}

	NodeStatus Task_BarrelRollAttack::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");

		float closureRate = (*BB)->MySpeed_MS - (*BB)->TargetSpeed_MS;
		float altitude = (*BB)->MyLocation_Cartesian.Z;

		bool triggered = (*BB)->Distance >= BARRELROLL_RANGE_MIN_M && (*BB)->Distance <= BARRELROLL_RANGE_MAX_M
			&& closureRate > BARRELROLL_CLOSURE_TRIGGER_MS
			&& altitude > BARRELROLL_ALT_MIN_M
			&& (*BB)->MySpeed_MS > BARRELROLL_SPEED_MIN_MS;

		// Entry gate only applies to a FRESH claim -- the sweep itself is meant to push closure/
		// range past the trigger band, so re-checking it every tick once active would abort the
		// maneuver right as it starts working (same convention as Task_HighYoYoUp/Task_LowYoYo).
		bool active = (*BB)->ActiveManeuverID == Maneuver_BarrelRollAttack;
		if (!triggered && !active)
		{
			return NodeStatus::FAILURE;
		}

		double elapsed = BTFunc::ClaimManeuverPhase(*BB, Maneuver_BarrelRollAttack, BARRELROLL_STALE_S);

		if (elapsed > BARRELROLL_TOTAL_MAX_S)
		{
			// Guide's own maneuver duration exhausted -- release unconditionally rather than
			// holding the completion aim indefinitely (same unconditional-release requirement
			// documented in Task_HighYoYoUp).
			BTFunc::ReleaseManeuverPhase(*BB, Maneuver_BarrelRollAttack);
			return NodeStatus::FAILURE;
		}

		Vector3 pursuitPoint = (*BB)->TargetLocaion_Cartesian + BTFunc::PredictedTargetTravel(*BB);

		if (elapsed < BARRELROLL_PITCHUP_PHASE_S)
		{
			// Pitch-up sweep: bias the aim point up and out of plane via MyUpVector, tapering
			// back toward straight pursuit as the sweep completes (guide: ~20-60deg-equivalent
			// sweep over the phase).
			float sweepFraction = 1.0f - (float)(elapsed / BARRELROLL_PITCHUP_PHASE_S);
			Vector3 sweepPoint = pursuitPoint + (*BB)->MyUpVector * (300.0f + 500.0f * sweepFraction);
			(*BB)->VP_Cartesian = sweepPoint;
			(*BB)->Throttle = 1.0f;
		}
		else
		{
			// Completion: roll back down onto plain pursuit, reduced throttle so the closure
			// that triggered this doesn't carry straight through into an overshoot.
			(*BB)->VP_Cartesian = pursuitPoint;
			(*BB)->Throttle = BARRELROLL_COMPLETION_THROTTLE;
		}

		return NodeStatus::SUCCESS;
	}
}
