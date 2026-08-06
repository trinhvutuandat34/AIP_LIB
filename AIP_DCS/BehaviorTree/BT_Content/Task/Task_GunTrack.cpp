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

	// RANGE-VALUE BIAS (added 2026-08-05). Until now this node had NO range term at all -- it was a
	// pure speed-matcher, so it held whatever range it happened to arrive at and treated every point
	// in the gun band as equally good. The competition damage rule says that is false by ~25x:
	//
	//     d_wez = (3000 - r_ft) / 2500      -> coefficient 1.00 at 500 ft, 0.00 at 3000 ft
	//
	// Measured (BT vs non-maneuvering target, 2 traces): while in-band the median range was
	// 1825 / 1915 ft -> damage coefficient 0.47 / 0.43, and the CLOSEST approach across ~450
	// in-band steps was 1739 ft. So roughly 2.1-2.3x of the available damage per scoring step was
	// being discarded, and the node never even trended toward the high-value edge.
	//
	// Target 220 m (~722 ft) -> coefficient ~0.91. Deliberately NOT the 500 ft edge: below
	// 152.4 m (500 ft) damage returns to ZERO, so overshooting the floor is worse than sitting
	// slightly long. The bias competes with the speed-match term rather than replacing it (that
	// term is what stops the overshoot this node exists to prevent), and both stay inside the
	// existing MIN/MAX clamps.
	//
	// UNVALIDATED. The eval harness is bimodal (see COMPETITION_PLAN.md E1) and this node ticks
	// only ~100 steps/episode in OBFM and zero in two-circle, so no A/B could establish an effect
	// today. TO REVERT EXACTLY: set GUNTRACK_RANGE_GAIN to 0.0f -- the term vanishes and behavior
	// is bit-identical to the pre-2026-08-05 speed-matcher.
	static const float GUNTRACK_TARGET_RANGE_M = 220.0f;
	static const float GUNTRACK_RANGE_GAIN = 0.0006f;   // per metre of range error; 0.0f == disabled
	static const float GUNTRACK_RANGE_FLOOR_M = 152.4f; // 500 ft: below this the damage rule pays 0

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

		// Range-value bias: add power while long of the high-damage band, ease off once at or
		// inside it. Clamped at the 500 ft floor so the term can only ever push AWAY from the
		// zero-damage zone, never deeper into it. See the constants above for the measured
		// justification and the exact revert.
		float rangeForBias = (*BB)->Distance;
		if (rangeForBias < GUNTRACK_RANGE_FLOOR_M) rangeForBias = GUNTRACK_RANGE_FLOOR_M;
		throttle += GUNTRACK_RANGE_GAIN * (rangeForBias - GUNTRACK_TARGET_RANGE_M);

		if (throttle < GUNTRACK_MIN_THROTTLE) throttle = GUNTRACK_MIN_THROTTLE;
		if (throttle > GUNTRACK_MAX_THROTTLE) throttle = GUNTRACK_MAX_THROTTLE;
		(*BB)->Throttle = throttle;

		return NodeStatus::SUCCESS;
	}
}
