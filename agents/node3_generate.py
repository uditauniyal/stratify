import datetime
from typing import Dict, Any, List, Optional
import os
import json
import hashlib
from dotenv import load_dotenv

# Load env vars
load_dotenv()

# RAG Imports
try:
    from rag.setup_vectorstore import get_vectorstore, query_vectorstore
    HAS_RAG_LIB = True
except ImportError:
    HAS_RAG_LIB = False
    print("Warning: Could not import rag.setup_vectorstore. RAG will be disabled.")

# LangChain Imports
try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False

def retrieve_rag_context(typology_name: str, alert_type: str) -> List[str]:
    """
    Retrieve relevant regulatory guidance via RAG.
    """
    if not HAS_RAG_LIB:
        return [
            "SAR Narrative Structure: 1. Introduction/Subject, 2. Summary of Activity, 3. Analysis, 4. Conclusion.",
            "Include 5Ws: Who, What, Where, When, Why."
        ]
        
    try:
        # Get/Create vectorstore (uses simple embeddings fallback if needed)
        vs = get_vectorstore()
        
        queries = [
            f"SAR narrative structure {typology_name}",
            f"5W How framework {alert_type} suspicious activity",
            f"{typology_name} indicators red flags"
        ]
        
        context_set = set()
        for q in queries:
            results = query_vectorstore(vs, q, k=2)
            for res in results:
                context_set.add(res)
                
        print(f"[RAG] Retrieved {len(context_set)} unique context chunks.")
        return list(context_set)
        
    except Exception as e:
        print(f"[RAG] Error retrieving context: {e}")
        return [
            "SAR Narrative Structure: 1. Introduction/Subject, 2. Summary of Activity, 3. Analysis, 4. Conclusion.",
            "Include 5Ws: Who, What, Where, When, Why."
        ]

def build_evidence_summary(state: Dict) -> str:
    """
    Consolidate all investigation data into a formatted summary for the LLM.
    """
    dossier = state.get("enriched_dossier", {})
    triage = state.get("triage_decision", {})
    typology = state.get("typology_assessment", {})
    case = state.get("case_input", {})
    
    cust = case.get("customer_profile", {})
    alert = case.get("alert", {})
    dev = dossier.get("deviation_analysis", {})
    
    # Txn stats
    txns = case.get("transaction_history", [])
    flagged_ids = alert.get("flagged_transaction_ids", [])
    flagged_txns = [t for t in txns if t["txn_id"] in flagged_ids]
    
    total_in = sum(t["amount"] for t in flagged_txns if t.get("direction") == "inbound")
    total_out = sum(t["amount"] for t in flagged_txns if t.get("direction") == "outbound")
    countries = sorted(list(set(t.get("counterparty_country", "Unknown") for t in flagged_txns if t.get("counterparty_country"))))
    
    summary = f"""
    ALERT DETAILS:
    - ID: {alert.get("alert_id")}
    - Type: {alert.get("type")} (Rule: {alert.get("rule_id")})
    - Date: {alert.get("generated_at")}
    - Risk Score: {alert.get("risk_score")}
    
    SUBJECT:
    - Name: {cust.get("name")}
    - ID: {cust.get("customer_id")}
    - Occupation: {cust.get("occupation")}
    - Employer: {cust.get("employer")}
    - Income: ${cust.get("annual_income", 0):,.2f}
    - Account Opened: {cust.get("account_opened_date")}
    
    KEY FINDINGS:
    - Triage Classification: {triage.get("classification")}
    - Primary Typology: {typology.get("primary_typology") if typology else "Unknown"}
    - Confidence: {typology.get("confidence", 0) if typology else 0:.2f}
    - Risk Score (Composite): {triage.get("composite_risk_score")}
    
    BEHAVIORAL ANALYSIS:
    - Volume Deviation: {dev.get("volume_deviation_factor", 0):.1f}x baseline
    - New Counterparties: {dev.get("new_counterparties_count")}
    - Deviation Summary: {dev.get("deviation_summary")}
    - Baseline Avg Inflow: ${dossier.get("behavioral_baseline", {}).get("avg_monthly_inflow", 0):,.2f}
    
    TRANSACTION ACTIVITY (Flagged):
    - Count: {len(flagged_txns)}
    - Total Inflow: ${total_in:,.2f}
    - Total Outflow: ${total_out:,.2f}
    - Involved Countries: {", ".join(countries)}
    
    PRIOR HISTORY:
    - Prior SARs: {len(case.get("risk_intelligence", {}).get("prior_sars", []))}
    """
    
    return summary

def generate_narrative_fallback(evidence_summary: str, typology: str, case_input: Dict) -> Dict:
    """
    Template-based generation for offline mode.
    """
    cust = case_input.get("customer_profile", {})
    alert = case_input.get("alert", {})
    
    subj_section = f"Subject {cust.get('name')} (ID: {cust.get('customer_id')}) is a {cust.get('occupation')} employed by {cust.get('employer')}."
    
    summary_section = f"An alert was generated on {alert.get('generated_at')} for {alert.get('type')}. Analysis identified {typology} with high confidence."
    
    rationale_section = f"The activity deviates significantly from the established baseline. The volume of transactions is inconsistent with the customer's declared income of ${cust.get('annual_income', 0):,.2f}."
    
    full_text = f"SUBJECT INFORMATION\n{subj_section}\n\nSUMMARY OF SUSPICIOUS ACTIVITY\n{summary_section}\n\nSUSPICION RATIONALE\n{rationale_section}\n\nACTIONS TAKEN\nCustomer placed on enhanced monitoring. SAR filed."
    
    return {
        "case_id": alert.get("alert_id"),
        "title": f"SAR - {typology} - {cust.get('name')}",
        "filing_type": "initial", # simplified
        "full_narrative": full_text,
        "sections": [
            {"section_name": "SUBJECT INFORMATION", "content": subj_section},
            {"section_name": "SUMMARY OF SUSPICIOUS ACTIVITY", "content": summary_section},
            {"section_name": "SUSPICION RATIONALE", "content": rationale_section}
        ],
        "word_count": len(full_text.split()),
        "generation_model": "template-fallback",
        "generation_timestamp": datetime.datetime.utcnow().isoformat(),
        "prompt_hash": "N/A",
        "rag_chunks_used": 0
    }

