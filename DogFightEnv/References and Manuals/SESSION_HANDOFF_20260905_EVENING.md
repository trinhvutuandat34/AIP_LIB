# Session handoff — 2026-09-05 (evening session)

**This supersedes `SESSION_HANDOFF_2026-09-05.md`** (the morning session's handoff). That file is
still worth reading for the F67/F68 investigation detail, but **its §7 priority list is wrong** and
carries a "SUPERSEDED" box saying so. Read this file first, then `COMPETITION_PLAN.md` §4.1 rows
**F69–F76**, which this file only summarises.

Git branch: `tgc/envelope-6000-90-round4-baseline`. **Nothing was committed.** All work below sits
in the working tree. The user was asked four times and never authorised a commit — don't commit
without asking, and don't block on it.

**8 days to the deadline: 2026-09-14 12:00 noon.**

---

## 0. The one-line summary

**Both models are now decided and measured. The `.exe` is not built, and it is the only mandatory
artifact.** Everything else is done or optional.

---

## 1. What this session actually changed

### Fixed a fatal bug that was sitting in `HEAD` (F69)

`run_unreal_inference.py:100` used `p.add_argument(` where the parser is named `parser`. `p` was
bound nowhere, so **every invocation raised `NameError` before argparse ran** — introduced by
`c0aa0ff`, the newest commit. It is the command in `startup_command.txt` and
`MATCH_DAY_RUNBOOK.md`, the only entry point with `--server-ip`, and the subprocess behind
`scripts/loopback_live_dryrun.py` — so the project's only end-to-end live-path test was dead too.

**Fixed and verified.** `loopback_live_dryrun.py` now passes: 600/600 frames answered, worst
latency **16.29 ms** against a 166.7 ms budget, **596 distinct commands of 600**. That last number
also clears F70's silent-zero discriminator — the shipped path genuinely flies.

Why no gate caught it: `package_release.py:176-181` "verifies" entry points by **grepping their
source text**. Any future gate must actually execute `parse_args(['--help'])`.

### Model 2 selected (F74)

**Model 2 = `prev_6000_90`** (6000 m, LOS 90°, throttle ON, **no** hard deck), live in
`controller_providers.py::MODEL_PROFILES[2]`.

1,200 episodes at the organizer-confirmed 3,048 m. Mean 1.64 / floor **1.18**, versus Model 1's
config at 1.57 / **0.44**. Decisive column is `cutoff`: Model 1 goes **11W/10D/39L (7% BO5)**,
Model 2 **19W/17D/24L (32%)** — loss-rate difference **z = −2.74**. Side symmetry cleared at
**0.3σ** on a paired forced-mirror run.

**Confidence, stated honestly:** "Model 2 ≠ Model 1's config" is strong (z = −2.74). "`prev_6000_90`
beats `m2_6000_90_deck`" is **not** (z ≈ 0.4 — not separable at N=60). `prev_6000_90` was chosen
because it wins both ranking keys and was already symmetry-validated; don't cite that margin as
established.

F61's switch rule now resolves **affirmatively** — always switch when Head-On triggers. Written
into `MATCH_DAY_RUNBOOK.md` §7.3's pre-commit line with the evidence.

### Model 1 is frozen and signed off

F66's 15 CSVs verified at 150 rows each. All three regression guards PASS. Spawn preset canonical.
DLL crc32 **`4026508473`**, size 2 821 632, `git diff` clean.

### Documentation corrections

- `CLAUDE.md:181` pointed at an interpreter path that **does not exist**. Real path:
  **`C:\Users\user\.conda\envs\aip\python.exe`** (`.conda`, not `anaconda3`).
- The morning handoff's DLL checksum (`2397216051`) matched **neither crc32 nor adler32**. Real
  crc32 is `4026508473`.
- It also claimed the DLLs were gitignored. They are **tracked and clean** — git is the backup.

---

## 2. Organizer answers received (F72, F73, F75) — these closed real risks

| Question | Answer | Consequence |
|---|---|---|
| Head-On separation | **3,048 m confirmed** | No longer an assumption. **Trap:** it coincides with the *superseded* slide's number — scenario changed, distance didn't. **Do not "correct" it back.** |
| Ops PC debug CRTs | Prelim ran on the finals PC | It loads `JSBSimAIPLib.dll` at import, which statically imports the CRTs — so they're present. **F68/F71 risk retired.** |
| `.exe` IP/port | **`config.json`, fixed `127.0.0.1:9999`** | Server is on **loopback**. No CLI/env channel needed. |
| onedir allowed? | **NO** | ZIP takes exactly 2 files. **onefile is mandatory.** |
| Group-stage draws → Head-On? | **결선라운드 only** | Model 2 is knockout-only. **Model 1 alone must survive the group stage.** |
| Alt/speed band | **Still unanswered** | Team decided to **retain** 1,000–7,700 m / 150–280 m/s. **This is an assumption, not a citation** (F76). |

### Submission spec (F75) — read `COMPETITION_RULES.md` §7.1

Two ZIPs, each exactly two files at the root (`<name>.exe` + optional `config.json`), no
subfolders, no library folders. Displayed team name must be the registered name verbatim;
head-on appends `_HeadOn` as a **suffix**.

**Naming resolved (F76):** `TEAM_NAME = "진짜보라매"` (displayed) and a new
`SUBMISSION_NAME = "JinjjaBoramae"` (filenames only). These are **two different fields** — the
"use English" rule governs filenames only. Verified: the Korean name round-trips exactly through
`pack_client_join_info` (15 B / 22 B of a 29-byte field). **`package_release.py:212` was building
its archive name from `TEAM_NAME` and would have emitted a Korean filename — fixed.**

---

## 3. What is left, in priority order

### 1. THE `.exe` — the entire remaining critical path, nothing built

The approved plan's Phase 3 recommends **onedir and is now void** (F75). Rewrite around onefile:

1. PyInstaller into a clean build env — **not installed**; exclude `ray`/`torch` or the bundle goes
   multi-GB via `src/dogfight/unreal/policies.py:11`'s nested imports
2. **`config.json` reader — does not exist anywhere**
3. `student/runtime_paths.py` — `native_bt.py:99`'s 4-deep `__file__` walk breaks when frozen. Fix
   by passing an **absolute** DLL path from the entry point (`os.path.join` discards its broken
   `lib_path` when the filename is absolute). **Do not patch `src/dogfight/**`.**
4. `student/match_client.py` + two thin shims → two exes from one codebase
5. `scripts/build_exe.py` + `scripts/smoke_exe.py`
6. Clean-machine test (Windows Sandbox works)

**The smoke test is not optional.** Per F70, if the native BT can't find `Rule_forTraining.xml`
(loaded from the **DLL's own directory**, `CPPBehaviorTree.cpp:141`) it catches the exception,
prints to `std::cout`, and `Step()` returns **all-zero stick and throttle**. The client still
handshakes and answers at 60 Hz. It is indistinguishable from healthy. So: build `--console`, and
assert commands are **not all `(0,0,0,0)`** and **vary across frames**.

Good news that makes this tractable: **the live path imports neither `ray` nor `torch`** (only
numpy, gymnasium, pymap3d, yaml, filelock), and the shipped model is BT/controller-only —
`MODE="vptrack"`, `BUNDLE_DIR=None`, no checkpoint.

### 2. Model 1 improvement (optional, unattended compute)

The largest **quantified** leak is closure, not the side asymmetry:

| opponent | nose-on (≤2°) | ever in WEZ | timeouts |
|---|---|---|---|
| `sniper` (GoGoSSung analogue) | **148/150** | **37/150** | 127 |
| `bt_only` | 150/150 | 31/150 | 130 |

We win the angle fight ~99% of the time and reach weapons range 25%. That maps onto two knobs that
have **never been swept**: `TARGET_RANGE_M = 220.0` and `THROTTLE_AUTHORITY = 0.7`. Also never
measured, all default-OFF: `DECK_TTC_S` (built in F62 *so it could be measured*), `ROLL_TAPER_DEG`,
`PITCH_FLOOR`, `CORNER_HOLD`. Add candidates to `league.py::CANDIDATES` and run
`--scenario-mode match_base`.

### 3. Team admin

개인정보수집및활용동의서 — separate ZIP, one signed PDF/HWP per member.

---

## 4. Do NOT re-do these

- **Don't reopen F67's roll boost.** Two fixes already measured worse. F74 did add evidence (the
  26-point asymmetry is **geometry-specific** — it vanishes in head-on, so it lives in how the tree
  resolves a side-dependent turn in the offset merge) but that is a native-BT investigation, not
  an 8-day task. **Note it is unmitigated for Model 1, and per the 2026-09-05 경기 기본규정
  Blue/Red strictly alternate, so we fly the bad side in exactly half of every match.**
- **Don't re-test the hard deck for Model 2.** Measured (F74): it cut self-crashes 11/300 → 3/300
  and **still scored worse**. Those crashes were aircraft already losing.
- **Don't re-run the F66 or F74 matrices** unless the DLL or a candidate changes.
- **Don't sweep head-on separation again** — 3,048 m is confirmed.
- **Don't use `--target-backend cutoff` on `eval_v5_vs_bt.py`** — it rejects it. Use
  `eval_vs_cutoff.py`, or `league.py`/`verify_side_symmetry.py` which dispatch correctly.
- **Don't edit `src/dogfight/**`.**

---

## 5. Operational notes

- Interpreter: **`C:\Users\user\.conda\envs\aip\python.exe`**. Bare `python` is a bare 3.12.
- **Run `python scripts/spawn_preset_guard.py --restore` after every eval run.** Drift is expected
  (`JSBSimWrapper.Fighter.__init__` rewrites `f16_init.xml` on every reset), not a bug.
- **Long runs get externally killed.** The N=900 sweep died mid-pass-4 at 6-way concurrency and
  lost only 59 episodes because `league.py` chunks and resumes. Use `--jobs 3–5` and drive it in a
  loop of passes; re-running the identical command resumes.
- New this session: `scripts/sweep_headon_separation.py` (per-separation output roots — without it
  a naive sweep silently appends a second geometry into the first's CSVs) and
  `DOGFIGHT_LEAGUE_OUT_DIR` on `league.py` (default unchanged).
- `ORGANIZER_QUESTIONS_20260905.md` is drafted and ready to send; items 1, 2, 4 are now answered,
  item 3 (alt/speed band) is the one still worth chasing.

## 6. Final verified state

All three regression guards **PASS** · spawn preset **canonical** · `AIP_BASE.dll` crc32
**`4026508473`** / 2 821 632 B, unchanged and git-clean · no dangling processes · Model 1 and
Model 2 profiles both verified, Model 1 still bound to the `SHIP_*` constants.
