#include "Task_RollingScissors.h"
#include <cmath>

namespace Action
{
	// Gate 2's third Scissors sibling: high-roll-authority oscillation rather than a flat or
	// vertical cut. Altitude/speed floors checked continuously (not just at entry) since the
	// guide's own bleed (100-200ft/cycle) is gradual, not a sudden side effect of one tick.
	static const double SCISSORS_NEUTRAL_MIN_S = 3.0;     // same persistence gate as Task_FlatScissors
	static const float RSCISSORS_ALT_MIN_M = 609.0f;      // 2000ft
	static const float RSCISSORS_SPEED_MIN_MS = 154.0f;   // 300kt
	static const double RSCISSORS_CYCLE_S = 10.0;
	static const double RSCISSORS_STALE_S = 20.0;
	static const double TWO_PI = 6.28318530718;

	PortsList Task_RollingScissors::providedPorts()
	{
		return {
				InputPort<CPPBlackBoard*>("BB")
		};
	}

	NodeStatus Task_RollingScissors::tick()
	{
		Optional<CPPBlackBoard*> BB = getInput<CPPBlackBoard*>("BB");

		// Gate 2's shared neutral-fight Sequence (Rule_forTraining.xml) already confirmed close
		// range and mutual off-boresight before this node is ever ticked. Also require the same
		// 3s persistence Task_FlatScissors enforces, for consistency -- a fresh merge shouldn't
		// jump straight to Rolling Scissors either.
		if ((*BB)->NeutralEngagementStartTime < 0.0)
		{
			return NodeStatus::FAILURE;
		}
		double neutralElapsed = (*BB)->RunningTime - (*BB)->NeutralEngagementStartTime;
		if (neutralElapsed < SCISSORS_NEUTRAL_MIN_S)
		{
			return NodeStatus::FAILURE;
		}

		float altitude = (*BB)->MyLocation_Cartesian.Z;
		if (altitude < RSCISSORS_ALT_MIN_M || (*BB)->MySpeed_MS < RSCISSORS_SPEED_MIN_MS)
		{
			BTFunc::ReleaseManeuverPhase(*BB, Maneuver_RollingScissors);
			return NodeStatus::FAILURE;
		}

		double elapsed = BTFunc::ClaimManeuverPhase(*BB, Maneuver_RollingScissors, RSCISSORS_STALE_S);

		// Oscillating bank cycle (guide: 70-80 -> 40-50 -> 20-30 -> 70-80 deg equivalent,
		// 8-12s period) via a sinusoid on MyRightVector, with a smaller MyUpVector component
		// for the guide's +/-10deg pitch oscillation.
		double phase = elapsed * (TWO_PI / RSCISSORS_CYCLE_S);
		double bankSign = sin(phase);
		double pitchSign = sin(phase * 2.0);

		Vector3 lateral = (*BB)->MyRightVector * (bankSign * 1800.0);
		Vector3 vertical = (*BB)->MyUpVector * (pitchSign * 300.0);
		(*BB)->VP_Cartesian = (*BB)->MyLocation_Cartesian + (*BB)->MyForwardVector * 800.0 + lateral + vertical;
		(*BB)->Throttle = 0.5f;

		return NodeStatus::SUCCESS;
	}
}
