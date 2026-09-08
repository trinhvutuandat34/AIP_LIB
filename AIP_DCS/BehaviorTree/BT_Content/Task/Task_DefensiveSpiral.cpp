#include "Task_DefensiveSpiral.h"

namespace Action
{
	// BFM_MANEUVER_GAP_REFERENCE.md 2026-09-06 addendum (SS5/SS6): "Defensive Spiral" -- a
	// close-range rear-hemisphere threat at low defender speed, where the doctrine response is a
	// very tight, steep, descending spiral with minimized acceleration (idle-ish power) rather
	// than trying to out-accelerate a faster attacker, forcing them to overshoot. Distinct from
	// Gate1_TheBreak (Task_Evade), which assumes there is enough energy to extend on max
	// afterburner -- this is the sibling case where that assumption doesn't hold: own speed is
	// already below the "slow" line, so adding thrust would just let the faster attacker stay
	// fast too. Shares Task_Evade's EnemyInSight_Target/phase-claim idiom; unlike the Scissors
	// family (Task_FlatScissors/Task_RollingScissors), this does NOT oscillate -- a spiral is one
	// sustained turn direction, not an alternating reversal.
	static const float SPIRAL_SPEED_TRIGGER_MS = 154.0f;  // ~300kt -- same "slow" line Task_Evade
	                                                       // already uses for its own nose-down bias
	static const float SPIRAL_RANGE_TRIGGER_M = 2000.0f;  // close rear-hemisphere threat, same band
	                                                       // as Gate1_JinkingTurn/Task_Notch
	// 1000 m, RAISED from 609 m (2000 ft) on 2026-09-08. At 609 this constant was DEAD CODE in
	// both of its uses: Gate0_ClimbToSafeAltitude is the first child of the outer Fallback and
	// returns SUCCESS at altitude <= 914 m, so the entire Gate 1 Fallback is unreachable below
	// 914. This node therefore only ever ticked above 914 -- making the entry check
	// (altitude > 609) always true and the floor abort (altitude <= 609) never true. Since that
	// abort is the ONLY path that arms SPIRAL_COOLDOWN_S outside the 15 s budget, the cooldown
	// was effectively unreachable too.
	//
	// 1000 m is the same "just above Gate 0's own 914 m trigger" choice SHIP_HARD_DECK_M already
	// makes on the Python side. It gives the node its own abort instead of relying on Gate 0 to
	// interrupt it: a ~37-degree dive at ~150 m/s is only about -90 m/s vertical, which does NOT
	// trip Gate 0's FAST_DESCENT_RATE_MS (-150), so before this change the spiral descended
	// unopposed to 914, got preempted mid-maneuver while KEEPING its claim and its running timer,
	// and resumed on the way back up -- a porpoise, with an effective hold well under the 10-20 s
	// doctrine band the node cites.
	static const float SPIRAL_ALT_FLOOR_M = 1000.0f;
	static const double SPIRAL_LATERAL_OFFSET_M = 1200.0; // tight turn -- between Task_Evade's hard
	                                                       // break (2000) and Task_Notch's beam (3000)
	static const double SPIRAL_DIVE_OFFSET_M = 900.0;     // steep nose-low bias (doctrine: 30-60 deg)
	static const float SPIRAL_THROTTLE = 0.1f;            // idle-ish -- doctrine: minimize acceleration
	static const double SPIRAL_STALE_S = 20.0;
	static const double SPIRAL_TOTAL_MAX_S = 15.0;        // doctrine duration band is 10-20s
	static const double SPIRAL_COOLDOWN_S = 10.0;

	PortsList Task_DefensiveSpiral::providedPorts()
	{
		return {
				InputPort<CPPBlackBoard*>("BB")
		};
	}

	NodeStatus Task_DefensiveSpiral::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");

		bool active = (*BB)->ActiveManeuverID == Maneuver_DefensiveSpiral;

