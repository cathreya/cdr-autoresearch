# -*- coding: utf-8 -*-
"""
CDR Cyclic Storage Rebalancing Visualizer
==========================================
Visualizes the coded data rebalancing algorithm from:
"Coded Data Rebalancing for Distributed Data Storage Systems with Cyclic Storage"

Algorithm overview:
- r-balanced cyclic database: K nodes, N=K segments, segment Wi stored in r consecutive nodes (cyclically)
- Node removal: Remove node K, restore r-balanced cyclic database on K-1 nodes
  - Phase 1: Split segments in removed node into subsegments
  - Phase 2: Transmit (coded XOR or uncoded) subsegments
  - Phase 3: Merge subsegments to form new target segments
- Node addition: Add node K+1, restore r-balanced cyclic database on K+1 nodes (uncoded, optimal)
"""

import tkinter as tk
from tkinter import ttk, font
import math


# ─────────────────────────── Helper arithmetic ───────────────────────────────

def cyclic_range(start, count, modulus):
    """Return 'count' indices starting at 'start' (1-indexed), mod 'modulus', 1-indexed."""
    return [(((start - 1 + i) % modulus) + 1) for i in range(count)]


def cyc_fwd(i, r, K):
    """Si = {i, i+1, ..., i+r-1} mod K (1-indexed)."""
    return cyclic_range(i, r, K)


def cyc_bwd(k, r, K):
    """Dk = {k-r+1, ..., k} mod K (1-indexed) — segments stored at node k."""
    return cyclic_range(k - r + 1, r, K)


# ─────────────────────────── Algorithm logic ─────────────────────────────────

def build_initial_db(K, r):
    """Return dict: segment_index -> list of node indices (1-indexed)."""
    return {i: cyc_fwd(i, r, K) for i in range(1, K + 1)}


def build_target_db_removal(K, r):
    """Target cyclic DB on K-1 nodes after removing node K."""
    K2 = K - 1
    return {i: cyc_fwd(i, r, K2) for i in range(1, K2 + 1)}


def build_target_db_addition(K, r):
    """Target cyclic DB on K+1 nodes after adding node K+1."""
    K2 = K + 1
    return {i: cyc_fwd(i, r, K2) for i in range(1, K2 + 1)}


def rth_threshold(K):
    return math.ceil((2 * K + 2) / 3)


def L1(K, r):
    return (K - r) * (2 * r - 1) / (K - 1)


def L2(K, r):
    # formula from paper (combined for odd/even r)
    if r % 2 == 1:
        return (1 / (2 * (K - 1))) * (r - 1) * (K + (r - 1) / 2)
    else:
        return (1 / (2 * (K - 1))) * ((r - 2) * (K + r / 2) + K)


def Lrem(K, r):
    base = (K - r) / (K - 1)
    return base + min(L1(K, r), L2(K, r))


def Ladd(K, r):
    return r * K / (K + 1)


def Lu(r):
    return r


# ─── Splitting ────────────────────────────────────────────────────────────────

def compute_split_removal(K, r):
    """
    Returns list of subsegments for each segment in DK = {WK-r+1, ..., WK}.
    Each subsegment: dict with keys 'segment', 'label', 'dest_nodes', 'size_num', 'size_den'
    size = size_num / size_den (in units of T)
    """
    subsegments = []
    denom = 2 * (K - 1)

    # Middle segments: WK-r+2, ..., WK-1  (i in [r-2])
    for idx in range(1, r - 1):  # i = 1..r-2
        seg = K - r + 1 + idx   # WK-r+1+i
        dest1 = idx + 1          # {i+1}
        dest2 = idx + K - r      # {i+K-r}
        size1 = K + r - 2 * idx - 2  # K+r-2i-2
        size2 = K - r + 2 * idx      # K-r+2i
        subsegments.append({'segment': seg, 'label': f'W{seg}^{{{dest1}}}',
                             'dest_nodes': [dest1], 'size_num': size1, 'size_den': denom,
                             'type': 'middle', 'pair_id': idx, 'which': 'A'})
        subsegments.append({'segment': seg, 'label': f'W{seg}^{{{dest2}}}',
                             'dest_nodes': [dest2], 'size_num': size2, 'size_den': denom,
                             'type': 'middle', 'pair_id': idx, 'which': 'B'})

    # Corner segments WK-r+1 and WK
    p = (K - r) // 2
    odd_diff = (K - r) % 2 == 1

    # Corner segment WK-r+1
    corner1 = K - r + 1
    # Large subsegment -> dest {1}
    subsegments.append({'segment': corner1, 'label': f'W{corner1}^{{1}}',
                         'dest_nodes': [1], 'size_num': K + r - 2, 'size_den': denom,
                         'type': 'corner_large', 'corner': 'left'})
    if odd_diff:
        # middle small subsegment (size 1/denom)
        mid_set = cyclic_range(K - r - p, min(r, p + 1), K - 1)
        lbl = ','.join(str(x) for x in mid_set)
        subsegments.append({'segment': corner1, 'label': f'W{corner1}^{{{lbl}}}',
                             'dest_nodes': mid_set, 'size_num': 1, 'size_den': denom,
                             'type': 'corner_small_mid', 'corner': 'left'})
    for j in range(1, p + 1):
        dest_set = cyclic_range(K - r + 1 - j, min(r, j), K - 1)
        lbl = ','.join(str(x) for x in dest_set)
        subsegments.append({'segment': corner1, 'label': f'W{corner1}^{{{lbl}}}',
                             'dest_nodes': dest_set, 'size_num': 2, 'size_den': denom,
                             'type': 'corner_small', 'corner': 'left', 'j': j})

    # Corner segment WK
    cornerK = K
    # Large subsegment -> dest {K-1}
    subsegments.append({'segment': cornerK, 'label': f'W{cornerK}^{{{K-1}}}',
                         'dest_nodes': [K - 1], 'size_num': K + r - 2, 'size_den': denom,
                         'type': 'corner_large', 'corner': 'right'})
    if odd_diff:
        mid_set = cyclic_range(r + p - (min(r, p + 1) - 1), min(r, p + 1), K - 1)
        # simpler: cyclic_range(r+p, min(r,p+1), K-1) going backwards
        mid_set2 = []
        start = r + p
        cnt = min(r, p + 1)
        for ci in range(cnt):
            mid_set2.append(((start - 1 - ci) % (K - 1)) + 1)
        lbl = ','.join(str(x) for x in mid_set2)
        subsegments.append({'segment': cornerK, 'label': f'W{cornerK}^{{{lbl}}}',
                             'dest_nodes': mid_set2, 'size_num': 1, 'size_den': denom,
                             'type': 'corner_small_mid', 'corner': 'right'})
    for j in range(1, p + 1):
        # {(r-1+j) mod K-1 <min(r,j)>} going backwards
        dest_set = []
        start = r - 1 + j
        cnt = min(r, j)
        for ci in range(cnt):
            dest_set.append(((start - 1 - ci) % (K - 1)) + 1)
        lbl = ','.join(str(x) for x in dest_set)
        subsegments.append({'segment': cornerK, 'label': f'W{cornerK}^{{{lbl}}}',
                             'dest_nodes': dest_set, 'size_num': 2, 'size_den': denom,
                             'type': 'corner_small', 'corner': 'right', 'j': j})

    return subsegments


def compute_transmissions_scheme1(K, r):
    """Returns list of coded transmissions for Scheme 1."""
    txs = []
    for i in range(1, K - r + 1):
        # Node 1 broadcasts XOR of W^{K-i-j(K-r)}_{K+1-i-j(K-r)} for j=0..floor((r-1-i)/(K-r))
        jmax = math.floor((r - 1 - i) / (K - r))
        grp1 = []
        for j in range(jmax + 1):
            seg = K + 1 - i - j * (K - r)
            dest = K - i - j * (K - r)
            grp1.append({'segment': seg, 'dest': dest})
        if grp1:
            txs.append({'broadcaster': 1, 'type': 'coded', 'subsegments': grp1,
                         'scheme': 1, 'i': i, 'direction': 'left'})
        # Node K-1 broadcasts XOR of W^{i+j(K-r)}_{K-r+i+j(K-r)}
        grp2 = []
        for j in range(jmax + 1):
            seg = K - r + i + j * (K - r)
            dest = i + j * (K - r)
            grp2.append({'segment': seg, 'dest': dest})
        if grp2:
            txs.append({'broadcaster': K - 1, 'type': 'coded', 'subsegments': grp2,
                         'scheme': 1, 'i': i, 'direction': 'right'})
    # Uncoded: Node 1 broadcasts small subsegments of WK (all except W^{K-1}_K)
    # Node K-1 broadcasts small subsegments of WK-r+1 (all except W^{1}_{K-r+1})
    txs.append({'broadcaster': 1, 'type': 'uncoded', 'segment': K,
                 'note': f'Broadcasts small subsegments of W{K}', 'scheme': 1})
    txs.append({'broadcaster': K - 1, 'type': 'uncoded', 'segment': K - r + 1,
                 'note': f'Broadcasts small subsegments of W{K-r+1}', 'scheme': 1})
    return txs


