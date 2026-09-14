"""Emit simplified Rule-XML variants by deleting whole gate blocks from the shipped tree.

    python scripts/make_rule_variant.py            # writes every variant listed in VARIANTS
    python scripts/make_rule_variant.py --list     # just show the top-level gate blocks

WHY A CUSTOM WALKER AND NOT ElementTree. The shipped Rule XMLs are NOT well-formed XML: they
carry `--` inside comments (e.g. Rule_real_eagle.xml line 202, "eligible -- Task_Evade"), which
is illegal per the spec. `xml.etree` refuses all three files; tinyxml2 inside the DLL accepts
them. So a standards parser cannot be used to read, edit or lint this tree, and hand-slicing the
text is how variants have been made until now. This does the slicing by tracking tag depth
instead, which is what makes "delete the Gate 1 block" a safe operation rather than a regex
guess.

WHY DELETE WHOLE BLOCKS. The outer Fallback's children ARE the gates, in priority order, and
BehaviorTree.CPP's Fallback semantics mean deleting one simply lets the next take its ticks. So
a deletion is the cleanest possible ablation: nothing is re-tuned, nothing is re-ordered, and any
change in outcome is attributable to that one block having been in the way.

WHAT THIS IS FOR. `ep_bt_frac` averages ~0.21, so the BT flies roughly one tick in five (the
Python law in student/controller_providers.py has the rest). The first gate trace showed the
tactical middle of the tree winning most of those ticks while Gun_Track ran on 0.2%. These
variants test whether that middle is earning its place against the cutoff, or fighting the
control law.

SAFETY. Never writes to Rule.xml / Rule_forTraining.xml / Rule_real_eagle.xml. Output goes to
experiments/rule_variants/ only, and every variant is checked for tag balance before it is
written.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SOURCE = _ROOT / "Rule_real_eagle.xml"
_OUT = _ROOT / "experiments" / "rule_variants"

_TAG = re.compile(r"<\s*(/?)\s*([A-Za-z_][\w.\-]*)([^>]*?)(/?)\s*>", re.S)

# name -> (blocks to delete, one-line rationale for the file header)
VARIANTS: dict[str, tuple[tuple[str, ...], str]] = {
    "bt_minimal": (
        ("Gate1", "Gate2", "Gate3", "Gate4", "Tail_SingleSideOffset", "Tail_DistGt2000"),
        "Gate 0 (climb) + the gun-hold sequence + Tail_Pure. Everything tactical removed: the "
        "Python control law already owns terminal pointing, so this asks whether the BT's middle "
        "is contributing anything or just taking ticks away from a simple pursuit.",
    ),
    "bt_no_gate1": (
        ("Gate1",),
        "The defensive block removed. Gate1_Notch alone succeeded on 7,660 of 15,751 traced "
        "ticks, and the cutoff has no defensive layer of its own to punish us for dropping it.",
    ),
    # NODE-LEVEL variants. These do not delete gates, they delete the specific nodes the gate
    # trace measured as either dead or disruptive. Handled by NODE_VARIANTS below, not here.
    "bt_pursuit_only": (
        ("Gate1", "Gate2", "Gate3"),
        "Keeps Gate 0, the gun hold and Gate 4's offensive selector; drops defensive, merge and "
        "energy. Middle ground between bt_minimal and the shipped tree.",
    ),
}



# Node-level variants: name -> (nodes to delete, rationale)
NODE_VARIANTS: dict[str, tuple[tuple[str, ...], str]] = {
    "bt_deadwood": (
        ("Gate1_DefensiveSpiral", "Gate2_RollingScissors", "Gate2_VerticalScissors",
         "Gate3_AnglesTactics", "Gate4_LowYoYo"),
        "Removes ONLY nodes the 2026-09-09 gate trace measured as never succeeding: "
        "Gate1_DefensiveSpiral 0/7287, Gate2_RollingScissors, Gate2_VerticalScissors and "
        "Gate4_LowYoYo NEVER-SUCCEEDS, Gate3_AnglesTactics NEVER-EVALUATED. Nothing that ever "
        "flew is touched, so this should be behaviourally identical to the shipped tree. It is "
        "therefore BOTH a real simplification and the control that proves the ablation harness "
        "is not itself changing outcomes. If this arm moves, distrust every other arm.",
    ),
    "bt_deadwood_no_notch": (
        ("Gate1_DefensiveSpiral", "Gate2_RollingScissors", "Gate2_VerticalScissors",
         "Gate3_AnglesTactics", "Gate4_LowYoYo", "Gate1_Notch"),
        "The deadwood above PLUS Gate1_Notch, the one node measured to disrupt rather than to "
        "sit idle: it succeeds on 7,660 of 15,695 traced ticks, sits first in the Gate 1 "
        "Fallback, holds no maneuver phase claim, and its own XML comment records it shadowing "
        "the whole of Gate 2 (F17). This is the targeted 'condense what interrupts the "
        "maneuvers' arm -- everything that still flies a coherent maneuver is left intact.",
    ),
}


def _children_of_outer_fallback(text: str) -> list[tuple[int, int, str]]:
    """Return (start, end, label) spans for each child of the gate Fallback.

    The gate Fallback is the one whose first child is Task_ClimbToSafeAltitude; identifying it by
    content rather than by position means this keeps working if a wrapper is added above it.
    """
    # Mask comments so tags mentioned inside them are never matched, but keep offsets identical.
    masked = re.sub(r"<!--.*?-->", lambda m: " " * len(m.group(0)), text, flags=re.S)

    stack: list[tuple[str, int]] = []
    outer_depth = None
    outer_close = None
    spans: list[tuple[int, int, str]] = []
    pending: tuple[int, str] | None = None

    for m in _TAG.finditer(masked):
        close, tag, attrs, sc = m.groups()
        if attrs.rstrip().endswith("/"):
            sc = "/"
        name_m = re.search(r'name="([^"]+)"', attrs)
        name = name_m.group(1) if name_m else ""

        if close:
            if not stack:
                continue
            _t, _s = stack.pop()
            if outer_depth is not None and len(stack) == outer_depth and pending is not None:
                spans.append((pending[0], m.end(), pending[1]))
                pending = None
            if outer_depth is not None and len(stack) < outer_depth:
                outer_close = m.start()
                break
            continue

        # A leaf child of the outer Fallback closes its own span immediately.
        if outer_depth is not None and len(stack) == outer_depth and pending is None and sc:
            spans.append((m.start(), m.end(), name or tag))
            continue

        if outer_depth is not None and len(stack) == outer_depth and pending is None and not sc:
            pending = (m.start(), name or tag)

        if not sc:
            stack.append((tag, m.start()))
            if outer_depth is None and tag == "Fallback":
                # Peek: is the next opening tag Task_ClimbToSafeAltitude?
                nxt = _TAG.search(masked, m.end())
                if nxt and nxt.group(2) == "Task_ClimbToSafeAltitude":
                    outer_depth = len(stack)
    if outer_depth is None:
        raise SystemExit("could not locate the gate Fallback (no Task_ClimbToSafeAltitude child)")
    return spans


def _label_for(text: str, span: tuple[int, int, str]) -> str:
    """A human name for a gate block: its first recognisable Gate*/Tail* node name."""
    chunk = text[span[0]:span[1]]
    names = re.findall(r'name="((?:Gate|Tail|Gun)[^"]*)"', chunk)
    if not names:
        return span[2]
    for n in names:
        if n.startswith(("Gate0", "Gun_")):
            return n
    return re.match(r"(Gate\d|Tail_\w+|Gun_\w+)", names[0]).group(1)



def _enclosing_block(text: str, node_name: str) -> tuple[int, int]:
    """Span to delete for `node_name`, decided by its IMMEDIATE parent.

    parent is a Sequence  -> delete the whole Sequence. That Sequence exists to guard this one
                             Task with its decorators; deleting the Task alone would leave a
                             Sequence of bare decorators, and in BehaviorTree.CPP that SUCCEEDS
                             whenever they all pass, silently claiming the tick and flying
                             nothing. That is the F25 shape and it must not be reintroduced.
    parent is a Fallback  -> delete just the node. The Gate 2 scissors trio and the Gate 4
                             selector children are bare Fallback children; taking their parent
                             would remove their siblings too. Getting this wrong produced
                             overlapping spans and a corrupted tree on the first attempt.
    """
    masked = re.sub(r"<!--.*?-->", lambda m: " " * len(m.group(0)), text, flags=re.S)
    stack: list[tuple[str, int]] = []
    for m in _TAG.finditer(masked):
        close, tag, attrs, sc = m.groups()
        if attrs.rstrip().endswith("/"):
            sc = "/"
        hit = re.search(r'name="%s"' % re.escape(node_name), attrs or "")
        if hit and not close:
            parent = stack[-1] if stack else None
            if parent and parent[0] == "Sequence":
                # Find that Sequence's close tag by depth from here.
                depth = 0
                for m2 in _TAG.finditer(masked, parent[1]):
                    c2, t2, a2, s2 = m2.groups()
                    if a2.rstrip().endswith("/"):
                        s2 = "/"
                    if c2:
                        depth -= 1
                        if depth == 0:
                            return (parent[1], m2.end())
                    elif not s2:
                        depth += 1
                raise ValueError(f"unclosed Sequence around {node_name}")
            if sc:
                return (m.start(), m.end())
            depth = 0
            for m2 in _TAG.finditer(masked, m.start()):
                c2, t2, a2, s2 = m2.groups()
                if a2.rstrip().endswith("/"):
                    s2 = "/"
                if c2:
                    depth -= 1
                    if depth == 0:
                        return (m.start(), m2.end())
                elif not s2:
                    depth += 1
            raise ValueError(f"unclosed node {node_name}")
        if close:
            if stack:
                stack.pop()
        elif not sc:
            stack.append((tag, m.start()))
    raise KeyError(node_name)


def _drop_nodes(text: str, names: tuple[str, ...]) -> tuple[str, list[str]]:
    spans = []
    for n in names:
        try:
            spans.append((*_enclosing_block(text, n), n))
        except KeyError:
            print(f"   !! node not found, skipped: {n}")
    # Overlapping spans would delete the same region twice and corrupt the tree. Two nodes that
    # resolve to one span means the parent rule picked a block that owns both; drop the duplicate
    # rather than applying it twice.
    spans.sort(key=lambda x: -x[0])
    kept: list[tuple[int, int, str]] = []
    for s_, e_, n_ in spans:
        if any(not (e_ <= ks or s_ >= ke) for ks, ke, _ in kept):
            print(f"   !! {n_} overlaps an already-removed span, skipped")
            continue
        kept.append((s_, e_, n_))
    removed = []
    for s_, e_, n_ in kept:
        text = text[:s_] + text[e_:]
        removed.append(n_)
    return text, list(reversed(removed))


def _balanced(text: str) -> bool:
    body = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    stack: list[str] = []
    for m in _TAG.finditer(body):
        close, tag, attrs, sc = m.groups()
        if attrs.rstrip().endswith("/"):
            sc = "/"
        if close:
            if not stack or stack.pop() != tag:
                return False
        elif not sc:
            stack.append(tag)
    return not stack


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="show the gate blocks and exit")
    a = ap.parse_args()

    text = _SOURCE.read_text(encoding="utf-8")
    spans = _children_of_outer_fallback(text)
    labelled = [(s, e, _label_for(text, (s, e, lab))) for s, e, lab in spans]

    if a.list:
        for s, e, lab in labelled:
            first = text[s:e].strip().splitlines()[0][:70]
            print(f"  {lab:26s} {e - s:6d} bytes   {first}")
        return 0

    _OUT.mkdir(parents=True, exist_ok=True)
    for name, (drop, why) in VARIANTS.items():
        out = text
        removed = []
        # Delete from the end so earlier offsets stay valid.
        for s, e, lab in sorted(labelled, key=lambda x: -x[0]):
            if any(lab.startswith(d) for d in drop):
                out = out[:s] + out[e:]
                removed.append(lab)
        if not removed:
            print(f"!! {name}: nothing matched {drop}")
            continue
        header = (f"<!-- VARIANT {name} (generated by scripts/make_rule_variant.py, 2026-09-09).\n"
                  f"     NOT SHIPPED. Removed: {', '.join(reversed(removed))}.\n"
                  f"     {why}\n"
                  f"     Regenerate rather than hand-editing. -->\n")
        out = header + out
        if not _balanced(out):
            print(f"!! {name}: tag balance broken, NOT written")
            continue
        dst = _OUT / f"{name}.xml"
        dst.write_text(out, encoding="utf-8")
        print(f"wrote {dst.name:24s} removed {len(removed)} blocks: {', '.join(reversed(removed))}")

    for name, (nodes, why) in NODE_VARIANTS.items():
        out, removed = _drop_nodes(text, nodes)
        if not removed:
            print(f"!! {name}: nothing matched")
            continue
        header = (f"<!-- VARIANT {name} (generated by scripts/make_rule_variant.py, 2026-09-09).\n"
                  f"     NOT SHIPPED. Removed nodes: {', '.join(removed)}.\n"
                  f"     {why}\n"
                  f"     Regenerate rather than hand-editing. -->\n")
        out = header + out
        if not _balanced(out):
            print(f"!! {name}: tag balance broken, NOT written")
            continue
        (_OUT / f"{name}.xml").write_text(out, encoding="utf-8")
        print(f"wrote {name+'.xml':24s} removed {len(removed)} nodes: {', '.join(removed)}")

    assert _SOURCE.read_text(encoding="utf-8") == text, "source Rule XML was modified"
    print("\nshipped Rule XMLs untouched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
