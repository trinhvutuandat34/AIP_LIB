"""Check geometry against the original matrix equations; optionally benchmark a baseline file.

    python scripts/test_geometry_performance.py [--baseline path/to/GeoMathUtil.py]
"""
import argparse
import importlib.util
from pathlib import Path
from statistics import median
import sys
from time import perf_counter

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from GeoMathUtil import D2R, R2D, GeometryInfo, _body_los


def reference(own, target, proj=False, aspect=False):
    if aspect:
        own, target = target, own
    roll, pitch, yaw = own[3:6] * D2R
    tx = np.array([[1, 0, 0], [0, np.cos(roll), np.sin(roll)],
                   [0, -np.sin(roll), np.cos(roll)]])
    ty = np.array([[np.cos(pitch), 0, -np.sin(pitch)], [0, 1, 0],
                   [np.sin(pitch), 0, np.cos(pitch)]])
    tz = np.array([[np.cos(yaw), np.sin(yaw), 0],
                   [-np.sin(yaw), np.cos(yaw), 0], [0, 0, 1]])
    transform = tz if proj else tx @ (ty @ tz)
    if aspect:
        transform = np.diag([-1, -1, 1]) @ transform
    rel = target[:3] - own[:3]
    norm = np.linalg.norm(rel)
    x, y, z = transform @ (rel / norm if norm != 0 else rel)
    angle = np.arctan2(y, x) if proj else np.arccos(np.clip(x, -1, 1))
    if aspect and not proj:
        sign = -1 if y < -0.10 else (np.sign(z) if -0.01 < y < 0.01 else 1)
        angle *= sign
    return angle * R2D, (np.arctan2(y, x) * R2D, -np.arcsin(np.clip(z, -1, 1)) * R2D)


def check():
    geo = GeometryInfo()
    rng = np.random.default_rng(20260912)
    own, target = np.zeros(51), np.zeros(51)
    cases = [(own.copy(), target.copy())]
    for yaw in (0, 90, 180, 270, 360):
        for roll in (0, 90, 180, -90):
            for position in ((100, 0, 0), (-100, 0, 0), (0, 0, -100)):
                target[:3] = position
                own[3:6] = roll, 0, yaw
                cases.append((own.copy(), target.copy()))
    for _ in range(1000):
        own[:6], target[:6] = rng.uniform(-180, 180, (2, 6))
        cases.append((own.copy(), target.copy()))
    # Equal values with different precision must not collide in the cache.
    for dtype in (np.float32, np.float64):
        a, b = own.astype(np.float32).astype(dtype), target.astype(np.float32).astype(dtype)
        for proj in (False, True):
            np.testing.assert_allclose(geo._get_antenna_train_angle(a, b, proj),
                                       reference(a, b, proj)[0], atol=1e-10, rtol=0)
            np.testing.assert_allclose(geo._get_aspect_angle(a, b, proj),
                                       reference(a, b, proj, True)[0], atol=1e-10, rtol=0)
    for a, b in cases:
        # Reuse and mutate the same arrays: caching their identity would return stale geometry.
        own[:], target[:] = a, b
        for first, second in ((own, target), (target, own)):
            for proj in (False, True):
                np.testing.assert_allclose(geo._get_antenna_train_angle(first, second, proj),
                                           reference(first, second, proj)[0], atol=1e-10, rtol=0)
                np.testing.assert_allclose(geo._get_aspect_angle(first, second, proj),
                                           reference(first, second, proj, True)[0], atol=1e-10, rtol=0)
            np.testing.assert_allclose(geo._get_los_angle(first, second),
                                       reference(first, second)[1], atol=1e-10, rtol=0)
    # Non-finite sensor values must propagate, rather than become a valid cached solution.
    with np.errstate(invalid="ignore"):
        own[0] = np.nan
        assert np.isnan(geo._get_antenna_train_angle(own, target))
        own[0], own[5] = 0, np.inf
        assert np.isnan(geo._get_antenna_train_angle(own, target))
    assert _body_los.cache_info().currsize <= 128
    print(f"PASS: {len(cases)} geometries, both directions, 2D/3D, array mutation and invalid input")
    return cases[-200:]


def benchmark(geo, cases):
    times = []
    for _ in range(5):
        start = perf_counter()
        for own, target in cases:
            # Observations for both aircraft, reward/damage and evaluation reuse each frame.
            for a, b in ((own, target), (target, own), (own, target)):
                geo._get_antenna_train_angle(a, b)
                geo._get_aspect_angle(a, b)
                geo._get_los_angle(a, b)
            for _ in range(3):
                geo._get_antenna_train_angle(own, target)
                geo._get_antenna_train_angle(target, own)
        times.append(perf_counter() - start)
    return median(times)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args()
    cases = check()
    if args.baseline:
        spec = importlib.util.spec_from_file_location("baseline_geometry", args.baseline)
        baseline = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(baseline)
        before = benchmark(baseline.GeometryInfo(), cases)
        after = benchmark(GeometryInfo(), cases)
        print(f"Geometry workload (median of 5): {before:.4f}s -> {after:.4f}s ({before/after:.2f}x)")