def compute_transmissions_scheme2(K, r):
    """Returns list of coded transmissions for Scheme 2."""
    txs = []
    # Node 1 broadcasts W^{i}_{K-r+i} XOR W^{K-r+i}_{K-r+i+1} for i=2..r-1
    for i in range(2, r):
        seg_a = K - r + i
        dest_a = i
        seg_b = K - r + i + 1
        dest_b = K - r + i
        txs.append({'broadcaster': 1, 'type': 'coded',
                     'subsegments': [{'segment': seg_a, 'dest': dest_a},
                                     {'segment': seg_b, 'dest': dest_b}],
                     'scheme': 2, 'i': i})
    # Node K-1 broadcasts W^{1}_{K-r+1} XOR W^{K-r+1}_{K-r+2}
    txs.append({'broadcaster': K - 1, 'type': 'coded',
                 'subsegments': [{'segment': K - r + 1, 'dest': 1},
                                  {'segment': K - r + 2, 'dest': K - r + 1}],
                 'scheme': 2})
    # Uncoded
    txs.append({'broadcaster': 1, 'type': 'uncoded', 'segment': K,
                 'note': f'Broadcasts small subsegments of W{K}', 'scheme': 2})
    txs.append({'broadcaster': K - 1, 'type': 'uncoded', 'segment': K - r + 1,
                 'note': f'Broadcasts small subsegments of W{K-r+1}', 'scheme': 2})
    return txs


