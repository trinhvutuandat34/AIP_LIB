#include "Task_GunTrack.h"

namespace Action
{
	// Neutral throttle when speed-matched to the bandit. Slightly below Task_pure's fixed 0.7
	// because this node's job is to HOLD the gun band (150-914 m, gated by Rule_forTraining.xml's
	// Gate 2.5), not to keep closing.
	static const float GUNTRACK_BASE_THROTTLE = 0.65f;
	// Throttle reduction per (m/s) of overtake. 0.01 -> a 30 m/s overtake eases throttle by 0.30
	// (0.65 -> 0.35); a ~45 m/s overtake pulls it to the floor.
	static const float GUNTRACK_THROTTLE_PER_MS = 0.01f;
	static const float GUNTRACK_MIN_THROTTLE = 0.20f;   // keep control authority; never full idle
	static const float GUNTRACK_MAX_THROTTLE = 0.95f;

	PortsList Task_GunTrack::providedPorts()
	{
		return {
				InputPort<CPPBlackBoard*>("BB")
		};
	}

	NodeStatus Task_GunTrack::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");

		// Reached only when Rule_forTraining.xml's Gate 2.5 has already confirmed we are inside
		// the gun band (150-914 m = the 500-3000 ft Phase 1 WEZ) AND own ATA < 5 deg, i.e. a
		// firing solution is already in hand. The job here is to STAY in it -- which is exactly
		// what plain Task_pure fails at: its fixed 0.7 throttle keeps closing even when already
		// overtaking, so the aircraft sails through the band to under 150 m and the range opens
		// again (the documented "reaches ATA 0.1 deg and range 270-511 m yet logs 0 WEZ steps").

		// Aim: pure pursuit at the target's CURRENT position, same as Task_pure. A lead point
		// risks over-lead overshoot at gun range (see Task_OneCircleFight's note) -- holding a
		// solution wants stability, not corner-cutting. (A small range-scaled lead is a possible
		// future refinement if replays show the pipper lagging a hard-turning target.)
		// NOTE 2026-08-05: a bounded lead feedforward was tried here and REVERTED -- the trace
		// showed a STATIC ~4.5 deg pointing error (near-zero crossing/LOS-rate), not a lag, so
		// the real fix is in Controller_CY::GetStick (near-zero-error authority), not the aim.
		(*BB)->VP_Cartesian = (*BB)->TargetLocaion_Cartesian;

		// Throttle: speed-match the bandit. overtake > 0 means we are faster and will overshoot
		// through the band -> ease off; overtake < 0 means we are dropping out the back -> add
		// power. This closed loop settles the aircraft at the target's speed and holds it in the
		// WEZ, where Task_pure's fixed throttle sails through. Uses only the two speed scalars
		// already on the blackboard -- no closure-rate field exists, and a LOS-projected closure
		// would need Vector3 math that is unnecessary for the astern hold this gates to.
		float overtake_ms = (*BB)->MySpeed_MS - (*BB)->TargetSpeed_MS;
		float throttle = GUNTRACK_BASE_THROTTLE - GUNTRACK_THROTTLE_PER_MS * overtake_ms;
		if (throttle < GUNTRACK_MIN_THROTTLE) throttle = GUNTRACK_MIN_THROTTLE;
		if (throttle > GUNTRACK_MAX_THROTTLE) throttle = GUNTRACK_MAX_THROTTLE;
		(*BB)->Throttle = throttle;

		return NodeStatus::SUCCESS;
	}
}
