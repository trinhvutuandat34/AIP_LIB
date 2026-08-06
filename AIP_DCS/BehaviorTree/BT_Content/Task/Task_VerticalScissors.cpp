#include "Task_VerticalScissors.h"
#include <cmath>

namespace Action
{
	// Gate 2's Scissors sibling for a significant attacker/defender speed differential
	// (AERIAL_COMBAT_BT_GUIDE_DETAILED.md). Deliberately does NOT port the guide's own
	// deceleration formula (g*sin(pitch)) -- it's internally inconsistent with the guide's own
	// worked example -- reads real MySpeed_MS each tick instead to decide when "peak" is reached.
	static const double SCISSORS_NEUTRAL_MIN_S = 3.0;        // same persistence gate as Task_FlatScissors
	static const float VSCISSORS_ALT_MIN_M = 1524.0f;        // 5000ft entry
	static const float VSCISSORS_ALT_ABORT_M = 914.0f;       // 3000ft abort
	static const float VSCISSORS_SPEED_DIFF_MIN_MS = 51.0f;  // ~100kt
	static const float VSCISSORS_PEAK_SPEED_MS = 77.0f;      // ~150kt "peak" per guide
	static const double VSCISSORS_CLIMB_ENTRY_S = 1.5;
	static const double VSCISSORS_CLIMB_MAX_S = 8.0;         // guide: 4-8s climb, force transition
	static const double VSCISSORS_TOTAL_MAX_S = 11.0;        // guide: ~4-8s climb + ~2-3s dive/escape
	static const double VSCISSORS_STALE_S = 20.0;
	// Found necessary in local testing: the geometry that triggers one activation is usually
	// still true immediately after release, so without a cooldown the node re-claims and
	// repeats the climb/dive cycle back-to-back, netting a persistent descent over several
	// cycles even though no single activation runs away indefinitely anymore.
	static const double VSCISSORS_COOLDOWN_S = 15.0;

	PortsList Task_VerticalScissors::providedPorts()
	{
		return {
				InputPort<CPPBlackBoard*>("BB")
		};
	}

	NodeStatus Task_VerticalScissors::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");

		// Gate 2's shared neutral-fight Sequence (Rule_forTraining.xml) already confirmed close
		// range and mutual off-boresight before this node is ever ticked. Also require the same
		// 3s persistence Task_FlatScissors enforces (checked every tick, unconditionally) -- a
		// merge that hasn't had a chance to resolve normally yet shouldn't jump straight to an
		// aggressive vertical dive just because it clears a one-tick altitude/speed-diff check.
		if ((*BB)->NeutralEngagementStartTime < 0.0)
		{
			return NodeStatus::FAILURE;
		}
		double neutralElapsed = (*BB)->RunningTime - (*BB)->NeutralEngagementStartTime;
		if (neutralElapsed < SCISSORS_NEUTRAL_MIN_S)
		{
			return NodeStatus::FAILURE;
		}

		bool active = (*BB)->ActiveManeuverID == Maneuver_VerticalScissors;

		if (!active && BTFunc::IsManeuverOnCooldown(*BB, Maneuver_VerticalScissors))
		{
			// Still cooling down from the last activation -- fail so Task_RollingScissors (or
			// Gate 4 offense, if the outer merge gate itself clears) gets sustained control
			// instead of an immediate repeat.
			return NodeStatus::FAILURE;
		}

		float altitude = (*BB)->MyLocation_Cartesian.Z;
		float speedDiff = fabsf((*BB)->MySpeed_MS - (*BB)->TargetSpeed_MS);

		if (!active && (altitude < VSCISSORS_ALT_MIN_M || speedDiff < VSCISSORS_SPEED_DIFF_MIN_MS))
		{
			// Not a fresh vertical-scissors setup (needs altitude buffer + a real speed
			// differential to exploit) -- fail so Task_RollingScissors (sibling in Gate 2's
			// nested Fallback) gets a turn.
			return NodeStatus::FAILURE;
		}

		if (altitude < VSCISSORS_ALT_ABORT_M)
		{
			// Unconditional abort -- fail so the Fallback rescans from Task_ClimbToSafeAltitude.
			BTFunc::ReleaseManeuverPhaseWithCooldown(*BB, Maneuver_VerticalScissors, VSCISSORS_COOLDOWN_S);
			return NodeStatus::FAILURE;
		}

		double elapsed = BTFunc::ClaimManeuverPhase(*BB, Maneuver_VerticalScissors, VSCISSORS_STALE_S);

		if (elapsed > VSCISSORS_TOTAL_MAX_S)
		{
			// Guide's own maneuver duration exhausted (~4-8s climb + ~2-3s dive/escape) --
			// release unconditionally. Fixes a real bug found in local testing: without this
			// cap the dive/escape phase below had no self-terminating condition other than the
			// altitude abort above, and drove the aircraft into an unrecoverable dive well
			// before Task_ClimbToSafeAltitude's 914m trigger could arrest it in time.
			BTFunc::ReleaseManeuverPhaseWithCooldown(*BB, Maneuver_VerticalScissors, VSCISSORS_COOLDOWN_S);
			return NodeStatus::FAILURE;
		}

		bool pastPeak = ((*BB)->MySpeed_MS < VSCISSORS_PEAK_SPEED_MS && elapsed > VSCISSORS_CLIMB_ENTRY_S)
			|| elapsed > VSCISSORS_CLIMB_MAX_S;

		if (!pastPeak)
		{
			// Climb phase: steep, mostly-vertical aim point.
			Vector3 climbPoint = (*BB)->MyLocation_Cartesian + (*BB)->MyUpVector * 2000.0
				+ (*BB)->MyForwardVector * 300.0;
			(*BB)->VP_Cartesian = climbPoint;
			(*BB)->Throttle = 1.0f;
		}
		else
		{
			// Dive/escape phase: nose back down and accelerate away.
			Vector3 divePoint = (*BB)->MyLocation_Cartesian - (*BB)->MyUpVector * 1500.0
				+ (*BB)->MyForwardVector * 1000.0;
			(*BB)->VP_Cartesian = divePoint;
			(*BB)->Throttle = 1.0f;
		}

		return NodeStatus::SUCCESS;
	}
}
