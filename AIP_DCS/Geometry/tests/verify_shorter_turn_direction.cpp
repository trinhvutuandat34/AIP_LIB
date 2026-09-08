// Standalone regression check for BTFunc::ShorterTurnDirection (BehaviorTree/BT_Content/Functions.cpp).
//
// Build (from AIP_DCS/). NOTE: no -I/Geometry -- see the include block below for why that
// breaks on Windows.
//
//   MSVC (what this box has; run inside a vcvars64 shell):
//     cl /nologo /EHsc /std:c++17 Geometry\tests\verify_shorter_turn_direction.cpp ^
//       Geometry\Vector3.cpp Geometry\Vector4.cpp Geometry\Quaternion.cpp Geometry\Matrix4.cpp ^
//       Geometry\Matrix3.cpp Geometry\Math.cpp Geometry\EulerAngle.cpp ^
//       Geometry\CoordinateConverter.cpp Geometry\AxisAngle.cpp Geometry\Angle.cpp ^
//       /Fe:verify_shorter_turn_direction.exe
//
//   g++:
//     g++ -std=c++17 Geometry/tests/verify_shorter_turn_direction.cpp \
//       Geometry/Vector3.cpp Geometry/Vector4.cpp Geometry/Quaternion.cpp Geometry/Matrix4.cpp \
//       Geometry/Matrix3.cpp Geometry/Math.cpp Geometry/EulerAngle.cpp Geometry/CoordinateConverter.cpp \
//       Geometry/AxisAngle.cpp Geometry/Angle.cpp -o /tmp/verify_shorter_turn_direction
//
//   Either way it exits 0 and prints ALL CHECKS PASSED.
//
// This links against the project's real Geometry/Vector3.{h,cpp} (and EulerAngle/Quaternion for
// the rotated-aircraft case) so the math is exactly what AIP_DCS.dll uses -- not a
// hand-reimplementation. It cannot run the actual JSBSim/BT simulation (Windows-only binaries),
// so this is a geometric-correctness check of the isolated function, not a match-outcome
// measurement -- run the peer-rig eval (see DogFightEnv HANDOFF.md) for that.
#include <cstdio>
#include <cmath>
// Relative, and deliberately NOT via -I/Geometry. On a case-insensitive filesystem (i.e. every
// Windows box this project is built on) putting Geometry/ on the include path makes <cmath>'s
// own `#include <math.h>` resolve to Geometry/Math.h, and the CRT math declarations then never
// appear -- MSVC fails with a wall of "'remquof': identifier not found" inside <cmath>. The
// documented g++ line works only because it was run somewhere case-sensitive.
#include "../Vector3.h"
#include "../EulerAngle.h"
#include "../Quaternion.h"

using namespace BT_Geometry;

// Exact copy of the pre-fix logic from Functions.cpp (git history), parameterized.
static Vector3 OldShorterTurnDirection(const Vector3& F, const Vector3& R, const Vector3& U, const Vector3& toTarget)
{
    Vector3 dir = U.cross(toTarget);
    if (dir.dot(R) < 0.0)
    {
        dir = -dir;
    }
    dir.normalize();
    return dir;
}

// Exact copy of the post-fix logic now in Functions.cpp, parameterized.
static Vector3 NewShorterTurnDirection(const Vector3& F, const Vector3& R, const Vector3& U, const Vector3& toTarget)
{
    Vector3 dir = U.cross(toTarget);
    if (dir.dot(F) < 0.0)
    {
        dir = -dir;
    }
    // Mirrors the 2026-09-08 degenerate guard in Functions.cpp: |U x toTarget| -> 0 when the
    // bandit is directly above or below, and Vector3::normalize() is a silent no-op on a
    // near-zero vector, so without this the function returns ~(0,0,0) and every caller adds
    // nothing to its aim point. Keep this copy in step with the real one.
    if (dir.length() < 1e-6)
    {
        dir = R;
    }
    dir.normalize();
    return dir;
}

