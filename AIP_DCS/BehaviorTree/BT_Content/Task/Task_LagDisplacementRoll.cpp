#include "Task_LagDisplacementRoll.h"

namespace Action
{
	// Guide's Lag Displacement Roll: single-shot bank/roll toward the target while abeam and not
	// yet tracked (Los_Degree near 90 means we're not yet pointed at them, EnemyInSight_Target
	// false means they haven't seen us either) -- a one-shot repositioning aim, not a phased
	// maneuver, so no ClaimManeuverPhase/BB-timestamp tracking (same convention as
	// Task_LeadTurn/Task_NoseToTailTurn: re-evaluated fresh every tick).
	static const float LDR_RANGE_MIN_M = 2000.0f;
	static const float LDR_RANGE_MAX_M = 5000.0f;
	static const float LDR_ATA_MIN_DEG = 75.0f;
	static const float LDR_ATA_MAX_DEG = 105.0f;
	static const double LDR_BANK_OFFSET_M = 1800.0;   // guide: ~60-70deg-equivalent lateral bias
	static const double LDR_PITCH_OFFSET_M = 150.0;   // guide: low pitch offset, not a full climb/dive

	PortsList Task_LagDisplacementRoll::providedPorts()
	{
		return {
				InputPort<CPPBlackBoard*>("BB")
		};
	}

	NodeStatus Task_LagDisplacementRoll::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");

		if ((*BB)->EnemyInSight_Target
			|| (*BB)->Distance < LDR_RANGE_MIN_M || (*BB)->Distance > LDR_RANGE_MAX_M
			|| (*BB)->Los_Degree < LDR_ATA_MIN_DEG || (*BB)->Los_Degree > LDR_ATA_MAX_DEG)
		{
			// Not the guide's "abeam, not yet tracked" geometry -- fail so the parent Fallback
			// tries Task_OneCircleFight/Task_LagPursuit instead.
			return NodeStatus::FAILURE;
		}

		// Bank/roll toward the target -- lateral bias via MyRightVector, whichever side is
		// actually toward the target (same shorter-turn technique Task_Notch/Task_TheBreak use),
		// plus a small downward pitch offset.
		Vector3 toTarget = (*BB)->TargetLocaion_Cartesian - (*BB)->MyLocation_Cartesian;
		Vector3 bankDir = (*BB)->MyRightVector;
		if (bankDir.dot(toTarget) < 0.0)
		{
			bankDir = -bankDir;
		}
		bankDir.normalize();

		Vector3 rollPoint = (*BB)->MyLocation_Cartesian + toTarget + bankDir * LDR_BANK_OFFSET_M;
		rollPoint.Z -= LDR_PITCH_OFFSET_M;
		(*BB)->VP_Cartesian = rollPoint;
		(*BB)->Throttle = 0.8f;

		return NodeStatus::SUCCESS;
	}
}
