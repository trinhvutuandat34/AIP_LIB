#!/usr/bin/env python3
"""Compact win/loss/draw + hard-deck-chatter tally across many ACMI files."""
import sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from analyze_acmi import load
import re

def tally(paths):
    rows = []
    for path in paths:
        header, objects, series, events = load(path)
        blue_id = [oid for oid, m in objects.items() if m.get("Color") == "Blue"][0]
        red_id = [oid for oid, m in objects.items() if m.get("Color") == "Red"][0]
        comments = header.get("Comments", "")
        m = re.search(r"scenario=([a-z_]+);seed=(-?\d+)", comments)
        scen, seed = (m.group(1), m.group(2)) if m else ("?", "?")
        om = re.search(r"_vs_(red_[a-z]+)_", path)
        oppo = om.group(1) if om else objects[red_id].get("CallSign", "?")
        outcome = next((e for t, e in events if "WINS" in e), "?")
        hp_b = series[blue_id]["Health"][-1][1]
        hp_r = series[red_id]["Health"][-1][1]
        t_end = series[blue_id]["Health"][-1][0]

        node_series = series[blue_id]["L1.node"]
        prev = None
        hd_entries = 0
        hd_time = 0.0
        for i, (t, n) in enumerate(node_series):
            t_next = node_series[i + 1][0] if i + 1 < len(node_series) else t_end
            if n == "recover_hard_deck":
                hd_time += max(t_next - t, 0)
                if prev != "recover_hard_deck":
                    hd_entries += 1
            prev = n
        rows.append(dict(path=path.split("/")[-1], scen=scen, oppo=oppo, seed=seed,
                          outcome=outcome, hp_b=hp_b, hp_r=hp_r, t_end=t_end,
                          hd_entries=hd_entries, hd_time=hd_time))
    return rows


def main():
    rows = tally(sys.argv[1:])
    w = l = d = 0
    print(f"{'시나리오':<15}{'상대':<14}{'결과':<28}{'HP(b-r)':<14}{'종료':>7}  {'HD진입':>6}  {'HD시간':>7}")
    for r in sorted(rows, key=lambda r: (r["oppo"], r["scen"])):
        tag = r["outcome"]
        if "BLUE WINS" in tag:
            w += 1
        elif "RED WINS" in tag:
            l += 1
        elif "DRAW" in tag:
            d += 1
        print(f"{r['scen']:<15}{r['oppo']:<14}{tag:<28}"
              f"{r['hp_b']:5.1f}-{r['hp_r']:<7.1f}{r['t_end']:7.1f}  "
              f"{r['hd_entries']:6d}  {r['hd_time']:6.1f}s")
    print(f"\n합계 {len(rows)}경기: {w}승 {l}패 {d}무")
    no_contact = sum(1 for r in rows if "no_contact" in r["outcome"])
    print(f"무접촉 쌍방패: {no_contact}")
    hd_total = sum(r["hd_entries"] for r in rows)
    print(f"하드덱 분기 총 진입 횟수(전 경기 합): {hd_total}  (평균 {hd_total/len(rows):.1f}/경기)")


if __name__ == "__main__":
    main()
