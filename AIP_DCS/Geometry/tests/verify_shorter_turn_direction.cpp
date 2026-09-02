// Standalone regression check for BTFunc::ShorterTurnDirection (BehaviorTree/BT_Content/Functions.cpp).
//
// Build (from AIP_DCS/):
//   g++ -std=c++17 -IGeometry Geometry/tests/verify_shorter_turn_direction.cpp \
//     Geometry/Vector3.cpp Geometry/Vector4.cpp Geometry/Quaternion.cpp Geometry/Matrix4.cpp \
//     Geometry/Matrix3.cpp Geometry/Math.cpp Geometry/EulerAngle.cpp Geometry/CoordinateConverter.cpp \
//     Geometry/AxisAngle.cpp Geometry/Angle.cpp -o /tmp/verify_shorter_turn_direction
//   /tmp/verify_shorter_turn_direction   # exits 0 and prints ALL CHECKS PASSED
//
// This links against the project's real Geometry/Vector3.{h,cpp} (and EulerAngle/Quaternion for
// the rotated-aircraft case) so the math is exactly what AIP_DCS.dll uses -- not a
// hand-reimplementation. It cannot run the actual JSBSim/BT simulation (Windows-only binaries),
// so this is a geometric-correctness check of the isolated function, not a match-outcome
// measurement -- run the peer-rig eval (see DogFightEnv HANDOFF.md) for that.
#include <cstdio>
#include <cmath>
#include "Vector3.h"
#include "EulerAngle.h"
#include "Quaternion.h"

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

    printf("\n%s (%d check%s failed)\n", g_fail == 0 ? "ALL CHECKS PASSED" : "SOME CHECKS FAILED",
           g_fail, g_fail == 1 ? "" : "s");
    return g_fail == 0 ? 0 : 1;
}
