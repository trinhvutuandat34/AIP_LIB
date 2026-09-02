// Standalone regression + micro-benchmark for the Controller_CY.cpp GetStick fix that removed a
// redundant Proj_TV.length() call (was computed once inline for UpVector2Proj_TV_Angle, then
// again a few lines later into Proj_TV_Length).
//
// Build (from AIP_DCS/):
//   g++ -O2 -std=c++17 -IGeometry Geometry/tests/verify_controller_proj_tv_fix.cpp \
//     Geometry/Vector3.cpp Geometry/Vector4.cpp Geometry/Quaternion.cpp Geometry/Matrix4.cpp \
//     Geometry/Matrix3.cpp Geometry/Math.cpp Geometry/EulerAngle.cpp Geometry/CoordinateConverter.cpp \
//     Geometry/AxisAngle.cpp Geometry/Angle.cpp -o /tmp/verify_controller_proj_tv_fix
//   /tmp/verify_controller_proj_tv_fix   # exits 0 and prints ALL CHECKS PASSED
//
// This links against the project's real Geometry/Vector3.{h,cpp} etc, and reproduces the exact
// pre-fix and post-fix formulas from GetStick's roll-command section (not the whole 300+ line
// function -- RollCMD/PitchCMD/RudderCMD downstream of this snippet only ever consume
// UpVector2Proj_TV_Angle, UTAngle and LOS, so proving those three (plus Proj_TV_Length) are
// bit-identical old vs. new proves GetStick's output is unaffected). It cannot run the actual
// JSBSim/BT simulation (Windows-only binaries) -- this is a correctness-equivalence and
// micro-benchmark check, not a match-outcome measurement.
#include <cstdio>
#include <cmath>
#include <cstdlib>
#include <chrono>
#include <vector>
#include "Vector3.h"
#include "EulerAngle.h"
#include "Quaternion.h"

using namespace BT_Geometry;

static const double RADTODEG_LOCAL = 180.0 / 3.14159265358979323846;

struct Angles
{
    float upAngle;
    float utAngle;
    float los;
    float projLen;
};

// Pre-fix logic: Proj_TV.length() computed twice (once inline, once into Proj_TV_Length).
static Angles OldCompute(const Vector3& F, const Vector3& U, const Vector3& R,
                          const Vector3& TargetLocation, const Vector3& Mylocation)
{
    Vector3 ForwardVectorPoint = F * 1000 + Mylocation;
    Vector3 ForwardVectorPoint2VP = TargetLocation - ForwardVectorPoint;
    Vector3 Proj_V = (ForwardVectorPoint2VP.dot(F)) * F;
    Vector3 Proj_P = TargetLocation - Proj_V;
    Vector3 Proj_TV = Proj_P - ForwardVectorPoint;

    float UpVector2Proj_TV_Angle = std::acos(U.dot(Proj_TV / Proj_TV.length()));
    float LOS = std::acos(F.dot(TargetLocation - Mylocation) / (TargetLocation - Mylocation).length()) * RADTODEG_LOCAL;

    if (std::isnan(UpVector2Proj_TV_Angle)) UpVector2Proj_TV_Angle = 0;
    if (std::isnan(LOS)) LOS = 0;

    float Proj_TV_Length = Proj_TV.length();
    if (Proj_TV_Length <= 0) Proj_TV_Length = 0.0001f;

    float UTAngle = (R.dot(Proj_TV / Proj_TV_Length) >= 0) ? UpVector2Proj_TV_Angle : -UpVector2Proj_TV_Angle;

    return { UpVector2Proj_TV_Angle, UTAngle, LOS, Proj_TV_Length };
}

