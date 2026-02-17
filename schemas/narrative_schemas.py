"""
STRATIFY - SAR Narrative & Output Schemas
Models for draft narrative, validation, audit trail, and final output.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime


class NarrativeSection(BaseModel):
    section_name: str
    content: str
    evidence_pointers_used: List[str] = []
    confidence: float = Field(ge=0, le=1.0, default=1.0)


class DraftNarrative(BaseModel):
    """Generated SAR narrative with evidence tracing."""
    case_id: str
    title: str
    filing_type: str = Field(description="initial, continuing, corrected")
    subject_info: Dict = {}
    sections: List[NarrativeSection] = []
    full_narrative: str = ""
    word_count: int = 0
    generation_model: str = ""
    generation_timestamp: datetime = Field(default_factory=datetime.utcnow)
    prompt_hash: str = ""
    rag_chunks_used: int = 0


class ValidationCheck(BaseModel):
    check_name: str
    status: str = Field(description="PASS, FAIL, WARN")
    detail: str
    severity: str = Field(description="critical, major, minor")


class ValidationResult(BaseModel):
    case_id: str
    overall_status: str = Field(description="PASS, FAIL, or WARN")
    checks: List[ValidationCheck]
    total_checks: int
    passed: int
    warnings: int
    failed: int
    validation_timestamp: datetime = Field(default_factory=datetime.utcnow)


class SentenceLevelTrace(BaseModel):
    sentence: str
    evidence_pointers: List[str]
    source_data_summary: str
    typology_basis: Optional[str] = None
    guidance_reference: Optional[str] = None


class AuditPackage(BaseModel):
    """Complete audit trail - the examiner-ready artifact."""
    case_id: str
    pipeline_version: str = "SARATHI v0.1"
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    sentence_traces: List[SentenceLevelTrace] = []
    ingestion_audit: Dict = {}
    enrichment_audit: Dict = {}
    triage_audit: Dict = {}
    typology_audit: Dict = {}
    evidence_assembly_audit: Dict = {}
    narrative_generation_audit: Dict = {}
    validation_audit: Dict = {}
    llm_model: str = ""
    embedding_model: str = ""
    prompt_versions: Dict[str, str] = {}
    all_prompt_hashes: Dict[str, str] = {}
    human_edits_log: List[Dict] = []


class SAROutput(BaseModel):
    """Final complete output of SARATHI pipeline."""
    case_id: str
    triage_decision: str
    triage_explanation: str
    sar_narrative: Optional[DraftNarrative] = None
    validation_result: Optional[ValidationResult] = None
    audit_package: Optional[AuditPackage] = None
    risk_score: float
    typology: Optional[str] = None
    processing_time_seconds: float = 0.0