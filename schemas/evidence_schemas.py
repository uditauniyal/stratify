"""
STRATIFY - Evidence & Enrichment Schemas
Models for behavioral baseline, deviation analysis, evidence pointers, and timeline.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime


class BehavioralBaseline(BaseModel):
    avg_monthly_inflow: float
    avg_monthly_outflow: float
    avg_txn_count_per_month: int
    usual_counterparties: List[str] = []
    usual_geographies: List[str] = []
    usual_channels: List[str] = []
    baseline_period: str = ""
    max_single_txn: float = 0.0


class DeviationAnalysis(BaseModel):
    volume_deviation_factor: float = Field(description="Current vs baseline multiplier e.g. 6.8x")
    velocity_spike: bool = False
    new_counterparties_count: int = 0
    new_geographies: List[str] = []
    new_channels: List[str] = []
    deviation_summary: str = ""
    flagged_txn_count: int = 0


class RiskFactor(BaseModel):
    factor: str
    source: str
    severity: str = Field(description="high, medium, low")
    detail: str


class EnrichedDossier(BaseModel):
    """Output of the enrichment process - complete risk profile."""
    unified_alert_id: str
    customer_id: str
    customer_name: str
    account_ids: List[str]
    jurisdiction: str
    behavioral_baseline: Dict
    deviation_analysis: Dict
    cross_source_risk_score: float
    risk_factors: List[Dict]
    has_prior_sars: bool = False
    prior_sar_count: int = 0
    is_pep: bool = False
    has_sanctions_hits: bool = False
    has_adverse_media: bool = False
    enrichment_timestamp: str = ""
    sources_consulted: List[str] = []
    data_quality_score: float = 100.0
    transactions_validated: int = 0
    transactions_quarantined: int = 0
    duplicates_removed: int = 0


class TimelineEvent(BaseModel):
    date: str
    event: str
    txn_ids: List[str] = []
    amount: float = 0.0
    evidence_type: str = "transaction_record"


class FlowChain(BaseModel):
    origin: List[str]
    intermediary: str
    destination: str
    total_amount: float
    timespan_days: int


class FlowOfFundsAnalysis(BaseModel):
    total_inflow: float
    total_outflow: float
    net_position: float
    flow_chains: List[FlowChain] = []
    velocity_analysis: Dict = {}


class EvidencePointer(BaseModel):
    pointer_id: str = Field(description="e.g. EP-001")
    claim: str = Field(description="The factual claim this evidence supports")
    source_txn_ids: List[str] = []
    source_type: str = Field(description="transaction, kyc, risk_intel, computed")
    computed_value: Optional[str] = None
    verification: str = Field(description="How this claim was verified against source data")


class EvidencePackage(BaseModel):
    """Complete evidence assembly output."""
    case_id: str
    timeline: List[TimelineEvent]
    flow_of_funds: FlowOfFundsAnalysis
    evidence_pointers: List[EvidencePointer]
    behavioral_deviation: DeviationAnalysis
    total_suspicious_amount: float
    review_period: str
    assembly_timestamp: datetime = Field(default_factory=datetime.utcnow)
    total_transactions_analyzed: int = 0
    total_evidence_pointers: int = 0
    computation_log: List[str] = []