// Post-fix logic: Proj_TV.length() computed once (as double -- Vector3::length()'s real return
// type, matching the precision the pre-fix code's FIRST use got) and reused.
static Angles NewCompute(const Vector3& F, const Vector3& U, const Vector3& R,
                          const Vector3& TargetLocation, const Vector3& Mylocation)
{
    Vector3 ForwardVectorPoint = F * 1000 + Mylocation;
    Vector3 ForwardVectorPoint2VP = TargetLocation - ForwardVectorPoint;
    Vector3 Proj_V = (ForwardVectorPoint2VP.dot(F)) * F;
    Vector3 Proj_P = TargetLocation - Proj_V;
    Vector3 Proj_TV = Proj_P - ForwardVectorPoint;

    double Proj_TV_Length = Proj_TV.length();

    float UpVector2Proj_TV_Angle = std::acos(U.dot(Proj_TV / Proj_TV_Length));
    float LOS = std::acos(F.dot(TargetLocation - Mylocation) / (TargetLocation - Mylocation).length()) * RADTODEG_LOCAL;

    if (std::isnan(UpVector2Proj_TV_Angle)) UpVector2Proj_TV_Angle = 0;
    if (std::isnan(LOS)) LOS = 0;

    if (Proj_TV_Length <= 0) Proj_TV_Length = 0.0001;

    float UTAngle = (R.dot(Proj_TV / Proj_TV_Length) >= 0) ? UpVector2Proj_TV_Angle : -UpVector2Proj_TV_Angle;

    return { UpVector2Proj_TV_Angle, UTAngle, LOS, (float)Proj_TV_Length };
}

static int g_fail = 0;
static void check(bool cond, const char* what)
{
    printf("  [%s] %s\n", cond ? "PASS" : "FAIL", what);
    if (!cond) g_fail++;
}

// Builds an orthonormal (F,U,R) triple the same way DirectionVectorUpdate.cpp/Controller_CY.cpp
// derive them from a quaternion, from an arbitrary yaw/pitch/roll.
static void buildFrame(double yawDeg, double pitchDeg, double rollDeg, Vector3& F, Vector3& U, Vector3& R)
{
    EulerAngle att(yawDeg / 57.2958, pitchDeg / 57.2958, rollDeg / 57.2958);
    Quaternion q = att.toQuaternion();
    F.Y = 2 * (q.X * q.Z + q.W * q.Y);
    F.Z = -2 * (q.Y * q.Z - q.W * q.X);
    F.X = 1 - 2 * (q.X * q.X + q.Y * q.Y);
    U.X = -2 * (q.Y * q.Z + q.W * q.X);
    U.Y = -2 * (q.X * q.Y - q.W * q.Z);
    U.Z = 1 - 2 * (q.X * q.X + q.Z * q.Z);
    R.X = 2 * (q.X * q.Z - q.W * q.Y);
    R.Y = 1 - 2 * (q.Y * q.Y + q.Z * q.Z);
    R.Z = -2 * (q.X * q.Y + q.W * q.Z);
}

static bool bitIdentical(const Angles& a, const Angles& b)
{
    return a.upAngle == b.upAngle && a.utAngle == b.utAngle && a.los == b.los && a.projLen == b.projLen;
}

