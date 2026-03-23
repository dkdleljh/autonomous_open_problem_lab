from __future__ import annotations

from collections import defaultdict, deque


def _adjacency(edges: list[tuple[str, str]]) -> dict[str, list[str]]:
    adj: dict[str, list[str]] = defaultdict(list)
    for src, dst in edges:
        adj[src].append(dst)
    return adj


def has_path(start: str, target: str, edges: list[tuple[str, str]]) -> bool:
    if start == target:
        return True
    adj = _adjacency(edges)
    queue = deque([start])
    seen: set[str] = {start}
    while queue:
        node = queue.popleft()
        for nxt in adj.get(node, []):
            if nxt == target:
                return True
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return False


def is_dag(nodes: list[str], edges: list[tuple[str, str]]) -> bool:
    adj = _adjacency(edges)
    color: dict[str, int] = dict.fromkeys(nodes, 0)

    def dfs(node: str) -> bool:
        color[node] = 1
        for nxt in adj.get(node, []):
            if color.get(nxt, 0) == 1:
                return False
            if color.get(nxt, 0) == 0 and not dfs(nxt):
                return False
        color[node] = 2
        return True

    for node in nodes:
        if color.get(node, 0) == 0 and not dfs(node):
            return False
    return True