		if (!(*BB)->EnemyInSight_Target)
		{
			// No longer threatened -- the spiral already forced the overshoot it exists to
			// force, or was never needed. Fail so the parent Fallback moves on.
			BTFunc::ReleaseManeuverPhase(*BB, Maneuver_DefensiveSpiral);
			return NodeStatus::FAILURE;
		}

		if (!active && BTFunc::IsManeuverOnCooldown(*BB, Maneuver_DefensiveSpiral))
		{
			// Still cooling down from a prior floor abort or budget timeout -- fail so
			// Gate1_TheBreak gets sustained control instead of an immediate repeat.
			return NodeStatus::FAILURE;
		}

		float altitude = (*BB)->MyLocation_Cartesian.Z;

		if (!active)
		{
			// Fresh-claim entry gate only -- once active, speed/altitude are expected to keep
			// changing as the dive works, so re-checking the full band every tick would abort
			// the maneuver right as it starts succeeding (same reasoning as Task_LowYoYo's
			// entry-gate comment). Close + threatened + too slow to extend like Gate1_TheBreak +
			// room below to dive into.
			bool triggered = (*BB)->Distance < SPIRAL_RANGE_TRIGGER_M
				&& (*BB)->MySpeed_MS < SPIRAL_SPEED_TRIGGER_MS
				&& altitude > SPIRAL_ALT_FLOOR_M;
			if (!triggered)
			{
				return NodeStatus::FAILURE;
			}
		}

		if (altitude <= SPIRAL_ALT_FLOOR_M)
		{
			// Hard floor -- pull out unconditionally regardless of phase, same abort idiom as
			// Task_FlatScissors' SCISSORS_ALTITUDE_ABORT_M.
			BTFunc::ReleaseManeuverPhaseWithCooldown(*BB, Maneuver_DefensiveSpiral, SPIRAL_COOLDOWN_S);
			return NodeStatus::FAILURE;
		}

		double elapsed = BTFunc::ClaimManeuverPhase(*BB, Maneuver_DefensiveSpiral, SPIRAL_STALE_S);

		if (elapsed > SPIRAL_TOTAL_MAX_S)
		{
			// Budget exhausted (doctrine duration band 10-20s) without the attacker overshooting
			// -- release rather than holding Gate 1's slot indefinitely (same reasoning as
			// Task_Evade's BREAK_TOTAL_MAX_S / Task_LowYoYo's LOWYOYO_TOTAL_MAX_S).
			BTFunc::ReleaseManeuverPhaseWithCooldown(*BB, Maneuver_DefensiveSpiral, SPIRAL_COOLDOWN_S);
			return NodeStatus::FAILURE;
		}

		// Very tight, steep, continuously-descending spiral: one sustained turn direction with a
		// steady nose-down bias so altitude bleeds into turn radius rather than the aircraft
		// trying to hold energy. Idle-ish throttle throughout -- per the source doctrine, the
		// point is to not help a faster attacker stay fast too.
		// LATCHED, not re-derived per tick. ShorterTurnDirection() flips sign when the bandit
		// crosses our vertical longitudinal plane, and this node is only reachable with the
		// bandit AFT of the 3-9 line (Gate1_JinkingTurn above it succeeds on a strict superset of
		// this node's trigger), so its own design geometry sits on that discontinuity. Without
		// the latch the aim point swings 2,400 m across the nose on noise and the spiral becomes
		// a wings-level idle-power dive. See ManeuverTurnDir in CPPBlackBoard.h.
		Vector3 turnDir = BTFunc::LatchedTurnDirection(*BB, Maneuver_DefensiveSpiral);
		Vector3 spiralPoint = (*BB)->MyLocation_Cartesian + turnDir * SPIRAL_LATERAL_OFFSET_M;
		spiralPoint.Z -= SPIRAL_DIVE_OFFSET_M;
		(*BB)->VP_Cartesian = spiralPoint;
		(*BB)->Throttle = SPIRAL_THROTTLE;

		return NodeStatus::SUCCESS;
	}
}
