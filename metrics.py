"""Two monitoring metrics that decide when the agent should expand its sources.

Last edited: 2026-10-27 — English docstrings; repetition_rate simplified with set size.

Plain counting only; no analytics library is needed.
"""


def repetition_rate(recommended_ids: list[str]) -> float:
    """R = repeated recommendations / total recommendations (0 = no repeats)."""
    total = len(recommended_ids)
    if total == 0:
        return 0.0
    repeats = total - len(set(recommended_ids))
    return round(repeats / total, 3)


def coverage(recommended_ids: list[str], all_node_ids: list[str]) -> float:
    """C = distinct nodes ever recommended / all nodes (detects recommendations circling a small cluster)."""
    universe = set(all_node_ids)
    if not universe:
        return 0.0
    return round(len(set(recommended_ids) & universe) / len(universe), 3)


def should_expand(repetition: float, frontier_size: int, repetition_threshold: float = 0.4) -> bool:
    """Trigger source expansion when repetition is high or the frontier is empty."""
    return repetition > repetition_threshold or frontier_size == 0
