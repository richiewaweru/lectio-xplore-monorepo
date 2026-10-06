"""``flow``: boxes and arrows for processes, decisions and loops.

Layout is deterministic and graph-library free: nodes get layers by longest
path (loop edges found by DFS are set aside), layers run top to bottom or left
to right, and loop edges are routed through a channel outside every box.
"""

from __future__ import annotations

from dataclasses import dataclass

from matplotlib.artist import Artist
from matplotlib.figure import Figure
from matplotlib.text import Text

from media.render.contracts import FlowSpec, RenderSpecError
from media.render.families import _nodes as n
from media.render.layout import fit_labels
from media.render.style import INK

_FLOW_GAP = {"vertical": 0.75, "horizontal": 0.85}
_CROSS_GAP = 0.7
_CHANNEL = 0.5
_CHANNEL_STEP = 0.4
_PAD = 0.3
_ALIGN_TOL = 0.05


# --- validation ---------------------------------------------------------------


def validate(spec: FlowSpec) -> list[RenderSpecError]:
    errors: list[RenderSpecError] = []
    ids: dict[str, int] = {}
    for i, node in enumerate(spec.nodes):
        if node.id in ids:
            errors.append(
                RenderSpecError("duplicate_node_id", f"nodes[{i}].id", f"id {node.id!r} is used twice")
            )
        ids.setdefault(node.id, i)
        width = n.DECISION_WRAP if node.kind == "decision" else n.STEP_WRAP
        if not n.fits(node.text, width):
            errors.append(
                RenderSpecError(
                    "node_text_too_long",
                    f"nodes[{i}].text",
                    f"{node.text!r} needs more than {n.MAX_LINES} lines in a box; shorten it to "
                    f"about {width * n.MAX_LINES - 6} characters or fewer",
                )
            )
    valid: list[int] = []
    seen: set[tuple[str, str]] = set()
    for k, edge in enumerate(spec.edges):
        ok = True
        for field in ("start", "end"):
            if getattr(edge, field) not in ids:
                errors.append(
                    RenderSpecError(
                        "unknown_node",
                        f"edges[{k}].{field}",
                        f"{getattr(edge, field)!r} is not a node id; ids are {sorted(ids)}",
                    )
                )
                ok = False
        if not ok:
            continue
        if edge.start == edge.end:
            errors.append(
                RenderSpecError("self_loop", f"edges[{k}]", "an edge cannot start and end at the same node")
            )
            continue
        if (edge.start, edge.end) in seen:
            errors.append(
                RenderSpecError(
                    "duplicate_edge", f"edges[{k}]", f"edge {edge.start} -> {edge.end} is listed twice"
                )
            )
            continue
        seen.add((edge.start, edge.end))
        valid.append(k)
    adjacency: dict[str, list[str]] = {node.id: [] for node in spec.nodes}
    for k in valid:
        adjacency[spec.edges[k].start].append(spec.edges[k].end)
    reached = {spec.nodes[0].id}
    stack = [spec.nodes[0].id]
    while stack:
        for nxt in adjacency[stack.pop()]:
            if nxt not in reached:
                reached.add(nxt)
                stack.append(nxt)
    for i, node in enumerate(spec.nodes):
        if node.id not in reached:
            errors.append(
                RenderSpecError(
                    "unreachable_node",
                    f"nodes[{i}]",
                    f"{node.id!r} cannot be reached from the first node {spec.nodes[0].id!r}; "
                    "add an edge into it",
                )
            )
    for i, node in enumerate(spec.nodes):
        if node.kind != "decision":
            continue
        outgoing = [k for k in valid if spec.edges[k].start == node.id]
        if len(outgoing) < 2:
            errors.append(
                RenderSpecError(
                    "decision_needs_labels",
                    f"nodes[{i}]",
                    f"decision {node.id!r} needs at least 2 outgoing edges labelled such as "
                    "'Yes' and 'No'",
                )
            )
        for k in outgoing:
            if not spec.edges[k].label:
                errors.append(
                    RenderSpecError(
                        "decision_needs_labels",
                        f"edges[{k}].label",
                        f"edge out of decision {node.id!r} needs a label such as 'Yes' or 'No'",
                    )
                )
    return errors


# --- layers ---------------------------------------------------------------------


