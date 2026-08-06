#include "Controller_CY.h"
#include <math.h>

// Sample count for GetLOSErrorSUM's rolling LOS-error mean. Was an untied literal 60 in three
// places (constructor pre-fill, the % index, and the divisor); they silently disagreed once the
// buffer grew, which is the bug documented in GetLOSErrorSUM below.
static const int ERROR_SUM_WINDOW = 60;
float clamp(float input, float RangeDown, float RangeUp)
{
	if (input <= RangeDown)
	{
		return RangeDown;
	}
	else if (input >= RangeUp)
	{
		return RangeUp;
	}
	else
	{
		return input;
	}
}

StickController::StickController()
{
	SumCount = 0;
	for (int i = 0; i < RUDDER_FILTER_WINDOW; i++)
		MF[i] = 0;
	FilterIndex = 0;
	
	for (int i = 0; i < ERROR_SUM_WINDOW; i++)
		ErrorSum.push_back(0.0f);
}

float StickController::GetLOSErrorSUM(float LOSError)
{
	// 2026-08-05 (second fix, same day): the buffer was GROWING past its intended 60 samples and
	// permanently poisoning this average with episode-opening error.
	//
	// The constructor already pre-fills ErrorSum with 60 zeros. The old code then did
	// `if (SumCount < 60) ErrorSum.push_back(...)` for the first 59 calls, growing the vector to
	// 119. From call 60 on it wrote only `ErrorSum[SumCount % 60]`, i.e. indices 0..59 -- so
	// indices 60..118 kept the first 59 samples of the episode FOREVER. The sum then ran over
	// all 119 entries but divided by 60.
	//
	// Net effect: a permanent constant bias equal to (59 opening samples)/60. In the OBFM start
	// geometry (~4.6 deg opening ATA) that is ~4.5, so the only consumer --
	// `clamp(GetLOSErrorSUM(LOS)/7.5, 0, 0.25)` in GetStick -- computed 4.5/7.5 = 0.6 and sat
	// PINNED at its 0.25 cap from the first second onward, regardless of the actual current
	// error. The "integral" term carried no information and the controller could never unwind
	// its own bias, which is exactly the documented "static ~4.5 deg pointing error / 0 WEZ".
	//
	// This also explains why both earlier same-day attempts failed: the int->float truncation fix
	// (kept, still correct) could not help a term already saturated by frozen history, and
	// widening the cap 0.25 -> 0.6 only scaled the constant bias up, producing the windup/
	// overshoot that got it reverted.
	//
	// Fixed by writing cyclically from the very first call (never growing) and dividing by the
	// buffer's true size, so this is a genuine 60-sample rolling mean of RECENT error that decays
	// toward 0 as the aim converges.
	ErrorSum[SumCount % ERROR_SUM_WINDOW] = (LOSError <= 10.0f) ? LOSError : 0.0f;
	SumCount++;

	float sum = 0.0f;   // 2026-08-05: was int -> `sum += ErrorSum[i]` truncated every sub-1-deg LOS to 0, killing near-target integral action.

	for (size_t i = 0; i < ErrorSum.size(); i++)
	{
		sum += ErrorSum[i];
	}

	float Re = sum / (float)ErrorSum.size();   // 2026-08-05: was `sum / 60` int division, and 60 was the WRONG count once the buffer had grown to 119.

	return Re;
}