// Ground truth: of {P, -P} where P is perpendicular to toTarget, the "shorter turn" is whichever
// is closer (larger dot) to the current forward vector -- an exhaustive check that doesn't reuse
// either implementation's canonicalization axis.
static Vector3 BruteForceShorterTurn(const Vector3& F, const Vector3& U, const Vector3& toTarget)
{
    Vector3 P = U.cross(toTarget);
    P.normalize();
    return (P.dot(F) >= (-P).dot(F)) ? P : (-P);
}

static const char* sideLabel(double rComponent)
{
    if (rComponent > 1e-6) return "RIGHT";
    if (rComponent < -1e-6) return "LEFT";
    return "AMBIGUOUS(on nose/tail)";
}

static int g_fail = 0;

static void check(bool cond, const char* what)
{
    printf("  [%s] %s\n", cond ? "PASS" : "FAIL", what);
    if (!cond) g_fail++;
}

static void runCase(const char* label, const Vector3& F, const Vector3& R, const Vector3& U, const Vector3& toTarget)
{
    printf("== %s ==\n", label);
    printf("  toTarget = (%.3f, %.3f, %.3f)\n", toTarget.X, toTarget.Y, toTarget.Z);

    Vector3 oldDir = OldShorterTurnDirection(F, R, U, toTarget);
    Vector3 newDir = NewShorterTurnDirection(F, R, U, toTarget);
    Vector3 truth  = BruteForceShorterTurn(F, U, toTarget);

    double oldR = oldDir.dot(R);
    double newR = newDir.dot(R);
    double truthR = truth.dot(R);

    printf("  old: dir=(%.3f,%.3f,%.3f) R-comp=%.3f -> %s\n", oldDir.X, oldDir.Y, oldDir.Z, oldR, sideLabel(oldR));
    printf("  new: dir=(%.3f,%.3f,%.3f) R-comp=%.3f -> %s\n", newDir.X, newDir.Y, newDir.Z, newR, sideLabel(newR));
    printf("  brute-force ground truth: R-comp=%.3f -> %s\n", truthR, sideLabel(truthR));

    // The fix must agree with the brute-force "closer to current forward" ground truth.
    char msg[128];
    snprintf(msg, sizeof(msg), "%s: new implementation matches brute-force ground truth", label);
    check(newDir.distance(truth) < 1e-6, msg);
}

