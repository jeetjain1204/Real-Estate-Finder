from __future__ import annotations

from pathlib import Path

from realestate_finder.graph import build_graph


def main():
    output_dir = Path("docs")
    output_dir.mkdir(parents=True, exist_ok=True)
    graph = build_graph().compile()
    graph_image = graph.get_graph()

    mermaid = graph_image.draw_mermaid()
    (output_dir / "architecture.mmd").write_text(mermaid, encoding="utf-8")

    try:
        png_bytes = graph_image.draw_mermaid_png()
        (output_dir / "architecture.png").write_bytes(png_bytes)
        print("Wrote docs/architecture.png")
    except Exception as exc:
        print(f"Could not render PNG locally: {exc}")
        print("Wrote docs/architecture.mmd instead; install graph rendering dependencies or rerun with internet access.")


if __name__ == "__main__":
    main()

