"""Data model: every relation must carry its source and a confidence score.

Last edited: 2026-10-27 — English docstrings; added KIND_VERB_ZH (shared display
labels for the 11 relation kinds, previously duplicated in recommend/build_viewer).

Only Pydantic is used for validation; no agent framework is needed at this scale.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

# Source authority tiers, highest first. Weights live in authority.TIER_BASE.
Tier = Literal["primary", "institution", "critic", "popular", "other"]

# Relation kinds. The last five let one work grow many edges
# (translations, studies, reviews, interpretations, exhibitions).
Kind = Literal[
    "influence", "critique", "extend", "belongs_to", "contrast", "discusses",
    "translate", "study", "review", "interpret", "exhibit",
]

# Direction conventions (source → target):
#   work      --belongs_to--> person        authorship ("the work belongs to its author")
#   person    --belongs_to--> institution/event/concept/work   membership, participation, school, featured in a journal/anthology
#   event     --exhibit--> person/work      the exhibition shows the artist/work
#   translator/translation --translate--> original work
#   A --influence/critique/extend/contrast/discusses/study/review/interpret--> B   A acts on B

# Chinese verb shown for each kind in the viewer, recommender and query output.
KIND_VERB_ZH: dict[str, str] = {
    "influence": "影響了", "critique": "批判了", "extend": "延伸自", "belongs_to": "屬於",
    "contrast": "對照於", "discusses": "討論了", "translate": "翻譯了", "study": "研究了",
    "review": "評論了", "interpret": "詮釋了", "exhibit": "展出了",
}

EntityType = Literal["person", "work", "concept", "event", "institution"]
Status = Literal["auto", "review", "approved", "rejected"]


class Entity(BaseModel):
    """A node: person, work, concept, event or institution."""
    id: str
    type: EntityType
    name_zh: str
    name_en: Optional[str] = None
    label_pref: Literal["en", "zh_en", "zh"] = "en"   # see data_io.display_label


class Relation(BaseModel):
    """A directed, sourced edge between two entities."""
    source_id: str              # where the edge starts
    target_id: str              # where the edge ends
    kind: Kind
    claim: str                  # what the relation asserts
    evidence: str = ""          # quoted passage or verification note (with URL when web-verified)
    source_ref: str             # id in sources.csv
    source_tier: Tier
    confidence: float = Field(ge=0, le=1)
    status: Status = "review"   # auto / approved enter the graph; review is queued; rejected is excluded
