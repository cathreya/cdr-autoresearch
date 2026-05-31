"""Pareto frontier over minimized axes.

A scheme is interesting if it is non-dominated: better on at least one axis without
being worse on any other. Frontiers are maintained PER REGIME (K, r) — a family can sit
on the front for one (K, r) and be dominated for another.
"""


def dominates(a, b, axes):
    """True if a dominates b: a <= b on every axis and a < b on at least one."""
    not_worse = all(a[k] <= b[k] for k in axes)
    strictly_better = any(a[k] < b[k] for k in axes)
    return not_worse and strictly_better


class ParetoFront:
    def __init__(self, axes):
        self.axes = list(axes)
        self.points = []  # records: dicts holding the axis keys (+ an "id"/metadata)

    def add(self, point):
        """Insert a point. Returns True if it is non-dominated (entered the front),
        evicting any existing points it dominates. Returns False if dominated (rejected).
        """
        # already present (same id) -> treat as not newly added
        pid = point.get("id")
        if pid is not None and any(p.get("id") == pid for p in self.points):
            return False
        for p in self.points:
            if dominates(p, point, self.axes):
                return False
        self.points = [p for p in self.points if not dominates(point, p, self.axes)]
        self.points.append(point)
        return True

    def front(self):
        return list(self.points)


def frontier_by_regime(records, axes, regime_keys=("K", "r")):
    """Group records by (K, r) and build a Pareto front per regime.
    Returns {(K, r): ParetoFront}.
    """
    fronts = {}
    for rec in records:
        key = tuple(rec[k] for k in regime_keys)
        fronts.setdefault(key, ParetoFront(axes)).add(rec)
    return fronts
