"""Canonical Event schema. Versioned contract every pipeline stage reads/writes."""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0"


class EventStatus(str, Enum):
    INGESTED = "ingested"
    PARSED = "parsed"
    SCORED = "scored"
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


class EntityRole(str, Enum):
    LOCATION = "location"
    ACTOR = "actor"
    OBJECT = "object"
    OTHER = "other"


class WriteLane(str, Enum):
    """Hybrid write model: which lane an event takes when published.

    SAFE_AUTO: source/reference statements added to existing event items.
    REVIEW: new-item minting or attachment to politically-sensitive items;
            requires Discord /approve before any write.
    """
    SAFE_AUTO = "safe_auto"
    REVIEW = "review"


class Source(BaseModel):
    page: str = "Portal:Current_events"
    rev_id: int
    section_date: date
    section_topic: str
    section_anchor: str


class LinkedEntity(BaseModel):
    surface: str
    wikipedia_title: Optional[str] = None
    wikidata_qid: Optional[str] = None
    role: EntityRole = EntityRole.OTHER
    confidence: float = 1.0


class Citation(BaseModel):
    url: str
    domain: str
    ref_name: Optional[str] = None
    publisher_qid: Optional[str] = None
    retrieved: datetime


class StatementProposal(BaseModel):
    """Pre-mapped Wikidata statement; value populated before write, IDs filled after."""
    property: str
    value: Optional[str]
    label: str
    qualifiers: list[dict] = Field(default_factory=list)
    references: list[dict] = Field(default_factory=list)


class WikidataProposal(BaseModel):
    primary_item: Optional[str] = None
    target_qid: Optional[str] = None
    statements: list[StatementProposal] = Field(default_factory=list)


class ScoreComponents(BaseModel):
    heuristic: Optional[float] = None
    llm: Optional[float] = None
    model: Optional[str] = None
    rubric_version: Optional[str] = None


class Review(BaseModel):
    operator: Optional[str] = None
    decision_at: Optional[datetime] = None
    notes: Optional[str] = None


class PublishMeta(BaseModel):
    attempts: int = 0
    last_error: Optional[str] = None
    wikidata_revisions: list[dict] = Field(default_factory=list)


class Timestamps(BaseModel):
    ingested_at: datetime
    parsed_at: Optional[datetime] = None
    scored_at: Optional[datetime] = None
    published_at: Optional[datetime] = None


class Event(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    schema_version: str = SCHEMA_VERSION
    event_id: str
    source: Source
    headline: str
    body: str
    topic_category: str
    linked_entities: list[LinkedEntity] = Field(default_factory=list)
    sources: list[Citation] = Field(default_factory=list)
    wikidata_proposal: WikidataProposal = Field(default_factory=WikidataProposal)
    score: Optional[float] = None
    score_rationale: Optional[str] = None
    score_components: ScoreComponents = Field(default_factory=ScoreComponents)
    status: EventStatus = EventStatus.INGESTED
    write_lane: Optional[WriteLane] = None
    review: Review = Field(default_factory=Review)
    publish: PublishMeta = Field(default_factory=PublishMeta)
    timestamps: Timestamps


# Portal section heading -> internal controlled-vocab category. Drives per-category
# BRFA gating. Add new mappings here before parser will accept new sections.
TOPIC_CATEGORIES: dict[str, str] = {
    "Armed conflicts and attacks": "armed_conflict",
    "Arts and culture": "arts_culture",
    "Business and economy": "business",
    "Disasters and accidents": "disaster",
    "Health and environment": "health",
    "International relations": "politics",
    "Law and crime": "law_crime",
    "Politics and elections": "politics",
    "Science and technology": "science",
    "Sports": "sports",
}

# v1 BRFA scope. Anything outside this set must stay in the REVIEW lane until
# an amended BRFA is approved for that category.
V1_BRFA_CATEGORIES: frozenset[str] = frozenset({"disaster", "sports"})


# Wikidata property mapping. Pre-mapped here so writer doesn't hardcode magic numbers.
P_INSTANCE_OF = "P31"
P_POINT_IN_TIME = "P585"
P_LOCATION = "P276"
P_COUNTRY = "P17"
P_PART_OF = "P361"
P_TITLE = "P1476"
P_DESCRIBED_BY_SOURCE = "P1343"
P_STATED_IN = "P248"
P_REFERENCE_URL = "P854"
P_RETRIEVED = "P813"
P_QUOTATION = "P1683"

Q_EVENT = "Q1656682"
