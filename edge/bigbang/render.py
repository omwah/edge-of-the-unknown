"""Render a generated universe to a PNG, port sectors highlighted (DESIGN §5).

A dev-only inspector (mirroring ExchangeConflict's uniview). matplotlib and
networkx are imported lazily here and used only for layout/drawing, so the rest
of `bigbang` stays free of them. The layout is seeded for reproducible images.

Colour key: StarDock (gold) · Core Space (cyan) · trade port (magenta) ·
empty sector (grey). Edges are the warp graph.
"""

from __future__ import annotations

from pathlib import Path

from edge.core.enums import PortClass
from edge.core.models import UniverseState

_DOCK = "#ffcc00"
_CORE = "#00cccc"
_PORT = "#cc00cc"
_EMPTY = "#3a3a3a"


def render_graph(state: UniverseState, path: Path | str, *, layout_seed: int = 0) -> None:
    """Draw the warp graph to `path` (PNG), highlighting port/Core/StarDock sectors."""
    import matplotlib

    matplotlib.use("Agg")  # headless: no display needed
    import matplotlib.pyplot as plt
    import networkx as nx
    from matplotlib.lines import Line2D

    graph = nx.DiGraph()
    graph.add_nodes_from(state.sectors)
    for src, targets in state.adjacency.items():
        for dst in targets:
            graph.add_edge(src, dst)

    node_count = graph.number_of_nodes()
    pos = nx.spring_layout(graph, seed=layout_seed, k=1.5 / max(node_count, 1) ** 0.5)

    port_sectors = {p.sector_id for p in state.ports.values()}
    dock_sector = next(
        (p.sector_id for p in state.ports.values() if p.klass is PortClass.STARDOCK), None
    )
    core = {s.id for s in state.sectors.values() if s.is_galactic_core}

    node_size = max(6.0, 1200.0 / max(node_count, 1) ** 0.5)
    colors: list[str] = []
    for sector_id in graph.nodes():
        if sector_id == dock_sector:
            colors.append(_DOCK)
        elif sector_id in core:
            colors.append(_CORE)
        elif sector_id in port_sectors:
            colors.append(_PORT)
        else:
            colors.append(_EMPTY)

    side = max(8.0, node_count ** 0.5)
    fig, ax = plt.subplots(figsize=(side, side))
    fig.patch.set_facecolor("black")
    ax.set_facecolor("black")
    nx.draw_networkx_edges(graph, pos, ax=ax, edge_color="#555555", width=0.4, arrows=False, alpha=0.6)
    nx.draw_networkx_nodes(
        graph, pos, ax=ax, nodelist=list(graph.nodes()),
        node_color=colors, node_size=node_size, linewidths=0.0,
    )
    legend = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=_DOCK, markersize=9, label="StarDock"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=_CORE, markersize=9, label="Core Space"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=_PORT, markersize=9, label="trade port"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=_EMPTY, markersize=9, label="empty"),
    ]
    leg = ax.legend(handles=legend, loc="upper right", facecolor="black", labelcolor="white", framealpha=0.4)
    leg.get_frame().set_edgecolor("#555555")
    ax.set_title(
        f"Universe seed={state.game.seed} · {node_count} sectors · {len(state.ports)} ports",
        color="white",
    )
    ax.axis("off")
    fig.savefig(path, dpi=120, facecolor="black", bbox_inches="tight")
    plt.close(fig)
