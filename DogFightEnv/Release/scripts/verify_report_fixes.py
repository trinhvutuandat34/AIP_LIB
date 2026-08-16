"""Regression guard for the 2026-08-11 fixes -- fast checks, no simulator required.

WHY THIS EXISTS. There is no test suite for the core package (References and Manuals/CLAUDE.md),
and the 2026-08-11 session fixed several defects whose common property is that they FAIL SILENTLY:
a stage advancing on another stage's metrics, a metric reading nan, a record that never saves, a
placeholder bundle path that arms itself the moment MODE changes, a scenario wrapper that is not
wired in. None of those announce themselves in a training log -- they just quietly make the run
mean something other than what it claims. So they need a guard that fails loudly instead.

Covers, with the register row each one protects:
    4.1 F6          stage advancement averages over EPISODES, and carry resets per stage
    Action 7 / N3   reward_mean / ep_len_mean carried with the custom metrics
    Action 6 / N4   training records actually save
    Action 12 / P7  BUNDLE_DIR is None and guarded
    4.1 F8          MatchScenarioWrapper wired into env_creator, no-op for other modes
    4.1 F8-STAGES   the curriculum ladder is the intended 16 stages
    v8 config       real_eagle_v8.yaml differs from v7 only where intended

Runs in a few seconds. The slower end-to-end spawn check that builds real envs lives in
scripts/verify_match_spawn.py -- run that too before committing compute to a campaign.

    python scripts/verify_report_fixes.py

Exit code 0 = all checks pass.
"""
from __future__ import annotations

import ast
import math
import sys
import tempfile
from pathlib import Path

for _s in ("stdout", "stderr"):
    try:
        getattr(sys, _s).reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import numpy as np
import yaml

import train_curriculum as tc
from dogfight.ai.curriculum import CurriculumStage, check_advancement
from dogfight.ai.training_record import save_training_record
from dogfight.config import DEFAULT_ENV_CONFIG
from student.match_scenario_wrapper import (
    MATCH_ALTITUDE_M, MATCH_LOS_DEG, MATCH_SEPARATION_MAX_M,
    MATCH_SEPARATION_MIN_M, MATCH_SPEED_MPS, MatchScenarioWrapper,
)
from student.my_curriculum import get_stages

_FAILED: list[str] = []


def check(label: str, cond: bool) -> None:
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}")
    if not cond:
        _FAILED.append(label)


def section(title: str) -> None:
    print(f"\n{title}")


# ---------------------------------------------------------------------------------------------
# 4.1 F6 -- the advancement gate must average over EPISODES, not over carried rows.
#
# v7 stage 0's final 10-row window was 8 copies of its single non-crashing episode plus 2 of a
# crashing one: the gate read crash_rate=0.2000, passed a crash_rate_max=0.30 threshold and
# advanced, while the true rate over that stage's 7 episodes was 0.8571.
# ---------------------------------------------------------------------------------------------
def _episode(crash: float) -> dict:
    return {"crash_rate": crash, "win_rate": 0.0, "ep_min_distance": 733.07, "ep_wez_steps": 0.0}


_MISSING = {"crash_rate": "n/a", "win_rate": "n/a", "ep_min_distance": "n/a", "ep_wez_steps": "n/a"}

_STAGE0 = CurriculumStage(
    index=0, name="flight_survival", description="d", target_mode="behavior_tree",
    max_iterations=500, episode_step_limit=12000, checkpoint_interval=10,
    reward_overrides={}, randomization={},
    advance_conditions={"crash_rate_max": 0.30}, advance_window=10,
)


def _rows_for(crashes, idle_between: int = 26) -> list[dict]:
    tc._reset_carry_forward()
    rows = []
    for c in crashes:
        rows.append(tc._carry_forward(dict(_episode(c))))
        for _ in range(idle_between):
            rows.append(tc._carry_forward(dict(_MISSING)))
    return rows


