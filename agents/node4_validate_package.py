import datetime
from typing import Dict, Any, List, Optional
import json
import re

def validate_5w_how(narrative: Dict, case_input: Dict, dossier: Dict) -> Dict:
    """
    Validate the generated SAR narrative against FinCEN's 5W+How framework.
    """
    full_text = narrative.get("full_narrative", "").lower()
    checks = []
    
    # 1. Critical Checks
    # a. WHO
    cust_name = case_input.get("customer_profile", {}).get("name", "").lower()
    checks.append({
        "check": "WHO_SUBJECT_IDENTIFIED",
        "status": "PASS" if cust_name in full_text else "FAIL",
        "severity": "critical",
        "detail": f"Subject name '{cust_name}' found." if cust_name in full_text else "Subject name missing."
    })
    
    # b. WHAT
    alert_type = case_input.get("alert", {}).get("type", "").lower()
    typology = narrative.get("title", "").lower()
    checks.append({
        "check": "WHAT_ACTIVITY_DESCRIBED",
        "status": "PASS" if (alert_type in full_text or "structuring" in full_text or "layering" in full_text) else "FAIL",
        "severity": "critical",
        "detail": "Activity type described."
    })
    
    # c. WHEN
    # Regex for dates: YYYY-MM-DD, MM/DD/YYYY, or Month names
    date_pattern = r"(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|january|february|march|april|may|june|july|august|september|october|november|december)"
    has_dates = re.search(date_pattern, full_text)
    checks.append({
        "check": "WHEN_DATES_PRESENT",
        "status": "PASS" if has_dates else "FAIL",
        "severity": "critical",
        "detail": "Dates found." if has_dates else "No dates found."
    })
    
    # d. WHERE
    # Check for simple location indicators
    loc_terms = ["branch", "state", "country", "jurisdiction", "bank", "location"]
    has_loc = any(t in full_text for t in loc_terms)
    checks.append({
        "check": "WHERE_LOCATION_PRESENT",
        "status": "PASS" if has_loc else "FAIL",
        "severity": "critical",
        "detail": "Location references found." if has_loc else "No location references."
    })
    
    # e. WHY
    suspicion_terms = ["suspicious", "inconsistent", "deviation", "unusual", "anomal", "red flag", "indicator", "appears"]
    suspicion_count = sum(1 for t in suspicion_terms if t in full_text)
    checks.append({
        "check": "WHY_SUSPICION_EXPLAINED",
        "status": "PASS" if suspicion_count >= 2 else "FAIL",
        "severity": "critical",
        "detail": f"Found {suspicion_count} suspicion keywords."
    })
    
    # 2. Major Checks
    # f. HOW
    mech_terms = ["deposit", "withdraw", "wire", "transfer", "cash", "fund", "transaction"]
    mech_count = sum(1 for t in mech_terms if t in full_text)
    checks.append({
        "check": "HOW_MECHANISM_DESCRIBED",
        "status": "PASS" if mech_count >= 3 else "FAIL",
        "severity": "major",
        "detail": f"Found {mech_count} mechanism keywords."
    })
    
    # g. AMOUNTS
    # $X, USD X, or strict numbers
    amount_pattern = r"(\$|usd|eur)\s?\d{1,3}(,\d{3})*(\.\d{2})?"
    amount_matches = len(re.findall(amount_pattern, full_text))
    checks.append({
        "check": "AMOUNTS_SPECIFIC",
        "status": "PASS" if amount_matches >= 2 else "WARN",
        "severity": "major",
        "detail": f"Found {amount_matches} specific amounts."
    })
    
    # h. COUNTS
    count_pattern = r"\d+\s(transactions|deposits|withdrawals|wires|transfers)"
    count_matches = len(re.findall(count_pattern, full_text))
    checks.append({
        "check": "TRANSACTION_COUNTS",
        "status": "PASS" if count_matches > 0 else "WARN",
        "severity": "major",
        "detail": "Transaction counts referenced." if count_matches > 0 else "No explicit transaction counts."
    })
    
    # 3. Minor Checks
    # i. PRIOR HISTORY
    prior_sars = case_input.get("risk_intelligence", {}).get("prior_sars", [])
    if prior_sars:
        has_ref = any(t in full_text for t in ["prior", "previous", "filing", "continuing", "dcn"])
        checks.append({
            "check": "PRIOR_HISTORY_REFERENCED",
            "status": "PASS" if has_ref else "WARN",
            "severity": "minor",
            "detail": "Prior SARs referenced." if has_ref else "Prior SARs exist but not referenced."
        })
        
    # j. LENGTH
    word_count = narrative.get("word_count", 0)
    length_status = "PASS"
    if word_count < 200: length_status = "WARN" # Too short
    if word_count > 5000: length_status = "WARN" # Too long
    checks.append({
        "check": "NARRATIVE_LENGTH",
        "status": length_status,
        "severity": "minor",
        "detail": f"Word count: {word_count}"
    })
    
    # k. DEFINITIVE CONCLUSIONS
    def_terms = ["is guilty", "committed money laundering", "is laundering money", "illegal activity confirmed"]
    has_def = any(t in full_text for t in def_terms)
    checks.append({
        "check": "NO_DEFINITIVE_CONCLUSIONS",
        "status": "FAIL" if has_def else "PASS", # Actually FAIL or WARN? Plan said WARN but logically FAIL. Let's stick to WARN to be safe for proto.
        "severity": "minor",
        "detail": "No definitive legal conclusions found." if not has_def else "Definitive conclusions found (avoid this)."
    })

    # Consolidate
    passed = sum(1 for c in checks if c["status"] == "PASS")
    warnings = sum(1 for c in checks if c["status"] == "WARN")
    failed = sum(1 for c in checks if c["status"] == "FAIL")
    
    # Overall Status
    crit_fail = any(c["status"] == "FAIL" and c["severity"] == "critical" for c in checks)
    maj_fail = any(c["status"] == "FAIL" and c["severity"] == "major" for c in checks) # actually plan said 'Fail' status only for critical?
    # Reread plan: "WARN if any major check failed" -> so major check returning FAIL is Status WARN for overall.
    # Actually my code above sets status to FAIL for major check if criteria not met.
    # Let's align:
    # Critical FAIL -> Overall FAIL
    # Major FAIL -> Overall WARN
    # >2 Warnings -> Overall WARN
    
    overall = "PASS"
    if crit_fail:
        overall = "FAIL"
    elif maj_fail or warnings > 2:
        overall = "WARN"
        
    return {
        "case_id": case_input.get("alert", {}).get("alert_id"),
        "overall_status": overall,
        "total_checks": len(checks),
        "passed": passed,
        "warnings": warnings,
        "failed": failed,
        "checks": checks,
        "validation_timestamp": datetime.datetime.utcnow().isoformat()
    }

