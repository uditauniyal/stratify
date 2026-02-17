"""
STRATIFY - Triage Decision Schemas
Models for false positive classification and typology assessment.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum


class TriageClassification(str, Enum):
    TRUE_POSITIVE = "TRUE_POSITIVE"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class DecisionFactor(BaseModel):
    factor: str
    direction: str = Field(description="supports_suspicious or supports_legitimate")
    weight: float = Field(ge=0, le=1.0)
    evidence: str


class TriageDecision(BaseModel):
    """Output of the triage classification."""
    unified_alert_id: str
    classification: TriageClassification
    composite_risk_score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1.0)
    rule_based_result: Optional[str] = None
    rule_matched: Optional[str] = None
    behavioral_anomaly_score: float = 0.0
    llm_reasoning: Optional[str] = None
    explanation: str
    decision_factors: List[DecisionFactor] = []
    triage_timestamp: datetime = Field(default_factory=datetime.utcnow)
    rules_evaluated: int = 0
    llm_used: bool = False
    model_version: Optional[str] = None


class TypologyMatch(BaseModel):
    code: str
    name: str
    fincen_activity_codes: List[str] = []
    confidence: float = Field(ge=0, le=1.0)
    reasoning: str
    matched_indicators: List[str] = []


class TypologyAssessment(BaseModel):
    """Output of typology classification."""
    primary_typology: Optional[TypologyMatch] = None
    secondary_typologies: List[TypologyMatch] = []
    total_typologies_evaluated: int = 0
    assessment_timestamp: datetime = Field(default_factory=datetime.utcnow)