def verify_f6() -> None:
    section("4.1 F6 -- stage advancement over distinct episodes")

    # Reproduce v7 stage 0 exactly: 6 crashes, then one survivor, then an idle tail.
    rows = _rows_for([1.0] * 6, idle_between=26)
    rows.append(tc._carry_forward(dict(_episode(0.0))))
    for _ in range(7):
        rows.append(tc._carry_forward(dict(_MISSING)))

    row_window = rows[-_STAGE0.advance_window:]
    old_ok, _ = check_advancement(_STAGE0, row_window)
    row_avg = sum(r["crash_rate"] for r in row_window) / len(row_window)
    check(f"the OLD row window would advance on avg {row_avg:.4f} (v7's logged 0.2000)",
          old_ok and abs(row_avg - 0.20) < 1e-9)

    episodes = [r for r in rows if r.get("metrics_age_iters") == 0]
    true_rate = sum(r["crash_rate"] for r in episodes) / len(episodes)
    check(f"true per-episode rate is {true_rate:.4f}, not 0.20", abs(true_rate - 6 / 7) < 1e-9)
    check("only 7 episodes exist, below advance_window -> no advancement",
          len(episodes[-_STAGE0.advance_window:]) == 7)

    # At the declared threshold the gate must fire; above it, hold.
    for crashes, want in (([1.0] * 3 + [0.0] * 7, True), ([1.0] * 4 + [0.0] * 6, False)):
        rows = _rows_for(crashes)
        win = [r for r in rows if r.get("metrics_age_iters") == 0][-10:]
        got, _ = check_advancement(_STAGE0, win)
        rate = sum(crashes) / len(crashes)
        check(f"10 episodes at crash_rate={rate:.2f} -> advance={got} (want {want})", got is want)

    # Carry must not survive a stage boundary.
    tc._reset_carry_forward()
    tc._carry_forward(dict(_episode(0.0)))
    leaked = tc._carry_forward(dict(_MISSING))
    check("without a reset the next iteration still reports the old episode",
          leaked.get("crash_rate") == 0.0)
    tc._reset_carry_forward()
    first = tc._carry_forward(dict(_MISSING))
    check("after _reset_carry_forward a new stage reports n/a",
          first.get("crash_rate") == "n/a" and first.get("metrics_age_iters") == "n/a")


# ---------------------------------------------------------------------------------------------
# Action 7 / N3 -- reward_mean and ep_len_mean share the custom metrics' carry.
# They were nan on 163 of v7's 194 rows.
# ---------------------------------------------------------------------------------------------
def _result(ret, ln, crash) -> dict:
    return {"env_runners": {
        "episode_return_mean": ret, "episode_len_mean": ln,
        "custom_metrics": {"crash": crash, "win": 0.0, "loss": 0.0, "timeout": 0.0,
                           "ep_wez_steps": 0.0, "ep_min_distance": 500.0},
    }}


def _result_idle() -> dict:
    return {"env_runners": {"episode_return_mean": float("nan"),
                            "episode_len_mean": float("nan"), "custom_metrics": {}}}


def verify_n3() -> None:
    section("Action 7 / N3 -- reward_mean carried, never nan mid-stage")
    tc._reset_carry_forward()
    m = tc._extract_custom_metrics(_result(12.04, 2813.0, 1.0))
    check("captured on an episode close", m["reward_mean"] == 12.04 and m["metrics_age_iters"] == 0)

    held = [tc._extract_custom_metrics(_result_idle()) for _ in range(5)]
    check("no nan across idle iterations",
          not any(isinstance(r["reward_mean"], float) and math.isnan(r["reward_mean"])
                  for r in held))
    check("holds the last measured value", all(r["reward_mean"] == 12.04 for r in held))
    check("age increments 1..5", [r["metrics_age_iters"] for r in held] == [1, 2, 3, 4, 5])

    m = tc._extract_custom_metrics(_result(-4.42, 2698.0, 0.0))
    check("reward_mean and crash_rate reset to age 0 together",
          m["metrics_age_iters"] == 0 and m["reward_mean"] == -4.42 and m["crash_rate"] == 0.0)

    tc._reset_carry_forward()
    m = tc._extract_custom_metrics(_result_idle())
    check("pre-first-episode rows read n/a, not nan", m["reward_mean"] == "n/a")