def edge_classes(spec: FlowSpec) -> tuple[dict[str, int], set[int]]:
    """Layer of every node (longest path from the first) and the loop-edge indexes."""
    ids = [node.id for node in spec.nodes]
    out: dict[str, list[tuple[int, str]]] = {i: [] for i in ids}
    for k, edge in enumerate(spec.edges):
        if edge.start in out and edge.end in out:
            out[edge.start].append((k, edge.end))
    state: dict[str, int] = {}
    back: set[int] = set()
    post: list[str] = []

    def visit(u: str) -> None:
        state[u] = 1
        for k, v in out[u]:
            if state.get(v) == 1:
                back.add(k)
            elif v not in state:
                visit(v)
        state[u] = 2
        post.append(u)

    for root in ids:
        if root not in state:
            visit(root)
    layers = {i: 0 for i in ids}
    for u in reversed(post):
        for k, v in out[u]:
            if k not in back:
                layers[v] = max(layers[v], layers[u] + 1)
    return layers, back


# --- layout -----------------------------------------------------------------------


@dataclass(frozen=True)
class _Label:
    text: str
    x: float
    y: float
    ha: str
    va: str


@dataclass(frozen=True)
class _Route:
    points: list[n.Pt]
    label: _Label | None


@dataclass(frozen=True)
class _Plan:
    centers: dict[str, n.Pt]
    sizes: dict[str, n.Pt]
    lines: dict[str, list[str]]
    routes: list[_Route]
    bounds: tuple[float, float, float, float]


