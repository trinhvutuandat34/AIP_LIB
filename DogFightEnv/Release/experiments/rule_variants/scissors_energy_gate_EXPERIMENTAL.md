# Scissors energy gate — experimental variant (2026-08-21, F41 candidate)

> **⚑ NOT RUN, AND NOT WORTH RUNNING. Killed at pre-flight — the change is mechanically a
> NO-OP on the geometry that decides everything. The live tree was never modified
> (`git` clean, md5 `F49BACF8…` unchanged throughout).**
>
> Before spending ~4 h of contended CPU on the A/B, the `energy_ratio` column already present
> in the gate traces was used to measure how often the proposed gate would actually bite —
> i.e. how often `EnergyRatio > 1.2` **while the scissors branch is entered**:
>
> | geometry | ticks inside scissors branch | of which ratio > 1.2 |
> |---|---|---|
> | `match_base` (confirmed prelim geometry) | 972 | **0 — 0.0 %** |
> | `two_circle_headon` | 439 | **0 — 0.0 %** |
> | `vptrack` trace (08-20) | 19 | **0 — 0.0 %** |
> | `obfm_defensive` | 9 | 4, but 9 ticks total is noise |
>
> Median energy ratio *inside* the branch is **1.000**. `Task_FlatScissors` would have failed
> its new guard on essentially zero ticks, so both shadowed nodes would have stayed dead and
> the A/B would have returned a null that looked like evidence.
>
> **Why, mechanically — and why this reframes the audit finding.** The branch only opens on
> mutual ATA > 45° inside 2000 m: a stalemate in which neither aircraft can point. Energy has
> necessarily equalised by then — that is *what makes it a flat scissors*. So
> `Task_VerticalScissors` / `Task_RollingScissors` are not starved by a defect; their doctrinal
> precondition (an energy advantage, or vertical separation) does not co-occur with the branch's
> own entry condition. **`Task_FlatScissors` holding the claim there is correct behaviour, not
> the F37 bug repeating.** F37 was a genuine defect because `Task_JinkingTurn` monopolised a
> *defensive* tick where `Task_Evade` was doctrinally preferable. No equivalent case is
> demonstrated here.
>
> **Standing conclusion: the unreachable-node audit found NO actionable defect.** 57/60 named
> nodes succeed; the 3 that never fire are explained without invoking a bug. Do not touch the
> tree on the strength of the audit alone.
>
> **If anyone revisits this:** a threshold near 1.0 *would* bite, but it is arbitrary rather
> than doctrinal — it would amount to a coin-flip between flat and vertical scissors, and would
> need the full two-seed peer-rig treatment plus a cutoff re-check to adopt. `Gate4_LowYoYo` is
> not fixable in XML at all: Gate 4's children self-gate their entry conditions **inside C++**,
> so the only XML lever there is a reorder — the exact shape F26-GATE1-REJECTED already
> rejected once.

**Status: pre-flight NEGATIVE, never executed. Do not apply to the live tree.**

## The defect this targets

`scripts/audit_unreachable_nodes.py` (new, 2026-08-21) gate-traced the live tree across four
geometries and found **3 of 60 named nodes have never once returned SUCCESS**, in any trace, in
either controller configuration:

| node | class | `bt` x4 geometries | `vptrack` (08-20 trace) |
|---|---|---|---|
| `Gate2_VerticalScissors` | `Task_VerticalScissors` | never evaluated | 0 S / 14 F |
| `Gate2_RollingScissors` | `Task_RollingScissors` | never evaluated | 0 S / 14 F |
| `Gate4_LowYoYo` | `Task_LowYoYo` | never evaluated | 0 S / 96 F |

The mechanism is **the F37 shape repeating**. `Task_FlatScissors` returns SUCCESS on every tick
it is ever evaluated when the tree is flying (300 S / **0 F** on `match_base`), and it is the
first child of the scissors `Fallback` — so the two nodes beneath it are structurally shadowed,
exactly as `Task_JinkingTurn` shadowed `Task_Evade` before F37.

All three dead nodes are **vertical-plane** maneuvers. Of our vertical repertoire only
`HighYoYoUp` and `BarrelRollAttack` work; Low Yo-Yo and both scissors never fire. Read alongside
`BFM_MANEUVER_GAP_REFERENCE.md` (the vertical-*reversal* family — Split-S, sliceback, pitchback —
has no node at all) and the cutoff model's own `Split` node which we lack entirely, the vertical
game is roughly half-implemented and half-shadowed.

## The change under test (scissors only — deliberately ONE change)

Wrap `Task_FlatScissors` in an **anonymous** `<Sequence>` behind one energy decorator, so it
stops claiming when we hold an energy advantage and the branch can fall through:

```xml
<Fallback>
  <Sequence>
    <DECO_EnergyRatioCheck name="Gate2_Flat_NotEnergyAdv_Lt1p2" UpDown="Less" Ratio="1.2" BB="{BB}"/>
    <Task_FlatScissors name="Gate2_FlatScissors" BB="{BB}"/>
  </Sequence>
  <Task_VerticalScissors name="Gate2_VerticalScissors" BB="{BB}"/>
  <Task_RollingScissors name="Gate2_RollingScissors" BB="{BB}"/>
</Fallback>
```

**Doctrinal basis:** the flat scissors is the classic *low-energy* answer — trade turn for an
overshoot when you cannot climb. With an energy advantage the rolling scissors (or a vertical
exit) is the doctrinally correct choice, and that is precisely the branch currently starved.
Ratio 1.2 mirrors the existing `Gate3_Ratio_Gt1_4` / `Gate3_Ratio_Lt0_8` band already in the
tree, sitting between them.

**Why an added decorator rather than a reorder:** F26-GATE1-REJECTED reordered `Task_Evade` above
`Task_JinkingTurn` and it reversed 2:1 on `match_base` under isolation. F37 succeeded by *adding
one guard* instead, leaving priority unchanged outside the targeted condition. This follows F37.

**Why not also fix `Gate4_LowYoYo` in the same change:** two changes at once confound the
measurement. If the scissors gate is adopted, Low Yo-Yo gets its own separate A/B.

## Constraints respected

- **XML-only, no DLL rebuild.** `DECO_EnergyRatioCheck` is already live in Gate 3.
- **The new `<Sequence>` is ANONYMOUS.** Per F25, a `name=` attribute on a control node makes
  BehaviorTree.CPP build it with **zero children**. Never name a control node in this tree.
- Applied to **both** `Rule_forTraining.xml` and `Rule_real_eagle.xml`, kept byte-identical,
  UTF-8 **no BOM**, CRLF, Korean comments preserved.
- Backups: `Rule_{forTraining,real_eagle}.xml.bak_pre_scissors_ab_20260821`.

## How it is being scored

Through the **peer rig only** (`scripts/setup_peer_bt.py`) — never a symmetric measurement
(F26-RULE). Peer runs the unmodified tree; ours runs the variant. Both sides pinned to the
shipping controller config (`throttle_control=True`, 4000 m / 60°) so the tree is the only
variable.

- `match_base` (the CONFIRMED prelim geometry) first, **two seeds** (0 and 1000) — F32 showed a
  single seed at this noise floor (SE ~8.4% at N=30) can produce a fully convincing illusion that
  reverses on a second seed.
- Only if `match_base` is neutral-or-better: `obfm_defensive`, then a cutoff-gate re-check
  (the one-shot mandatory bar, currently 100%).

**Adoption bar:** must not regress `match_base` on *either* seed. A change that helps only the
unconfirmed OBFM geometries while costing the confirmed one is what F26-GATE1-REJECTED already
rejected once.