int main()
{
    srand(12345);
    int nCases = 0;
    bool sawZeroLength = false, sawPositiveUT = false, sawNegativeUT = false;

    printf("== Equivalence sweep: random attitudes x random target offsets ==\n");
    for (int a = 0; a < 20; a++)
    {
        double yaw = (rand() % 3600) / 10.0;
        double pitch = (rand() % 1600) / 10.0 - 80.0;
        double roll = (rand() % 3600) / 10.0;
        Vector3 F, U, R;
        buildFrame(yaw, pitch, roll, F, U, R);
        Vector3 Mylocation(0, 0, 0);

        for (int t = 0; t < 25; t++)
        {
            double fwd = (rand() % 20000) / 10.0 - 1000.0;   // -1000..1000 along/behind boresight
            double lat = (rand() % 4000) / 10.0 - 200.0;     // -200..200 lateral
            double vert = (rand() % 4000) / 10.0 - 200.0;    // -200..200 vertical
            Vector3 TargetLocation = F * (1000.0 + fwd) + R * lat + U * vert + Mylocation;

            Angles o = OldCompute(F, U, R, TargetLocation, Mylocation);
            Angles n = NewCompute(F, U, R, TargetLocation, Mylocation);
            nCases++;
            if (!bitIdentical(o, n))
            {
                printf("  MISMATCH at attitude(%.1f,%.1f,%.1f) target(%.2f,%.2f,%.2f): "
                       "old(up=%.9f,ut=%.9f,los=%.9f,len=%.9f) new(up=%.9f,ut=%.9f,los=%.9f,len=%.9f)\n",
                       yaw, pitch, roll, fwd, lat, vert,
                       o.upAngle, o.utAngle, o.los, o.projLen,
                       n.upAngle, n.utAngle, n.los, n.projLen);
                g_fail++;
            }
            if (n.projLen <= 0.0001f) sawZeroLength = true;
            if (n.utAngle > 0) sawPositiveUT = true;
            if (n.utAngle < 0) sawNegativeUT = true;
        }
    }
    check(true, "random sweep completed (mismatches, if any, printed above)");
    printf("  %d cases compared\n", nCases);

    printf("\n== Edge case: target exactly on the projected-forward line (Proj_TV -> zero) ==\n");
    {
        Vector3 F(1, 0, 0), U(0, 0, 1), R(0, 1, 0), Mylocation(0, 0, 0);
        // TargetLocation chosen so Proj_P collapses exactly onto ForwardVectorPoint: Proj_TV == 0.
        Vector3 TargetLocation = F * 1000.0 + Mylocation;
        Angles o = OldCompute(F, U, R, TargetLocation, Mylocation);
        Angles n = NewCompute(F, U, R, TargetLocation, Mylocation);
        printf("  old: up=%.6f ut=%.6f los=%.6f len=%.6f\n", o.upAngle, o.utAngle, o.los, o.projLen);
        printf("  new: up=%.6f ut=%.6f los=%.6f len=%.6f\n", n.upAngle, n.utAngle, n.los, n.projLen);
        check(bitIdentical(o, n), "zero-length Proj_TV: fix preserves the exact pre-fix NaN-guard behaviour");
    }

    printf("\n== Sanity: both UTAngle signs were exercised by the sweep ==\n");
    check(sawZeroLength || true, "(zero-length edge covered explicitly above)");
    check(sawPositiveUT && sawNegativeUT, "sweep exercised both the RightVector.dot(...) >= 0 and < 0 branches");

    printf("\n== Micro-benchmark: sqrt-call reduction on the hot path ==\n");
    {
        const int N = 2000000;
        std::vector<Vector3> Fs, Us, Rs, Ts;
        Fs.reserve(N); Us.reserve(N); Rs.reserve(N); Ts.reserve(N);
        for (int i = 0; i < N; i++)
        {
            double yaw = (rand() % 3600) / 10.0;
            double pitch = (rand() % 1600) / 10.0 - 80.0;
            double roll = (rand() % 3600) / 10.0;
            Vector3 F, U, R;
            buildFrame(yaw, pitch, roll, F, U, R);
            Fs.push_back(F); Us.push_back(U); Rs.push_back(R);
            double fwd = (rand() % 20000) / 10.0 - 1000.0;
            double lat = (rand() % 4000) / 10.0 - 200.0;
            double vert = (rand() % 4000) / 10.0 - 200.0;
            Ts.push_back(F * (1000.0 + fwd) + R * lat + U * vert);
        }
        Vector3 Mylocation(0, 0, 0);

        volatile float sinkOld = 0, sinkNew = 0;

        auto t0 = std::chrono::steady_clock::now();
        for (int i = 0; i < N; i++)
        {
            Angles o = OldCompute(Fs[i], Us[i], Rs[i], Ts[i], Mylocation);
            sinkOld += o.utAngle;
        }
        auto t1 = std::chrono::steady_clock::now();
        for (int i = 0; i < N; i++)
        {
            Angles n = NewCompute(Fs[i], Us[i], Rs[i], Ts[i], Mylocation);
            sinkNew += n.utAngle;
        }
        auto t2 = std::chrono::steady_clock::now();

        double oldMs = std::chrono::duration<double, std::milli>(t1 - t0).count();
        double newMs = std::chrono::duration<double, std::milli>(t2 - t1).count();
        printf("  N=%d calls -- old (2x length() calls): %.2f ms   new (1x length() call): %.2f ms\n", N, oldMs, newMs);
        printf("  delta: %.1f%% %s (sink values: old=%.6f new=%.6f, ignore -- keeps the loop from being optimized away)\n",
               100.0 * (oldMs - newMs) / oldMs, (newMs < oldMs) ? "faster" : "NOT faster", sinkOld, sinkNew);
        check(newMs <= oldMs * 1.05, "new implementation is not slower than old (allowing 5% measurement noise)");
    }

    printf("\n%s (%d check%s failed)\n", g_fail == 0 ? "ALL CHECKS PASSED" : "SOME CHECKS FAILED",
           g_fail, g_fail == 1 ? "" : "s");
    return g_fail == 0 ? 0 : 1;
}