def compile_audit_package(state: Dict) -> Dict:
    """
    Compile full audit trail.
    """
    case = state.get("case_input", {})
    dossier = state.get("enriched_dossier", {})
    triage = state.get("triage_decision", {})
    typology = state.get("typology_assessment", {})
    narrative = state.get("draft_narrative", {})
    validation = state.get("validation_result", {})
    
    # Traceability
    full_text = narrative.get("full_narrative", "") if narrative else ""
    sentences = full_text.split(". ")
    traces = []
    for s in sentences:
        if len(s.strip()) > 10:
            traces.append({
                "sentence": s.strip(),
                "evidence_pointers": [], # Placeholder
                "source_data_summary": "Derived from enriched dossier",
                "typology_basis": typology.get("primary_typology") if typology else "None"
            })
            
    # Audit Logs
    ingest = {
        "sources_consulted": ["Core Banking", "CRM", "Watchlist DB"],
        "transactions_validated": len(case.get("transaction_history", [])),
        "data_quality_score": 98.5 # Placeholder or derived
    }
    
    enrich = {
        "behavioral_baseline": dossier.get("behavioral_baseline", {}),
        "deviation_factors": dossier.get("deviation_analysis", {}),
        "risk_factors_count": len(dossier.get("risk_factors", []))
    }
    
    triage_log = {
        "classification": triage.get("classification"),
        "score": triage.get("composite_risk_score"),
        "explanation": triage.get("explanation"),
        "llm_used": triage.get("llm_reasoning") is not None
    }
    
    narrative_log = {
        "model": narrative.get("generation_model"),
        "word_count": narrative.get("word_count"),
        "rag_chunks": narrative.get("rag_chunks_used"),
        "prompt_hash": narrative.get("prompt_hash")
    }
    
    return {
        "case_id": case.get("alert", {}).get("alert_id"),
        "pipeline_version": "STRATIFY v0.1",
        "generated_at": datetime.datetime.utcnow().isoformat(),
        "traceability": traces,
        "audit_logs": {
            "ingestion": ingest,
            "enrichment": enrich,
            "triage": triage_log,
            "typology": typology,
            "generation": narrative_log,
            "validation": validation
        }
    }

def build_final_output(state: Dict) -> Dict:
    """
    Construct the final SAR Output object.
    """
    triage = state.get("triage_decision", {})
    narrative = state.get("draft_narrative")
    validation = state.get("validation_result")
    audit = state.get("audit_package")
    
    output = {
        "case_id": state.get("case_input", {}).get("alert", {}).get("alert_id"),
        "triage_decision": triage.get("classification"),
        "triage_explanation": triage.get("explanation"),
        "risk_score": triage.get("composite_risk_score"),
        "typology": state.get("typology_assessment", {}).get("primary_typology"),
        "processing_time_seconds": 0.0 # Placeholder
    }
    
    if triage.get("classification") == "TRUE_POSITIVE" and narrative:
        output["sar_narrative"] = narrative
        output["validation_result"] = validation
        output["audit_package"] = audit
        
    return output

def node4_validate_package(state: Dict[str, Any]) -> Dict[str, Any]:
    print("[Node 4] Starting Validation & Packaging...")
    
    triage = state.get("triage_decision", {})
    
    # Skip validation if not TP or no narrative
    if triage.get("classification") != "TRUE_POSITIVE" or not state.get("draft_narrative"):
        print("[Node 4] Skipping validation (Not TRUE_POSITIVE or missing narrative).")
        final = build_final_output(state)
        return {**state, "final_output": final}
        
    # 1. Validate
    validation_result = validate_5w_how(
        narrative=state["draft_narrative"],
        case_input=state["case_input"],
        dossier=state["enriched_dossier"]
    )
    
    print(f"[Node 4] Validation Status: {validation_result['overall_status']}")
    print(f"         Passed: {validation_result['passed']}, Warnings: {validation_result['warnings']}, Failed: {validation_result['failed']}")
    
    # Update state temporarily to allow compile function to use it
    state_with_val = {**state, "validation_result": validation_result}
    
    # 2. Audit Package
    audit_package = compile_audit_package(state_with_val)
    print(f"[Node 4] Audit Package compiled with {len(audit_package['traceability'])} sentence traces.")
    
    # 3. Final Output
    final_state = {**state_with_val, "audit_package": audit_package}
    final_output = build_final_output(final_state)
    
    return {**final_state, "final_output": final_output}
