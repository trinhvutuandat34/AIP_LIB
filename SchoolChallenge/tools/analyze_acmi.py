#!/usr/bin/env python3
"""Lightweight ACMI reader for this competition's telemetry format.

Not the SDK's own scripts/analyze_wez.py (that needs the compiled aircombat
engine, which isn't importable outside Windows+Python 3.14). This is a
from-scratch parser over the plain-text ACMI 2.2 format the engine emits,
good enough to answer "what did my tree actually do, and did it win."

Usage:
    python3 analyze_acmi.py match1.acmi [match2.acmi ...]
"""
import re
import sys
from collections import defaultdict

FIELD_RE = re.compile(r"([A-Za-z0-9_]+)=([^,]*)")


def parse_object_line(line):
    obj_id, rest = line.split(",", 1)
    fields = {}
    # T=... field can contain '|' separated values with no '=' inside except
    # the leading T=, so split on the first comma-separated chunks normally.
    for chunk in rest.split(","):
        if "=" not in chunk:
            continue
        k, v = chunk.split("=", 1)
        fields[k] = v
    return obj_id, fields


def parse_l1(v):
    # "node=yoyo_low_pullup pursuit=lead burst=0.00"
    out = {}
    for part in v.split():
        if "=" in part:
            k, val = part.split("=", 1)
            out[k] = val
    return out


def load(path):
    header = {}
    objects = {}  # id -> {"Name":..., "Color":..., "CallSign":...}
    series = defaultdict(lambda: defaultdict(list))  # id -> field -> [(t,val)]
    events = []
    t = 0.0
    # utf-8-sig, not utf-8: this engine's ACMI export writes a UTF-8 BOM on some
    # runs. Plain utf-8 leaves the BOM glued to "FileType", so the startswith()
    # check below misses it, the line falls through to parse_object_line(), and
    # that crashes on a line with no comma. utf-8-sig strips a leading BOM if
    # present and is a no-op otherwise, so it's safe for files without one too.
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            if line.startswith("FileType") or line.startswith("FileVersion"):
                continue
            if line.startswith("#"):
                t = float(line[1:])
                continue
            if line.startswith("0,"):
                rest = line[2:]
                if rest.startswith("Event="):
                    events.append((t, rest[len("Event="):]))
                else:
                    for k, v in FIELD_RE.findall(rest):
                        header[k] = v
                continue
            if line.startswith("-"):
                continue
            obj_id, fields = parse_object_line(line)
            if obj_id not in objects:
                objects[obj_id] = {}
            # Identity fields are set once at spawn; Color in particular can be
            # re-sent later (Tacview color-flash UI state) with a different
            # value (e.g. Blue -> Grey), so keep only the first value seen.
            for k in ("Name", "Type", "Color", "Coalition", "CallSign"):
                if k in fields and k not in objects[obj_id]:
                    objects[obj_id][k] = fields[k]
            for k, v in fields.items():
                if k == "T":
                    continue
                if k == "L1":
                    l1 = parse_l1(v)
                    for lk, lv in l1.items():
                        series[obj_id][f"L1.{lk}"].append((t, lv))
                    continue
                if k in ("L2", "L3"):
                    continue
                try:
                    fv = float(v)
                except ValueError:
                    fv = v
                series[obj_id][k].append((t, fv))
    return header, objects, series, events


def occupancy(node_series, total_t):
    """time spent per L1 node name, from a list of (t, name) samples."""
    dur = defaultdict(float)
    for i, (t, name) in enumerate(node_series):
        t_next = node_series[i + 1][0] if i + 1 < len(node_series) else total_t
        dur[name] += max(t_next - t, 0.0)
    return dict(sorted(dur.items(), key=lambda kv: -kv[1]))


def summarize(path):
    header, objects, series, events = load(path)
    print("=" * 78)
    print(path.split("/")[-1])
    comments = header.get("Comments", "")
    print(f"  {comments}")

    blue_id = red_id = None
    for oid, meta in objects.items():
        if meta.get("Color") == "Blue":
            blue_id = oid
        elif meta.get("Color") == "Red":
            red_id = oid
    if blue_id is None or red_id is None:
        print("  [경고] Blue/Red 객체를 못 찾음")
        return

    blue_name = objects[blue_id].get("CallSign", blue_id)
    red_name = objects[red_id].get("CallSign", red_id)

    def last(oid, key, default=None):
        s = series[oid].get(key)
        return s[-1][1] if s else default

    def first_t(oid, key):
        s = series[oid].get(key)
        return s[0][0] if s else None

    t_end = 0.0
    for oid in (blue_id, red_id):
        for key in ("Health",):
            s = series[oid].get(key)
            if s:
                t_end = max(t_end, s[-1][0])

    hp_blue0 = series[blue_id]["Health"][0][1] if series[blue_id].get("Health") else None
    hp_red0 = series[red_id]["Health"][0][1] if series[red_id].get("Health") else None
    hp_blue_end = last(blue_id, "Health")
    hp_red_end = last(red_id, "Health")

    print(f"  종료 시각: {t_end:.1f}s   HP  blue={hp_blue0:.0f}->{hp_blue_end:.0f}   "
          f"red={hp_red0:.0f}->{hp_red_end:.0f}")

    outcome_events = [e for t, e in events if "WINS" in e or "DRAW" in e
                      or "Bookmark" in e]
    for t, e in events:
        if "Bookmark" in e:
            print(f"  결과: {e}  @ {t:.1f}s")

    hit_events = [(t, e) for t, e in events if "hit" in e.lower() or "Hit" in e]
    if hit_events:
        print(f"  피격 이벤트 {len(hit_events)}건: " +
              ", ".join(f"{t:.1f}s" for t, _ in hit_events[:10]) +
              (" ..." if len(hit_events) > 10 else ""))

    # min distance, max InWEZ time, min CAS (stall risk), min alt-equivalent (T z)
    for oid, label in ((blue_id, blue_name), (red_id, red_name)):
        cas = series[oid].get("CAS", [])
        dist = series[oid].get("Distance", [])
        wez = series[oid].get("InWEZ", [])
        ata = series[oid].get("ATA", [])
        min_cas = min((v for _, v in cas), default=None)
        min_dist = min((v for _, v in dist), default=None)
        wez_time = 0.0
        for i, (t, v) in enumerate(wez):
            if v == "True":
                t_next = wez[i + 1][0] if i + 1 < len(wez) else t_end
                wez_time += max(t_next - t, 0.0)
        min_ata = min((v for _, v in ata), default=None)
        below220 = sum(1 for _, v in cas if v < 220)
        print(f"  [{label}] minCAS={min_cas:.0f}kt  minDist={min_dist:.0f}ft  "
              f"minATA={min_ata:.1f}deg  InWEZ={wez_time:.1f}s  "
              f"<220kt샘플={below220}/{len(cas)}")

    print(f"  [{blue_name}] L1 노드 점유 (내림차순, 상위 8개):")
    node_series = series[blue_id].get("L1.node", [])
    occ = occupancy(node_series, t_end)
    for name, dur in list(occ.items())[:8]:
        print(f"    {name:<24}{dur:7.1f}s")


def main():
    for p in sys.argv[1:]:
        summarize(p)


if __name__ == "__main__":
    main()
