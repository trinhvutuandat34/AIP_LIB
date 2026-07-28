#include "Task_ClimbToSafeAltitude.h"

namespace Action
{
	// Trigger altitude: 914 m (~3000 ft) -- well above the 1000 ft / ~305 m Hard Deck line in
	// COMPETITION_RULES.md sec.5, to leave margin to arrest a dive before crossing it.
	static const float SAFE_ALTITUDE_TRIGGER_M = 914.0f;
	// Early-warning: found necessary in local testing that this single absolute-altitude
	// trigger is not sufficient on its own -- by the time a fast, sustained dive (whatever its
	// origin -- any node's aim point chasing a target through unusual attitudes, not limited to
	// any one maneuver) crosses 914m, the aircraft can already be too deep into an unusual
	// attitude/energy state for this simple "aim straight up" response to arrest before Hard
	// Deck. Escalate the SAME response earlier, based on descent RATE rather than only absolute
	// altitude, using AltSpeed (declared in CPPBlackBoard before this expansion but never
	// populated -- now written by EnergyStateUpdate). Threshold is deliberately high (150 m/s)
	// so it only catches a genuinely runaway dive, not a deliberate, controlled maneuver dive
	// (e.g. Task_LowYoYo/Task_VerticalScissors's own much gentler, short dives).
	static const float FAST_DESCENT_ALTITUDE_TRIGGER_M = 3000.0f;
	static const float FAST_DESCENT_RATE_MS = -150.0f;

	PortsList Task_ClimbToSafeAltitude::providedPorts()
	{
		return {
				InputPort<CPPBlackBoard*>("BB")
		};
	}

	NodeStatus Task_ClimbToSafeAltitude::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");

		// LLAtoCartesian() converts altitude straight through with a zero-altitude reference
		// origin (see CPPBehaviorTree.cpp), so MyLocation_Cartesian.Z is altitude in meters.
		float altitude = (*BB)->MyLocation_Cartesian.Z;

		bool criticalLow = altitude <= SAFE_ALTITUDE_TRIGGER_M;
		bool runawayDescent = altitude <= FAST_DESCENT_ALTITUDE_TRIGGER_M && (*BB)->AltSpeed <= FAST_DESCENT_RATE_MS;

		if (!criticalLow && !runawayDescent)
		{
			// Safe altitude and not descending dangerously fast -- fail so the parent Fallback
			// moves on to evasion/pursuit.
			return NodeStatus::FAILURE;
		}

		// Below the safety trigger (or descending too fast this low): aim straight up from the
		// current position and firewall the throttle to break the dive before Hard Deck
		// (instant-loss on violation).
		Vector3 climbPoint = (*BB)->MyLocation_Cartesian;
		climbPoint.Z += 5000.0f;
		(*BB)->VP_Cartesian = climbPoint;
		(*BB)->Throttle = 1.0f;

		return NodeStatus::SUCCESS;
	}
}
