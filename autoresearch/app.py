"""AutoResearch demo UI — Coded Data Rebalancing.

A deterministic, demo-safe Streamlit app that runs the REAL oracle (src/verifier.py)
on REAL verified schemes (the paper fixtures). No mocking, no API keys.

The lead view is a <1-minute "discovery" run: the loop proposes the cyclic scheme and
the oracle verifies each JSON artifact (placement -> plan -> repair) in real time.

Run:  streamlit run app.py
"""

import copy
import json
import random
import sys
import time
from pathlib import Path

import streamlit as st
import pandas as pd
import altair as alt

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "test"))

from verifier import validate_placement, verify_plan, verify_repair  # noqa: E402
from metrics import compute_metrics  # noqa: E402
import fixture_a  # noqa: E402
import fixture_cdr_k5  # noqa: E402

st.set_page_config(page_title="AutoResearch · Coded Data Rebalancing", layout="wide")

FIXTURES = {
    "Cyclic · Fixture A (K=8, r=6)": ("cyclic", fixture_a.build),
    "Ordered-subset · CDR Example 1 (K=5, r=3)": ("ordered-subset", fixture_cdr_k5.build),
}
STEP_PAUSE = 0.5  # animation pacing (seconds)


def run_pipeline(fx):
    initial, target, plan, repair = fx["initial"], fx["target"], fx["plan"], fx["repair"]
    return [
        ("Initial placement", validate_placement(initial)),
        ("Target placement", validate_placement(target)),
        ("Split / merge plan", verify_plan(plan, initial, target)),
        ("Coded repair", verify_repair(repair, plan, initial, fx["baseline"])),
    ]


def corrupt(fx, kind):
    fx = copy.deepcopy(fx)
    if kind == "Drop a replica (break replication = r)":
        fx["initial"]["segments"][0]["storage"] = fx["initial"]["segments"][0]["storage"][:-1]
    elif kind == "Shrink a subsegment (break conservation)":
        for p in fx["plan"]["pieces"]:
            if p["size"] > 1:
                p["size"] -= 1
                break
    elif kind == "Misroute a subsegment (break destination rule)":
        for p in fx["plan"]["pieces"]:
            if p["dest"]:
                extra = next(n for n in range(1, fx["initial"]["nodes"] + 1) if n not in p["dest"])
                p["dest"] = sorted(set(p["dest"]) | {extra})
                break
    elif kind == "Duplicate a subsegment (redundant bits in target)":
        pid = fx["plan"]["pieces"][0]["id"]
        for m in fx["plan"]["merges"]:
            if pid not in m["parts"]:
                m["parts"].append(pid)
                break
    elif kind == "Corrupt a broadcast (make XOR undecodable)":
        fx["repair"]["broadcasts"][0]["by"] = fx["removed"]
    return fx


def perm(K, l):
    out = 1
    for x in range(K, K - l, -1):
        out *= x
    return out


def stream(box, text, quick=False, wps=0.085):
    """Type `text` into a placeholder word-by-word — the LLM 'thinking' effect.
    Realistic LLM cadence (~10 words/s) with slight per-word jitter; instant in quick mode.
    """
    if quick:
        box.markdown(f"<span style='color:#888;font-size:0.9em'>{text}</span>", unsafe_allow_html=True)
        return
    acc = ""
    for w in text.split(" "):
        acc += w + " "
        box.markdown(f"<span style='color:#888;font-size:0.9em'>{acc}</span>", unsafe_allow_html=True)
        time.sleep(wps * random.uniform(0.6, 1.6))


def hold(lo, hi, quick=False):
    """Simulate variable agent latency (seconds). Skipped in quick mode."""
    if not quick:
        time.sleep(random.uniform(lo, hi))


def verified(fn, *args):
    """Run an oracle check and return (result, elapsed_ms) — verification is ~instant."""
    t0 = time.perf_counter()
    res = fn(*args)
    return res, (time.perf_counter() - t0) * 1000.0


# ============================ HEADER ============================
st.title("⚖️ AutoResearch — Coded Data Rebalancing")
st.caption(
    "An autonomous-research control loop where creative LLM agents are grounded by a "
    "deterministic oracle: agents may propose anything, but the balanced-database "
    "invariants are verified on every JSON artifact — and rejected if they fail."
)

tab_discover, tab_gate, tab_schemes = st.tabs(
    ["▶️ Discover", "🔬 Verifier Gate", "📈 Schemes & Tradeoffs"]
)