def generate_narrative_with_llm(evidence_summary: str, rag_context: List[str], typology: str, case_input: Dict) -> Dict:
    """
    Generate narrative using GPT-4o-mini via LangChain.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not HAS_LANGCHAIN or not api_key or api_key.startswith("sk-your-key"):
        print("[Node 3] LLM unavailable. Using fallback.")
        return generate_narrative_fallback(evidence_summary, typology, case_input)
        
    try:
        print("[Node 3] Calling LLM for narrative generation...")
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2, max_tokens=3000, api_key=api_key)
        
        system_prompt = """
        You are an expert BSA/AML compliance analyst drafting a SAR narrative. Follow FinCEN guidelines strictly. 
        Use the 5W+How framework. Write in formal regulatory language. 
        Every claim must be supported by the evidence provided. 
        Do NOT conclude that money laundering has occurred — describe why the activity APPEARS suspicious. 
        Use specific dollar amounts, dates, and transaction counts. 
        Structure the narrative with these sections:

        SUBJECT INFORMATION
        SUMMARY OF SUSPICIOUS ACTIVITY
        DETAILED TRANSACTION ANALYSIS
        FLOW OF FUNDS
        SUSPICION RATIONALE
        PRIOR HISTORY (if applicable)
        ACTIONS TAKEN
        """
        
        context_str = "\n\n".join(rag_context)
        user_prompt = f"REGULATORY GUIDANCE:\n{context_str}\n\nEVIDENCE PACKAGE:\n{evidence_summary}\n\nGenerate a complete SAR narrative for this case. Be specific with all amounts, dates, and counts."
        
        # Hash prompt for audit
        prompt_hash = hashlib.md5((system_prompt + user_prompt).encode()).hexdigest()
        
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ])
        
        full_text = response.content
        
        # Parse sections (simplified)
        sections = []
        current_section = None
        buffer = []
        
        for line in full_text.split("\n"):
            upper_line = line.strip().upper()
            if upper_line in ["SUBJECT INFORMATION", "SUMMARY OF SUSPICIOUS ACTIVITY", "DETAILED TRANSACTION ANALYSIS", "FLOW OF FUNDS", "SUSPICION RATIONALE", "PRIOR HISTORY", "ACTIONS TAKEN"]:
                if current_section:
                    sections.append({"section_name": current_section, "content": "\n".join(buffer).strip()})
                current_section = upper_line
                buffer = []
            else:
                buffer.append(line)
        if current_section:
            sections.append({"section_name": current_section, "content": "\n".join(buffer).strip()})
            
        # Determine filing type
        prior_sars = case_input.get("risk_intelligence", {}).get("prior_sars", [])
        filing_type = "continuing" if prior_sars else "initial"
        
        return {
            "case_id": case_input.get("alert", {}).get("alert_id"),
            "title": f"SAR - {typology} - {case_input.get('customer_profile', {}).get('name')}",
            "filing_type": filing_type,
            "full_narrative": full_text,
            "sections": sections,
            "word_count": len(full_text.split()),
            "generation_model": "gpt-4o-mini",
            "generation_timestamp": datetime.datetime.utcnow().isoformat(),
            "prompt_hash": prompt_hash,
            "rag_chunks_used": len(rag_context)
        }

    except Exception as e:
        print(f"[Node 3] LLM Error: {e}. Using fallback.")
        return generate_narrative_fallback(evidence_summary, typology, case_input)

def node3_generate(state: Dict[str, Any]) -> Dict[str, Any]:
    print("[Node 3] Starting SAR Narrative Generation...")
    
    # Check if we should generate
    triage = state.get("triage_decision", {})
    if triage.get("classification") != "TRUE_POSITIVE":
        print("[Node 3] Alert not TRUE_POSITIVE. Skipping narrative.")
        return {**state, "draft_narrative": None}
        
    # Get details
    typology_assess = state.get("typology_assessment", {})
    typology = typology_assess.get("primary_typology") if typology_assess else "Suspicious Activity"
    case = state.get("case_input", {})
    alert_type = case.get("alert", {}).get("type", "General")
    
    # 1. Retrieve RAG
    rag_context = retrieve_rag_context(typology, alert_type)
    
    # 2. Build Evidence
    evidence = build_evidence_summary(state)
    
    # 3. Generate
    narrative = generate_narrative_with_llm(evidence, rag_context, typology, case)
    
    print(f"[Node 3] Generated narrative ({narrative['word_count']} words) using {narrative['generation_model']}.")
    
    return {**state, "draft_narrative": narrative, "rag_context": rag_context}