def _plan(spec: FlowSpec) -> _Plan:
    vertical = spec.direction == "vertical"
    fv: n.Pt = (0.0, -1.0) if vertical else (1.0, 0.0)  # flow axis
    cv: n.Pt = (1.0, 0.0) if vertical else (0.0, -1.0)  # cross axis

    def xy(a: float, c: float) -> n.Pt:
        return a * fv[0] + c * cv[0], a * fv[1] + c * cv[1]

    kinds = {node.id: node.kind for node in spec.nodes}
    plain = [nd for nd in spec.nodes if nd.kind != "decision"]
    decisions = [nd for nd in spec.nodes if nd.kind == "decision"]
    step_width = n.choose_width([nd.text for nd in plain], (16,) if vertical else (12, 14, 16))
    dec_width = n.choose_width([nd.text for nd in decisions], (11, 13, 15))
    lines = {
        nd.id: n.wrap_lines(nd.text, dec_width if nd.kind == "decision" else step_width)
        for nd in spec.nodes
    }
    blocks = {nd.id: n.text_size(lines[nd.id]) for nd in spec.nodes}
    step_size = n.box_size("step", [blocks[nd.id] for nd in plain]) if plain else (0.0, 0.0)
    if any(nd.kind == "terminal" for nd in spec.nodes):
        terminal_size = n.box_size("terminal", [blocks[nd.id] for nd in plain])
        step_size = (max(step_size[0], terminal_size[0]), step_size[1])
    dec_size = n.box_size("decision", [blocks[nd.id] for nd in decisions]) if decisions else (0.0, 0.0)
    sizes = {nd.id: dec_size if nd.kind == "decision" else step_size for nd in spec.nodes}

    def ext_a(i: str) -> float:
        return abs(fv[0]) * sizes[i][0] + abs(fv[1]) * sizes[i][1]

    def ext_c(i: str) -> float:
        return abs(cv[0]) * sizes[i][0] + abs(cv[1]) * sizes[i][1]

    layer_of, back = edge_classes(spec)
    forward_in: dict[str, list[tuple[int, str]]] = {nd.id: [] for nd in spec.nodes}
    for k, edge in enumerate(spec.edges):
        if k not in back and edge.start in forward_in and edge.end in forward_in:
            forward_in[edge.end].append((k, edge.start))

    depth = max(layer_of.values()) + 1
    index = {nd.id: i for i, nd in enumerate(spec.nodes)}
    cross: dict[str, float] = {}
    members: list[list[str]] = []
    for layer in range(depth):
        ids = [nd.id for nd in spec.nodes if layer_of[nd.id] == layer]

        def key(i: str) -> tuple[float, float, int]:
            preds = forward_in[i]
            if not preds:
                return (0.0, float("inf"), index[i])
            mean = sum(cross[u] for _, u in preds) / len(preds)
            return (round(mean, 6), float(min(k for k, _ in preds)), index[i])

        ids.sort(key=key)
        spacing = max(ext_c(i) for i in ids) + _CROSS_GAP
        for i in ids:
            for _, u in forward_in[i]:
                if kinds[u] == "decision" and len(ids) > 1:
                    spacing = max(spacing, ext_c(u) + 1.5)
        for slot, i in enumerate(ids):
            cross[i] = (slot - (len(ids) - 1) / 2) * spacing
        members.append(ids)

    flow_pos: dict[str, float] = {}
    cursor = 0.0
    previous = 0.0
    for layer, ids in enumerate(members):
        extent = max(ext_a(i) for i in ids)
        if layer == 0:
            cursor = extent / 2
        else:
            cursor += previous / 2 + _FLOW_GAP[spec.direction] + extent / 2
        previous = extent
        for i in ids:
            flow_pos[i] = cursor
    centers = {i: xy(flow_pos[i], cross[i]) for i in flow_pos}

    def exit_point(i: str, d: n.Pt) -> n.Pt:
        cx, cy = centers[i]
        return cx + d[0] * sizes[i][0] / 2, cy + d[1] * sizes[i][1] / 2

    def anchor(p: n.Pt, d: n.Pt) -> tuple[float, float, str, str]:
        if d[0] != 0:
            return p[0] + d[0] * 0.1, p[1] + 0.06, "left" if d[0] > 0 else "right", "bottom"
        return p[0] + 0.1, p[1] + d[1] * 0.18, "left", "center"

    def unit(p: n.Pt, q: n.Pt) -> n.Pt:
        dx, dy = q[0] - p[0], q[1] - p[1]
        length = max(abs(dx), abs(dy)) or 1.0
        return dx / length, dy / length

    extreme = {s: max(s * cross[i] + ext_c(i) / 2 for i in cross) for s in (1.0, -1.0)}
    used = {1.0: 0, -1.0: 0}
    default_side = 1.0 if vertical else -1.0
    routes: list[_Route] = []
    for k, edge in enumerate(spec.edges):
        if edge.start not in centers or edge.end not in centers:
            continue
        u, v = edge.start, edge.end
        label: _Label | None = None
        if k in back:

            def blocked(s: float, u: str = u, v: str = v) -> int:
                count = 0
                for end in (u, v):
                    for i in members[layer_of[end]]:
                        if i != end and s * (cross[i] - cross[end]) > 0:
                            count += 1
                return count

            side = min((default_side, -default_side), key=lambda s: (blocked(s), s != default_side))
            channel = side * (extreme[side] + _CHANNEL + _CHANNEL_STEP * used[side])
            used[side] += 1
            bc = (side * cv[0], side * cv[1])
            a_u, a_v = flow_pos[u], flow_pos[v]
            c_u = cross[u] + side * ext_c(u) / 2
            c_v = cross[v] + side * ext_c(v) / 2
            points = [xy(a_u, c_u), xy(a_u, channel), xy(a_v, channel), xy(a_v, c_v)]
            if edge.label:
                mid = ((points[1][0] + points[2][0]) / 2, (points[1][1] + points[2][1]) / 2)
                if bc[0] != 0:  # channel is a vertical line: the label sits outside it
                    ha = "left" if bc[0] > 0 else "right"
                    label = _Label(edge.label, mid[0] + bc[0] * 0.1, mid[1], ha, "center")
                else:
                    va = "bottom" if bc[1] > 0 else "top"
                    label = _Label(edge.label, mid[0], mid[1] + bc[1] * 0.08, "center", va)
            routes.append(_Route(points, label))
            continue
        start = exit_point(u, fv)
        end = exit_point(v, (-fv[0], -fv[1]))
        offset = cross[v] - cross[u]
        if abs(offset) < _ALIGN_TOL:
            points = [start, end]
        elif kinds[u] == "decision":
            sc = 1.0 if offset > 0 else -1.0
            s_pt = exit_point(u, (sc * cv[0], sc * cv[1]))
            points = [s_pt, xy(flow_pos[u], cross[v]), end]
        else:
            a_s = start[0] * fv[0] + start[1] * fv[1]
            mid_a = a_s + _FLOW_GAP[spec.direction] / 2
            points = [start, xy(mid_a, cross[u]), xy(mid_a, cross[v]), end]
        if edge.label:
            lx, ly, ha, va = anchor(points[0], unit(points[0], points[1]))
            label = _Label(edge.label, lx, ly, ha, va)
        routes.append(_Route(points, label))

    xs: list[float] = []
    ys: list[float] = []
    for i, (cx, cy) in centers.items():
        xs += [cx - sizes[i][0] / 2, cx + sizes[i][0] / 2]
        ys += [cy - sizes[i][1] / 2, cy + sizes[i][1] / 2]
    for route in routes:
        xs += [p[0] for p in route.points]
        ys += [p[1] for p in route.points]
        if route.label:
            lab = route.label
            w, h = n.text_size([lab.text])
            x0 = lab.x if lab.ha == "left" else lab.x - w if lab.ha == "right" else lab.x - w / 2
            y0 = lab.y if lab.va == "bottom" else lab.y - h if lab.va == "top" else lab.y - h / 2
            xs += [x0, x0 + w]
            ys += [y0, y0 + h]
    bounds = (min(xs) - _PAD, max(xs) + _PAD, min(ys) - _PAD, max(ys) + _PAD)
    return _Plan(centers, sizes, lines, routes, bounds)