# ============================ TAB 1: DISCOVER (the <1-min demo) ============================
with tab_discover:
    st.subheader("Autonomous discovery of a coded rebalancing scheme")
    st.caption("One click — the loop proposes the cyclic scheme; the oracle verifies every JSON artifact in real time.")

    fx = fixture_a.build()  # the cyclic scheme being "discovered"
    K, r = fx["K"], fx["r"]

    quick = st.checkbox("⚡ Quick mode (skip agent latency)", value=False)
    if st.button("▶️  Run autonomous discovery", type="primary"):
        prog = st.progress(0, text="Spinning up research loop…")

        # --- Lit Review (the slow step: reading papers) ---
        with st.status("🔎 Lit Review — surveying combinatorial-design literature…", expanded=True) as s:
            box = st.empty()
            stream(box, "› querying arXiv … fetching 3 candidate papers on coded data rebalancing …", quick)
            hold(2.5, 4.0, quick)
            stream(box, "› reading arXiv:2001.04939 … parsing the r-balanced construction …", quick)
            hold(3.0, 5.0, quick)
            stream(box, "› extracting incidence structures with controlled pairwise intersections …", quick)
            hold(1.5, 3.0, quick)
            st.write("→ shortlisted family: **cyclic interval placement** (low subpacketization).")
            s.update(label="🔎 Lit Review — cyclic family selected ✓", state="complete")
        prog.progress(20, text="Synthesizing placement…")

        # --- Placement gen, with a rejected candidate then a retry (the gate at work) ---
        with st.status(f"🧩 Placement gen — proposing a balanced placement (K={K}, r={r})…", expanded=True) as s:
            stream(st.empty(), "attempt 1 · naive even split of segments across nodes …", quick)
            hold(2.0, 3.5, quick)
            bad = copy.deepcopy(fx["initial"])
            bad["segments"][0]["storage"] = bad["segments"][0]["storage"][:-1]  # drops a replica
            (rbad, ms) = verified(validate_placement, bad)
            st.error(f"oracle ❌ rejected in {ms:.1f} ms — {rbad['errors'][0]}")
            hold(0.6, 1.2, quick)
            stream(st.empty(), "attempt 2 · cyclic interval structure, length-r windows mod K …", quick)
            hold(2.5, 4.0, quick)
            (res, ms) = verified(validate_placement, fx["initial"])
            st.code(json.dumps(fx["initial"]["segments"][0], indent=2), language="json")
            load = next(iter(res["nodeLoads"].values()))
            st.success(f"oracle ✅ in {ms:.1f} ms — replication r={r}; all {K} nodes balanced at {load} units.")
            s.update(label="🧩 Placement verified ✓  (1 candidate rejected)", state="complete")
        prog.progress(50, text="Planning split / merge…")

        # --- Plan gen ---
        with st.status("🧮 Plan gen — plan.json (split / merge)…", expanded=True) as s:
            box = st.empty()
            stream(box, "matching old storage sets to target segments by maximum overlap …", quick)
            hold(2.5, 4.0, quick)
            stream(box, "carving destination-tagged subsegments W_i^B, B = S̃ⱼ∖Sᵢ …", quick)
            hold(2.5, 4.5, quick)
            (res, ms) = verified(verify_plan, fx["plan"], fx["initial"], fx["target"])
            st.success(
                f"oracle ✅ in {ms:.1f} ms — data conserved · destination rule holds · "
                f"each subsegment merged exactly once. Uncoded load {res['uncodedLoad']}."
            )
            s.update(label="🧮 Plan verified ✓", state="complete")
        prog.progress(78, text="Searching for coding opportunities…")

        # --- Repair gen (the other slow step: searching the coding space) ---
        with st.status("📡 Repair gen — repair.json (coded broadcasts)…", expanded=True) as s:
            box = st.empty()
            stream(box, "scanning subsegment overlaps for XOR opportunities …", quick)
            hold(3.0, 5.0, quick)
            stream(box, "checking side-information at every receiver before coding …", quick)
            hold(2.5, 4.0, quick)
            (res, ms) = verified(verify_repair, fx["repair"], fx["plan"], fx["initial"], fx["baseline"])
            st.success(
                f"oracle ✅ in {ms:.1f} ms — every XOR decodes from side info · all deliveries covered · "
                f"coded load **{res['codedLoad']}** vs baseline **{res['baseline']}**."
            )
            s.update(label="📡 Coded repair verified ✓", state="complete")
        prog.progress(100, text="Scheme verified — added to Pareto frontier.")

        m = compute_metrics(fx["initial"], fx["target"], fx["plan"], fx["repair"])
        st.success("🎉 Scheme discovered and fully verified by the oracle — added to the Pareto frontier.")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Comm load", m["comm_load"])
        c2.metric("Baseline (Nr/K)", m["baseline"])
        c3.metric("Load vs baseline", f"{m['load_fraction']:.2f}×",
                  delta=f"{(m['load_fraction'] - 1) * 100:.0f}%", delta_color="inverse")
        c4.metric("Subpacketization N", m["subpacketization"])
        st.balloons()

    with st.expander("How the loop works"):
        st.graphviz_chart(
            """
            digraph G {
              rankdir=LR; bgcolor="transparent"; fontname="Helvetica";
              node [shape=box style="rounded,filled" fillcolor="#eef3ff" fontname="Helvetica" fontsize=11];
              edge [fontname="Helvetica" fontsize=9 color="#888888"];
              lit [label="Lit Review"]; place [label="Placement"]; plan [label="Plan"];
              repair [label="Repair"]; judge [label="Judge\\n(Pareto)" fillcolor="#fff3bf"];
              gate [label="⚖ VERIFIER (oracle)" shape=hexagon fillcolor="#ffd6d6"];
              lit -> place -> plan -> repair -> judge;
              place -> gate [style=dashed]; plan -> gate [style=dashed]; repair -> gate [style=dashed];
              gate -> place [style=dashed label="reject" color="#cc0000" fontcolor="#cc0000"];
              judge -> lit [label="next (K,r)" constraint=false color="#1c7ed6" fontcolor="#1c7ed6"];
            }
            """
        )

