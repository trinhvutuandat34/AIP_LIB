#include "Task_Notch.h"

namespace Action
{
	// AERIAL_COMBAT_BT_GUIDE_DETAILED.md's Notch maneuver was originally missile-defense
	// (rear-aspect launch warning, turn to put the missile source at 90 relative bearing). No
	// missile mechanic exists in this guns-only competition, so this is repurposed as a
	// generic aggressive-rear-aspect-threat reaction: same geometry, keyed off
	// EnemyInSight_Target/close range instead of a launch event.
	static const float NOTCH_RANGE_TRIGGER_M = 2000.0f;
	static const float NOTCH_BEAM_MIN_DEG = 70.0f;
	static const float NOTCH_BEAM_MAX_DEG = 110.0f;
	static const double NOTCH_SUSTAIN_S = 1.5;
	static const double NOTCH_OFFSET_M = 3000.0;
	static const double NOTCH_STALE_S = 20.0;

	PortsList Task_Notch::providedPorts()
	{
		return {
				InputPort<CPPBlackBoard*>("BB")
		};
	}

	NodeStatus Task_Notch::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");

		// Los_Degree_Target is the target's own ATA to us (CheckSight.cpp computes it
		// symmetrically for both aircraft) -- near 90 means they're tracking us from the beam,
		// not dead astern, which is exactly the geometry Notch is meant to sustain.
		bool beamThreat = (*BB)->Los_Degree_Target >= NOTCH_BEAM_MIN_DEG && (*BB)->Los_Degree_Target <= NOTCH_BEAM_MAX_DEG;
		if (!(*BB)->EnemyInSight_Target || (*BB)->Distance > NOTCH_RANGE_TRIGGER_M || !beamThreat)
		{
			BTFunc::ReleaseManeuverPhase(*BB, Maneuver_Notch);
			// Not a beam-aspect close threat -- fail so the parent Fallback tries
			// Task_JinkingTurn/Task_TheBreak instead.
			return NodeStatus::FAILURE;
		}

		double elapsed = BTFunc::ClaimManeuverPhase(*BB, Maneuver_Notch, NOTCH_STALE_S);
		if (elapsed > NOTCH_SUSTAIN_S)
		{
			// Held the beam long enough -- release so the Fallback reassesses from the top
			// rather than notching indefinitely.
			BTFunc::ReleaseManeuverPhase(*BB, Maneuver_Notch);
			return NodeStatus::FAILURE;
		}

		// Turn perpendicular to the line-of-sight to the threat (beam-on).
		Vector3 perp = BTFunc::ShorterTurnDirection(*BB);
		(*BB)->VP_Cartesian = (*BB)->MyLocation_Cartesian + perp * NOTCH_OFFSET_M;
		(*BB)->Throttle = 1.0f;

		return NodeStatus::SUCCESS;
	}
}