def compute_merges_removal(K, r):
    """Returns list of merge operations for node-removal rebalancing."""
    K2 = K - 1
    merges = []
    # For i in [r-1]: W~_{K-r+i} = W^{i}_{K-r+i} | W^{K-r+i}_{K-r+i+1}
    for i in range(1, r):
        new_seg = K - r + i
        part_a = {'segment': K - r + i, 'dest': i}
        part_b = {'segment': K - r + i + 1, 'dest': K - r + i}
        nodes = cyc_fwd(new_seg, r, K2)
        merges.append({'new_seg': new_seg, 'parts': [part_a, part_b], 'nodes': nodes,
                        'description': f'W̃{new_seg} = W{K-r+i}^{{{i}}} | W{K-r+i+1}^{{{K-r+i}}}'})

    p = (K - r) // 2
    odd_diff = (K - r) % 2 == 1

    if not odd_diff:
        # Even K-r
        for i in range(1, (K - r) // 2 + 1):
            dest_set = cyclic_range(r - 1 + i - (min(r, i) - 1), min(r, i), K2)
            lbl = ','.join(str(x) for x in dest_set)
            nodes = cyc_fwd(i, r, K2)
            merges.append({'new_seg': i,
                            'parts': [{'old_seg': i, 'whole': True},
                                      {'segment': K, 'dest_label': lbl}],
                            'nodes': nodes,
                            'description': f'W̃{i} = W{i} | W{K}^{{{lbl}}}'})
        for i in range((K - r) // 2 + 1, K - r + 1):
            dest_set = cyclic_range(i, min(r, K - r - i + 1), K2)
            lbl = ','.join(str(x) for x in dest_set)
            nodes = cyc_fwd(i, r, K2)
            merges.append({'new_seg': i,
                            'parts': [{'old_seg': i, 'whole': True},
                                      {'segment': K - r + 1, 'dest_label': lbl}],
                            'nodes': nodes,
                            'description': f'W̃{i} = W{i} | W{K-r+1}^{{{lbl}}}'})
    else:
        # Odd K-r
        for i in range(1, (K - r - 1) // 2 + 1):
            dest_set = cyclic_range(r - 1 + i - (min(r, i) - 1), min(r, i), K2)
            lbl = ','.join(str(x) for x in dest_set)
            nodes = cyc_fwd(i, r, K2)
            merges.append({'new_seg': i,
                            'parts': [{'old_seg': i, 'whole': True},
                                      {'segment': K, 'dest_label': lbl}],
                            'nodes': nodes,
                            'description': f'W̃{i} = W{i} | W{K}^{{{lbl}}}'})
        for i in range((K - r + 1) // 2 + 1, K - r + 1):
            dest_set = cyclic_range(i, min(r, K - r - i + 1), K2)
            lbl = ','.join(str(x) for x in dest_set)
            nodes = cyc_fwd(i, r, K2)
            merges.append({'new_seg': i,
                            'parts': [{'old_seg': i, 'whole': True},
                                      {'segment': K - r + 1, 'dest_label': lbl}],
                            'nodes': nodes,
                            'description': f'W̃{i} = W{i} | W{K-r+1}^{{{lbl}}}'})
        # Middle target segment W~_{(K-r+1)/2}
        mid_i = (K - r + 1) // 2
        dest_K_set = cyclic_range(r + p - (min(r, p + 1) - 1), min(r, p + 1), K2)
        dest_c1_set = cyclic_range(K - r - p, min(r, p + 1), K2)
        lbl_K = ','.join(str(x) for x in dest_K_set)
        lbl_c1 = ','.join(str(x) for x in dest_c1_set)
        nodes = cyc_fwd(mid_i, r, K2)
        merges.append({'new_seg': mid_i,
                        'parts': [{'old_seg': mid_i, 'whole': True},
                                  {'segment': K, 'dest_label': lbl_K},
                                  {'segment': K - r + 1, 'dest_label': lbl_c1}],
                        'nodes': nodes,
                        'description': f'W̃{mid_i} = W{mid_i} | W{K}^{{{lbl_K}}} | W{K-r+1}^{{{lbl_c1}}}'})

    return merges


def compute_split_addition(K, r):
    """Split for node addition: each Wi -> W~i (size K/(K+1)) + small subsegment (size 1/(K+1))."""
    splits = []
    for i in range(1, K + 1):
        dest_set = [K + 1] + list(range(1, min(r - 1, i - 1) + 1))
        lbl = ','.join(str(x) for x in dest_set)
        splits.append({'segment': i, 'keep_label': f'W̃{i}',
                        'small_label': f'W{i}^{{{lbl}}}', 'dest_nodes': dest_set,
                        'keep_size': 'K/(K+1)', 'small_size': '1/(K+1)'})
    return splits


# ─────────────────────────── Color palette ───────────────────────────────────

PALETTE = {
    'bg': '#1a1a2e',
    'panel': '#16213e',
    'card': '#0f3460',
    'accent': '#e94560',
    'accent2': '#533483',
    'accent3': '#05b49a',
    'text': '#eaeaea',
    'text_dim': '#8899aa',
    'node_normal': '#1e6091',
    'node_removed': '#c0392b',
    'node_added': '#27ae60',
    'node_survivor': '#2980b9',
    'seg_colors': ['#e74c3c', '#e67e22', '#f1c40f', '#2ecc71', '#1abc9c',
                   '#3498db', '#9b59b6', '#e91e63', '#00bcd4', '#8bc34a',
                   '#ff5722', '#607d8b', '#795548', '#ff9800', '#4caf50'],
    'subseg_a': '#f39c12',
    'subseg_b': '#8e44ad',
    'coded_tx': '#e74c3c',
    'uncoded_tx': '#27ae60',
    'border': '#2c3e50',
    'highlight': '#f39c12',
    'scheme1': '#3498db',
    'scheme2': '#9b59b6',
}


def seg_color(i, total):
    return PALETTE['seg_colors'][i % len(PALETTE['seg_colors'])]


# ─────────────────────────── Main Application ────────────────────────────────

class CDRVisualizer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CDR Cyclic Storage Rebalancing Visualizer")
        self.configure(bg=PALETTE['bg'])
        self.geometry("1400x900")
        self.minsize(1100, 750)

        self.K = tk.IntVar(value=6)
        self.r = tk.IntVar(value=3)
        self.mode = tk.StringVar(value='removal')
        self.step = tk.IntVar(value=0)

        self._steps = []  # computed step list
        self._build_ui()
        self._recompute()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Top control bar ───────────────────────────────────────────────────
        ctrl = tk.Frame(self, bg=PALETTE['panel'], pady=8, padx=12)
        ctrl.pack(side=tk.TOP, fill=tk.X)

        tk.Label(ctrl, text="CDR Cyclic Storage Rebalancing", bg=PALETTE['panel'],
                 fg=PALETTE['accent'], font=('Helvetica', 16, 'bold')).pack(side=tk.LEFT, padx=(0, 20))

        tk.Label(ctrl, text="K (nodes):", bg=PALETTE['panel'], fg=PALETTE['text']).pack(side=tk.LEFT)
        self._k_spin = tk.Spinbox(ctrl, from_=4, to=12, textvariable=self.K, width=4,
                                   bg=PALETTE['card'], fg=PALETTE['text'],
                                   buttonbackground=PALETTE['card'],
                                   command=self._on_param_change, font=('Helvetica', 12))
        self._k_spin.pack(side=tk.LEFT, padx=(2, 12))

        tk.Label(ctrl, text="r (replication):", bg=PALETTE['panel'], fg=PALETTE['text']).pack(side=tk.LEFT)
        self._r_spin = tk.Spinbox(ctrl, from_=2, to=10, textvariable=self.r, width=4,
                                   bg=PALETTE['card'], fg=PALETTE['text'],
                                   buttonbackground=PALETTE['card'],
                                   command=self._on_param_change, font=('Helvetica', 12))
        self._r_spin.pack(side=tk.LEFT, padx=(2, 20))

        tk.Label(ctrl, text="Mode:", bg=PALETTE['panel'], fg=PALETTE['text']).pack(side=tk.LEFT)
        for txt, val in [("Node Removal", "removal"), ("Node Addition", "addition")]:
            tk.Radiobutton(ctrl, text=txt, variable=self.mode, value=val,
                           bg=PALETTE['panel'], fg=PALETTE['text'],
                           selectcolor=PALETTE['card'], activebackground=PALETTE['panel'],
                           command=self._on_param_change).pack(side=tk.LEFT, padx=4)

        # Nav buttons
        self._prev_btn = tk.Button(ctrl, text="◀ Prev", command=self._prev_step,
                                    bg=PALETTE['card'], fg=PALETTE['text'],
                                    relief=tk.FLAT, padx=10, font=('Helvetica', 11))
        self._prev_btn.pack(side=tk.RIGHT, padx=4)
        self._next_btn = tk.Button(ctrl, text="Next ▶", command=self._next_step,
                                    bg=PALETTE['accent'], fg='white',
                                    relief=tk.FLAT, padx=10, font=('Helvetica', 11, 'bold'))
        self._next_btn.pack(side=tk.RIGHT, padx=4)
        self._step_lbl = tk.Label(ctrl, text="Step 0/0", bg=PALETTE['panel'],
                                   fg=PALETTE['text_dim'], font=('Helvetica', 11))
        self._step_lbl.pack(side=tk.RIGHT, padx=8)

        # ── Main area: left panel + canvas ────────────────────────────────────
        main = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=PALETTE['bg'],
                               sashwidth=4, sashrelief=tk.FLAT)
        main.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Left info panel
        left = tk.Frame(main, bg=PALETTE['panel'], width=340)
        main.add(left, minsize=280)

        self._info_title = tk.Label(left, text="", bg=PALETTE['panel'], fg=PALETTE['accent'],
                                     font=('Helvetica', 13, 'bold'), anchor='w',
                                     wraplength=300, justify=tk.LEFT)
        self._info_title.pack(fill=tk.X, padx=10, pady=(10, 2))

        self._info_text = tk.Text(left, bg=PALETTE['panel'], fg=PALETTE['text'],
                                   font=('Courier', 10), wrap=tk.WORD,
                                   relief=tk.FLAT, state=tk.DISABLED,
                                   width=38)
        self._info_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 4))

        # Stats frame at bottom of left panel
        self._stats_frame = tk.Frame(left, bg=PALETTE['card'], padx=8, pady=6)
        self._stats_frame.pack(fill=tk.X, padx=10, pady=(0, 8))
        self._stats_lbl = tk.Label(self._stats_frame, text="", bg=PALETTE['card'],
                                    fg=PALETTE['accent3'], font=('Courier', 9),
                                    justify=tk.LEFT, anchor='w')
        self._stats_lbl.pack(fill=tk.X)

        # Canvas
        right = tk.Frame(main, bg=PALETTE['bg'])
        main.add(right, minsize=600)

        self._canvas = tk.Canvas(right, bg=PALETTE['bg'], highlightthickness=0)
        self._canvas.pack(fill=tk.BOTH, expand=True)
        self._canvas.bind('<Configure>', lambda e: self._draw())

    # ── Parameter changes ─────────────────────────────────────────────────────

    def _on_param_change(self):
        self._recompute()

    def _recompute(self):
        K = self.K.get()
        r = self.r.get()
        # clamp r
        r = max(3, min(r, K - 1))
        self.r.set(r)
        self._build_steps(K, r, self.mode.get())
        self.step.set(0)
        self._update_step_ui()
        self._draw()

    def _build_steps(self, K, r, mode):
        steps = []
        if mode == 'removal':
            steps += self._build_removal_steps(K, r)
        else:
            steps += self._build_addition_steps(K, r)
        self._steps = steps

    def _build_removal_steps(self, K, r):
        steps = []
        db_initial = build_initial_db(K, r)
        db_target = build_target_db_removal(K, r)
        subsegments = compute_split_removal(K, r)
        scheme_choice = 1 if r >= rth_threshold(K) else 2
        if scheme_choice == 1:
            transmissions = compute_transmissions_scheme1(K, r)
        else:
            transmissions = compute_transmissions_scheme2(K, r)
        merges = compute_merges_removal(K, r)

        # Step 0: Initial database
        steps.append({
            'phase': 'initial',
            'title': 'Initial r-balanced Cyclic Database',
            'db': db_initial,
            'K': K, 'r': r,
            'removed': None,
            'added': None,
            'highlight_segs': [],
            'info': (
                f"Initial Setup:\n"
                f"  K = {K} nodes\n"
                f"  r = {r} replication factor\n"
                f"  N = {K} segments W₁,...,W{K}\n\n"
                f"Each segment Wᵢ is stored in r={r}\n"
                f"consecutive nodes (cyclically):\n"
                f"  Sᵢ = {{i, i+1, ..., i+r-1}} mod K\n\n"
                f"Each node stores r/K fraction\n"
                f"of the file = {r}/{K} segments.\n\n"
                f"We will remove node K={K}.\n"
                f"Segments in node {K}: {cyc_bwd(K, r, K)}"
            )
        })

        # Step 1: Mark removed node
        steps.append({
            'phase': 'removal_marked',
            'title': f'Mark Node {K} for Removal',
            'db': db_initial,
            'K': K, 'r': r,
            'removed': K,
            'added': None,
            'highlight_segs': list(range(K - r + 1, K + 1)),
            'info': (
                f"Node {K} is removed.\n\n"
                f"Segments stored in node {K}:\n"
                f"  D{K} = {{W{K-r+1}, ..., W{K}}}\n\n"
                f"These {r} segments lose one\n"
                f"replica each, breaking balance.\n\n"
                f"We must restore r={r} replicas\n"
                f"in the K-1={K-1} remaining nodes.\n\n"
                f"Target: r-balanced cyclic DB\n"
                f"on {K-1} nodes with {K-1} segments\n"
                f"W̃₁,...,W̃{K-1}."
            )
        })

        # Step 2: Splitting phase
        steps.append({
            'phase': 'splitting',
            'title': 'Phase 1: Splitting Segments',
            'db': db_initial,
            'K': K, 'r': r,
            'removed': K,
            'added': None,
            'highlight_segs': list(range(K - r + 1, K + 1)),
            'subsegments': subsegments,
            'scheme': scheme_choice,
            'info': self._splitting_info(K, r, subsegments, scheme_choice)
        })

        # Step 3: Transmission phase
        steps.append({
            'phase': 'transmission',
            'title': f'Phase 2: Transmission (Scheme {scheme_choice})',
            'db': db_initial,
            'K': K, 'r': r,
            'removed': K,
            'added': None,
            'highlight_segs': [],
            'transmissions': transmissions,
            'subsegments': subsegments,
            'scheme': scheme_choice,
            'info': self._transmission_info(K, r, transmissions, scheme_choice)
        })

        # Step 4: Merging phase
        steps.append({
            'phase': 'merging',
            'title': 'Phase 3: Merging & Relabelling',
            'db': db_initial,
            'K': K, 'r': r,
            'removed': K,
            'added': None,
            'highlight_segs': [],
            'merges': merges,
            'subsegments': subsegments,
            'info': self._merging_info(K, r, merges)
        })

        # Step 5: Final database
        steps.append({
            'phase': 'final',
            'title': f'Final r-balanced Cyclic Database (K-1={K-1} nodes)',
            'db': db_target,
            'K': K - 1, 'r': r,
            'removed': None,
            'added': None,
            'highlight_segs': [],
            'info': self._final_removal_info(K, r)
        })

        return steps

    def _splitting_info(self, K, r, subsegments, scheme):
        denom = 2 * (K - 1)
        lines = [
            f"Segments in D{K} = {{W{K-r+1},...,W{K}}}\n"
            f"are split into subsegments.\n\n"
            f"Segment sizes normalized to T.\n"
            f"Denominator = 2(K-1) = {denom}\n\n"
            "Subsegment W_i^{{dest}} means the\n"
            "part of Wᵢ to be delivered to\n"
            "nodes listed in superscript.\n\n"
        ]
        by_seg = {}
        for s in subsegments:
            by_seg.setdefault(s['segment'], []).append(s)
        for seg in sorted(by_seg):
            lines.append(f"W{seg}:")
            for ss in by_seg[seg]:
                frac = f"{ss['size_num']}/{denom}"
                lines.append(f"  {ss['label']} → size {frac}T")
            lines.append("")
        lines.append(f"\nScheme selected: Scheme {scheme}")
        lines.append(f"(r_th = ⌈(2K+2)/3⌉ = {rth_threshold(K)})")
        if scheme == 1:
            lines.append("→ r ≥ r_th: Scheme 1 chosen")
        else:
            lines.append("→ r < r_th: Scheme 2 chosen")
        return '\n'.join(lines)

    def _transmission_info(self, K, r, txs, scheme):
        coded = [t for t in txs if t['type'] == 'coded']
        uncoded = [t for t in txs if t['type'] == 'uncoded']
        l1v = L1(K, r)
        l2v = L2(K, r)
        lrem = Lrem(K, r)
        lu = Lu(r)
        denom = 2 * (K - 1)

        lines = [f"Scheme {scheme}  (r_th=\u2308(2K+2)/3\u2309={rth_threshold(K)})\n"]

        if scheme == 1:
            lines.append(
                "Scheme 1: Multi-XOR clique cover.\n"
                "Broadcasters: Node 1 and Node K-1.\n"
                "For i=1..K-r, each pair of nodes\n"
                "XORs multiple subsegments together.\n"
                "Each dest decodes its subsegment\n"
                "by XORing away the others it holds.\n"
            )
        else:
            lines.append(
                "Scheme 2: Pairwise XOR coding.\n"
                "Broadcasters: Node 1 and Node K-1.\n"
                "Each broadcast XORs exactly 2\n"
                "subsegments W_i^a XOR W_j^b.\n"
                "Node a holds W_j so it decodes\n"
                "W_i^a, and vice versa.\n"
            )

        lines.append(f"\nCoded ({len(coded)}) + Uncoded ({len(uncoded)}):\n")

        for t in coded:
            subs = t['subsegments']
            xor_str = ' \u2295 '.join(
                f"W{s['segment']}^\u007b{s['dest']}\u007d" for s in subs)
            lines.append(f"N{t['broadcaster']}: {xor_str}")

        lines.append("")
        for t in uncoded:
            seg = t.get('segment', '?')
            lines.append(f"N{t['broadcaster']}: small subs of W{seg}")

        lines.append(
            f"\nLoad breakdown:\n"
            f"  Uncoded part = (K-r)/(K-1)\n"
            f"    = ({K}-{r})/({K}-1) = {(K-r)/(K-1):.4f}\n"
            f"  Coded L{scheme} = {l1v if scheme==1 else l2v:.4f}\n"
            f"  Total Lrem = {lrem:.4f}\n"
            f"  Uncoded Lu = {lu}\n"
            f"  Saving = {(1-lrem/lu)*100:.1f}%"
        )
        return '\n'.join(lines)

    def _merging_info(self, K, r, merges):
        lines = [
            "Each surviving node merges\n"
            "received subsegments to form\n"
            "new target segments W̃ᵢ.\n\n"
            f"New segment size = K/(K-1) = {K}/{K-1}·T\n\n"
            "Merge operations:\n"
        ]
        for m in merges:
            lines.append(f"  {m['description']}")
            lines.append(f"    → stored at nodes {m['nodes']}")
        return '\n'.join(lines)

    def _final_removal_info(self, K, r):
        K2 = K - 1
        db = build_target_db_removal(K, r)
        l1 = L1(K, r)
        l2 = L2(K, r)
        lrem = Lrem(K, r)
        lu = Lu(r)
        ladd = Ladd(K, r)
        scheme = 1 if r >= rth_threshold(K) else 2
        lines = [
            f"Final r-balanced cyclic DB\n"
            f"on K-1={K2} nodes.\n\n"
            f"Segments: W̃₁,...,W̃{K2}\n"
            f"Each has size {K}/{K2}·T\n"
            f"Each stored in {r} nodes.\n\n"
            f"Communication Loads:\n"
            f"  Uncoded load Lu(r)   = {lu}\n"
            f"  L₁(r)                = {l1:.4f}\n"
            f"  L₂(r)                = {l2:.4f}\n"
            f"  min(L₁,L₂)          = {min(l1,l2):.4f}\n"
            f"  Lrem(r) = (K-r)/(K-1) + min(L₁,L₂)\n"
            f"           = {(K-r)/(K-1):.4f} + {min(l1,l2):.4f}\n"
            f"           = {lrem:.4f}\n\n"
            f"Scheme used: Scheme {scheme}\n"
            f"r_th = ⌈(2K+2)/3⌉ = {rth_threshold(K)}\n\n"
            f"Ratio Lrem/Lu = {lrem/lu:.4f} < 1 ✓\n"
            f"(strictly better than uncoded)"
        ]
        return '\n'.join(lines)

    def _build_addition_steps(self, K, r):
        steps = []
        db_initial = build_initial_db(K, r)
        db_target = build_target_db_addition(K, r)
        splits = compute_split_addition(K, r)

        steps.append({
            'phase': 'initial',
            'title': 'Initial r-balanced Cyclic Database',
            'db': db_initial,
            'K': K, 'r': r,
            'removed': None, 'added': None,
            'highlight_segs': [],
            'info': (
                f"Initial Setup:\n"
                f"  K = {K} nodes\n"
                f"  r = {r} replication factor\n"
                f"  N = {K} segments W₁,...,W{K}\n\n"
                f"A new empty node K+1={K+1} will\n"
                f"be added to the system.\n\n"
                f"Target: r-balanced cyclic DB\n"
                f"on K+1={K+1} nodes.\n\n"
                f"Note: No coding opportunities\n"
                f"since node {K+1} starts empty.\n"
                f"→ Uncoded scheme is used."
            )
        })

        steps.append({
            'phase': 'addition_marked',
            'title': f'Add Empty Node {K+1}',
            'db': db_initial,
            'K': K, 'r': r,
            'removed': None, 'added': K + 1,
            'highlight_segs': [],
            'info': (
                f"New empty node {K+1} added.\n\n"
                f"The system now has {K+1} nodes\n"
                f"but the database is unbalanced:\n"
                f"  Node {K+1} stores nothing.\n"
                f"  Original nodes store too much.\n\n"
                f"Each segment Wᵢ needs to be\n"
                f"available in {r} of the {K+1} nodes.\n\n"
                f"Algorithm 6 (uncoded) will\n"
                f"rebalance to K+1={K+1} cyclic DB."
            )
        })

        steps.append({
            'phase': 'splitting_add',
            'title': 'Splitting: Each Wᵢ → W̃ᵢ + small subsegment',
            'db': db_initial,
            'K': K, 'r': r,
            'removed': None, 'added': K + 1,
            'highlight_segs': [],
            'splits_add': splits,
            'info': self._addition_split_info(K, r, splits)
        })

        steps.append({
            'phase': 'transmission_add',
            'title': 'Transmission: Broadcast small subsegments',
            'db': db_initial,
            'K': K, 'r': r,
            'removed': None, 'added': K + 1,
            'highlight_segs': [],
            'splits_add': splits,
            'info': self._addition_tx_info(K, r)
        })

        steps.append({
            'phase': 'final_add',
            'title': f'Final r-balanced Cyclic Database (K+1={K+1} nodes)',
            'db': db_target,
            'K': K + 1, 'r': r,
            'removed': None, 'added': None,
            'highlight_segs': [],
            'info': self._final_addition_info(K, r)
        })

        return steps

    def _addition_split_info(self, K, r, splits):
        lines = [
            "Each segment Wᵢ is split into:\n"
            "  W̃ᵢ: kept portion (size K/(K+1)·T)\n"
            "  W_i^{dest}: small part (size 1/(K+1)·T)\n"
            "     broadcast to node K+1 and\n"
            "     some other nodes.\n\n"
            "Splits:\n"
        ]
        for s in splits:
            dest_str = ','.join(str(d) for d in s['dest_nodes'])
            lines.append(f"  W{s['segment']} → W̃{s['segment']} | W{s['segment']}^{{{dest_str}}}")
        return '\n'.join(lines)

    def _addition_tx_info(self, K, r):
        lines = [
            "Transmission Phase:\n\n"
            "Each node i broadcasts its small\n"
            "subsegment W_i^{{K+1,...}} of size\n"
            "1/(K+1)·T to node K+1 and\n"
            "the first min(r-1,i-1) nodes.\n\n"
            f"Additionally, nodes {K-r+2}..{K}\n"
            f"transmit W̃ᵢ directly to node {K+1}.\n\n"
            "No XOR coding is possible since\n"
            f"node {K+1} starts empty.\n\n"
            f"Communication Load:\n"
            f"  Ladd(r) = rK/(K+1)\n"
            f"           = {r}×{K}/{K+1}\n"
            f"           = {Ladd(K,r):.4f}\n\n"
            f"This is OPTIMAL (matches lower\n"
            f"bound L*add(r) = r/(K+1)·N)."
        ]
        return '\n'.join(lines)

    def _final_addition_info(self, K, r):
        K2 = K + 1
        l_add = Ladd(K, r)
        lines = [
            f"Final r-balanced cyclic DB\n"
            f"on K+1={K2} nodes.\n\n"
            f"Segments: W̃₁,...,W̃{K2}\n"
            f"Each has size K/(K+1)·T = {K}/{K2}T\n"
            f"Each stored in r={r} nodes.\n\n"
            f"New segment W̃{K2} is formed by\n"
            f"concatenating all small subsegments\n"
            f"received by node {K2}.\n\n"
            f"Communication Load:\n"
            f"  Ladd({r}) = {r}×{K}/{K2} = {l_add:.4f}\n\n"
            f"Optimal load L*add = r/(K+1)·N\n"
            f"= {r}/{K2}×{K} = {r*K/(K+1):.4f} ✓\n\n"
            f"Scheme is OPTIMAL."
        ]
        return '\n'.join(lines)

    # ── Step navigation ───────────────────────────────────────────────────────

    def _next_step(self):
        s = self.step.get()
        if s < len(self._steps) - 1:
            self.step.set(s + 1)
            self._update_step_ui()
            self._draw()

    def _prev_step(self):
        s = self.step.get()
        if s > 0:
            self.step.set(s - 1)
            self._update_step_ui()
            self._draw()

    def _update_step_ui(self):
        s = self.step.get()
        total = len(self._steps)
        self._step_lbl.config(text=f"Step {s+1}/{total}")
        self._prev_btn.config(state=tk.NORMAL if s > 0 else tk.DISABLED)
        self._next_btn.config(state=tk.NORMAL if s < total - 1 else tk.DISABLED)

        step = self._steps[s] if self._steps else {}
        title = step.get('title', '')
        info = step.get('info', '')
        self._info_title.config(text=title)
        self._info_text.config(state=tk.NORMAL)
        self._info_text.delete('1.0', tk.END)
        self._info_text.insert('1.0', info)
        self._info_text.config(state=tk.DISABLED)

        # Stats
        K = self.K.get()
        r = max(3, min(self.r.get(), K - 1))
        if self.mode.get() == 'removal':
            l1 = L1(K, r)
            l2 = L2(K, r)
            lrem = Lrem(K, r)
            lu = Lu(r)
            scheme = 1 if r >= rth_threshold(K) else 2
            stats = (
                f"K={K}  r={r}  r_th={rth_threshold(K)}\n"
                f"Scheme: {scheme}  (r {'≥' if scheme==1 else '<'} r_th)\n"
                f"L_rem = {lrem:.3f}  L_u = {lu}\n"
                f"L_rem/L_u = {lrem/lu:.3f} < 1 ✓\n"
                f"L1={l1:.3f}  L2={l2:.3f}"
            )
        else:
            l_add = Ladd(K, r)
            stats = (
                f"K={K}  r={r}\n"
                f"L_add = r·K/(K+1)\n"
                f"      = {r}·{K}/{K+1} = {l_add:.3f}\n"
                f"Optimal (matches lower bound)"
            )
        self._stats_lbl.config(text=stats)

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw(self):
        self._canvas.delete('all')
        if not self._steps:
            return
        s = self.step.get()
        step = self._steps[s]
        phase = step.get('phase', '')

        W = self._canvas.winfo_width()
        H = self._canvas.winfo_height()
        if W < 2 or H < 2:
            return

        if phase in ('initial', 'removal_marked', 'addition_marked', 'final', 'final_add'):
            self._draw_db(step, W, H)
        elif phase == 'splitting':
            self._draw_splitting(step, W, H)
        elif phase == 'transmission':
            self._draw_transmission(step, W, H)
        elif phase == 'merging':
            self._draw_merging(step, W, H)
        elif phase == 'splitting_add':
            self._draw_splitting_add(step, W, H)
        elif phase == 'transmission_add':
            self._draw_transmission_add(step, W, H)

    def _node_positions(self, K_display, W, H, cx=None, cy=None, radius=None):
        """Return list of (x, y) for K_display nodes arranged in a circle."""
        if cx is None:
            cx = W / 2
        if cy is None:
            cy = H / 2
        if radius is None:
            radius = min(W, H) * 0.35
        positions = []
        for i in range(K_display):
            angle = math.pi / 2 - 2 * math.pi * i / K_display
            x = cx + radius * math.cos(angle)
            y = cy - radius * math.sin(angle)
            positions.append((x, y))
        return positions

    def _draw_db(self, step, W, H):
        db = step['db']
        K_display = step['K']
        r = step['r']
        removed = step.get('removed')
        added = step.get('added')
        highlight_segs = step.get('highlight_segs', [])

        # If added node, draw K+1 nodes
        total_nodes = K_display
        if added is not None:
            total_nodes = K_display + 1

        cx, cy = W / 2, H / 2
        radius = min(W, H) * 0.33
        node_r = max(22, min(36, radius / (total_nodes + 1)))

        positions = self._node_positions(total_nodes, W, H, cx, cy, radius)

        # Draw segment arcs around the circle (outer ring)
        # Each segment as a colored arc between its first and last node
        N_segs = len(db)
        for seg_i, (seg, nodes) in enumerate(sorted(db.items())):
            color = seg_color(seg_i, N_segs)
            alpha_color = color
            if highlight_segs and seg not in highlight_segs:
                alpha_color = PALETTE['border']

            # Draw arc on the node circle
            if len(nodes) >= 2:
                # Draw lines between consecutive stored nodes
                for ni in range(len(nodes)):
                    n1 = nodes[ni] - 1
                    n2 = nodes[(ni + 1) % len(nodes)] - 1
                    if n1 < len(positions) and n2 < len(positions):
                        x1, y1 = positions[n1]
                        x2, y2 = positions[n2]
                        # Only draw the arc if it's actually a consecutive arc
                        diff = abs(nodes[(ni + 1) % len(nodes)] - nodes[ni])
                        if diff == 1 or diff == total_nodes - 1:
                            self._canvas.create_line(x1, y1, x2, y2,
                                                      fill=alpha_color, width=2,
                                                      dash=(4, 3))

        # Draw nodes
        for i in range(total_nodes):
            x, y = positions[i]
            node_id = i + 1

            if node_id == removed:
                fill = PALETTE['node_removed']
                outline = '#ff6b6b'
                text_color = 'white'
                lw = 3
            elif node_id == added:
                fill = PALETTE['node_added']
                outline = '#2ecc71'
                text_color = 'white'
                lw = 3
            else:
                fill = PALETTE['node_normal']
                outline = PALETTE['node_survivor']
                text_color = PALETTE['text']
                lw = 2

            self._canvas.create_oval(x - node_r, y - node_r, x + node_r, y + node_r,
                                      fill=fill, outline=outline, width=lw)
            self._canvas.create_text(x, y, text=str(node_id),
                                      fill=text_color, font=('Helvetica', int(node_r * 0.55), 'bold'))

        # Draw segment bars below nodes
        bar_height = 10
        bar_gap = 2
        max_segs_per_node = r
        bar_w = node_r * 1.4

        for i in range(total_nodes):
            x, y = positions[i]
            node_id = i + 1
            # Find which segments are stored here
            stored = [seg for seg, nodes in db.items() if node_id in nodes]
            stored.sort()
            bar_start_y = y + node_r + 4
            for si, seg in enumerate(stored):
                color = seg_color(list(sorted(db.keys())).index(seg), N_segs)
                if highlight_segs and seg not in highlight_segs:
                    color = PALETTE['border']
                bx0 = x - bar_w / 2
                bx1 = x + bar_w / 2
                by0 = bar_start_y + si * (bar_height + bar_gap)
                by1 = by0 + bar_height
                self._canvas.create_rectangle(bx0, by0, bx1, by1, fill=color, outline='')
                self._canvas.create_text(x, (by0 + by1) / 2,
                                          text=f'W{seg}', fill='white',
                                          font=('Helvetica', 7, 'bold'))

        # Legend
        self._draw_legend(db, highlight_segs, W, H)

        # Title
        phase = step['phase']
        subtitle = ""
        if phase == 'removal_marked':
            subtitle = f"⚠ Node {removed} removed — {r} segments lose a replica"
        elif phase == 'addition_marked':
            subtitle = f"✦ Node {added} added (empty) — rebalancing needed"
        elif phase == 'final':
            subtitle = f"✓ Rebalancing complete — cyclic DB on {K_display} nodes"
        elif phase == 'final_add':
            subtitle = f"✓ Rebalancing complete — cyclic DB on {K_display} nodes"

        if subtitle:
            self._canvas.create_text(W / 2, H - 20, text=subtitle,
                                      fill=PALETTE['accent3'], font=('Helvetica', 11, 'italic'))

    def _draw_legend(self, db, highlight_segs, W, H):
        segs = sorted(db.keys())
        x0, y0 = 10, 10
        cols = max(1, W // 80)
        for si, seg in enumerate(segs):
            color = seg_color(si, len(segs))
            if highlight_segs and seg not in highlight_segs:
                color = PALETTE['border']
            col = si % cols
            row = si // cols
            lx = x0 + col * 75
            ly = y0 + row * 18
            self._canvas.create_rectangle(lx, ly, lx + 14, ly + 12, fill=color, outline='')
            self._canvas.create_text(lx + 18, ly + 6, text=f'W{seg}',
                                      fill=PALETTE['text_dim'], font=('Helvetica', 8), anchor='w')

    def _draw_splitting(self, step, W, H):
        K = step['K']
        r = step['r']
        db = step['db']
        subsegments = step.get('subsegments', [])
        scheme = step.get('scheme', 1)
        removed = step.get('removed', K)

        # Group by segment
        by_seg = {}
        for ss in subsegments:
            by_seg.setdefault(ss['segment'], []).append(ss)

        segs = sorted(by_seg.keys())
        n_segs = len(segs)
        denom = 2 * (K - 1)

        # Layout: each segment as a horizontal bar divided into subsegments
        margin_left = 60
        margin_right = 20
        margin_top = 40
        bar_height = 36
        bar_gap = 18
        total_height = n_segs * (bar_height + bar_gap) + margin_top + 20

        bar_w = W - margin_left - margin_right

        for si, seg in enumerate(segs):
            subs = by_seg[seg]
            y = margin_top + si * (bar_height + bar_gap)

            # Segment label
            self._canvas.create_text(margin_left - 10, y + bar_height / 2,
                                      text=f'W{seg}', fill=seg_color(si, n_segs),
                                      font=('Helvetica', 12, 'bold'), anchor='e')

            # Draw subsegment rectangles proportional to size
            total_size = sum(s['size_num'] for s in subs)
            x = margin_left
            colors = [PALETTE['subseg_a'], PALETTE['subseg_b'], PALETTE['accent'],
                      PALETTE['accent2'], PALETTE['accent3']]
            for ssi, ss in enumerate(subs):
                frac = ss['size_num'] / total_size
                sw = bar_w * frac
                c = colors[ssi % len(colors)]
                self._canvas.create_rectangle(x, y, x + sw, y + bar_height,
                                               fill=c, outline=PALETTE['bg'], width=2)
                # Label inside if wide enough
                lbl = ss['label'].replace('{', '').replace('}', '')
                frac_str = f"{ss['size_num']}/{denom}·T"
                if sw > 60:
                    self._canvas.create_text(x + sw / 2, y + bar_height / 2 - 6,
                                              text=lbl, fill='white',
                                              font=('Helvetica', 8, 'bold'))
                    self._canvas.create_text(x + sw / 2, y + bar_height / 2 + 8,
                                              text=frac_str, fill='#ddd',
                                              font=('Helvetica', 7))
                elif sw > 25:
                    self._canvas.create_text(x + sw / 2, y + bar_height / 2,
                                              text=frac_str, fill='white',
                                              font=('Helvetica', 7))
                x += sw

        # Title
        self._canvas.create_text(W / 2, 15, text=f'Splitting of segments in removed node {removed}',
                                  fill=PALETTE['text'], font=('Helvetica', 11, 'bold'))

        # Scheme indicator
        scheme_color = PALETTE['scheme1'] if scheme == 1 else PALETTE['scheme2']
        self._canvas.create_text(W - 10, H - 20,
                                  text=f'Scheme {scheme} will be used in transmission',
                                  fill=scheme_color, font=('Helvetica', 10, 'italic'),
                                  anchor='e')

    def _draw_transmission(self, step, W, H):
        K = step['K']
        r = step['r']
        removed = step.get('removed', K)
        transmissions = step.get('transmissions', [])
        subsegments = step.get('subsegments', [])
        scheme = step.get('scheme', 1)

        node_ids = [i for i in range(1, K + 1) if i != removed]
        dk_segs = list(range(K - r + 1, K + 1))   # segments that were in removed node
        denom = 2 * (K - 1)

        # Build subseg size lookup: (segment, frozenset(dest_nodes)) -> size_num
        ss_size = {}
        for ss in subsegments:
            ss_size[(ss['segment'], tuple(sorted(ss['dest_nodes'])))] = ss['size_num']

        # ── Layout ────────────────────────────────────────────────────────────
        # Top half: node row with storage info
        # Bottom half: scrollable-ish table of transmissions

        scheme_color = PALETTE['scheme1'] if scheme == 1 else PALETTE['scheme2']

        # ── Header ────────────────────────────────────────────────────────────
        header_h = 28
        self._canvas.create_rectangle(0, 0, W, header_h, fill=PALETTE['panel'], outline='')
        self._canvas.create_text(W / 2, header_h / 2,
                                  text=f'Scheme {scheme} Transmissions  '
                                       f'(r={r}, K={K}, r_th={rth_threshold(K)}, '
                                       f'removed node={removed})',
                                  fill=scheme_color, font=('Helvetica', 10, 'bold'))

        # ── Node row ──────────────────────────────────────────────────────────
        n_nodes = len(node_ids)
        node_section_h = 140
        node_y = header_h + node_section_h // 2 - 10
        node_r = min(20, max(14, (W - 80) // (n_nodes * 2 + 2)))
        margin = 40
        avail_w = W - 2 * margin
        node_spacing = avail_w / max(n_nodes - 1, 1)

        node_x = {nid: margin + ni * node_spacing for ni, nid in enumerate(node_ids)}

        # Which nodes broadcast
        broadcasters = set(tx['broadcaster'] for tx in transmissions)

        for nid in node_ids:
            x = node_x[nid]
            is_bcast = nid in broadcasters
            fill = PALETTE['accent2'] if is_bcast else PALETTE['node_normal']
            outline_c = PALETTE['highlight'] if is_bcast else PALETTE['node_survivor']
            lw = 3 if is_bcast else 2

            self._canvas.create_oval(x - node_r, node_y - node_r,
                                      x + node_r, node_y + node_r,
                                      fill=fill, outline=outline_c, width=lw)
            self._canvas.create_text(x, node_y, text=str(nid),
                                      fill='white', font=('Helvetica', int(node_r * 0.55), 'bold'))

            # All segments stored at this node
            all_stored = cyc_bwd(nid, r, K)
            rel_stored = [s for s in all_stored if s in dk_segs]
            other_stored = [s for s in all_stored if s not in dk_segs]

            # Relevant (from removed node) in orange, others dimmed
            y_off = node_y + node_r + 4
            if rel_stored:
                lbl = ' '.join(f'W{s}' for s in rel_stored)
                self._canvas.create_text(x, y_off, text=lbl, fill=PALETTE['highlight'],
                                          font=('Helvetica', 7, 'bold'))
                y_off += 12
            if other_stored:
                lbl = ' '.join(f'W{s}' for s in other_stored)
                self._canvas.create_text(x, y_off, text=lbl, fill=PALETTE['text_dim'],
                                          font=('Helvetica', 6))
                y_off += 11

            if is_bcast:
                self._canvas.create_text(x, y_off, text='BROADCASTS',
                                          fill=PALETTE['highlight'], font=('Helvetica', 6, 'bold'))

        # Storage header note
        self._canvas.create_text(margin, header_h + 6, anchor='w',
                                  text='Node storage  (orange = from removed node, dim = other segments)',
                                  fill=PALETTE['text_dim'], font=('Helvetica', 8, 'italic'))

        # ── Separator ─────────────────────────────────────────────────────────
        sep_y = header_h + node_section_h
        self._canvas.create_line(0, sep_y, W, sep_y, fill=PALETTE['border'], width=1)

        # ── Transmission table ────────────────────────────────────────────────
        # Columns: #  | Broadcaster | Type | Transmission (XOR expression) | Destinations | Decode reason
        table_top = sep_y + 6
        col_x = [8, 28, 68, 118, W * 0.52, W * 0.77]
        col_hdrs = ['#', 'Node', 'Type', 'Broadcast content', 'Dest nodes & decode', 'Size (×T)']
        row_h = max(18, min(24, (H - table_top - 10) // max(len(transmissions) + 1, 1)))
        hdr_y = table_top + row_h / 2

        # Header row bg
        self._canvas.create_rectangle(0, table_top, W, table_top + row_h,
                                       fill=PALETTE['card'], outline='')
        for ci, (cx, hdr) in enumerate(zip(col_x, col_hdrs)):
            self._canvas.create_text(cx + 2, hdr_y, text=hdr, anchor='w',
                                      fill=PALETTE['accent3'], font=('Helvetica', 8, 'bold'))

        font_tx = ('Courier', 8)
        font_sm = ('Helvetica', 7)

        for ti, tx in enumerate(transmissions):
            ry = table_top + (ti + 1) * row_h
            # Alternating row background
            bg = PALETTE['panel'] if ti % 2 == 0 else PALETTE['bg']
            self._canvas.create_rectangle(0, ry, W, ry + row_h, fill=bg, outline='')

            cy_mid = ry + row_h / 2
            broadcaster = tx['broadcaster']
            tx_type = tx['type']
            type_color = PALETTE['coded_tx'] if tx_type == 'coded' else PALETTE['uncoded_tx']
            type_lbl = 'XOR' if tx_type == 'coded' else 'raw'

            # Col 0: index
            self._canvas.create_text(col_x[0] + 2, cy_mid, text=str(ti + 1), anchor='w',
                                      fill=PALETTE['text_dim'], font=font_sm)
            # Col 1: broadcaster
            self._canvas.create_rectangle(col_x[1], ry + 2, col_x[1] + 36, ry + row_h - 2,
                                           fill=PALETTE['accent2'] if broadcaster in broadcasters else PALETTE['card'],
                                           outline='')
            self._canvas.create_text(col_x[1] + 18, cy_mid, text=f'N{broadcaster}',
                                      fill='white', font=('Helvetica', 8, 'bold'))
            # Col 2: type pill
            self._canvas.create_rectangle(col_x[2], ry + 3, col_x[2] + 42, ry + row_h - 3,
                                           fill=type_color, outline='')
            self._canvas.create_text(col_x[2] + 21, cy_mid, text=type_lbl,
                                      fill='white', font=('Helvetica', 7, 'bold'))

            # Col 3: broadcast expression
            if tx_type == 'coded':
                subs = tx['subsegments']
                expr = ' \u2295 '.join(f"W{s['segment']}^{s['dest']}" for s in subs)
            else:
                seg = tx.get('segment', '?')
                expr = f"small subs of W{seg} (uncoded)"
            # Truncate if needed
            max_expr_chars = max(10, int((col_x[4] - col_x[3] - 4) / 6))
            if len(expr) > max_expr_chars:
                expr = expr[:max_expr_chars - 2] + '..'
            self._canvas.create_text(col_x[3] + 2, cy_mid, text=expr, anchor='w',
                                      fill=PALETTE['text'], font=font_tx)

            # Col 4: destinations and decode info
            if tx_type == 'coded':
                subs = tx['subsegments']
                dest_parts = []
                for s in subs:
                    dest = s['dest']
                    seg = s['segment']
                    # What does dest node hold that lets it decode?
                    # dest node holds segments in cyc_bwd(dest, r, K)
                    held = cyc_bwd(dest, r, K)
                    held_dk = [h for h in held if h in dk_segs and h != seg]
                    other_subs_segs = [sub['segment'] for sub in subs if sub['segment'] != seg]
                    # Decode: node dest XORs away the other subsegments it holds
                    can_decode = [h for h in held_dk if h in other_subs_segs]
                    if can_decode:
                        held_str = '+'.join(f'W{h}' for h in can_decode[:2])
                        dest_parts.append(f"N{dest}\u2190W{seg}^{dest} (has {held_str})")
                    else:
                        dest_parts.append(f"N{dest}\u2190W{seg}^{dest}")
                decode_str = '  |  '.join(dest_parts)
            else:
                seg = tx.get('segment', '?')
                note = tx.get('note', '')
                # Who receives?
                dest_parts = []
                for nid in node_ids:
                    stored_segs = cyc_bwd(nid, r, K)
                    if seg in stored_segs and nid != broadcaster:
                        pass  # they already have it
                    # small subs go to specific nodes that don't have the corner segment
                decode_str = note if note else f"all nodes needing subsegments of W{seg}"

            max_dest_chars = max(10, int((col_x[5] - col_x[4] - 4) / 6))
            if len(decode_str) > max_dest_chars:
                decode_str = decode_str[:max_dest_chars - 2] + '..'
            self._canvas.create_text(col_x[4] + 2, cy_mid, text=decode_str, anchor='w',
                                      fill=PALETTE['accent3'], font=('Helvetica', 7))

            # Col 5: size
            if tx_type == 'coded':
                subs = tx['subsegments']
                # Size = max subsegment size (smaller ones are zero-padded)
                max_sz = 0
                for s in subs:
                    key = (s['segment'], (s['dest'],))
                    sz = ss_size.get(key, 0)
                    max_sz = max(max_sz, sz)
                size_str = f"{max_sz}/{denom}" if max_sz else '?'
            else:
                size_str = f"small"
            self._canvas.create_text(col_x[5] + 2, cy_mid, text=size_str, anchor='w',
                                      fill=PALETTE['text_dim'], font=font_sm)

            # Divider line
            self._canvas.create_line(0, ry + row_h, W, ry + row_h,
                                      fill=PALETTE['border'], width=1, dash=(2, 4))

        # ── Load summary bar at the bottom ────────────────────────────────────
        l1v = L1(K, r)
        l2v = L2(K, r)
        lrem = Lrem(K, r)
        lu = Lu(r)
        gain = (1 - lrem / lu) * 100

        footer_y = H - 24
        self._canvas.create_rectangle(0, footer_y - 2, W, H, fill=PALETTE['panel'], outline='')

        load_txt = (f"  Load:  L_rem = (K-r)/(K-1) + min(L1,L2) = "
                    f"{(K-r)/(K-1):.3f} + {min(l1v,l2v):.3f} = {lrem:.3f}   |   "
                    f"Uncoded Lu = {lu}   |   "
                    f"Saving: {gain:.1f}% over uncoded   |   "
                    f"L1={l1v:.3f}  L2={l2v:.3f}")
        self._canvas.create_text(4, footer_y + 10, text=load_txt, anchor='w',
                                  fill=PALETTE['accent3'], font=('Courier', 8, 'bold'))

        # Column dividers
        for cx in col_x[1:]:
            self._canvas.create_line(cx - 2, sep_y, cx - 2, H - 26,
                                      fill=PALETTE['border'], width=1)

    def _draw_merging(self, step, W, H):
        K = step['K']
        r = step['r']
        merges = step.get('merges', [])

        margin = 50
        bar_height = 28
        bar_gap = 12
        n = len(merges)
        avail_h = H - 60
        item_h = min(bar_height + bar_gap, avail_h / max(n, 1))
        bar_h = item_h - bar_gap

        self._canvas.create_text(W / 2, 20, text='Merging: Forming target segments W̃ᵢ',
                                  fill=PALETTE['text'], font=('Helvetica', 11, 'bold'))

        bar_w = W - 2 * margin - 200  # leave room for node list

        for mi, merge in enumerate(merges):
            y = 45 + mi * item_h
            new_seg = merge['new_seg']

            # Label
            self._canvas.create_text(margin - 8, y + bar_h / 2,
                                      text=f'W̃{new_seg}', fill=PALETTE['accent3'],
                                      font=('Helvetica', 10, 'bold'), anchor='e')

            # Parts bar
            parts = merge['parts']
            total_parts = len(parts)
            pw = bar_w / total_parts if total_parts else bar_w
            colors = [PALETTE['node_normal'], PALETTE['subseg_a'], PALETTE['subseg_b'],
                      PALETTE['accent'], PALETTE['accent2']]

            x = margin
            for pi, part in enumerate(parts):
                c = colors[pi % len(colors)]
                self._canvas.create_rectangle(x, y, x + pw, y + bar_h,
                                               fill=c, outline=PALETTE['bg'], width=1)
                if part.get('whole'):
                    lbl = f"W{part['old_seg']}"
                else:
                    dl = part.get('dest_label', part.get('dest', ''))
                    lbl = f"W{part['segment']}^{{{dl}}}"
                if pw > 30:
                    self._canvas.create_text(x + pw / 2, y + bar_h / 2,
                                              text=lbl, fill='white', font=('Helvetica', 7))
                x += pw

            # Nodes label
            nodes_str = '{' + ','.join(str(n) for n in merge['nodes']) + '}'
            self._canvas.create_text(margin + bar_w + 8, y + bar_h / 2,
                                      text=f'→ nodes {nodes_str}',
                                      fill=PALETTE['text_dim'], font=('Helvetica', 8),
                                      anchor='w')

        # Size note
        self._canvas.create_text(W / 2, H - 15,
                                  text=f'Each W̃ᵢ has size K/(K-1)·T = {K}/{K-1}·T',
                                  fill=PALETTE['accent3'], font=('Helvetica', 9, 'italic'))

    def _draw_splitting_add(self, step, W, H):
        K = step['K']
        r = step['r']
        splits = step.get('splits_add', [])

        margin_left = 60
        margin_right = 20
        margin_top = 40
        bar_height = 30
        bar_gap = 14
        bar_w = W - margin_left - margin_right

        self._canvas.create_text(W / 2, 18,
                                  text='Splitting: Wᵢ → W̃ᵢ (keep) + Wᵢ^{dest} (small, broadcast)',
                                  fill=PALETTE['text'], font=('Helvetica', 11, 'bold'))

        for si, sp in enumerate(splits):
            seg = sp['segment']
            y = margin_top + si * (bar_height + bar_gap)

            # Segment label
            self._canvas.create_text(margin_left - 10, y + bar_height / 2,
                                      text=f'W{seg}', fill=seg_color(si, K),
                                      font=('Helvetica', 11, 'bold'), anchor='e')

            # Big kept part (K/(K+1))
            w_big = bar_w * K / (K + 1)
            self._canvas.create_rectangle(margin_left, y, margin_left + w_big, y + bar_height,
                                           fill=PALETTE['node_normal'], outline=PALETTE['bg'], width=2)
            self._canvas.create_text(margin_left + w_big / 2, y + bar_height / 2,
                                      text=f'W̃{seg}  ({K}/{K+1}·T)',
                                      fill='white', font=('Helvetica', 8, 'bold'))

            # Small broadcast part (1/(K+1))
            w_small = bar_w / (K + 1)
            dest_str = ','.join(str(d) for d in sp['dest_nodes'])
            self._canvas.create_rectangle(margin_left + w_big, y,
                                           margin_left + w_big + w_small, y + bar_height,
                                           fill=PALETTE['accent'], outline=PALETTE['bg'], width=2)
            if w_small > 20:
                self._canvas.create_text(margin_left + w_big + w_small / 2, y + bar_height / 2,
                                          text=f'^{{{dest_str}}}', fill='white', font=('Helvetica', 7))

    def _draw_transmission_add(self, step, W, H):
        K = step['K']
        r = step['r']
        added = step.get('added', K + 1)
        splits = step.get('splits_add', [])

        # ── Header ────────────────────────────────────────────────────────────
        header_h = 28
        self._canvas.create_rectangle(0, 0, W, header_h, fill=PALETTE['panel'], outline='')
        self._canvas.create_text(W / 2, header_h / 2,
                                  text=f'Node Addition Transmissions  (K={K}, r={r}, new node={added})  '
                                       f'— Uncoded, Optimal',
                                  fill=PALETTE['uncoded_tx'], font=('Helvetica', 10, 'bold'))

        # ── Node row ──────────────────────────────────────────────────────────
        all_nodes = list(range(1, K + 1)) + [added]
        n_nodes = len(all_nodes)
        node_section_h = 130
        node_y = header_h + node_section_h // 2 - 10
        node_r = min(20, max(12, (W - 80) // (n_nodes * 2 + 2)))
        margin = 40
        avail_w = W - 2 * margin
        node_spacing = avail_w / max(n_nodes - 1, 1)
        node_x = {nid: margin + i * node_spacing for i, nid in enumerate(all_nodes)}

        # Draw arcs BEFORE nodes so nodes render on top
        tx_y = node_y + node_r + 4
        direct_nodes = list(range(K - r + 2, K + 1))  # transmit W̃ directly

        for i, nid in enumerate(range(1, K + 1)):
            bx = node_x[nid]
            dx = node_x[added]
            # Small subsegment arc (everyone → new node)
            arc_h = 18 + i * 7
            mid_x = (bx + dx) / 2
            mid_y = tx_y + arc_h
            self._canvas.create_line(bx, tx_y, mid_x, mid_y, dx, tx_y,
                                      fill=PALETTE['uncoded_tx'], width=1, smooth=True,
                                      arrow=tk.LAST, arrowshape=(5, 7, 3))
            sp = splits[i - 1] if i - 1 < len(splits) else {}
            dest_str = ','.join(str(d) for d in sp.get('dest_nodes', [added]))
            lbl = f"W{nid}^{{{dest_str}}} (1/{K+1}·T)"
            # Stagger label above/below arc
            lbl_y = mid_y - 9 if i % 2 == 0 else mid_y + 2
            if abs(dx - bx) > 60:
                self._canvas.create_text(mid_x, lbl_y, text=lbl,
                                          fill=PALETTE['uncoded_tx'], font=('Helvetica', 6))

        # Direct W̃ transmissions (last r-1 nodes → new node)
        for nid in direct_nodes:
            bx = node_x[nid]
            dx = node_x[added]
            self._canvas.create_line(bx, tx_y - node_r - 2, dx, tx_y - node_r - 2,
                                      fill=PALETTE['highlight'], width=2,
                                      arrow=tk.LAST, arrowshape=(7, 9, 4))
            mid_x = (bx + dx) / 2
            self._canvas.create_text(mid_x, tx_y - node_r - 10,
                                      text=f"W\u0303{nid} ({K}/{K+1}·T) direct",
                                      fill=PALETTE['highlight'], font=('Helvetica', 6, 'bold'))

        # Draw nodes
        for nid in all_nodes:
            x = node_x[nid]
            is_new = (nid == added)
            is_direct = (nid in direct_nodes)
            fill = (PALETTE['node_added'] if is_new
                    else PALETTE['highlight'] if is_direct
                    else PALETTE['node_normal'])
            outline_c = '#2ecc71' if is_new else (PALETTE['highlight'] if is_direct else PALETTE['node_survivor'])
            lw = 3 if (is_new or is_direct) else 2

            self._canvas.create_oval(x - node_r, node_y - node_r,
                                      x + node_r, node_y + node_r,
                                      fill=fill, outline=outline_c, width=lw)
            self._canvas.create_text(x, node_y, text=str(nid),
                                      fill='white', font=('Helvetica', int(node_r * 0.55), 'bold'))

            y_off = node_y + node_r + 4
            if is_new:
                self._canvas.create_text(x, y_off, text='(new/empty)',
                                          fill=PALETTE['node_added'], font=('Helvetica', 6, 'italic'))
            else:
                stored = cyc_bwd(nid, r, K)
                lbl = ' '.join(f'W{s}' for s in stored)
                self._canvas.create_text(x, y_off, text=lbl,
                                          fill=PALETTE['text_dim'], font=('Helvetica', 6))
                if is_direct:
                    self._canvas.create_text(x, y_off + 10, text='sends W\u0303 direct',
                                              fill=PALETTE['highlight'], font=('Helvetica', 6, 'bold'))

        self._canvas.create_text(margin, header_h + 4, anchor='w',
                                  text='Gold nodes send W\u0303 segment directly  |  '
                                       'Green arcs = small subsegment (1/(K+1)·T)  |  '
                                       'Gold arrow = large part (K/(K+1)·T)',
                                  fill=PALETTE['text_dim'], font=('Helvetica', 7, 'italic'))

        # ── Separator ─────────────────────────────────────────────────────────
        sep_y = header_h + node_section_h
        self._canvas.create_line(0, sep_y, W, sep_y, fill=PALETTE['border'], width=1)

        # ── Per-node transmission table ───────────────────────────────────────
        table_top = sep_y + 6
        col_x = [8, 30, W * 0.14, W * 0.38, W * 0.60, W * 0.82]
        col_hdrs = ['#', 'Node', 'Keeps (size)', 'Broadcasts (to nodes)', 'Discards', 'New segment']
        row_h = max(16, min(22, (H - table_top - 30) // max(K + 1, 1)))
        hdr_y = table_top + row_h / 2

        self._canvas.create_rectangle(0, table_top, W, table_top + row_h,
                                       fill=PALETTE['card'], outline='')
        for ci, (cx, hdr) in enumerate(zip(col_x, col_hdrs)):
            self._canvas.create_text(cx + 2, hdr_y, text=hdr, anchor='w',
                                      fill=PALETTE['accent3'], font=('Helvetica', 8, 'bold'))

        # Target DB for reference
        db_target = build_target_db_addition(K, r)

        for i, sp in enumerate(splits):
            nid = sp['segment']
            ry = table_top + (i + 1) * row_h
            bg = PALETTE['panel'] if i % 2 == 0 else PALETTE['bg']
            self._canvas.create_rectangle(0, ry, W, ry + row_h, fill=bg, outline='')
            cy_mid = ry + row_h / 2

            is_direct = (nid in direct_nodes)
            row_color = PALETTE['highlight'] if is_direct else PALETTE['text']

            dest_nodes = sp.get('dest_nodes', [added])
            dest_str = '{' + ','.join(str(d) for d in dest_nodes) + '}'

            # Which segment does this node discard?
            stored_init = cyc_bwd(nid, r, K)
            stored_target = [s for s in range(1, K + 2) if nid in db_target.get(s, [])]
            discard = [s for s in stored_init if s not in stored_target and s != nid]
            discard_str = ('W̃' + str(discard[0])) if discard else '—'

            # New target segment this node participates in
            new_segs = stored_target
            new_str = ' '.join(f'W\u0303{s}' for s in new_segs[:3])
            if len(new_segs) > 3:
                new_str += '..'

            self._canvas.create_text(col_x[0] + 2, cy_mid, text=str(i + 1), anchor='w',
                                      fill=PALETTE['text_dim'], font=('Helvetica', 7))
            self._canvas.create_text(col_x[1] + 2, cy_mid, text=f'N{nid}', anchor='w',
                                      fill=row_color, font=('Helvetica', 8, 'bold'))
            self._canvas.create_text(col_x[2] + 2, cy_mid,
                                      text=f'W\u0303{nid}  ({K}/{K+1}·T)', anchor='w',
                                      fill=PALETTE['node_added'], font=('Courier', 8))
            self._canvas.create_text(col_x[3] + 2, cy_mid,
                                      text=f'W{nid}^{dest_str}  (1/{K+1}·T)', anchor='w',
                                      fill=PALETTE['uncoded_tx'], font=('Courier', 8))
            self._canvas.create_text(col_x[4] + 2, cy_mid, text=discard_str, anchor='w',
                                      fill=PALETTE['node_removed'], font=('Helvetica', 8))
            self._canvas.create_text(col_x[5] + 2, cy_mid, text=new_str, anchor='w',
                                      fill=PALETTE['text_dim'], font=('Helvetica', 7))

            self._canvas.create_line(0, ry + row_h, W, ry + row_h,
                                      fill=PALETTE['border'], width=1, dash=(2, 4))

        for cx in col_x[1:]:
            self._canvas.create_line(cx - 2, sep_y, cx - 2, H - 26,
                                      fill=PALETTE['border'], width=1)

        # ── Footer load summary ───────────────────────────────────────────────
        load = Ladd(K, r)
        footer_y = H - 22
        self._canvas.create_rectangle(0, footer_y - 2, W, H, fill=PALETTE['panel'], outline='')
        self._canvas.create_text(4, footer_y + 8, anchor='w',
                                  text=f"  Load: L_add(r) = r·K/(K+1) = {r}·{K}/{K+1} = {load:.4f}  "
                                       f"|  Optimal L*_add = r/(K+1)·N = {r}/{K+1}·{K} = {load:.4f}  ✓",
                                  fill=PALETTE['accent3'], font=('Courier', 8, 'bold'))


# ─────────────────────────── Entry point ─────────────────────────────────────

if __name__ == '__main__':
    app = CDRVisualizer()
    app.mainloop()