# ---------------------------------------------------------------------------------------------
# Action 6 / N4 -- training records must actually save.
# training_record._to_markdown() reads item["iteration"]; our rows are keyed total_iter.
# ---------------------------------------------------------------------------------------------
def verify_n4() -> None:
    section("Action 6 / N4 -- stage training records save")
    rows = [
        {"stage": 0, "iter_in_stage": 24, "total_iter": 24, "reward_mean": 1.9988,
         "ep_len_mean": 2813.0, "crash_rate": 1.0, "metrics_age_iters": 0},
        {"stage": 0, "iter_in_stage": 51, "total_iter": 51, "reward_mean": -8.0851,
         "ep_len_mean": 2734.0, "crash_rate": 1.0, "metrics_age_iters": 0},
    ]
    env_config = {
        "observation_mode": DEFAULT_ENV_CONFIG.get("observation_mode", "tactical16"),
        "reward": dict(DEFAULT_ENV_CONFIG["reward"]),
        "wez": dict(DEFAULT_ENV_CONFIG["wez"]),
    }
    adapted = [{**m, "iteration": m.get("total_iter", m.get("iter_in_stage")),
                "episode_len_mean": m.get("ep_len_mean", "n/a")} for m in rows]

    with tempfile.TemporaryDirectory() as td:
        try:
            save_training_record(output_dir=Path(td) / "raw", algorithm_name="sac", cli_args={},
                                 env_config=dict(env_config), algorithm_config={},
                                 result_history=rows, workspace_root=ROOT)
            raw_raised = False
        except KeyError:
            raw_raised = True
        check("the UNADAPTED row shape still raises KeyError('iteration')", raw_raised)

        out = Path(td) / "adapted"
        save_training_record(output_dir=out, algorithm_name="sac", cli_args={},
                             env_config=dict(env_config), algorithm_config={},
                             result_history=adapted, workspace_root=ROOT)
        md = (out / "training_record.md")
        check("training_record.json + .md written",
              (out / "training_record.json").exists() and md.exists())
        text = md.read_text(encoding="utf-8")
        check("markdown carries real iterations and episode lengths",
              "iter `24`" in text and "2813.0" in text and "episode_len_mean=`n/a`" not in text)


# ---------------------------------------------------------------------------------------------
# Action 12 / P7 -- BUNDLE_DIR must be None and guarded, so no MODE flip can arm the
# 100%-crash v4 bundle. Checked by AST: importing my_submission loads the DLL via ctypes.
# ---------------------------------------------------------------------------------------------
def verify_p7() -> None:
    section("Action 12 / P7 -- BUNDLE_DIR None and guarded")
    src_path = ROOT / "student" / "my_submission.py"
    raw = src_path.read_text(encoding="utf-8")
    tree = ast.parse(raw, filename=str(src_path))

    assigns = [n for n in tree.body if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == "BUNDLE_DIR" for t in n.targets)]
    check("exactly one module-level BUNDLE_DIR, assigned literal None",
          len(assigns) == 1 and isinstance(assigns[0].value, ast.Constant)
          and assigns[0].value.value is None)

    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
               and n.name == "_build_action_provider_raw"), None)
    guard_line = None
    if fn is not None:
        for node in ast.walk(fn):
            if not isinstance(node, ast.If):
                continue
            t = node.test
            if (isinstance(t, ast.Compare) and isinstance(t.left, ast.Name)
                    and t.left.id == "BUNDLE_DIR" and len(t.ops) == 1
                    and isinstance(t.ops[0], ast.Is)
                    and isinstance(t.comparators[0], ast.Constant)
                    and t.comparators[0].value is None
                    and any(isinstance(b, ast.Raise) for b in node.body)):
                guard_line = node.lineno
                break
    check("a raising `if BUNDLE_DIR is None` guard exists", guard_line is not None)
    if fn is not None and guard_line is not None:
        uses = [n.lineno for n in ast.walk(fn)
                if isinstance(n, ast.Name) and n.id == "BUNDLE_DIR" and n.lineno != guard_line]
        check("every later BUNDLE_DIR read is after the guard", all(u > guard_line for u in uses))
        early = [n.lineno for n in ast.walk(fn) if isinstance(n, ast.Return)]
        check("bt and vptrack return before the guard -- safe modes unaffected",
              sum(1 for r in early if r < guard_line) >= 2)
    check("no stale v4/stage_3 reference anywhere in the file",
          "v4/stage_3_autopilot_pursuit" not in raw)


# ---------------------------------------------------------------------------------------------
# 4.1 F8 -- MatchScenarioWrapper wired into env_creator, and a genuine no-op elsewhere.
# Before 2026-08-11 a match_base stage would have trained the DEFAULT spawn, silently.
# ---------------------------------------------------------------------------------------------
class _StubEnv:
    def __init__(self, mode):
        self.config = {"initial_scenario": ({"mode": mode} if mode is not None else {})}
        self.np_random = np.random.default_rng(0)
        self.calls: list[str] = []
        self.reset_called = False
        self.unwrapped = self

    def change_init_position(self, who, **kw):
        self.calls.append(who)

    def reset(self, *, seed=None, options=None):
        self.reset_called = True
        return ("obs", {})


