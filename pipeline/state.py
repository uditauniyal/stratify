"""
STRATIFY - Pipeline State Definition
Complete pipeline state passed between LangGraph nodes.
"""

from typing import Optional, List, Dict, Any
from typing_extensions import TypedDict


class STRATIFYState(TypedDict):
    """
    Complete pipeline state. Each node reads from and writes to this shared state.
    LangGraph passes this between nodes automatically.
    """

    # Initial structured case input
    case_input: Optional[Dict[str, Any]]

    # Enrichment + analysis outputs
    enriched_dossier: Optional[Dict[str, Any]]
    triage_decision: Optional[Dict[str, Any]]
    evidence_package: Optional[Dict[str, Any]]
    typology_assessment: Optional[Dict[str, Any]]

    # RAG layer
    rag_context: Optional[List[str]]

    # Narrative generation
    draft_narrative: Optional[Dict[str, Any]]

    # Validation layer
    validation_result: Optional[Dict[str, Any]]

    # Audit + packaging
    audit_package: Optional[Dict[str, Any]]
    final_output: Optional[Dict[str, Any]]

    # Control fields
    retry_count: int
    error: Optional[str]
