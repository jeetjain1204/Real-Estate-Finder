"""Generate the LangGraph state diagram for RealEstateFinder.

Usage:
    python scripts/draw_graph.py

Outputs:
    docs/architecture.mmd  — Mermaid source (always succeeds)
    docs/architecture.png  — PNG raster  (requires internet or graphviz)
    docs/architecture.svg  — SVG vector  (requires internet or graphviz)

The PNG/SVG are committed to the repo so evaluators can view them without
running this script.  Regenerate after changing graph.py or nodes.py.
"""
from __future__ import annotations

from pathlib import Path

from realestate_finder.graph import build_graph


def main():
    output_dir = Path("docs")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build the graph without a checkpointer — we only need the structure.
    graph = build_graph().compile()
    graph_image = graph.get_graph()

    # Always write the Mermaid text source (no dependencies needed).
    mermaid = graph_image.draw_mermaid()
    (output_dir / "architecture.mmd").write_text(mermaid, encoding="utf-8")
    print("Wrote docs/architecture.mmd")

    # Try PNG first via graphviz (draw_png), fall back to Mermaid.ink API.
    try:
        png_bytes = graph_image.draw_png()
        (output_dir / "architecture.png").write_bytes(png_bytes)
        print("Wrote docs/architecture.png  (via graphviz draw_png)")
    except Exception:
        try:
            png_bytes = graph_image.draw_mermaid_png()
            (output_dir / "architecture.png").write_bytes(png_bytes)
            print("Wrote docs/architecture.png  (via mermaid.ink)")
        except Exception as exc:
            print(f"Could not render PNG: {exc}  — docs/architecture.mmd is the fallback.")

    # Try SVG via graphviz, fall back to Mermaid.ink SVG.
    try:
        svg_bytes = graph_image.draw_mermaid_png(output_file_path=None)
        # draw_mermaid() already gave us the SVG-compatible mermaid text; for
        # true SVG we use mermaid.ink with the /svg endpoint via requests.
        import urllib.request
        import urllib.parse
        import base64

        encoded = base64.urlsafe_b64encode(mermaid.encode()).decode()
        url = f"https://mermaid.ink/svg/{encoded}"
        req = urllib.request.Request(url, headers={"User-Agent": "draw_graph.py/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            svg_data = resp.read()
        (output_dir / "architecture.svg").write_bytes(svg_data)
        print("Wrote docs/architecture.svg  (via mermaid.ink)")
    except Exception as exc:
        print(f"Could not render SVG: {exc}")


if __name__ == "__main__":
    main()

