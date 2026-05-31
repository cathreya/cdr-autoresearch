#!/usr/bin/env python3
"""Render an AutoResearch JSON artifact as a standalone HTML page."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Visualize an AutoResearch placement, plan, or repair JSON file."
    )
    parser.add_argument(
        "json_file",
        type=Path,
        help="Path to an AutoResearch JSON file, e.g. autoresearch/test/fixtures/fixtureA.initial.json",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output HTML path. Defaults to <json_file stem>.html next to the input.",
    )
    return parser.parse_args()


def load_artifact(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    kind = data.get("kind")
    if kind == "placement":
        required = ["nodes", "r", "unit", "segments"]
    elif kind == "plan":
        required = ["removed", "pieces", "merges"]
    elif kind == "repair":
        required = ["broadcasts"]
    else:
        raise ValueError(
            f"{path} has kind={kind!r}; expected one of 'placement', 'plan', or 'repair'"
        )

    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError(f"{path} is missing required field(s): {', '.join(missing)}")

    return data


def sort_key(value: Any) -> tuple[int, Any]:
    try:
        return (0, int(value))
    except (TypeError, ValueError):
        return (1, str(value))


def color_for_segment(index: int, total: int) -> str:
    hue = (index * 137.508) % 360
    saturation = 68
    lightness = 44 if total > 12 else 40
    return f"hsl({hue:.1f} {saturation}% {lightness}%)"


def render_body(data: dict[str, Any]) -> str:
    if data["kind"] == "placement":
        return render_placement(data)
    if data["kind"] == "plan":
        return render_plan(data)
    if data["kind"] == "repair":
        return render_repair(data)
    raise ValueError(f"Unsupported artifact kind: {data.get('kind')!r}")


def render_placement(data: dict[str, Any]) -> str:
    nodes = int(data["nodes"])
    unit = int(data["unit"])
    segments = sorted(data["segments"], key=lambda segment: sort_key(segment["id"]))
    node_ids = list(range(1, nodes + 1))

    loads = {node: 0 for node in node_ids}
    segment_colors: dict[str, str] = {}
    for index, segment in enumerate(segments):
        segment_id = str(segment["id"])
        segment_colors[segment_id] = color_for_segment(index, len(segments))
        for node in segment["storage"]:
            loads[int(node)] += int(segment["size"])

    max_load = max(loads.values()) if loads else 0

    matrix_rows = []
    for segment in segments:
        segment_id = str(segment["id"])
        storage = {int(node) for node in segment["storage"]}
        color = segment_colors[segment_id]
        cells = []
        for node in node_ids:
            if node in storage:
                cells.append(
                    f'<td class="stored" style="--segment-color: {color};" '
                    f'title="Segment {html.escape(segment_id)} is stored on node {node}"></td>'
                )
            else:
                cells.append('<td class="empty"></td>')

        matrix_rows.append(
            "<tr>"
            f'<th scope="row"><span class="swatch" style="--segment-color: {color};"></span>'
            f'{html.escape(segment_id)}</th>'
            f'<td class="size">{int(segment["size"])}/{unit}</td>'
            + "".join(cells)
            + "</tr>"
        )

    load_rows = []
    for node in node_ids:
        load = loads[node]
        width = 0 if max_load == 0 else round(load / max_load * 100, 2)
        load_rows.append(
            "<tr>"
            f"<th scope=\"row\">Node {node}</th>"
            f"<td>{load}/{unit}</td>"
            f'<td><div class="bar"><span style="width: {width}%"></span></div></td>'
            "</tr>"
        )

    node_headers = "".join(f"<th>N{node}</th>" for node in node_ids)
    return f"""
    <section class="stats" aria-label="Placement summary">
      <div class="stat"><strong>{nodes}</strong><span>nodes</span></div>
      <div class="stat"><strong>{int(data["r"])}</strong><span>replication factor</span></div>
      <div class="stat"><strong>{len(segments)}</strong><span>segments</span></div>
      <div class="stat"><strong>{unit}</strong><span>unit denominator</span></div>
    </section>
    <section>
      <h2>Storage Matrix</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th>Segment</th><th>Size</th>{node_headers}</tr>
          </thead>
          <tbody>
            {''.join(matrix_rows)}
          </tbody>
        </table>
      </div>
    </section>
    <section>
      <h2>Node Loads</h2>
      <div class="table-wrap">
        <table class="load-table">
          <tbody>
            {''.join(load_rows)}
          </tbody>
        </table>
      </div>
    </section>
