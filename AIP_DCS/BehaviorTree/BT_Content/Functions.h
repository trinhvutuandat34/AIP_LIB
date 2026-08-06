#pragma once
#include "../../Geometry/Vector3.h"
#include "../../Geometry/EulerAngle.h"
#include "../../Geometry/Quaternion.h"
#include <vector>
#include "BlackBoard/CPPBlackBoard.h"

using namespace BT_Geometry;

namespace BTFunc
{
	/*
	국과연에서 요구한 비헤비어트리 결정 과정을 보여주기 위해 각 노드에서 실행 과정(결과)를 문자열로 저장하기 위한 함수
	기존 문자열, 추가할 문자열
	*/
	void AddNodeExcute(std::string * out, std::string input);
	void SaveTextData(std::string * tempString, std::string * BT_Text);

	// Claims BB->ActiveManeuverID/ActiveManeuverStartTime for `id` (restamping if a different
	// maneuver last held it) and returns elapsed time since the claim. Self-heals a stale claim
	// left behind by a silent exit -- e.g. an XML-level Decorator gate stops reaching the node
	// that held `id` before it gets a final tick to release cleanly (see ReleaseManeuverPhase) --
	// once elapsed exceeds staleAfterSeconds, treating it as a fresh claim instead of resuming a
	// bogus multi-minute elapsed count.
	double ClaimManeuverPhase(CPPBlackBoard* BB, ManeuverID id, double staleAfterSeconds);

	// Releases a maneuver claim early (abort / goal-met exit) so the next trigger of the SAME
	// maneuver starts a fresh phase timer instead of resuming the old one.
	void ReleaseManeuverPhase(CPPBlackBoard* BB, ManeuverID id);

	// ReleaseManeuverPhase + arm this maneuver's re-entry cooldown in one call, for the
	// "time-cap / abort exit, don't let it immediately re-claim" pattern (Task_Evade,
	// Task_VerticalScissors). Pairs with IsManeuverOnCooldown below -- callers should not read or
	// write BB->ManeuverCooldownUntil[] directly.
	void ReleaseManeuverPhaseWithCooldown(CPPBlackBoard* BB, ManeuverID id, double cooldownSeconds);

	// True while `id` is still within its armed cooldown window. Intended to gate a FRESH claim
	// only -- an already-active maneuver should keep running, so the usual call site is
	// `if (!active && IsManeuverOnCooldown(BB, id)) return FAILURE;`.
	bool IsManeuverOnCooldown(CPPBlackBoard* BB, ManeuverID id);

	// Target's predicted travel over the estimated closing time (Distance / MySpeed, capped at
	// 4s -- past a few seconds the target's current heading stops being a good predictor: it may
	// turn, and an uncapped lead can throw the aim off further than pure pursuit would at long
	// range). Lead pursuit aims at TargetLocaion + travel, lag pursuit at TargetLocaion - travel.
	Vector3 PredictedTargetTravel(CPPBlackBoard* BB);

	// Unit vector perpendicular to the line-of-sight to the target, on whichever side is the
	// shorter turn from current heading (MyUpVector x toTarget, flipped to agree with
	// MyRightVector) -- not an arbitrary fixed handedness that might demand a near-180 reversal.
	Vector3 ShorterTurnDirection(CPPBlackBoard* BB);

}