def _dispatch(mode) -> _StubEnv:
    stub = _StubEnv(mode)
    w = MatchScenarioWrapper.__new__(MatchScenarioWrapper)   # bypass space checks
    w.env = stub
    w.reset()
    return stub


def verify_f8_wiring() -> None:
    section("4.1 F8 -- MatchScenarioWrapper wiring and no-op behaviour")
    for mode in (None, "obfm_offensive", "obfm_defensive", "habfm_beam_merge",
                 "two_circle_headon", "full_dogfight", "static"):
        stub = _dispatch(mode)
        check(f"mode={mode!r}: geometry untouched, reset still runs",
              not stub.calls and stub.reset_called)
    for mode in ("match_base", "match_tiebreak"):
        stub = _dispatch(mode)
        check(f"mode={mode!r}: both aircraft repositioned", stub.calls == ["ownship", "target"])

    fn = next(n for n in ast.walk(ast.parse((ROOT / "train_curriculum.py").read_text("utf-8")))
              if isinstance(n, ast.FunctionDef) and n.name == "env_creator")
    # SORT BY LINE NUMBER -- ast.walk() is breadth-first, NOT source order, so any wrapper applied
    # inside a conditional (ResidualBTWrapper, 2026-08-13) is yielded AFTER the top-level ones and
    # lands spuriously last. That made the "GLimitWrapper stays outermost" check below fail on a
    # tree whose runtime order was verified correct (GLimitWrapper -> ResidualBTWrapper ->
    # MatchScenarioWrapper -> ... -> DogFightWrapper). A guard that cries wolf gets ignored, which
    # is worse than no guard, so it sorts explicitly rather than trusting traversal order.
    applied = [name for _, name in sorted(
        (n.lineno, n.value.func.id) for n in ast.walk(fn)
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call)
        and isinstance(n.value.func, ast.Name) and n.value.func.id.endswith("Wrapper"))]
    check(f"MatchScenarioWrapper applied in env_creator (order: {applied})",
          "MatchScenarioWrapper" in applied)
    check("GLimitWrapper stays outermost", applied and applied[-1] == "GLimitWrapper")


# ---------------------------------------------------------------------------------------------
# 4.1 F8-STAGES -- the curriculum is the intended 16-stage ladder.
# ---------------------------------------------------------------------------------------------
def verify_ladder() -> None:
    section("4.1 F8-STAGES -- curriculum ladder")
    stages = get_stages()
    names = [s.name for s in stages]
    check(f"16 stages with contiguous unique indices (got {len(stages)})",
          len(stages) == 16 and [s.index for s in stages] == list(range(len(stages)))
          and len(set(names)) == len(names))
    check("high two-circle alphas 45/90/135/180 removed",
          not any(f"two_circle_headon_a{a:03d}" in names for a in (45, 90, 135, 180)))
    check("low alphas 0/3/5/8/12 kept",
          all(f"two_circle_headon_a{a:03d}" in names for a in (0, 3, 5, 8, 12)))
    check("ladder is wide -> close -> match_base, consecutive, before full_dogfight",
          names.index("match_base_close") == names.index("match_base_wide") + 1
          and names.index("match_base") == names.index("match_base_close") + 1
          and names.index("match_base") < names.index("full_dogfight"))

    # Every gated stage must be able to REACH its own advance_window. 4.1 F6 made that window
    # mean episodes rather than rows, and at ~27 iterations/episode a stage budgeted at the old
    # max_iterations=200 could only close ~7.4 -- so its gate was never evaluated and it exited
    # on max_iterations with the condition untested, silently. That hit 10 of the 15 gated
    # stages, including all three match_base ones. This is the check that would have caught it.
    ITERATIONS_PER_EPISODE = 27
    unreachable = [
        (s.name, s.max_iterations, s.max_iterations / ITERATIONS_PER_EPISODE, s.advance_window)
        for s in stages
        if s.advance_conditions
        and s.max_iterations < s.advance_window * ITERATIONS_PER_EPISODE
    ]
    for name, mx, eps, win in unreachable:
        print(f"      {name}: max_iterations={mx} -> ~{eps:.1f} episodes, needs {win}")
    check(f"every gated stage can reach its advance_window "
          f"({len(unreachable)} unreachable)", not unreachable)

    sib = next(s for s in stages if s.name == "habfm_beam_merge")
    for s in (x for x in stages if x.name.startswith("match_base")):
        sc = s.env_overrides["initial_scenario"]
        merged = {**DEFAULT_ENV_CONFIG["initial_scenario"], **sc}
        check(f"{s.name}: survives the DEFAULT_ENV_CONFIG merge at "
              f"{merged.get('altitude_m')} m / {merged.get('speed_mps')} m/s / "
              f"LOS {merged.get('los_deg')} deg",
              merged.get("mode") == "match_base"
              and merged.get("altitude_m") == MATCH_ALTITUDE_M
              and merged.get("speed_mps") == MATCH_SPEED_MPS
              and merged.get("los_deg") == MATCH_LOS_DEG
              and "separation_m" not in merged)
        check(f"{s.name}: separation band inside "
              f"[{MATCH_SEPARATION_MIN_M}, {MATCH_SEPARATION_MAX_M}]",
              MATCH_SEPARATION_MIN_M <= merged["separation_min_m"] <= MATCH_SEPARATION_MAX_M
              and MATCH_SEPARATION_MIN_M <= merged["separation_max_m"] <= MATCH_SEPARATION_MAX_M)
        check(f"{s.name}: gates mirror the neutral-merge siblings",
              s.advance_conditions == sib.advance_conditions and s.advance_window == 10
              and s.episode_step_limit == 12000)


