"""Data model: every relation must carry its source and a confidence score.

Last edited: 2026-11-02: two optional fields on Relation. `role` says what a belongs_to edge
means (author / contributor / movement / member / award / participant / part_of; required for
belongs_to, forbidden elsewhere), because 64% of formal edges were belongs_to and an agent
could not tell authorship from an award. `year` is the year the relation holds (publication,
award, exhibition, joining), filled by data_io.year_from_claim when the claim states one year.
2026-10-27: English docstrings; added KIND_VERB_ZH (shared display labels for the 11 relation
kinds, previously duplicated in recommend/build_viewer).

Only Pydantic is used for validation; no agent framework is needed at this scale.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

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

# What a belongs_to edge means (source → target). Seven roles cover the whole dataset.
Role = Literal[
    "author",        # work → person: the work is by this person
    "contributor",   # person/work → anthology, journal, series: included or published in it
    "movement",      # person/work/group → concept: belongs to this movement or genre
    "member",        # person → group, agency, magazine, school: member, staff, student
    "award",         # person/work → award: won it
    "participant",   # person/work → exhibition or event: took part
    "part_of",       # exhibition/journal/institution → institution: hosted, published or run by it
]
ROLE_VERB_ZH: dict[str, str] = {
    "author": "作者是", "contributor": "收錄於", "movement": "屬於流派", "member": "成員於",
    "award": "獲獎", "participant": "參與", "part_of": "隸屬於",
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
    role: Optional[Role] = None            # only for belongs_to (see Role)
    year: Optional[int] = Field(default=None, ge=1500, le=2100)   # year the relation holds, when the claim states one

    @model_validator(mode="after")
    def role_matches_kind(self) -> "Relation":
        if self.kind == "belongs_to" and self.role is None:
            raise ValueError("belongs_to needs a role")
        if self.kind != "belongs_to" and self.role is not None:
            raise ValueError(f"role is only for belongs_to, not {self.kind}")
        return self