StickValue StickController::GetStick(Vector3 MyLocation_FNED, Vector3 MyRotation_FNED, Vector3 VP)
{
	Vector3 Mylocation(MyLocation_FNED.X, MyLocation_FNED.Y, MyLocation_FNED.Z);
	Vector3 TargetLocation(VP.X, VP.Y, VP.Z);

	//오일러 각을 입력. 이 부분은 언리얼4의 각도를 회사의 ECEF_LLA_Converter 쪽의 각도와 함수들을 이용하기 위해 이쪽 양식에 맞추는 과정
	EulerAngle EA;
	EA.Roll = MyRotation_FNED.X;
	EA.Pitch = MyRotation_FNED.Y;
	EA.Yaw = MyRotation_FNED.Z;

	//오일러각을 이용하면 축변화에 따른 오차가 생기기 때문에 쿼터니언으로 변환하여 사용
	Quaternion QU = EA.toQuaternion();

	//쿼터니언을 이용하여 전방벡터(ForwardVector)를 생성 
	Vector3 ForwardVector;
	ForwardVector.X = 1 - 2 * (QU.X * QU.X + QU.Y * QU.Y);
	ForwardVector.Y = 2 * (QU.X * QU.Z + QU.W * QU.Y);
	ForwardVector.Z = -2 * (QU.Y * QU.Z - QU.W * QU.X);

	//쿼터니언을 이용하여 수직벡터(UpVector)를 생성 
	Vector3 UpVector;
	UpVector.X = -2 * (QU.Y * QU.Z + QU.W * QU.X);
	UpVector.Y = -2 * (QU.X * QU.Y - QU.W * QU.Z);
	UpVector.Z = 1 - 2 * (QU.X * QU.X + QU.Z * QU.Z);

	//쿼터니언을 이용하여 오른쪽벡터(RightVector)를 생성 
	Vector3 RightVector;
	RightVector.X = 2 * (QU.X * QU.Z - QU.W * QU.Y);
	RightVector.Y = 1 - 2 * (QU.Y * QU.Y + QU.Z * QU.Z);
	RightVector.Z = -2 * (QU.X * QU.Y + QU.W * QU.Z);


	Vector3 ForwardVectorPoint = ForwardVector * 1000 + Mylocation;

	Vector3 ForwardVectorPoint2VP = TargetLocation - ForwardVectorPoint;

	Vector3 Proj_V = (ForwardVectorPoint2VP.dot(ForwardVector)) * ForwardVector;

	Vector3 Proj_P = TargetLocation - Proj_V;
	Vector3 Proj_TV = Proj_P - ForwardVectorPoint;

	// 롤커멘드 생성 부분

	float UpVector2Proj_TV_Angle = std::acos(UpVector.dot(Proj_TV / Proj_TV.length()));
	float UTAngle;
	float LOS = std::acos(ForwardVector.dot((TargetLocation - Mylocation)) / (TargetLocation - Mylocation).length()) * RADTODEG;

	if (_isnan(UpVector2Proj_TV_Angle) != 0)
	{
		UpVector2Proj_TV_Angle = 0;
	}

	// MOVED UP 2026-08-06 (was ~45 lines below, after the roll branch). LOS is first CONSUMED by
	// `if (LOS > 3)` in the |UTAngle| > 90 branch; a NaN LOS makes that compare false, so control
	// fell into `RollCMD = RollCMD * LOS * (-0.1)` and RollCMD became NaN. The guard then set
	// LOS = 0 far too late to help, and clamp() propagates NaN unchanged (both comparisons are
	// false for NaN, so it returns `input`), meaning NaN reached Result.RollCMD. Only Python's
	// nan_to_num in clip_action was catching it. Latent -- LOS comes from an unclamped
	// std::acos(dot/len) that can exceed +/-1 on rounding -- so the ordering matters even though
	// no NaN has been observed in eval. Pure ordering fix: identical behaviour when LOS is finite.
	if (_isnan(LOS) != 0)
	{
		LOS = 0;
	}

	float Proj_TV_Length = Proj_TV.length();

	if(Proj_TV_Length <= 0)
	{
		Proj_TV_Length = 0.0001;
	}

	if (RightVector.dot(Proj_TV / Proj_TV_Length) >= 0)
	{
		UTAngle = UpVector2Proj_TV_Angle;
	}
	else
	{
		UTAngle = UpVector2Proj_TV_Angle * (-1);
	}

	float RollCMD;

	if (std::abs(UTAngle * RADTODEG) > 90)
	{
		RollCMD = (std::sin(UTAngle) * 1);

		if (LOS > 3)
			RollCMD = clamp(RollCMD, -1, 1);
		else
			RollCMD = RollCMD * LOS * (-0.1);
	}
	else
	{
		RollCMD = (std::sin(UTAngle) * 1.0);

		RollCMD = clamp(RollCMD, -1, 1);

		RollCMD = RollCMD * std::abs(RollCMD);
	}


	// (LOS NaN guard moved ABOVE the roll branch 2026-08-06 -- see the note there.)

	// SMALL-COMMAND BOOST. Counteracts the `RollCMD * abs(RollCMD)` squaring above, which crushes
	// small lateral corrections (UTAngle 5 deg -> sin 0.087 -> 0.0076, an 11x reduction).
	//
	// `RollCMD < 0.1` IS SIGN-ASYMMETRIC AND THAT IS LOAD-BEARING -- DO NOT "FIX" IT TO abs().
	//
	// The condition is true for EVERY negative RollCMD and only for positives below 0.1, so a left
	// roll of -0.5 is boosted to -1.5 while an equal right roll of +0.5 is untouched. That is
	// almost certainly not the original intent (the boost exists to lift SMALL commands, and -0.5
	// is not small) -- but changing it to `std::abs(RollCMD) < ROLL_BOOST_THRESHOLD` was TRIED
	// 2026-08-06 and REVERTED on measurement:
	//
	//     asymmetric (as written)  rate 8/20 40%   attractor 1.0070 (sd 0.0027)
	//     std::abs() "fix"         rate 8/20 40%   attractor 1.2116 (sd 0.0060)   <-- 0.20 deg WORSE
	//
	// Reason: the asymmetry effectively acts as a 3x boost on all large NEGATIVE roll commands, so
	// removing it strips real roll authority. The regression is ~30x the sd -- unambiguous. The
	// useful signal is the SIGN of that result: adding roll authority helps, removing it hurts,
	// which independently supports the roll-taper hypothesis (see ROLL_TAPER_CEIL below). Prefer
	// adding authority deliberately there over "correcting" this line.
	//
	// Constants named 2026-08-06: this file has produced three bugs from untied inline literals
	// (ERROR_SUM_WINDOW's bare 60s, MFsum's bare 20s, and the roll magic numbers here).
	static const float ROLL_BOOST_THRESHOLD = 0.1f;
	static const float ROLL_BOOST_GAIN = 3.0f;
	// ROLL AUTHORITY TAPER -- `RollCMD *= clamp(LOS, FLOOR, CEIL)`. At LOS >= CEIL the factor is 1
	// (no attenuation); below it, roll authority scales DOWN linearly with the pointing error.
	//
	// Why FLOOR exists (added 2026-08-06): with FLOOR=0 the taper drives roll authority to ZERO as
	// LOS -> 0, i.e. the controller progressively stops being able to correct exactly in the region
	// it must enter to score. The knee sits at 1.0 deg and, after the MFsum fix removed the rudder
	// constraint, the tracking attractor landed at 1.0070 deg -- ON the knee. The convergence
	// history reads as: rudder-limited at 1.038 -> fix rudder -> converge onto the NEXT limiter and
	// stall there. S1's result points the same way from the opposite direction: accidentally
	// REMOVING roll authority cost 0.20 deg, so authority on this axis is the binding resource.
	//
	// SWEPT 2026-08-06 AND RULED OUT -- FLOOR IS NOT LIVE AT THE OPERATING POINT. N=20 per arm:
	//
	//     FLOOR 0.00 (original)  rate 8/20   attractor 1.0052 (sd 0.0030)
	//     FLOOR 0.25             rate 7/20   attractor 1.0062 (sd 0.0017)
	//     FLOOR 0.50             rate 8/20   attractor 1.0056 (sd 0.0021)
	//
	// All three inside one sd. The arithmetic explains it: clamp(LOS, FLOOR, CEIL) with
	// LOS = 1.006 > CEIL = 1.0 returns CEIL for ANY floor <= CEIL, so the floor cannot bind until
	// LOS is already under 1.0 -- i.e. until after we have already scored. Chicken-and-egg: the
	// taper is simply INACTIVE at the attractor (factor == 1.0) and therefore is not the limiter.
	// Same error class as INTEGRAL_CAP -- a knob that is not live where it matters. Restored to
	// 0.0f (original behaviour), left named for clarity.
	//
	// WHAT THIS LEAVES: at LOS ~= 1.006 the roll taper contributes 1.0 (inactive), but the RUDDER
	// taper clamp(LOS, 0, RUDDER_TAPER_CEIL) is still at 1.006/6 = 16.8% of nominal -- that one IS
	// active, and is the remaining lateral attenuation. See RUDDER_TAPER_CEIL below.
	static const float ROLL_TAPER_CEIL = 1.0f;
	static const float ROLL_TAPER_FLOOR = 0.0f;

	if (RollCMD < ROLL_BOOST_THRESHOLD)   // deliberately NOT abs() -- see the note above
		RollCMD = RollCMD * ROLL_BOOST_GAIN;

	RollCMD = RollCMD * clamp(LOS, ROLL_TAPER_FLOOR, ROLL_TAPER_CEIL);
	//러더 커맨드 생성 부분
	float RudderCMD = 0;

	// RUDDER AUTHORITY TAPER. Unlike the roll taper (ROLL_TAPER_CEIL above, swept and found
	// INACTIVE at the attractor because LOS > its ceiling), this one IS live at the operating
	// point: at LOS ~= 1.006 the factor is 1.006/6 = 16.8% of nominal. After the MFsum fix
	// restored the moving average, this is the dominant remaining attenuation on the lateral
	// axis -- the axis the MFsum result proved the residual error lives on.
	// SWEPT 2026-08-06 AND RULED OUT -- MORE AUTHORITY HERE IS WORSE, MONOTONICALLY. N=20 per arm
	// (lower ceiling == more near-target authority, since LOS >= ceil saturates to 1.0 either way):
	//
	//     CEIL 6.0 (original)  16.8% at LOS 1.0   attractor 1.0064 (sd 0.0017)
	//     CEIL 3.0             33.5%              attractor 1.0540 (sd 0.0024)
	//     CEIL 1.5             67%                attractor 1.1107 (sd 0.0027)
	//
	// Read together with the MFsum result (which DOUBLED rudder authority, 8.7% -> 16.8%, and
	// improved the attractor 1.038 -> 1.007) this says there is an OPTIMUM and the MFsum fix
	// landed near it: too little authority and the error cannot be nulled, too much and the
	// lateral axis overshoots. Kept at 6.0f.
	static const float RUDDER_TAPER_CEIL = 6.0f;
	RudderCMD = -std::sin(UTAngle) * clamp(LOS, 0, RUDDER_TAPER_CEIL) * 1;

	MF[FilterIndex % RUDDER_FILTER_WINDOW] = RudderCMD;
	FilterIndex++;

	// 2026-08-06: MFsum was `int`, which broke this moving-average filter completely.
	//
	// `MFsum += MF[i]` expands to `MFsum = (int)(MFsum + MF[i])`, so the fraction was discarded on
	// EVERY one of the 20 iterations -- not once at the end. For any |MF[i]| < 1.0 the accumulator
	// therefore never left zero (verified across the real value range: 0.15/0.30/0.52/0.90 all
	// yield exactly 0). The divisor `MFsum / 20` was integer division as well, so even a surviving
	// sum needed |MFsum| >= 20 to contribute anything.
	//
	// Why that mattered here specifically: RudderCMD = -sin(UTAngle) * clamp(LOS, 0, 6), so at the
	// documented 1.038 deg tracking attractor |RudderCMD| <= 1.038 -- every MF[] entry sat inside
	// the dead band. This line reduced to exactly `RudderCMD = RudderCMD / 2`: the moving average
	// (the entire purpose of MF[] and FilterIndex) contributed NOTHING and its only surviving
	// effect was halving rudder. Compounded with the clamp(LOS,0,6) taper (0.173 at that LOS),
	// rudder authority at the attractor was ~8.7% of nominal -- a concrete candidate for why a
	// residual lateral error could not be nulled, and consistent with the INTEGRAL_DIV sweep's
	// null result (pitch gain cannot fix an error the lateral axis lacks authority to remove).
	//
	// Correctness fix, but its CONSEQUENCE is a control change (~2x rudder authority in steady
	// state, since the average converges to RudderCMD). Revert = restore `int MFsum` and
	// `MFsum / 20`.
	//
	// MEASURED (N=20 per arm, BT vs non-maneuvering target, identical seed/scenario):
	//
	//                     converging rate   attractor (sd)     gap to 1.000   dwell <=2 deg
	//   int MFsum   (old)     7/20  35%     1.0380 (0.0024)      +0.0380         84 steps
	//   float MFsum (new)     8/20  40%     1.0070 (0.0027)      +0.0070         96 steps
	//
	// The attractor moved 1.038 -> 1.007, closing ~82% of the standing pointing gap, with the
	// converging-mode rate slightly UP (so no destabilization from the added authority) and more
	// dwell inside 2 deg. With sd ~0.0025 over 7-8 samples the standard error is ~0.001, so a
	// 0.031 shift is ~30 SE -- not noise, even on this bimodal harness.
	//
	// This is the FIRST change all session to move the attractor at all: both pitch-side knobs
	// (INTEGRAL_CAP, INTEGRAL_DIV -- see their sweep results below) moved it by less than one sd.
	// That asymmetry is itself the finding: the residual pointing error lives on the LATERAL axis,
	// not the pitch axis. Still 0 steps at <=1.0 deg, so still no WEZ -- the remaining 0.007 deg
	// is the next target, and the prime suspect is the surviving lateral attenuation on the two
	// lines above (RollCMD * clamp(LOS,0,1) and RudderCMD's clamp(LOS,0,6) taper, which alone is
	// 0.173 at this LOS).
	float MFsum = 0.0f;
	for (int i = 0; i < RUDDER_FILTER_WINDOW; i++)
		MFsum += MF[i];
	RudderCMD = (MFsum / (float)RUDDER_FILTER_WINDOW + RudderCMD) / 2;

	//피치 커맨드 생성 부분
	float PitchCMD = 0;;

	// PITCH-ERROR GAIN CONSTANTS -- history matters here, read before touching.
	//
	// 2026-08-05 (first attempt): INTEGRAL_CAP widened 0.25 -> 0.6, REVERTED after a 20-episode
	// mirror sweep showed 0% WEZ-contact. Read at the time: the int->float truncation fix had
	// "unlocked real integral authority" and a 2.4x wider cap on top caused windup.
	//
	// 2026-08-05 (later): that read was wrong about the mechanism. GetLOSErrorSUM was ALSO
	// returning a frozen ~4.5 constant (ring-buffer bug, fixed in the same session -- see its own
	// comment), so the term being widened was a CONSTANT BIAS, not an error signal; widening it
	// only added constant nose-down authority, which is the windup that was observed.
	//
	// 2026-08-05 (harness bisect): what looked like unrepeatable noise across single-episode runs
	// turned out to be a strict BIMODAL split, not noise -- 9 runs of --episodes 1 --seed 0 on an
	// md5-identical DLL gave ATA-min clustered at 1.034-1.041 deg (4/9) or 4.398-4.406 deg (5/9),
	// nothing between, despite spawn ATA varying only ~0.017 deg. Source is inside JSBSimAIPLib.dll
	// (protected, no source) -- perfect determinism is unachievable, so the harness now recycles
	// the native BT between episodes (scripts/eval_v5_vs_bt.py's _recycle_native_bts(), 2026-08-05)
	// for episode INDEPENDENCE and reports the converging-mode RATE + attractor mean, never a
	// single-episode point value. Baseline (N=20, BT vs non-maneuvering target): converging-mode
	// rate 35% (7/20), attractor mean 1.038 deg (sd 0.0024) -- i.e. the tight cluster this file's
	// history called "1.033 deg" is real and reproducible; the 4.4 deg cluster is a distinct
	// non-converging mode, not scatter around the first.
	//
	// THIS MATTERS FOR THIS LINE SPECIFICALLY: at the 1.038 deg attractor,
	// GetLOSErrorSUM(LOS) ~= 1.038, so the integral term is 1.038/INTEGRAL_DIV = 0.138 -- WELL
	// UNDER INTEGRAL_CAP (0.25), i.e. NOT clamped at the attractor. The cap only binds above
	// ~1.9 deg error, where the proportional term already dominates. Raising INTEGRAL_CAP therefore
	// cannot move this attractor at all, which is exactly why both the 0.25->0.6 attempt and the
	// once-noise-contaminated cap sweep read as "no effect" -- they were tuning a knob that isn't
	// live at the operating point that matters. THE LIVE KNOB HERE IS INTEGRAL_DIV.
	//
	// Named 2026-08-05 (was three untied literals inline -- the same pattern that caused the
	// ERROR_SUM_WINDOW bug, where three copies of a bare "60" silently disagreed).
	// SWEEP RESULT 2026-08-05 -- INTEGRAL_DIV IS ALSO RULED OUT. Swept 7.5 / 6.0 / 5.0 / 4.5,
	// N=16 episodes per arm on the now-independent harness (values chosen so INTEGRAL_CAP stays
	// non-binding at the attractor; below ~4.15 it would clamp and every arm would be identical):
	//
	//   DIV 7.5 -> rate 5/16, attractor 1.0388 (sd 0.0021)
	//   DIV 6.0 -> rate 6/16, attractor 1.0389 (sd 0.0020)
	//   DIV 5.0 -> rate 6/16, attractor 1.0377 (sd 0.0030)
	//   DIV 4.5 -> rate 6/16, attractor 1.0381 (sd 0.0024)
	//
	// A 67% gain increase (integral term 0.138 -> 0.231 at the attractor, a real swing) moved the
	// steady-state ATA by less than one standard deviation. So BOTH pitch-error knobs are dead
	// ends for the 0.038 deg gap: neither the cap (not binding) nor the gain (no response).
	//
	// NEXT HYPOTHESIS, from the formula rather than from measurement:
	// PitchCMD = ERROR_Effect * Roll_Effect * Horizon_Effect, a PRODUCT, where
	// Roll_Effect = 1 - clamp(|UTAngle|*RADTODEG / 90, 0, 1). If at the attractor the residual
	// error lies mostly out of the pitch plane (|UTAngle| near 90 deg), Roll_Effect ~ 0 and
	// ERROR_Effect is multiplied by ~nothing -- which would produce exactly the flat response
	// measured above. That points at the ROLL/YAW path (RollCMD's `clamp(LOS,0,1)` scaling and its
	// `LOS > 3` / `RollCMD < 0.1` branches, and the inert rudder filter noted at MFsum above),
	// NOT at this pitch expression. UNVERIFIED: confirming it needs UTAngle/RollCMD/Roll_Effect
	// logged per tick, which the Python-side trace cannot see (it only reads the geometry module's
	// ATA). Instrument the C++ side before spending further effort here.
	static const float PROPORTIONAL_DIV = 6.0f;   // LOS / PROPORTIONAL_DIV -- untested
	static const float INTEGRAL_DIV = 7.5f;       // swept, NO effect on the attractor (see above)
	static const float INTEGRAL_CAP = 0.25f;      // NOT binding at the 1.038 deg attractor -- do not expect this to move it
	float ERROR_Effect = clamp(LOS / PROPORTIONAL_DIV + clamp(GetLOSErrorSUM(LOS) / INTEGRAL_DIV, 0, INTEGRAL_CAP), 0, 1.5);
	//float ERROR_Effect = clamp(LOS / PROPORTIONAL_DIV, 0, 1.5);


	float Roll_Effect = 1 - clamp(std::abs(UTAngle * RADTODEG) / 90, 0, 1);

	float Horizon_Effect;
	if (std::abs(UTAngle * RADTODEG) <= 90)
	{
		Horizon_Effect = 1;
	}
	else
		Horizon_Effect = 0.5;

	//std::cout << "ERROR_Effect : " << ERROR_Effect << " Roll_Effect : " << Roll_Effect << " Horizon_Effect : " << Horizon_Effect << std::endl;

	if (LOS < 90)
		PitchCMD = ERROR_Effect * Roll_Effect * Horizon_Effect * (-1);//+Roll_Effect2;
	else
		PitchCMD = -1;

	StickValue Result;
	Result.RollCMD = clamp(RollCMD, -1, 1);
	Result.PitchCMD = clamp(PitchCMD, -1, 1);
	Result.RudderCMD = clamp(RudderCMD, -1, 1);
	//Result.RudderCMD = RudderCMD;
	return Result;
}
