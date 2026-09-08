#include "Functions.h"

namespace BTFunc
{
	void AddNodeExcute(std::string * out, std::string input)
	{
		out->append(input);
		out->append("\n");
	}
	void SaveTextData(std::string * tempString, std::string * BT_Text)
	{
		if (tempString != nullptr && BT_Text != nullptr)
		{
			static const size_t MAX_TEMP_LEN = 910;
			if (tempString->length() > MAX_TEMP_LEN)
			{
				// Keep the most recent MAX_TEMP_LEN characters instead of wiping the whole
				// trace -- a truncated-but-useful log beats a silently blank one. Drop up to
				// the first newline inside that window so the kept text starts on a clean
				// entry boundary (AddNodeExcute terminates every entry with "\n") rather than
				// mid-line.
				size_t start = tempString->length() - MAX_TEMP_LEN;
				size_t firstNewline = tempString->find('\n', start);
				if (firstNewline != std::string::npos && firstNewline + 1 < tempString->length())
				{
					start = firstNewline + 1;
				}
				tempString->erase(0, start);
			}

			BT_Text->clear();

			BT_Text->append((*tempString));
			tempString->clear();
		}
	}

	double ClaimManeuverPhase(CPPBlackBoard* BB, ManeuverID id, double staleAfterSeconds)
	{
		if (BB->ActiveManeuverID != id)
		{
			BB->ActiveManeuverID = id;
			BB->ActiveManeuverStartTime = BB->RunningTime;
			// Latch the turn direction for the life of this claim -- see ManeuverTurnDir's
			// comment in CPPBlackBoard.h for why a sustained turn cannot re-derive it per tick.
			BB->ManeuverTurnDir = ShorterTurnDirection(BB);
			return 0.0;
		}

		double elapsed = BB->RunningTime - BB->ActiveManeuverStartTime;
		if (elapsed > staleAfterSeconds)
		{
			BB->ActiveManeuverStartTime = BB->RunningTime;
			// A stale reset restarts the maneuver's phase clock, so it restarts the latch too:
			// the node is about to re-run its phase 0, and holding a direction chosen from
			// geometry 20 s stale would be worse than re-deriving it from the current picture.
			BB->ManeuverTurnDir = ShorterTurnDirection(BB);
			return 0.0;
		}

		return elapsed;
	}

	void ReleaseManeuverPhase(CPPBlackBoard* BB, ManeuverID id)
	{
		if (BB->ActiveManeuverID == id)
		{
			BB->ActiveManeuverID = Maneuver_None;
		}
	}

	void ReleaseManeuverPhaseWithCooldown(CPPBlackBoard* BB, ManeuverID id, double cooldownSeconds)
	{
		ReleaseManeuverPhase(BB, id);
		if (id > Maneuver_None && id < Maneuver_Count)
		{
			BB->ManeuverCooldownUntil[id] = BB->RunningTime + cooldownSeconds;
		}
	}

	bool IsManeuverOnCooldown(CPPBlackBoard* BB, ManeuverID id)
	{
		if (id <= Maneuver_None || id >= Maneuver_Count)
		{
			return false;
		}
		return BB->RunningTime < BB->ManeuverCooldownUntil[id];
	}

	Vector3 PredictedTargetTravel(CPPBlackBoard* BB)
	{
		float leadTime = 0.0f;
		if (BB->MySpeed_MS > 1.0f)
		{
			leadTime = BB->Distance / BB->MySpeed_MS;
		}
		if (leadTime > 4.0f)
		{
			leadTime = 4.0f;
		}
		return BB->TargetForwardVector * BB->TargetSpeed_MS * leadTime;
	}

	Vector3 ShorterTurnDirection(CPPBlackBoard* BB)
	{
		Vector3 toTarget = BB->TargetLocaion_Cartesian - BB->MyLocation_Cartesian;
		Vector3 dir = BB->MyUpVector.cross(toTarget);
		// dir is one of the two directions perpendicular to the line-of-sight; canonicalize
		// against MyForwardVector (not MyRightVector) so we keep whichever of dir/-dir needs
		// the smaller heading change from where the nose is already pointed -- that's the
		// "shorter turn" this function is named for. Dotting against MyRightVector instead is a
		// scalar-triple-product identity for toTarget's fore/aft component, not its left/right
		// component, so it could never tell a left-offset target from a right-offset one.
		if (dir.dot(BB->MyForwardVector) < 0.0)
		{
			dir = -dir;
		}

		// DEGENERATE CASE (2026-09-08). |MyUpVector x toTarget| -> 0 when the LOS is parallel to
		// MyUpVector, i.e. the bandit is directly above or below -- entirely plausible in a steep
		// descending spiral with an attacker in the vertical. Vector3::normalize() is a silent
		// NO-OP on a near-zero vector (Vector3.h: it skips the divide when Equals(0.0, length())),
		// so it would return the near-zero vector unchanged and every caller would then add
		// ~nothing to its aim point. For Task_DefensiveSpiral that yields an aim point ~900 m
		// straight down at 10% throttle. Fall back to the wing line, which is a real turn
		// direction and is what "turn hardest away from a threat directly above/below" means.
		if (dir.length() < 1e-6)
		{
			dir = BB->MyRightVector;
		}

		dir.normalize();
		return dir;
	}

	Vector3 LatchedTurnDirection(CPPBlackBoard* BB, ManeuverID id)
	{
		// The latch is written by ClaimManeuverPhase, which every phased node calls before it
		// aims. If some other maneuver owns the slot the latch is not ours, so fall back to the
		// live value rather than steering on a direction picked for a different maneuver.
		if (BB->ActiveManeuverID != id)
		{
			return ShorterTurnDirection(BB);
		}
		return BB->ManeuverTurnDir;
	}

}