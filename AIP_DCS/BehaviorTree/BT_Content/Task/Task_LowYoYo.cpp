#include "Task_LowYoYo.h"

namespace Action
{
	// Under-energized-behind case (own speed too low, closing too slowly to risk overshoot the
	// way Task_HighYoYoUp handles) -- dive to trade altitude for speed, then pull back up once
	// attack-ready.
	static const float LOWYOYO_RANGE_TRIGGER_M = 3000.0f;
	static const float LOWYOYO_SPEED_MIN_MS = 128.0f;    // 250kt
	static const float LOWYOYO_SPEED_MAX_MS = 180.0f;    // 350kt
	static const float LOWYOYO_ALT_MIN_M = 914.0f;       // 3000ft
	static const float LOWYOYO_ALT_MAX_M = 2438.0f;      // 8000ft
	static const float LOWYOYO_CLOSURE_MIN_MS = 26.0f;   // 50kt
	static const float LOWYOYO_CLOSURE_MAX_MS = 103.0f;  // 200kt
	static const double LOWYOYO_DIVE_PHASE_S = 3.0;
	static const double LOWYOYO_ATTACK_READY_S = 7.0;
	static const float LOWYOYO_ATTACK_READY_SPEED_MS = 231.0f;  // 450kt
	// Unconditional cap (mirrors Task_HighYoYoUp's YOYO_TOTAL_MAX_S). Without it, the only
	// release is the compound "elapsed>7 AND speed>231" below: a sustained low-energy pull-up
	// that never recovers 450kt leaves that condition permanently false, and STALE_S's self-heal
	// only resets elapsed rather than releasing -- so this Gate-4 node could monopolize its
	// Fallback slot (starving OneCircleFight/LagPursuit/Tail) cycling dive->pull-up indefinitely.
	// Found in the same node-wide recheck as the Task_Evade fix.
	static const double LOWYOYO_TOTAL_MAX_S = 10.0;
	static const double LOWYOYO_STALE_S = 20.0;
	static const float LOWYOYO_POSITION_BEHIND_M = 900.0f;

	PortsList Task_LowYoYo::providedPorts()
	{
		return {
				InputPort<CPPBlackBoard*>("BB")
		};
	}

	NodeStatus Task_LowYoYo::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");

		float closureRate = (*BB)->MySpeed_MS - (*BB)->TargetSpeed_MS;
		float altitude = (*BB)->MyLocation_Cartesian.Z;

		bool triggered = (*BB)->Distance < LOWYOYO_RANGE_TRIGGER_M
			&& (*BB)->MySpeed_MS >= LOWYOYO_SPEED_MIN_MS && (*BB)->MySpeed_MS <= LOWYOYO_SPEED_MAX_MS
			&& altitude >= LOWYOYO_ALT_MIN_M && altitude <= LOWYOYO_ALT_MAX_M
			&& closureRate >= LOWYOYO_CLOSURE_MIN_MS && closureRate <= LOWYOYO_CLOSURE_MAX_MS;

		// Entry gate only applies to a FRESH claim -- the dive itself is meant to push speed
		// past LOWYOYO_SPEED_MAX_MS, so re-checking the full entry band every tick once active
		// would abort the maneuver right as it starts working.
		bool active = (*BB)->ActiveManeuverID == Maneuver_LowYoYo;
		if (!triggered && !active)
		{
			return NodeStatus::FAILURE;
		}

		double elapsed = BTFunc::ClaimManeuverPhase(*BB, Maneuver_LowYoYo, LOWYOYO_STALE_S);

		if (elapsed > LOWYOYO_ATTACK_READY_S && (*BB)->MySpeed_MS > LOWYOYO_ATTACK_READY_SPEED_MS)
		{
			// Attack-ready -- hand off to Task_OneCircleFight/Task_LagPursuit (Gate 4).
			BTFunc::ReleaseManeuverPhase(*BB, Maneuver_LowYoYo);
			return NodeStatus::FAILURE;
		}

		if (elapsed > LOWYOYO_TOTAL_MAX_S)
		{
			// Budget exhausted without recovering attack speed -- release unconditionally rather
			// than holding Gate 4 while cycling dive/pull-up. Hands back to the other Gate 4/Tail
			// nodes (which may re-trigger this next tick if the entry gate still holds -- that's a
			// fresh claim with a fresh timer, not a stuck one).
			BTFunc::ReleaseManeuverPhase(*BB, Maneuver_LowYoYo);
			return NodeStatus::FAILURE;
		}

		if (elapsed < LOWYOYO_DIVE_PHASE_S)
		{
			// Dive-accelerate: cut below the lead-pursuit aim point to trade altitude for
			// speed, full throttle.
			Vector3 divePoint = (*BB)->TargetLocaion_Cartesian + BTFunc::PredictedTargetTravel(*BB);
			divePoint.Z -= 300.0;
			(*BB)->VP_Cartesian = divePoint;
			(*BB)->Throttle = 1.0f;
		}
		else
		{
			// Pull-up: converge back toward a position behind the target as speed recovers.
			Vector3 behindOffset = -(*BB)->TargetForwardVector * LOWYOYO_POSITION_BEHIND_M;
			(*BB)->VP_Cartesian = (*BB)->TargetLocaion_Cartesian + behindOffset;
			(*BB)->Throttle = 1.0f;
		}

		return NodeStatus::SUCCESS;
	}
}
