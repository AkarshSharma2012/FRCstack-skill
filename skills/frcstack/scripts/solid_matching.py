"""Geometry-only solid bijection, with a heuristic shortlist and exact fallback.

The 50 mm center window and 1% volume window only prioritize candidates. If
they cannot yield a perfect matching, remaining pairs are tested too, so the
heuristic never decides acceptance. The supplied Boolean verifier does that.
Typical separated layouts are sparse; coincident bodies or failed matches can
require quadratic work/storage. No exact bounding boxes or recursive searches.

Verifier calls are lazy: each (i, j) edge is evaluated at most once across the
whole match_solids call. BFS augmenting paths stop when a free right node is
reachable, avoiding unused candidate checks after a valid path is found.
"""
from bisect import bisect_left, bisect_right
from collections import deque
import math


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f'{label} must be a real numeric value')
    try:
        value = float(value)
    except OverflowError as error:
        raise ValueError(f'{label} exceeds finite float range') from error
    if not math.isfinite(value):
        raise ValueError(f'{label} must be finite')
    return value


def _properties(shape):
    volume = _number(shape.Volume(), 'solid volume')
    if volume <= 0:
        raise ValueError('solid volume must be positive')
    try:
        center_method = shape.Center
    except AttributeError:
        return volume, None  # Compatibility with genuinely opaque test doubles.
    center = center_method()  # A real kernel/center failure must not be hidden.
    coords = []
    for lower, upper in (('x', 'X'), ('y', 'Y'), ('z', 'Z')):
        try:
            value = getattr(center, lower)
        except AttributeError:
            value = getattr(center, upper)
        coords.append(_number(value() if callable(value) else value, 'center '+lower))
    return volume, tuple(coords)


def _maximum_matching(adjacency, count, verify_edge=None):
    """Iterative augmenting paths, optionally verifying candidate edges lazily."""
    left, right = {}, {}
    for root in range(count):
        queue, seen_left, parent_right = deque([root]), {root}, {}
        free = None
        while queue and free is None:
            i = queue.popleft()
            for j in adjacency[i]:
                if j in parent_right:
                    continue
                if verify_edge is not None and not verify_edge(i, j):
                    continue
                parent_right[j] = i
                if j not in right:
                    free = j
                    break
                next_left = right[j]
                if next_left not in seen_left:
                    seen_left.add(next_left)
                    queue.append(next_left)
        while free is not None:
            i = parent_right[free]
            previous = left.get(i)
            left[i], right[free] = free, i
            free = previous
    return left


def match_solids(original, roundtrip, verify_pair, tol_mm3=1e-5):
    """Return (passed, per-original reports); neither names nor mates verified."""
    tol = _number(tol_mm3, 'tol_mm3')
    if tol < 0:
        raise ValueError('tol_mm3 must be nonnegative')
    n, m = len(original), len(roundtrip)
    if n != m:
        return False, [{'error': f'solid count mismatch: original={n} roundtrip={m}'}]
    if not n:
        return False, [{'error': 'empty solid lists'}]
    properties = []
    for label, shapes in (('original', original), ('roundtrip', roundtrip)):
        row = []
        for i, shape in enumerate(shapes):
            try:
                row.append(_properties(shape))
            except Exception as error:
                return False, [{'error': f'{label} solid {i}: {error}'}]
        properties.append(row)
    op, rp = properties
    indexed = sorted((p[1][0], j) for j, p in enumerate(rp) if p[1] is not None)
    xs = [x for x, _ in indexed]
    unknown_centers = [j for j, p in enumerate(rp) if p[1] is None]

    cache = {}
    errors, error_count = [], 0

    def check(i, j):
        nonlocal error_count
        if (i, j) in cache:
            return cache[(i, j)]
        try:
            result = verify_pair(original[i], roundtrip[j], tol)
            if type(result) is not bool:
                raise TypeError('verifier must return bool')
            cache[(i, j)] = result
            return result
        except Exception as error:
            error_count += 1
            if len(errors) < 32:
                errors.append({'original_index': i, 'roundtrip_index': j,
                                'error': str(error)})
            cache[(i, j)] = False
            return False

    def build_shortlist(i):
        volume, center = op[i]
        if center is None:
            # No spatial info: conservative full enumeration by index.
            return list(range(m))
        lo = bisect_left(xs, center[0] - 50)
        hi = bisect_right(xs, center[0] + 50)
        cands = set(j for _, j in indexed[lo:hi]) | set(unknown_centers)
        filtered = []
        for j in cands:
            rv, rc = rp[j]
            if rc is not None and any(abs(a - b) > 50 for a, b in zip(center, rc)):
                continue
            if rc is not None and abs(volume - rv) > max(tol, 0.01 * max(volume, rv)):
                continue
            dist2 = (sum((a - b) ** 2 for a, b in zip(center, rc))
                     if rc is not None else float('inf'))
            filtered.append((dist2, abs(volume - rv), j))
        filtered.sort()
        return [j for _, _, j in filtered]

    shortlists = [build_shortlist(i) for i in range(n)]

    matched = _maximum_matching(shortlists, n, check)

    if len(matched) != n:
        # Fallback: extend each candidate list to all rt indices (shortlist first,
        # then remaining sorted by volume difference and index). Cached results are
        # reused so no (i, j) edge is verified twice across the whole call. Prior
        # greedy assignments are cleared so augmenting paths can reassign freely.
        shortlist_sets = [set(sl) for sl in shortlists]
        full_candidates = []
        for i in range(n):
            vol_i = op[i][0]
            remaining = sorted(
                (j for j in range(m) if j not in shortlist_sets[i]),
                key=lambda j, v=vol_i: (abs(v - rp[j][0]), j),
            )
            full_candidates.append(shortlists[i] + remaining)
        matched = _maximum_matching(full_candidates, n, check)

    passed = len(matched) == n
    results = []
    for i in range(n):
        j = matched.get(i)
        record = {'solid_orig_index': i, 'solid_rt_index': j,
                  'passed': j is not None, 'original_volume_mm3': op[i][0],
                  'roundtrip_volume_mm3': rp[j][0] if j is not None else None}
        if not passed and i == 0 and error_count:
            record.update(verifier_errors=errors, verifier_error_count=error_count,
                          omitted_verifier_error_count=max(0, error_count - len(errors)))
        results.append(record)
    return passed, results
