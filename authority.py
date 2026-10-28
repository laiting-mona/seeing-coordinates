"""Authority weighting: how a relation gets its confidence score and its route.

Last edited: 2026-10-27 — English docstrings; no logic change.

Photography discourse has no citation graph, so authority is approximated with
three checkable signals: source tier, number of corroborating sources, and how
directly the source states the relation. Kept as one simple formula so it can be
explained in a report and audited line by line.
"""

TIER_BASE = {"primary": 0.85, "institution": 0.75, "critic": 0.6, "popular": 0.30, "other": 0.4}
AUTO_THRESHOLD = 0.7   # confidence >= AUTO_THRESHOLD enters the graph automatically
AUTO = AUTO_THRESHOLD  # backward-compatible alias

DIRECTNESS_EXPLICIT = 1.0   # the source states the relation outright
DIRECTNESS_IMPLIED = 0.7    # the relation follows from context
DIRECTNESS_INTERPRETED = 0.5  # the relation is a reading, not a statement


def auto_confidence(tier: str, n_sources: int = 1, directness: float = DIRECTNESS_EXPLICIT) -> float:
    """Score a relation.

    Inputs: source tier, number of independent sources, directness (1.0 / 0.7 / 0.5).
    Output: confidence in [0, 1] = min(1, tier_base + 0.1 * (n_sources - 1)) * directness.
    """
    base = TIER_BASE.get(tier, TIER_BASE["other"])
    corroboration_bonus = 0.1 * max(0, n_sources - 1)
    return round(min(1.0, base + corroboration_bonus) * directness, 2)


def route(confidence: float) -> str:
    """Return 'auto' when the score clears the threshold, else 'review' (human queue)."""
    return "auto" if confidence >= AUTO_THRESHOLD else "review"
