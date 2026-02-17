import json
import os
import sys
from typing import Dict, Any, Literal

# Add project root to path
sys.path.append(os.getcwd())

from langgraph.graph import StateGraph, END
from pipeline.state import STRATIFYState

# Import Agents
from agents.node1_ingest_enrich import node1_ingest_enrich
from agents.node2_triage_classify import node2_triage_classify
from agents.node3_generate import node3_generate
from agents.node4_validate_package import node4_validate_package

def triage_router(state: STRATIFYState) -> Literal["node3_generate", "package_fp_exit"]:
    """
    Conditional router after Node 2.
    """
    triage = state.get("triage_decision", {})
    classification = triage.get("classification")
    
    if classification == "TRUE_POSITIVE":
        return "node3_generate"
    else:
        return "package_fp_exit"

def package_fp_exit(state: STRATIFYState) -> STRATIFYState:
    """
    Handle False Positives/Review cases (No narrative generation).
    """
    triage = state.get("triage_decision", {})
    case = state.get("case_input", {})
    
    classification = triage.get("classification", "UNKNOWN")
    explanation = triage.get("explanation", "No explanation provided.")
    risk_score = triage.get("composite_risk_score", 0)
    
    final_output = {
        "case_id": case.get("alert", {}).get("alert_id"),
        "triage_decision": classification,
        "triage_explanation": explanation,
        "risk_score": risk_score,
        "typology": None,
        "sar_narrative": None,
        "validation_result": None,
        "audit_package": None,
        "processing_time_seconds": 0.0
    }
    
    print(f"[Exit] Case classified as {classification}. No SAR narrative required.")
    
    return {**state, "final_output": final_output}

def build_graph():
    """
    Construct the STRATIFY StateGraph.
    """
    workflow = StateGraph(STRATIFYState)
    
    # Add Nodes
    workflow.add_node("node1_ingest", node1_ingest_enrich)
    workflow.add_node("node2_triage", node2_triage_classify)
    workflow.add_node("node3_generate", node3_generate)
    workflow.add_node("node4_validate", node4_validate_package)
    workflow.add_node("package_fp_exit", package_fp_exit)
    
    # Set Entry
    workflow.set_entry_point("node1_ingest")
    
    # Add Edges
    workflow.add_edge("node1_ingest", "node2_triage")
    
    # Conditional Edge from Node 2
    workflow.add_conditional_edges(
        "node2_triage",
        triage_router,
        {
            "node3_generate": "node3_generate",
            "package_fp_exit": "package_fp_exit"
        }
    )
    
    # Standard Edges
    workflow.add_edge("node3_generate", "node4_validate")
    workflow.add_edge("node4_validate", END)
    workflow.add_edge("package_fp_exit", END)
    
    return workflow.compile()

def run_pipeline(case_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the full pipeline for a given case input.
    """
    app = build_graph()
    
    initial_state: STRATIFYState = {
        "case_input": case_input,
        "enriched_dossier": None,
        "triage_decision": None,
        "evidence_package": None,
        "typology_assessment": None,
        "rag_context": None,
        "draft_narrative": None,
        "validation_result": None,
        "audit_package": None,
        "final_output": None,
        "retry_count": 0,
        "error": None
    }
    
    print("\n=== Starting STRATIFY Pipeline ===")
    final_state = app.invoke(initial_state)
    print("=== Pipeline Complete ===\n")
    
    return final_state

if __name__ == "__main__":
    # Test with Scenario 1
    scenario_path = "data/scenarios/scenario_1.json"
    if os.path.exists(scenario_path):
        print(f"Loading {scenario_path}...")
        with open(scenario_path, "r") as f:
            case_data = json.load(f)
            
        result = run_pipeline(case_data)
        
        final = result.get("final_output", {})
        print(f"Final Classification: {final.get('triage_decision')}")
        
        if final.get("sar_narrative"):
            wc = final["sar_narrative"].get("word_count")
            print(f"SAR Narrative Generated: Yes ({wc} words)")
        else:
            print("SAR Narrative Generated: No")
    else:
        print("Scenario file not found.")