def draw(spec: FlowSpec) -> Figure:
    plan = _plan(spec)
    x0, x1, y0, y1 = plan.bounds

    def build(font_size: float) -> tuple[Figure, list[Text], list[Artist]]:
        fig = Figure(figsize=(x1 - x0, y1 - y0))
        ax = fig.add_axes((0, 0, 1, 1))
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        ax.axis("off")
        texts: list[Text] = []
        obstacles: list[Artist] = []
        for node in spec.nodes:
            patch, text = n.add_node(
                ax,
                node.kind,
                plan.centers[node.id],
                plan.sizes[node.id],
                plan.lines[node.id],
                font_size,
            )
            texts.append(text)
            obstacles.append(patch)
        for route in plan.routes:
            obstacles.append(n.add_arrow(ax, route.points))
            if route.label:
                lab = route.label
                texts.append(
                    ax.text(
                        lab.x, lab.y, lab.text, ha=lab.ha, va=lab.va, fontsize=font_size, color=INK, zorder=5
                    )
                )
        return fig, texts, obstacles

    return fit_labels(build)


def describe(spec: FlowSpec) -> str:
    text = {node.id: node.text for node in spec.nodes}
    outs: dict[str, int] = {}
    for edge in spec.edges:
        outs[edge.start] = outs.get(edge.start, 0) + 1
    chain = [spec.nodes[0].id]
    while True:
        nxt = [e.end for e in spec.edges if e.start == chain[-1] and e.end not in chain]
        if len(nxt) != 1 or outs.get(chain[-1], 0) != 1:
            break
        chain.append(nxt[0])
    count = len(spec.nodes)
    if len(chain) == count and len(spec.edges) == count - 1:
        return f"Flow of {count} steps: " + " → ".join(text[i] for i in chain) + "."
    parts = []
    for edge in spec.edges:
        arrow = f" —{edge.label}→ " if edge.label else " → "
        if edge.start in text and edge.end in text:
            parts.append(f"{text[edge.start]}{arrow}{text[edge.end]}")
    return f"Flowchart of {count} boxes: " + "; ".join(parts) + "."


def numbers(spec: FlowSpec) -> list[float]:
    return []


# --- gallery ---------------------------------------------------------------------

GALLERY: dict[str, dict] = {
    "flow_linear": {
        "family": "flow",
        "direction": "vertical",
        "nodes": [
            {"id": "a", "text": "Gather the materials"},
            {"id": "b", "text": "Measure each ingredient"},
            {"id": "c", "text": "Mix in a large bowl"},
            {"id": "d", "text": "Bake for 30 minutes"},
            {"id": "e", "text": "Let it cool"},
        ],
        "edges": [
            {"start": "a", "end": "b"},
            {"start": "b", "end": "c"},
            {"start": "c", "end": "d"},
            {"start": "d", "end": "e"},
        ],
    },
    "flow_decision": {
        "family": "flow",
        "direction": "vertical",
        "nodes": [
            {"id": "start", "text": "Start", "kind": "terminal"},
            {"id": "even", "text": "Is the number even?", "kind": "decision"},
            {"id": "half", "text": "Divide by 2"},
            {"id": "triple", "text": "Multiply by 3, add 1"},
            {"id": "write", "text": "Write the result"},
            {"id": "end", "text": "End", "kind": "terminal"},
        ],
        "edges": [
            {"start": "start", "end": "even"},
            {"start": "even", "end": "half", "label": "Yes"},
            {"start": "even", "end": "triple", "label": "No"},
            {"start": "half", "end": "write"},
            {"start": "triple", "end": "write"},
            {"start": "write", "end": "end"},
        ],
    },
    "flow_loop": {
        "family": "flow",
        "direction": "horizontal",
        "nodes": [
            {"id": "plan", "text": "Plan"},
            {"id": "draft", "text": "Draft"},
            {"id": "review", "text": "Review"},
            {"id": "revise", "text": "Revise"},
        ],
        "edges": [
            {"start": "plan", "end": "draft"},
            {"start": "draft", "end": "review"},
            {"start": "review", "end": "revise"},
            {"start": "revise", "end": "draft", "label": "Repeat"},
        ],
    },
}

__all__ = ["GALLERY", "describe", "draw", "edge_classes", "numbers", "validate"]
