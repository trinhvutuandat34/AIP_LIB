#include "EnergyStateUpdate.h"

namespace Action
{
	// Standard gravity, m/s^2.
	static const float ENERGY_G = 9.81f;
	// Close range + both aircraft off-boresight of each other -- a persisting merged turning
	// fight where neither side has a tracking advantage. Feeds Gate 2's Scissors trigger
	// (Task_FlatScissors requires this to have held for 3+ seconds).
	static const float NEUTRAL_RANGE_M = 2000.0f;
	static const float NEUTRAL_ATA_DEG = 45.0f;

	PortsList EnergyStateUpdate::providedPorts()
	{
		return {
				InputPort<CPPBlackBoard*>("BB")
		};
	}

	NodeStatus EnergyStateUpdate::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");

		// Specific energy: E_s = V^2/2g + h (AERIAL_COMBAT_BT_GUIDE_DETAILED.md sec.6).
		// MyLocation_Cartesian.Z / TargetLocaion_Cartesian.Z are altitude in meters
		// (LLAtoCartesian passes altitude straight through, see Task_ClimbToSafeAltitude.cpp).
		float ownAlt = (*BB)->MyLocation_Cartesian.Z;
		float targetAlt = (*BB)->TargetLocaion_Cartesian.Z;
		float ownV = (*BB)->MySpeed_MS;
		float targetV = (*BB)->TargetSpeed_MS;

		(*BB)->OwnSpecificEnergy = (ownV * ownV) / (2.0f * ENERGY_G) + ownAlt;
		(*BB)->TargetSpecificEnergy = (targetV * targetV) / (2.0f * ENERGY_G) + targetAlt;

		// AltSpeed (m/s, +up): declared in CPPBlackBoard since before this expansion but never
		// populated anywhere. Feeds Task_ClimbToSafeAltitude's early-warning descent-rate check.
		if ((*BB)->PreviousAltitudeForRate > -999999.0f && (*BB)->DeltaSecond > 1e-6)
		{
			(*BB)->AltSpeed = (ownAlt - (*BB)->PreviousAltitudeForRate) / (float)(*BB)->DeltaSecond;
		}
		(*BB)->PreviousAltitudeForRate = ownAlt;

		float denom = (*BB)->TargetSpecificEnergy;
		if (denom < 1.0f)
		{
			denom = 1.0f;
		}
		(*BB)->EnergyRatio = (*BB)->OwnSpecificEnergy / denom;

		bool neutral = (*BB)->Distance < NEUTRAL_RANGE_M
			&& (*BB)->Los_Degree > NEUTRAL_ATA_DEG
			&& (*BB)->Los_Degree_Target > NEUTRAL_ATA_DEG;

		if (neutral)
		{
			if ((*BB)->NeutralEngagementStartTime < 0.0)
			{
				(*BB)->NeutralEngagementStartTime = (*BB)->RunningTime;
			}
		}
		else
		{
			(*BB)->NeutralEngagementStartTime = -1.0;
		}

		return NodeStatus::SUCCESS;
	}
}
