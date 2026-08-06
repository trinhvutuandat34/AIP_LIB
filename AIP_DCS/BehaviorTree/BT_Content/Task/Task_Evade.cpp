#include "Task_Evade.h"

namespace Action
{
	// Implements AERIAL_COMBAT_BT_GUIDE_DETAILED.md's "The Break" maneuver. Keeps this class's
	// established name/file/Fallback slot (Task_Evade, gated by EnemyInSight_Target) rather
	// than adding a second node -- Break's phased logic is simply a proper version of what this
	// node always approximated with a straight-line aim point.
	static const float BREAK_RANGE_TRIGGER_M = 3000.0f;
	static const double BREAK_NOSE_DOWN_CHECK_S = 1.5;
	static const double BREAK_DECISION_S = 5.0;
	static const float BREAK_SLOW_SPEED_MS = 154.0f;      // ~300kt
	static const float BREAK_GOAL_SEPARATION_M = 5000.0f; // guide: 5+ km separation
	static const double BREAK_STALE_S = 20.0;
	static const double BREAK_LATERAL_OFFSET_M = 2000.0;
	// Unconditional release cap + cooldown, found missing in a recheck (see
	// ManeuverCooldownUntil[]'s comment in CPPBlackBoard.h for the full failure mode). 5s hard-turn
	// + up to 15s of extend/reassess before giving up on reaching the 5km goal this cycle.
	static const double BREAK_TOTAL_MAX_S = 20.0;
	static const double BREAK_COOLDOWN_S = 15.0;

	PortsList Task_Evade::providedPorts()
	{
		return {
				InputPort<CPPBlackBoard*>("BB")
		};
	}

	NodeStatus Task_Evade::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");

		if (!(*BB)->EnemyInSight_Target)
		{
			// No longer threatened -- the break already succeeded, or was never needed. Fail
			// so the parent Fallback moves on to the offensive branches.
			BTFunc::ReleaseManeuverPhase(*BB, Maneuver_TheBreak);
			return NodeStatus::FAILURE;
		}

		// Entry gate only applies to a FRESH claim -- once active, Distance is expected (and
		// wanted) to grow past this threshold as the break works, so re-checking it every tick
		// here would abort the maneuver right as it starts succeeding. The decision-point logic
		// below is what actually decides when to release.
		bool active = (*BB)->ActiveManeuverID == Maneuver_TheBreak;

		if (!active && BTFunc::IsManeuverOnCooldown(*BB, Maneuver_TheBreak))
		{
			// Still cooling down from hitting the time cap below -- fail so Task_JinkingTurn (or
			// Gate 2/4, if the outer Gate 1 Fallback itself clears) gets sustained control instead
			// of an immediate repeat of the same break cycle.
			return NodeStatus::FAILURE;
		}

		if (!active && (*BB)->Distance > BREAK_RANGE_TRIGGER_M)
		{
			// Threatened but not close enough to need a hard break yet -- fail so
			// Task_JinkingTurn/Task_Notch (closer-range) or the offensive branches handle it.
			return NodeStatus::FAILURE;
		}

		double elapsed = BTFunc::ClaimManeuverPhase(*BB, Maneuver_TheBreak, BREAK_STALE_S);

		if (elapsed > BREAK_TOTAL_MAX_S)
		{
			// Didn't reach the 5km goal separation within budget -- release unconditionally
			// rather than relying on EnemyInSight_Target/goal-distance alone, neither of which is
			// guaranteed to trip against a target that stays broadly nose-on and doesn't let
			// separation cleanly grow. See ManeuverCooldownUntil[]'s comment in CPPBlackBoard.h.
			BTFunc::ReleaseManeuverPhaseWithCooldown(*BB, Maneuver_TheBreak, BREAK_COOLDOWN_S);
			return NodeStatus::FAILURE;
		}

		if (elapsed > BREAK_DECISION_S && (*BB)->Distance > BREAK_RANGE_TRIGGER_M)
		{
			// Decision point (guide: T+5.0s) -- separation has grown past the close-range
			// threshold: reduce aggression and extend toward the goal separation at reduced
			// throttle instead of continuing the max-G break turn indefinitely.
			Vector3 awayFromTarget = (*BB)->MyLocation_Cartesian - (*BB)->TargetLocaion_Cartesian;
			(*BB)->VP_Cartesian = (*BB)->MyLocation_Cartesian + awayFromTarget;
			(*BB)->Throttle = 0.5f;

			if ((*BB)->Distance > BREAK_GOAL_SEPARATION_M)
			{
				BTFunc::ReleaseManeuverPhase(*BB, Maneuver_TheBreak);
				return NodeStatus::FAILURE;
			}
			return NodeStatus::SUCCESS;
		}

		// Hard break turn: aim point offset ~90 degrees off the line to the threat (same
		// technique as Task_Notch) -- a real angular break, not a straight extension.
		Vector3 breakDir = BTFunc::ShorterTurnDirection(*BB);
		Vector3 breakPoint = (*BB)->MyLocation_Cartesian + breakDir * BREAK_LATERAL_OFFSET_M;
		if ((*BB)->MySpeed_MS < BREAK_SLOW_SPEED_MS && elapsed > BREAK_NOSE_DOWN_CHECK_S)
		{
			// Guide: if speed drops below ~300kt, bias the aim point nose-down to recover energy.
			breakPoint.Z -= 300.0;
		}

		(*BB)->VP_Cartesian = breakPoint;
		(*BB)->Throttle = 1.0f;

		return NodeStatus::SUCCESS;
	}
}
