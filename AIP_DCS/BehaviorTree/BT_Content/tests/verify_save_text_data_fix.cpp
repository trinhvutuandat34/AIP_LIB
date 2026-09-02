// Standalone regression check for BTFunc::SaveTextData (../Functions.cpp).
//
// Build (from AIP_DCS/BehaviorTree/BT_Content/):
//   g++ -std=c++17 -I../../Geometry -I.. -I. tests/verify_save_text_data_fix.cpp Functions.cpp \
//     ../../Geometry/Vector3.cpp ../../Geometry/Vector4.cpp ../../Geometry/Quaternion.cpp \
//     ../../Geometry/Matrix4.cpp ../../Geometry/Matrix3.cpp ../../Geometry/Math.cpp \
//     ../../Geometry/EulerAngle.cpp ../../Geometry/CoordinateConverter.cpp \
//     ../../Geometry/AxisAngle.cpp ../../Geometry/Angle.cpp \
//     -o /tmp/verify_save_text_data_fix
//   /tmp/verify_save_text_data_fix   # exits 0 and prints ALL CHECKS PASSED
//
// Links directly against the real (post-fix) BTFunc::SaveTextData. The pre-fix behaviour
// (tempString->clear() once length() > 910) is reproduced here for comparison rather than built
// from a second copy of the whole BT_Content tree, since the function itself is only 4 lines.
#include <cstdio>
#include <string>

#include "../Functions.h"

// Exact copy of the pre-fix logic from Functions.cpp (git history).
static void OldSaveTextData(std::string* tempString, std::string* BT_Text)
{
    if (tempString != nullptr && BT_Text != nullptr)
    {
        if (tempString->length() > 910)
            tempString->clear();

        BT_Text->clear();
        BT_Text->append(*tempString);
        tempString->clear();
    }
}

static int g_fail = 0;
static void check(bool cond, const char* what)
{
    printf("  [%s] %s\n", cond ? "PASS" : "FAIL", what);
    if (!cond) g_fail++;
}

static std::string makeEntries(int count, int lineLen)
{
    // Mirrors AddNodeExcute's format: each entry is text + "\n".
    std::string s;
    for (int i = 0; i < count; i++)
    {
        s.append(std::string(lineLen, 'A' + (i % 26)));
        s.append("\n");
    }
    return s;
}

int main()
{
    printf("== Below the cap (910 chars): both must pass through unchanged ==\n");
    {
        std::string tmpOld = makeEntries(10, 20); // well under 910
        std::string tmpNew = tmpOld;
        std::string btOld, btNew;
        OldSaveTextData(&tmpOld, &btOld);
        BTFunc::SaveTextData(&tmpNew, &btNew);
        check(btOld == btNew, "old and new agree when under the cap");
        check(btNew == makeEntries(10, 20), "new output equals the untouched input when under the cap");
        check(tmpNew.empty(), "new still clears tempString after flushing (unchanged contract)");
    }

    printf("\n== Over the cap: old wipes it, new keeps a truncated-but-useful tail ==\n");
    {
        std::string original = makeEntries(60, 20); // 60 * 21 = 1260 chars, over 910
        printf("  original length = %zu\n", original.length());

        std::string tmpOld = original;
        std::string btOld;
        OldSaveTextData(&tmpOld, &btOld);
        check(btOld.empty(), "confirms bug: old code produces an EMPTY BT_Text once the buffer exceeds 910 chars");

        std::string tmpNew = original;
        std::string btNew;
        BTFunc::SaveTextData(&tmpNew, &btNew);
        check(!btNew.empty(), "fix confirmed: new code produces a NON-EMPTY BT_Text over the cap");
        check(btNew.length() <= 910, "new output never exceeds the 910-char cap");
        check(original.size() >= btNew.size() && original.compare(original.size() - btNew.size(), btNew.size(), btNew) == 0,
              "new output is exactly a suffix of the original buffer (no corruption, just truncation)");
        check(btNew.back() == '\n' && (btNew.empty() || btNew.front() != '\n'),
              "new output starts on a clean entry boundary (no partial leading line) and keeps the trailing newline");
        printf("  kept %zu of %zu chars: \"%.40s...\"\n", btNew.length(), original.length(), btNew.c_str());
    }

    printf("\n== Boundary: exactly 910 and 911 chars ==\n");
    {
        std::string exact(910, 'x');
        std::string tmp = exact;
        std::string bt;
        BTFunc::SaveTextData(&tmp, &bt);
        check(bt == exact, "exactly 910 chars: passed through unchanged (not classified as 'over the cap')");

        std::string over(911, 'y');
        std::string tmp2 = over;
        std::string bt2;
        BTFunc::SaveTextData(&tmp2, &bt2);
        check(!bt2.empty() && bt2.length() <= 910, "911 chars (no newline at all): truncated, not wiped, even with no line boundary to align to");
    }

    printf("\n== Repeated calls (simulating repeated ticks) never crash or wipe once corrected ==\n");
    {
        std::string tmp;
        std::string bt;
        bool everEmptyAfterGrowth = false;
        for (int tick = 0; tick < 200; tick++)
        {
            tmp.append(makeEntries(3, 15)); // grows every tick, like real per-tick appends would
            BTFunc::SaveTextData(&tmp, &bt);
            if (tick > 5 && bt.empty()) everEmptyAfterGrowth = true;
        }
        check(!everEmptyAfterGrowth, "across 200 growth ticks, BT_Text is never spuriously wiped");
    }

    printf("\n%s (%d check%s failed)\n", g_fail == 0 ? "ALL CHECKS PASSED" : "SOME CHECKS FAILED",
           g_fail, g_fail == 1 ? "" : "s");
    return g_fail == 0 ? 0 : 1;
}
