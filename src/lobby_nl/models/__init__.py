"""Core Pydantic data models for the OSINT research pipeline.

All models enforce:
- Every actor must have at least one source_id.
- Every claim must have a source_id.
- Every relationship must have a source_id.
- Every source must have access_date and (optionally) content_hash.
- No person included from identity alone.
- No organization classified from identity alone.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ActorCategory(str, Enum):
    pro_israel_org = "pro_israel_org"
    christian_zionist_org = "christian_zionist_org"
    jewish_civic_org = "jewish_civic_org"
    israeli_diplomatic_channel = "israeli_diplomatic_channel"
    antisemitism_policy_infrastructure = "antisemitism_policy_infrastructure"
    parliamentary_actor = "parliamentary_actor"
    palestine_rights_counter_lobby = "palestine_rights_counter_lobby"
    eu_register_actor = "eu_register_actor"
    media_actor = "media_actor"
    alternative_media_actor = "alternative_media_actor"
    journalist_actor = "journalist_actor"
    influencer_actor = "influencer_actor"
    talkshow_or_program_actor = "talkshow_or_program_actor"
    podcast_actor = "podcast_actor"
    newsletter_actor = "newsletter_actor"
    party_actor = "party_actor"
    senate_actor = "senate_actor"
    house_actor = "house_actor"
    committee_actor = "committee_actor"
    government_actor = "government_actor"
    ministry_actor = "ministry_actor"
    municipal_actor = "municipal_actor"
    mayor_actor = "mayor_actor"
    police_actor = "police_actor"
    security_actor = "security_actor"
    public_broadcaster_actor = "public_broadcaster_actor"
    academic_actor = "academic_actor"
    think_tank_actor = "think_tank_actor"
    education_actor = "education_actor"
    research_actor = "research_actor"
    funding_actor = "funding_actor"
    donor_actor = "donor_actor"
    pr_or_consultancy_actor = "pr_or_consultancy_actor"
    law_firm_actor = "law_firm_actor"
    event_platform_actor = "event_platform_actor"
    celebrity_actor = "celebrity_actor"
    religious_actor = "religious_actor"
    diaspora_actor = "diaspora_actor"
    archive_actor = "archive_actor"
    social_platform_actor = "social_platform_actor"
    campaign_actor = "campaign_actor"
    presenter_actor = "presenter_actor"
    newsletter_author_actor = "newsletter_author_actor"
    opining_activist_actor = "opining_activist_actor"
    media_framing_actor = "media_framing_actor"
    department_actor = "department_actor"
    implementation_org_actor = "implementation_org_actor"
    nctv_actor = "nctv_actor"
    semi_government_actor = "semi_government_actor"
    speaker_event_actor = "speaker_event_actor"
    researcher_actor = "researcher_actor"
    consultant_advisor_actor = "consultant_advisor_actor"
    expert_media_guest_actor = "expert_media_guest_actor"
    sponsor_actor = "sponsor_actor"
    grantmaker_actor = "grantmaker_actor"
    foundation_actor = "foundation_actor"
    lobbying_firm_actor = "lobbying_firm_actor"
    pr_firm_actor = "pr_firm_actor"
    event_organizer_actor = "event_organizer_actor"
    venue_actor = "venue_actor"
    platform_actor = "platform_actor"
    unknown = "unknown"


class EvidenceType(str, Enum):
    legal_evidence = "legal_evidence"
    documentary_evidence = "documentary_evidence"
    registry_evidence = "registry_evidence"
    parliamentary_evidence = "parliamentary_evidence"
    osint_evidence = "osint_evidence"
    behavioral_pattern_evidence = "behavioral_pattern_evidence"
    network_evidence = "network_evidence"
    financial_trace_evidence = "financial_trace_evidence"
    institutional_interaction_evidence = "institutional_interaction_evidence"
    media_framing_evidence = "media_framing_evidence"
    event_evidence = "event_evidence"
    archival_evidence = "archival_evidence"
    weak_associative_evidence = "weak_associative_evidence"


class EvidenceStrength(str, Enum):
    hard = "hard"
    strong = "strong"
    medium = "medium"
    light = "light"
    weak = "weak"


class CertaintyLevel(str, Enum):
    fact = "fact"
    interpretation = "interpretation"
    hypothesis = "hypothesis"
    uncertainty = "uncertainty"
    missingness = "missingness"
    opacity_risk = "opacity_risk"
    exclusion = "exclusion"


class RelationshipType(str, Enum):
    member_of = "member_of"
    affiliated_with = "affiliated_with"
    funded_by = "funded_by"
    funds = "funds"
    lobbies = "lobbies"
    lobbied_by = "lobbied_by"
    represents = "represents"
    represented_by = "represented_by"
    works_with = "works_with"
    collaborates = "collaborates"
    employed_by = "employed_by"
    employs = "employs"
    advises = "advises"
    advised_by = "advised_by"
    speaks_at = "speaks_at"
    hosted_by = "hosted_by"
    attended_by = "attended_by"
    co_signed = "co_signed"
    cited_by = "cited_by"
    amplifies = "amplifies"
    amplified_by = "amplified_by"
    opposes = "opposes"
    opposed_by = "opposed_by"
    diplomatic_relation = "diplomatic_relation"
    parliamentary_relation = "parliamentary_relation"
    media_relation = "media_relation"
    social_media_relation = "social_media_relation"
    funding_relation = "funding_relation"
    event_relation = "event_relation"
    unknown = "unknown"


class OpacityMechanism(str, Enum):
    hard_to_trace_funding = "hard_to_trace_funding"
    intermediary_structures = "intermediary_structures"
    cross_border_offshore = "cross_border_offshore"
    link_rot = "link_rot"
    source_removal = "source_removal"
    archive_disappearance = "archive_disappearance"
    stale_documents = "stale_documents"
    document_ageing = "document_ageing"
    legal_complexity_delay = "legal_complexity_delay"
    reputational_pressure = "reputational_pressure"
    delegitimization_patterns = "delegitimization_patterns"
    conflicting_information = "conflicting_information"
    source_contradiction = "source_contradiction"
    disinformation_indicators = "disinformation_indicators"
    media_framing_asymmetry = "media_framing_asymmetry"
    institutional_non_response = "institutional_non_response"
    partial_disclosure = "partial_disclosure"


class InclusionType(str, Enum):
    structural = "structural"
    source_backed = "source_backed"


# ---------------------------------------------------------------------------
# Source
# ---------------------------------------------------------------------------

class Source(BaseModel):
    source_id: str = Field(default_factory=lambda: f"src_{uuid.uuid4().hex[:12]}")
    url: str
    title: str = ""
    source_type: str = "web"
    access_date: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    content_hash: Optional[str] = None
    content_text: str = ""
    content_markdown: str = ""
    extraction_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    archive_url: Optional[str] = None
    archive_available: bool = False
    is_dead: bool = False
    is_stale: bool = False
    is_redirected: bool = False
    redirect_url: Optional[str] = None
    is_changed: bool = False
    language: str = "nl"
    metadata: dict[str, Any] = Field(default_factory=dict)
    notes: str = ""

    @field_validator("url")
    @classmethod
    def url_must_be_valid(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    def compute_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Actor
# ---------------------------------------------------------------------------

class Actor(BaseModel):
    actor_id: str = Field(default_factory=lambda: f"act_{uuid.uuid4().hex[:12]}")
    name: str
    name_aliases: list[str] = Field(default_factory=list)
    category: ActorCategory = ActorCategory.unknown
    subcategories: list[ActorCategory] = Field(default_factory=list)
    description: str = ""
    country: str = "NL"
    countries_active: list[str] = Field(default_factory=lambda: ["NL"])
    organization: Optional[str] = None
    role: str = ""
    public_function: str = ""
    source_ids: list[str] = Field(default_factory=list)
    event_ids: list[str] = Field(default_factory=list)
    relationship_count: int = 0
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    certainty: CertaintyLevel = CertaintyLevel.fact
    inclusion_rationale: str = ""
    inclusion_type: InclusionType = InclusionType.source_backed
    is_person: bool = False
    is_organization: bool = True
    is_dutch: bool = True
    is_active: bool = True
    first_seen: str = ""
    last_seen: str = ""
    twitter_handle: str = ""
    linkedin_url: str = ""
    website: str = ""
    notes: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_source_backing(self) -> "Actor":
        if not self.source_ids:
            self.certainty = CertaintyLevel.missingness
            self.inclusion_rationale = self.inclusion_rationale or "NO_SOURCE_BACKING"
        return self

    @model_validator(mode="after")
    def prevent_identity_classification(self) -> "Actor":
        if self.category in (ActorCategory.jewish_civic_org, ActorCategory.pro_israel_org):
            if self.inclusion_type == InclusionType.structural:
                raise ValueError(
                    "Cannot auto-classify Jewish civic or pro-Israel org from identity alone"
                )
        return self


# ---------------------------------------------------------------------------
# Claim
# ---------------------------------------------------------------------------

class Claim(BaseModel):
    claim_id: str = Field(default_factory=lambda: f"clm_{uuid.uuid4().hex[:12]}")
    actor_id: str
    claim_text: str
    claim_type: str = "statement"
    source_id: str
    source_ids: list[str] = Field(default_factory=list)
    event_id: Optional[str] = None
    date: str = ""
    topic: str = ""
    topics: list[str] = Field(default_factory=list)
    stance: str = ""
    evidence_type: EvidenceType = EvidenceType.osint_evidence
    evidence_strength: EvidenceStrength = EvidenceStrength.medium
    certainty: CertaintyLevel = CertaintyLevel.fact
    language: str = "nl"
    url: str = ""
    context: str = ""
    notes: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_source(self) -> "Claim":
        if not self.source_id:
            raise ValueError("Every claim must have a source_id")
        return self


# ---------------------------------------------------------------------------
# Relationship
# ---------------------------------------------------------------------------

class Relationship(BaseModel):
    relationship_id: str = Field(default_factory=lambda: f"rel_{uuid.uuid4().hex[:12]}")
    actor_a_id: str
    actor_b_id: str
    relationship_type: RelationshipType = RelationshipType.unknown
    direction: str = "undirected"
    source_ids: list[str] = Field(default_factory=list)
    evidence_type: EvidenceType = EvidenceType.osint_evidence
    evidence_strength: EvidenceStrength = EvidenceStrength.medium
    certainty: CertaintyLevel = CertaintyLevel.fact
    first_seen: str = ""
    last_seen: str = ""
    weight: float = Field(default=1.0, ge=0.0, le=10.0)
    description: str = ""
    notes: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_source(self) -> "Relationship":
        if not self.source_ids:
            raise ValueError("Every relationship must have at least one source_id")
        return self


# ---------------------------------------------------------------------------
# Event
# ---------------------------------------------------------------------------

class Event(BaseModel):
    event_id: str = Field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    name: str
    event_type: str = ""
    date: str = ""
    end_date: str = ""
    location: str = ""
    city: str = ""
    country: str = "NL"
    organizer_id: Optional[str] = None
    organizer_name: str = ""
    venue_id: Optional[str] = None
    venue_name: str = ""
    participant_ids: list[str] = Field(default_factory=list)
    speaker_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    description: str = ""
    url: str = ""
    topics: list[str] = Field(default_factory=list)
    notes: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# ParliamentaryRecord
# ---------------------------------------------------------------------------

class ParliamentaryRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: f"par_{uuid.uuid4().hex[:12]}")
    chamber: str = ""
    document_type: str = ""
    title: str = ""
    date: str = ""
    document_number: str = ""
    url: str = ""
    source_ids: list[str] = Field(default_factory=list)
    actor_ids: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    motion_by: list[str] = Field(default_factory=list)
    submitter: list[str] = Field(default_factory=list)
    committee: str = ""
    status: str = ""
    text_excerpt: str = ""
    notes: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Signal models
# ---------------------------------------------------------------------------

class DataGap(BaseModel):
    gap_id: str = Field(default_factory=lambda: f"gap_{uuid.uuid4().hex[:12]}")
    gap_type: str = ""
    description: str
    affected_actor_ids: list[str] = Field(default_factory=list)
    affected_urls: list[str] = Field(default_factory=list)
    opacity_mechanisms: list[OpacityMechanism] = Field(default_factory=list)
    alternative_explanation: str = ""
    severity: str = "unknown"
    date_detected: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: str = ""


class OpacitySignal(BaseModel):
    signal_id: str = Field(default_factory=lambda: f"opq_{uuid.uuid4().hex[:12]}")
    signal_type: OpacityMechanism
    description: str
    actor_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    evidence_strength: EvidenceStrength = EvidenceStrength.light
    certainty: CertaintyLevel = CertaintyLevel.opacity_risk
    alternative_explanation: str = ""
    follow_up_target: bool = True
    date_detected: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: str = ""


class SourceConflict(BaseModel):
    conflict_id: str = Field(default_factory=lambda: f"cnf_{uuid.uuid4().hex[:12]}")
    source_a_id: str
    source_b_id: str
    description: str
    conflict_type: str = "contradiction"
    resolution: str = "unresolved"
    date_detected: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: str = ""


class Exclusion(BaseModel):
    exclusion_id: str = Field(default_factory=lambda: f"exc_{uuid.uuid4().hex[:12]}")
    entity_name: str
    exclusion_reason: str
    actor_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    date_excluded: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: str = ""