int main()
{
    // --- Case set A: identity orientation (F,R,U) = ((1,0,0),(0,1,0),(0,0,1)), the exact basis
    // DirectionVectorUpdate.cpp produces at the identity quaternion, and the one the code review
    // used to demonstrate the bug.
    Vector3 F(1, 0, 0), R(0, 1, 0), U(0, 0, 1);

    runCase("A1: near head-on, target slightly LEFT", F, R, U, Vector3(100, -10, 0));
    runCase("A2: near head-on, target slightly RIGHT", F, R, U, Vector3(100, 10, 0));

    printf("\n-- Old-vs-old comparison for A1/A2 (the bug) --\n");
    {
        Vector3 leftOld  = OldShorterTurnDirection(F, R, U, Vector3(100, -10, 0));
        Vector3 rightOld = OldShorterTurnDirection(F, R, U, Vector3(100, 10, 0));
        printf("  old(LEFT target)  R-comp = %.3f -> %s\n", leftOld.dot(R), sideLabel(leftOld.dot(R)));
        printf("  old(RIGHT target) R-comp = %.3f -> %s\n", rightOld.dot(R), sideLabel(rightOld.dot(R)));
        check((leftOld.dot(R) > 0) == (rightOld.dot(R) > 0),
              "confirms bug: old code picks the SAME side for a left-offset and a right-offset target");
    }
    printf("\n-- New-vs-new comparison for A1/A2 (the fix) --\n");
    {
        Vector3 leftNew  = NewShorterTurnDirection(F, R, U, Vector3(100, -10, 0));
        Vector3 rightNew = NewShorterTurnDirection(F, R, U, Vector3(100, 10, 0));
        printf("  new(LEFT target)  R-comp = %.3f -> %s\n", leftNew.dot(R), sideLabel(leftNew.dot(R)));
        printf("  new(RIGHT target) R-comp = %.3f -> %s\n", rightNew.dot(R), sideLabel(rightNew.dot(R)));
        check((leftNew.dot(R) > 0) != (rightNew.dot(R) > 0),
              "fix confirmed: new code differentiates a left-offset target from a right-offset one");
    }

    // Beam crossing sweep: exercise the exact discontinuity the review flagged (a=0 for the old
    // code, at the beam) and show the new code's transition point moves to b=0 (dead-ahead/astern)
    // instead, matching NoseToNoseTurn's own comment ("shorter turn ... from current heading").
    printf("\n-- Beam-crossing sweep (bearing from -100..+100 deg off the nose, R=100m fixed) --\n");
    for (int deg = -100; deg <= 100; deg += 5)
    {
        double rad = deg * 3.14159265358979323846 / 180.0;
        Vector3 toTarget(100.0 * std::cos(rad), 100.0 * std::sin(rad), 0.0);
        double oR = OldShorterTurnDirection(F, R, U, toTarget).dot(R);
        double nR = NewShorterTurnDirection(F, R, U, toTarget).dot(R);
        printf("  bearing=%4d deg  old R-comp=%7.3f  new R-comp=%7.3f\n", deg, oR, nR);
    }
    // Old code's sign flips at bearing +-90 (the beam); new code's flips at bearing 0 (the
    // nose/tail line) -- visible directly in the table above, and matches the analysis that
    // dotting against MyRightVector tests fore/aft (flip at the beam) while dotting against
    // MyForwardVector tests left/right (flip at dead-ahead/astern).

    // --- Case set B: a rotated aircraft (heading 40 deg, pitch 10 deg, roll 15 deg), built the
    // same way DirectionVectorUpdate.cpp derives F/R/U from a quaternion, to prove the fix isn't
    // an artifact of the trivial identity basis.
    printf("\n-- Case set B: rotated aircraft attitude (not identity) --\n");
    // EulerAngle(yaw, pitch, roll), radians -- yaw=40deg, pitch=10deg, roll=15deg.
    EulerAngle att(40.0 / 57.2958, 10.0 / 57.2958, 15.0 / 57.2958);
    Quaternion q = att.toQuaternion();
    Vector3 Fb, Rb, Ub;
    Fb.Y = 2 * (q.X * q.Z + q.W * q.Y);
    Fb.Z = -2 * (q.Y * q.Z - q.W * q.X);
    Fb.X = 1 - 2 * (q.X * q.X + q.Y * q.Y);
    Ub.X = -2 * (q.Y * q.Z + q.W * q.X);
    Ub.Y = -2 * (q.X * q.Y - q.W * q.Z);
    Ub.Z = 1 - 2 * (q.X * q.X + q.Z * q.Z);
    Rb.X = 2 * (q.X * q.Z - q.W * q.Y);
    Rb.Y = 1 - 2 * (q.Y * q.Y + q.Z * q.Z);
    Rb.Z = -2 * (q.X * q.Y + q.W * q.Z);
    printf("  F=(%.3f,%.3f,%.3f) R=(%.3f,%.3f,%.3f) U=(%.3f,%.3f,%.3f)\n",
           Fb.X, Fb.Y, Fb.Z, Rb.X, Rb.Y, Rb.Z, Ub.X, Ub.Y, Ub.Z);

    // Two targets placed symmetrically about the rotated nose (one to its left, one to its right).
    Vector3 aheadB = Fb * 1000.0;
    Vector3 targetLeftB  = aheadB - Rb * 80.0;
    Vector3 targetRightB = aheadB + Rb * 80.0;
    runCase("B1: rotated attitude, target LEFT of nose", Fb, Rb, Ub, targetLeftB);
    runCase("B2: rotated attitude, target RIGHT of nose", Fb, Rb, Ub, targetRightB);
    {
        Vector3 leftNew  = NewShorterTurnDirection(Fb, Rb, Ub, targetLeftB);
        Vector3 rightNew = NewShorterTurnDirection(Fb, Rb, Ub, targetRightB);
        check((leftNew.dot(Rb) > 0) != (rightNew.dot(Rb) > 0),
              "B: fix differentiates left/right under a non-trivial (rotated) attitude too");
    }

    // --- Case set C: THE REAR HEMISPHERE (added 2026-09-08).
    //
    // Every case above places the target in the FORWARD hemisphere. That is why nothing here
    // caught the defect that motivated the ManeuverTurnDir latch: Task_DefensiveSpiral is only
    // reachable with the bandit AFT of the 3-9 line (Gate1_JinkingTurn sits above it in the
    // Fallback and succeeds on a strict superset of its trigger), and Task_Evade's break turn is
    // flown in the same regime. The function is CORRECT there -- it agrees with brute force --
    // but it is not STABLE, and a sustained turn needs stability, not just correctness.
    printf("\n-- Case set C: rear hemisphere (what the spiral and the break actually fly) --\n");
    runCase("C1: bandit at 5 o'clock (aft, RIGHT)", F, R, U, Vector3(-100, 10, 0));
    runCase("C2: bandit at 7 o'clock (aft, LEFT)", F, R, U, Vector3(-100, -10, 0));
    {
        Vector3 aftRight = NewShorterTurnDirection(F, R, U, Vector3(-100, 10, 0));
        Vector3 aftLeft  = NewShorterTurnDirection(F, R, U, Vector3(-100, -10, 0));
        check((aftRight.dot(R) > 0) != (aftLeft.dot(R) > 0),
              "C: left/right are still differentiated with the bandit behind us");
    }

    printf("\n-- C3: the dead-six discontinuity, which is why a SUSTAINED turn must latch --\n");
    {
        // Walk the bandit across dead six one metre at a time. The commanded side is the sign of
        // (toTarget . R), so it inverts at exactly y = 0 -- no deadband, no memory of last tick.
        // In flight that is a full roll reversal driven by metre-scale jitter, which for
        // Task_DefensiveSpiral (1200 m lateral aim offset, 900 m dive, 10% throttle) turns a
        // spiral into a wings-level dive.
        bool flipped = false;
        double prev = 0.0;
        for (int i = -3; i <= 3; ++i)
        {
            Vector3 d = NewShorterTurnDirection(F, R, U, Vector3(-1000, (double)i, 0));
            double comp = d.dot(R);
            printf("  lateral offset %+d m -> R-comp %+.3f (%s)\n", i, comp, sideLabel(comp));
            if (i > -3 && (comp > 0) != (prev > 0))
            {
                flipped = true;
            }
            prev = comp;
        }
        check(flipped,
              "C3: confirms the dead-six sign flip is real -- BTFunc::LatchedTurnDirection() and "
              "CPPBlackBoard::ManeuverTurnDir exist to hold one direction across it. If this ever "
              "stops flipping, ShorterTurnDirection() itself gained hysteresis and the latch "
              "should be re-examined rather than silently kept.");
    }

    printf("\n-- C4: bandit directly below -- the degenerate cross product --\n");
    {
        // LOS parallel to U, so |U x toTarget| = 0. Before the 2026-09-08 guard this returned a
        // near-zero vector that normalize() left alone (it skips the divide), collapsing the
        // caller's aim point onto its own position plus the dive bias: a commanded vertical dive
        // at 10% throttle.
        Vector3 d = NewShorterTurnDirection(F, R, U, Vector3(0, 0, -1000));
        printf("  dir=(%.3f,%.3f,%.3f) length=%.3f\n", d.X, d.Y, d.Z, d.length());
        check(d.length() > 0.99, "C4: a degenerate LOS still yields a unit turn direction");
    }

    printf("\n%s (%d check%s failed)\n", g_fail == 0 ? "ALL CHECKS PASSED" : "SOME CHECKS FAILED",
           g_fail, g_fail == 1 ? "" : "s");
    return g_fail == 0 ? 0 : 1;
}
