"""Regression Fixture A (K=8, r=6, removed=8, unit T=14) as reusable artifacts."""


def _mod1(x, n):
    return ((x - 1) % n + n) % n + 1


def _cyc(s, n, r):
    return sorted(_mod1(s + t, n) for t in range(r))


def build():
    K, r, unit, removed = 8, 6, 14, 8
    initial = {
        "kind": "placement", "nodes": K, "r": r, "unit": unit,
        "segments": [{"id": i + 1, "size": unit, "storage": _cyc(i + 1, K, r)} for i in range(K)],
    }
    target_size = (unit * K) // (K - 1)  # 16
    target = {
        "kind": "placement", "nodes": K - 1, "r": r, "unit": unit,
        "segments": [{"id": i + 1, "size": target_size, "storage": _cyc(i + 1, K - 1, r)} for i in range(K - 1)],
    }

    def P(pid, source, dest, size):
        return {"id": pid, "source": source, "dest": dest, "size": size}

    plan = {
        "kind": "plan", "removed": removed,
        "pieces": [
            P("W1", 1, [], 14), P("W2", 2, [], 14),
            P("W3_1", 3, [1], 12), P("W3_2", 3, [2], 2),
            P("W4_2", 4, [2], 10), P("W4_3", 4, [3], 4),
            P("W5_3", 5, [3], 8), P("W5_4", 5, [4], 6),
            P("W6_4", 6, [4], 6), P("W6_5", 6, [5], 8),
            P("W7_5", 7, [5], 4), P("W7_6", 7, [6], 10),
            P("W8_6", 8, [6], 2), P("W8_7", 8, [7], 12),
        ],
        "merges": [
            {"target": 1, "parts": ["W1", "W8_6"]},
            {"target": 2, "parts": ["W2", "W3_2"]},
            {"target": 3, "parts": ["W3_1", "W4_3"]},
            {"target": 4, "parts": ["W4_2", "W5_4"]},
            {"target": 5, "parts": ["W5_3", "W6_5"]},
            {"target": 6, "parts": ["W6_4", "W7_6"]},
            {"target": 7, "parts": ["W7_5", "W8_7"]},
        ],
    }

    moving = [p for p in plan["pieces"] if len(p["dest"]) > 0]
    repair = {
        "kind": "repair",
        "broadcasts": [{"by": 3, "terms": ["W3_1", "W8_7"]}] + [
            {"by": next(n for n in initial["segments"][p["source"] - 1]["storage"] if n != removed),
             "terms": [p["id"]]}
            for p in moving if p["id"] not in ("W3_1", "W8_7")
        ],
    }
    return {"K": K, "r": r, "removed": removed, "baseline": 84,
            "initial": initial, "target": target, "plan": plan, "repair": repair}
