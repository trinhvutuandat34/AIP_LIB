#include "Task_LeadTurn.h"
#include <cmath>

namespace Action
{
	// Off-center merge / re-merge handler (Gate 2's merge-check Sequence in Rule_forTraining.xml
	// already confirmed AA 30-90, Distance 3000-5000m, closing). Given matches start at
	// 2000-3000ft (near-merge already), this mostly matters for the Finals tie-break's longer
	// 10,000+ft start and post-disengagement re-merges, not the initial approach.
	static const double LEADTURN_RATIO_MIN = 1.1;   // guide: >1.1 = lead turn cuts the corner
	static const double LEADTURN_ROLL_CLAMP_DEG = 85.0;   // avoid tan() blowing up near +/-90

	static double ClampRollDeg(double rollDeg)
	{
		if (rollDeg > LEADTURN_ROLL_CLAMP_DEG) return LEADTURN_ROLL_CLAMP_DEG;
		if (rollDeg < -LEADTURN_ROLL_CLAMP_DEG) return -LEADTURN_ROLL_CLAMP_DEG;
		return rollDeg;
	}

	PortsList Task_LeadTurn::providedPorts()
	{
		return {
				InputPort<CPPBlackBoard*>("BB")
		};
	}

	NodeStatus Task_LeadTurn::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");

		double myRollRad = ClampRollDeg((*BB)->MyRotation_EDegree.Roll) * DEGTORAD;
		double targetRollRad = ClampRollDeg((*BB)->TargetRotation_EDegree.Roll) * DEGTORAD;

		double myTurnRate = (9.81 * tan(myRollRad)) / (double)fmaxf((*BB)->MySpeed_MS, 1.0f);
		double targetTurnRate = (9.81 * tan(targetRollRad)) / (double)fmaxf((*BB)->TargetSpeed_MS, 1.0f);

		if (fabs(targetTurnRate) < 1e-4)
		{
			// Defender isn't really turning -- no turn circle to cut the corner on. Fail so the
			// parent Fallback moves on to Task_LeadPursuit/plain pursuit.
			return NodeStatus::FAILURE;
		}

		double ratio = fabs(myTurnRate) / fabs(targetTurnRate);
		if (ratio <= LEADTURN_RATIO_MIN)
		{
			// Guide: turn-rate advantage must exceed 1.1 for the lead turn to actually cut the
			// corner -- otherwise it just falls behind on a worse line than plain pursuit.
			return NodeStatus::FAILURE;
		}

		// Predicted intercept ahead of the target's own turn circle: lead = R_turn*(1-cos(angle)).
		// R_turn approximated from the target's current speed/turn rate (R = V/omega); "angle"
		// as how far around that circle it travels in a short lookahead window.
		double targetTurnRadius = (double)(*BB)->TargetSpeed_MS / fmax(fabs(targetTurnRate), 1e-3);
		double lookaheadAngleRad = fabs(targetTurnRate) * 2.0;   // ~2s of the target's own turn
		double leadDistance = targetTurnRadius * (1.0 - cos(lookaheadAngleRad));
		double leadSign = (targetTurnRate >= 0.0) ? 1.0 : -1.0;

		Vector3 targetVelocity = (*BB)->TargetForwardVector * (*BB)->TargetSpeed_MS;
		Vector3 leadPoint = (*BB)->TargetLocaion_Cartesian + targetVelocity * 2.0
			+ (*BB)->TargetRightVector * (leadDistance * leadSign);

		(*BB)->VP_Cartesian = leadPoint;
		(*BB)->Throttle = 1.0f;

		return NodeStatus::SUCCESS;
	}
}