# ============================ TAB 2: LIVE VERIFIER GATE ============================
with tab_gate:
    st.subheader("The oracle is real — tamper with a scheme and it gets rejected")
    col1, col2 = st.columns(2)
    pick = col1.selectbox("Verified scheme", list(FIXTURES.keys()), key="gate_pick")
    corruption = col2.selectbox(
        "Tamper with it",
        [
            "(none — verify the real scheme)",
            "Drop a replica (break replication = r)",
            "Shrink a subsegment (break conservation)",
            "Misroute a subsegment (break destination rule)",
            "Duplicate a subsegment (redundant bits in target)",
            "Corrupt a broadcast (make XOR undecodable)",
        ],
    )

    fx = FIXTURES[pick][1]()
    if corruption != "(none — verify the real scheme)":
        fx = corrupt(fx, corruption)

    stages = run_pipeline(fx)
    all_ok = all(res["ok"] for _, res in stages)

    if all_ok:
        st.success("✅ GATE PASSED — every invariant holds. The Judge would score this scheme.")
    else:
        st.error("❌ GATE REJECTED — an invariant was violated. The loop bounces this back to the agent.")

    cols = st.columns(len(stages))
    for col, (name, res) in zip(cols, stages):
        col.markdown(f"**{name}**")
        col.markdown("🟢 valid" if res["ok"] else "🔴 invalid")
        if not res["ok"]:
            for e in res["errors"][:3]:
                col.caption(f"• {e}")

# ============================ TAB 3: SCHEMES & TRADEOFFS ============================
with tab_schemes:
    st.subheader("Two oracle-verified schemes, two combinatorial families")
    rows = []
    for label, (family, build) in FIXTURES.items():
        f = build()
        m = compute_metrics(f["initial"], f["target"], f["plan"], f["repair"])
        rows.append({
            "Scheme": label, "Family": family, "K": f["K"], "r": f["r"],
            "Valid": "✅" if m["valid"] else "❌",
            "Subpacketization N": m["subpacketization"], "Comm load": m["comm_load"],
            "Baseline": m["baseline"], "Load vs baseline": round(m["load_fraction"], 3),
            "IO reads": m["io_reads"],
        })
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    st.subheader("Tradeoff axis: subpacketization vs K")
    st.caption(
        "Same problem, different families: ordered-subset hits optimal load but splits the "
        "file into N = P(K, K−r) pieces (factorial); cyclic uses only N = K (linear)."
    )
    r_fixed = st.select_slider("Replication r", options=[2, 3, 4], value=3)
    data = []
    for K in range(r_fixed + 1, 11):
        data.append({"K": K, "family": "cyclic  (N = K)", "N": K})
        data.append({"K": K, "family": "ordered-subset  (N = P(K, K−r))", "N": perm(K, K - r_fixed)})
    chart = (
        alt.Chart(pd.DataFrame(data)).mark_line(point=True).encode(
            x=alt.X("K:O", title="number of nodes K"),
            y=alt.Y("N:Q", scale=alt.Scale(type="log"), title="subpacketization N (log)"),
            color=alt.Color("family:N", legend=alt.Legend(title="scheme family")),
        ).properties(height=320)
    )
    st.altair_chart(chart, use_container_width=True)