# ---------------------------------------------------------------------------------------------
# v8 config -- must be v7 with only name / output.tag / notes changed, so v6/v7/v8 stay
# comparable. Skipped (not failed) if either file is absent.
# ---------------------------------------------------------------------------------------------
def verify_v8_yaml() -> None:
    section("v8 config -- differs from v7 only where intended")
    p7, p8 = ROOT / "experiments" / "real_eagle_v7.yaml", ROOT / "experiments" / "real_eagle_v8.yaml"
    if not (p7.exists() and p8.exists()):
        print("  [SKIP] real_eagle_v7.yaml / real_eagle_v8.yaml not both present")
        return
    v7 = yaml.safe_load(p7.read_text(encoding="utf-8"))
    v8 = yaml.safe_load(p8.read_text(encoding="utf-8"))

    def keypaths(d, prefix=""):
        out = set()
        for k, v in (d or {}).items():
            out.add(f"{prefix}{k}")
            if isinstance(v, dict):
                out |= keypaths(v, f"{prefix}{k}.")
        return out

    def get(d, path):
        cur = d
        for part in path.split("."):
            if not isinstance(cur, dict):
                return None
            cur = cur.get(part)
        return cur

    k7, k8 = keypaths(v7), keypaths(v8)
    check(f"same key structure (missing {sorted(k7 - k8) or 'none'}, "
          f"extra {sorted(k8 - k7) or 'none'})", k7 == k8)
    changed = sorted(k for k in (k7 & k8)
                     if not isinstance(get(v7, k), dict) and get(v7, k) != get(v8, k))
    check(f"only name / output.tag / notes differ (changed: {changed})",
          set(changed) == {"name", "output.tag", "notes"})
    check("hyperparameters identical -- v6/v7/v8 stay comparable", v7["algo"] == v8["algo"])
    check("v8 header drops the stale GEOMETRY WARNING",
          "GEOMETRY WARNING" not in p8.read_text(encoding="utf-8"))


def main() -> int:
    print("=" * 88)
    print("Regression guard for the 2026-08-11 fixes (fast checks; no simulator)")
    print("=" * 88)
    for fn in (verify_f6, verify_n3, verify_n4, verify_p7,
               verify_f8_wiring, verify_ladder, verify_v8_yaml):
        fn()
    print("\n" + "=" * 88)
    if _FAILED:
        print(f"{len(_FAILED)} CHECK(S) FAILED:")
        for f in _FAILED:
            print(f"  - {f}")
        print("Do not commit compute to a campaign until these pass.")
        return 1
    print("All checks passed.")
    print("NOTE: these are fast checks only. scripts/verify_match_spawn.py builds real envs and")
    print("confirms the match_base stages actually spawn at the competition geometry -- run it")
    print("too before launching a campaign.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