"""


def render_plan(data: dict[str, Any]) -> str:
    pieces = sorted(data["pieces"], key=lambda piece: sort_key(piece["id"]))
    merges = sorted(data["merges"], key=lambda merge: sort_key(merge["target"]))

    piece_rows = []
    for index, piece in enumerate(pieces):
        color = color_for_segment(index, len(pieces))
        dest = ", ".join(str(node) for node in piece["dest"]) or "already placed"
        piece_rows.append(
            "<tr>"
            f'<th scope="row"><span class="swatch" style="--segment-color: {color};"></span>'
            f'{html.escape(str(piece["id"]))}</th>'
            f'<td>{html.escape(str(piece["source"]))}</td>'
            f"<td>{html.escape(dest)}</td>"
            f'<td class="size">{html.escape(str(piece["size"]))}</td>'
            "</tr>"
        )

    merge_rows = []
    for merge in merges:
        parts = " + ".join(html.escape(str(part)) for part in merge["parts"])
        merge_rows.append(
            "<tr>"
            f'<th scope="row">Target {html.escape(str(merge["target"]))}</th>'
            f"<td>{parts}</td>"
            "</tr>"
        )

    return f"""
    <section class="stats" aria-label="Plan summary">
      <div class="stat"><strong>{html.escape(str(data["removed"]))}</strong><span>removed node</span></div>
      <div class="stat"><strong>{len(pieces)}</strong><span>pieces</span></div>
      <div class="stat"><strong>{len(merges)}</strong><span>merges</span></div>
    </section>
    <section>
      <h2>Pieces</h2>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Piece</th><th>Source</th><th>Destination</th><th>Size</th></tr></thead>
          <tbody>{''.join(piece_rows)}</tbody>
        </table>
      </div>
    </section>
    <section>
      <h2>Merges</h2>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Target</th><th>Parts</th></tr></thead>
          <tbody>{''.join(merge_rows)}</tbody>
        </table>
      </div>
    </section>
"""


def render_repair(data: dict[str, Any]) -> str:
    broadcasts = data["broadcasts"]
    rows = []
    for index, broadcast in enumerate(broadcasts, start=1):
        terms = " XOR ".join(html.escape(str(term)) for term in broadcast["terms"])
        rows.append(
            "<tr>"
            f'<th scope="row">{index}</th>'
            f'<td>Node {html.escape(str(broadcast["by"]))}</td>'
            f"<td>{terms}</td>"
            f'<td class="size">{len(broadcast["terms"])}</td>'
            "</tr>"
        )

    coded_count = sum(1 for broadcast in broadcasts if len(broadcast["terms"]) > 1)
    return f"""
    <section class="stats" aria-label="Repair summary">
      <div class="stat"><strong>{len(broadcasts)}</strong><span>broadcasts</span></div>
      <div class="stat"><strong>{coded_count}</strong><span>coded broadcasts</span></div>
      <div class="stat"><strong>{len(broadcasts) - coded_count}</strong><span>uncoded broadcasts</span></div>
    </section>
    <section>
      <h2>Broadcasts</h2>
      <div class="table-wrap">
        <table>
          <thead><tr><th>#</th><th>By</th><th>Terms</th><th>Term count</th></tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </div>
    </section>
"""


def render_html(data: dict[str, Any], source: Path) -> str:
    source_label = html.escape(str(source))
    title = html.escape(source.stem)
    body = render_body(data)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} placement visualization</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8fa;
      --panel: #ffffff;
      --text: #20242a;
      --muted: #667085;
      --line: #d8dde5;
      --empty: #eef1f5;
      --bar: #26706a;
    }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 32px 20px 48px;
    }}
    h1 {{
      margin: 0 0 6px;
      font-size: 26px;
      line-height: 1.15;
      letter-spacing: 0;
    }}
    .meta {{
      color: var(--muted);
      margin-bottom: 24px;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 10px;
      margin-bottom: 20px;
    }}
    .stat {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px 14px;
    }}
    .stat strong {{
      display: block;
      font-size: 20px;
      line-height: 1.2;
    }}
    .stat span {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
    }}
    .table-wrap {{
      overflow-x: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 560px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 8px 10px;
      text-align: center;
      white-space: nowrap;
    }}
    thead th {{
      position: sticky;
      top: 0;
      background: #f0f3f7;
      z-index: 1;
      font-size: 12px;
      color: #344054;
    }}
    tbody tr:last-child th,
    tbody tr:last-child td {{
      border-bottom: 0;
    }}
    tbody th {{
      text-align: left;
      font-weight: 600;
    }}
    .size {{
      color: var(--muted);
      font-variant-numeric: tabular-nums;
    }}
    .stored, .empty {{
      width: 42px;
      min-width: 42px;
      height: 26px;
      padding: 0;
    }}
    .stored {{
      background: var(--segment-color);
      box-shadow: inset 0 0 0 3px #fff;
    }}
    .empty {{
      background: var(--empty);
      box-shadow: inset 0 0 0 3px #fff;
    }}
    .swatch {{
      display: inline-block;
      width: 12px;
      height: 12px;
      margin-right: 8px;
      border-radius: 3px;
      background: var(--segment-color);
      vertical-align: -1px;
    }}
    h2 {{
      margin: 28px 0 10px;
      font-size: 18px;
      letter-spacing: 0;
    }}
    .load-table th {{
      width: 110px;
    }}
    .load-table td:nth-child(2) {{
      width: 90px;
      color: var(--muted);
      font-variant-numeric: tabular-nums;
    }}
    .bar {{
      height: 12px;
      background: var(--empty);
      border-radius: 999px;
      overflow: hidden;
    }}
    .bar span {{
      display: block;
      height: 100%;
      background: var(--bar);
    }}
  </style>
</head>
<body>
  <main>
    <h1>{title}</h1>
    <div class="meta">Kind: {html.escape(str(data["kind"]))} | Source: {source_label}</div>
    {body}
  </main>
</body>
</html>
"""


def main() -> int:
    args = parse_args()
    json_path = args.json_file
    output_path = args.output or json_path.with_suffix(".html")

    data = load_artifact(json_path)
    output_path.write_text(render_html(data, json_path), encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
