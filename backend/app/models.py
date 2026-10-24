"""Pydantic schemas for case intake, rule results, the AI output contract and human decisions."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def aware(value):
    from datetime import timezone
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

ClaimedGround = Literal[
    "paid", "permit", "blue_badge", "loading", "signage", "medical_emergency", "breakdown", "other"
]
EvidenceType = Literal[
    "ceo_photo", "payment_receipt", "permit_record", "badge_record", "delivery_note",
    "signage_photo", "medical_letter", "breakdown_report", "correspondence", "other",
]


class EvidenceIn(BaseModel):
    id: str = Field(min_length=1, max_length=20, description="Case-local evidence id, e.g. E1")
    type: EvidenceType
    description: str = ""
    source: Literal["council", "motorist"] = "motorist"
    filename: str | None = None
    sha256: str | None = None
    size_bytes: int | None = None
    captured_at: datetime | None = None
    vrm_seen: str | None = None
    location_seen: str | None = None

    @field_validator("captured_at")
    @classmethod
    def normalise_time(cls, value):
        return aware(value) if value else value


class PaymentRecord(BaseModel):
    reference: str
    vrm: str
    zone: str
    start: datetime
    end: datetime

    @field_validator("start", "end")
    @classmethod
    def normalise_time(cls, value):
        return aware(value)


class PermitRecord(BaseModel):
    permit_id: str
    vrm: str
    zone: str
    valid_from: datetime
    valid_to: datetime
    displayed: bool | None = None

    @field_validator("valid_from", "valid_to")
    @classmethod
    def normalise_time(cls, value):
        return aware(value)


class BadgeRecord(BaseModel):
    badge_id: str
    valid_from: date
    valid_to: date
    displayed: bool | None = None


class CouncilRecords(BaseModel):
    """Records the council system supplied for this case. Absent list = not supplied, not 'none exist'."""
    payments: list[PaymentRecord] | None = None
    permits: list[PermitRecord] | None = None
    badges: list[BadgeRecord] | None = None


class CaseIn(BaseModel):
    pcn_ref: str = Field(min_length=1)
    vrm: str = Field(min_length=1, description="Synthetic vehicle registration mark")
    contravention_code: str
    contravention_datetime: datetime
    location: str = Field(min_length=1)
    zone: str | None = None
    notice_date: date
    representation_received_date: date
    representation_text: str = Field(min_length=1)
    claimed_grounds: list[ClaimedGround] = Field(default_factory=list)
    observation_minutes: int | None = None
    prior_undisplayed_permit_count: int = 0
    evidence: list[EvidenceIn] = Field(default_factory=list)
    records: CouncilRecords = Field(default_factory=CouncilRecords)
    synthetic: bool = True
    stage: Literal["informal", "formal"] = "informal"
    response_due_date: date | None = None

    @field_validator("contravention_datetime", mode="after")
    @classmethod
    def normalise_time(cls, value):
        return aware(value)


class ResolutionIn(BaseModel):
    outcome: Literal["accept", "reject", "needs_review"]
    review_id: int | None = None
    reason: str = Field(default="", max_length=2000)
    response: str = Field(default="", max_length=20000)
    reviewer: str = Field(min_length=1, max_length=100)


class ValidationIssue(BaseModel):
    code: str
    severity: Literal["error", "warning", "info"]
    message: str
    field: str | None = None


RuleStatus = Literal["pass", "fail", "not_applicable", "insufficient_data"]
RuleEffect = Literal["supports_accept", "supports_reject", "needs_review", "neutral"]


class RuleResult(BaseModel):
    rule_id: str
    ruleset_version: str
    status: RuleStatus
    effect: RuleEffect
    finding: str
    policy_refs: list[str] = Field(default_factory=list)


Recommendation = Literal["accept", "reject", "needs_review"]


class AIRecommendation(BaseModel):
    """The output contract requested from Mubit. 'accept' means accept the motorist's representation."""
    model_config = ConfigDict(extra="ignore")

    recommendation: Recommendation
    reason_summary: str = Field(min_length=1, max_length=2000)
    relevant_rule_references: list[str] = Field(default_factory=list)
    evidence_references: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    uncertainty_flags: list[str] = Field(default_factory=list)
    draft_response: str | None = None


DecisionAction = Literal["accept", "override", "reject", "escalate"]
FinalOutcome = Literal["representation_accepted", "representation_rejected", "escalated"]


class DecisionIn(BaseModel):
    """Reviewer action on the AI recommendation.

    accept   - adopt the AI recommendation as the outcome (reason optional)
    override - choose a different outcome and/or edit the draft (reason required)
    reject   - discard the AI recommendation entirely and decide manually (reason required)
    escalate - send for senior/manual investigation (reason required)
    """
    ai_review_id: int | None = None
    action: DecisionAction
    final_outcome: FinalOutcome | None = None
    reason_code: str | None = None
    reason: str | None = None
    final_response: str | None = None
    reviewer: str = Field(min_length=1)


class CurateIn(BaseModel):
    eligible: bool
    curator: str = Field(min_length=1)
    note: str | None = None
