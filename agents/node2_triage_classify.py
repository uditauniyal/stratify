import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

def _get_year(date_str: str) -> int:
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).year
    except:
        return 0

def _get_month(date_str: str) -> int:
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).month
    except:
        return 0

def apply_rule_based_triage(case_input: Dict, dossier: Dict) -> Tuple[Optional[str], Optional[str]]:
    """
    Layer 1: Hard rules. Returns (classification, rule_id) or (None, None).
    """
    risk_intel = case_input.get("risk_intelligence", {})
    alert = case_input.get("alert", {})
    txns = case_input.get("transaction_history", [])
    flagged_ids = alert.get("flagged_transaction_ids", [])
    
    # Rule 1 - SANC-001: Sanctions Hits
    if risk_intel.get("sanctions_hits"):
        return "TRUE_POSITIVE", "SANC-001"

    # Rule 2 - HIST-001: Prior SAR + High Volume Deviation
    deviation = dossier.get("deviation_analysis", {})
    vol_dev = deviation.get("volume_deviation_factor", 0.0)
    if risk_intel.get("prior_sars") and vol_dev > 2.0:
        return "TRUE_POSITIVE", "HIST-001"

    # Rule 3 - SAL-001: Salary/Bonus False Positive
    if len(flagged_ids) == 1:
        flagged_txn = next((t for t in txns if t["txn_id"] == flagged_ids[0]), None)
        employer = case_input.get("customer_profile", {}).get("employer", "").lower()
        
        if flagged_txn and employer:
            cp_name = (flagged_txn.get("counterparty_name") or "").lower()
            memo = (flagged_txn.get("memo") or "").lower()
            
            is_employer_match = employer in cp_name
            is_payroll = any(kw in memo for kw in ["salary", "bonus", "payroll", "compensation"])
            
            # check historical similarity
            output_txns = [t for t in txns if t["txn_id"] != flagged_ids[0]]
            has_history = any((t.get("counterparty_name") or "").lower() == cp_name for t in output_txns)
            
            if is_employer_match and is_payroll and has_history:
                return "FALSE_POSITIVE", "SAL-001"

    # Rule 4 - SEAS-001: Seasonal Spike
    if vol_dev > 2.0:
        # Check prior year same months
        # Get flagged months
        flagged_months = set()
        for fid in flagged_ids:
            t = next((tx for tx in txns if tx["txn_id"] == fid), None)
            if t:
                m = _get_month(t["date"])
                flagged_months.add(m)
        
        # Check prior year volume for these months
        if flagged_months:
            # Assume alert year is max year in flagged
            alert_year = 0
            for fid in flagged_ids:
                t = next((tx for tx in txns if tx["txn_id"] == fid), None)
                if t:
                    y = _get_year(t["date"])
                    if y > alert_year: alert_year = y
            
            prior_year = alert_year - 1
            prior_year_txns = [
                t for t in txns 
                if _get_year(t["date"]) == prior_year 
                and _get_month(t["date"]) in flagged_months
                and t.get("direction") == "inbound"
            ]
            
            prior_vol = sum(t["amount"] for t in prior_year_txns)
            prior_count = len(prior_year_txns)
            
            # Current flagged volume
            flagged_inbound_vol = sum(
                t["amount"] for t in txns 
                if t["txn_id"] in flagged_ids and t.get("direction") == "inbound"
            )
            
            if prior_count > 20 and prior_vol > 0:
                ratio = flagged_inbound_vol / prior_vol
                if ratio < 1.5:
                    return "FALSE_POSITIVE", "SEAS-001"

    return None, None

def compute_behavioral_anomaly_score(case_input: Dict, dossier: Dict) -> float:
    """
    Layer 2: Scoring 0-100 based on anomalies.
    """
    score = 0.0
    deviation = dossier.get("deviation_analysis", {})
    customer = case_input.get("customer_profile", {})
    alert = case_input.get("alert", {})
    
    # 1. Volume Deviation (0-30)
    vol_dev = deviation.get("volume_deviation_factor", 0.0)
    if vol_dev > 8: score += 30
    elif vol_dev > 5: score += 25
    elif vol_dev > 3: score += 20
    elif vol_dev > 2: score += 15
    elif vol_dev > 1.5: score += 8
    
    # 2. New Counterparties (0-20)
    new_cps = deviation.get("new_counterparties_count", 0)
    if new_cps > 20: score += 20
    elif new_cps > 10: score += 15
    elif new_cps > 5: score += 10
    elif new_cps > 2: score += 5
    
    # 3. Velocity Spike (0-15)
    if deviation.get("velocity_spike"):
        score += 15
        
    # 4. New Geographies (0-10)
    new_geos = deviation.get("new_geographies", [])
    high_risk = {"AE", "KY", "PA", "BZ", "VG", "BS", "LR"}
    if any(g in high_risk for g in new_geos):
        score += 10
    elif new_geos:
        score += 5
        
    # 5. Account Age (0-10)
    opened = customer.get("account_opened_date") # YYYY-MM-DD
    if opened:
        try:
            open_dt = datetime.strptime(opened, "%Y-%m-%d")
            alert_dt = datetime.fromisoformat(alert.get("generated_at", datetime.now().isoformat()).replace("Z", "+00:00"))
            age_days = (alert_dt - open_dt.replace(tzinfo=alert_dt.tzinfo)).days
            
            if age_days < 90: score += 10
            elif age_days < 180: score += 7
            elif age_days < 365: score += 3
        except:
            pass
            
    # 6. Income Mismatch (0-15)
    income = float(customer.get("annual_income", 0.0))
    flagged_ids = alert.get("flagged_transaction_ids", [])
    txns = case_input.get("transaction_history", [])
    flagged_vol = sum(t["amount"] for t in txns if t["txn_id"] in flagged_ids)
    
    if income > 0:
        ratio = flagged_vol / income
        if ratio > 5: score += 15
        elif ratio > 2: score += 10
        elif ratio > 1: score += 5
    elif flagged_vol > 100000:
        score += 15
        
    return min(score, 100.0)

def classify_typology(case_input: Dict, dossier: Dict) -> Dict:
    """
    Determine typology for True Positives.
    """
    typologies = []
    
    alert = case_input.get("alert", {})
    txns = case_input.get("transaction_history", [])
    flagged_ids = alert.get("flagged_transaction_ids", [])
    deviation = dossier.get("deviation_analysis", {})
    customer = case_input.get("customer_profile", {})
    alert_type = alert.get("alert_type", "").lower()
    if not alert_type: alert_type = str(alert.get("type", "")).lower() # fallback
    
    # 1. Structuring + Layering
    s_indicators = 0
    if "structuring" in alert_type: s_indicators += 1
    if deviation.get("new_counterparties_count", 0) > 10: s_indicators += 1
    if deviation.get("volume_deviation_factor", 0.0) > 3: s_indicators += 1
    
    # International wire check in flagged
    has_intl_wire = False
    for fid in flagged_ids:
        t = next((tx for tx in txns if tx["txn_id"] == fid), None)
        if t:
            is_wire = "wire" in t.get("type", "").lower()
            country = t.get("counterparty_country")
            if is_wire and country and country != "US":
                has_intl_wire = True
                break
    if has_intl_wire: s_indicators += 1
    
    if s_indicators >= 2:
        name = "Structuring with Layering"
        prior_sars = case_input.get("risk_intelligence", {}).get("prior_sars")
        if prior_sars:
            name += " - Continuing Activity"
        
        typologies.append({
            "typology": name,
            "confidence": min(0.5 + s_indicators * 0.12, 0.95),
            "indicators": s_indicators
        })

    # 2. Funnel Account
    f_indicators = 0
    if "funnel" in alert_type: f_indicators += 1
    
    # Age < 180
    is_young = False
    opened = customer.get("account_opened_date")
    if opened:
        try:
            open_dt = datetime.strptime(opened, "%Y-%m-%d")
            alert_dt = datetime.fromisoformat(alert.get("generated_at", datetime.now().isoformat()).replace("Z", "+00:00"))
            if (alert_dt - open_dt.replace(tzinfo=alert_dt.tzinfo)).days < 180:
                is_young = True
        except: pass
    if is_young: f_indicators += 1
    
    # Income/Occupation
    income = float(customer.get("annual_income", 0.0))
    occ = customer.get("occupation", "").lower()
    if income == 0 or "student" in occ: f_indicators += 1
    
    # Cash withdrawal
    has_cash_out = any(
        "cash_withdrawal" in next((t.get("type", "") for t in txns if t["txn_id"] == fid), "") 
        for fid in flagged_ids
    )
    if has_cash_out: f_indicators += 1
    
    if deviation.get("new_counterparties_count", 0) > 5: f_indicators += 1
    
    if f_indicators >= 2:
        typologies.append({
            "typology": "Funnel Account (Money Mule)",
            "confidence": min(0.5 + f_indicators * 0.12, 0.95),
            "indicators": f_indicators
        })
        
    typologies.sort(key=lambda x: x["confidence"], reverse=True)
    
    primary = typologies[0]["typology"] if typologies else "General Suspicious Activity"
    secondary = [t["typology"] for t in typologies[1:]]
    
    return {
        "primary_typology": primary,
        "secondary_typologies": secondary,
        "total_typologies_evaluated": 5,
        "assessment_timestamp": datetime.utcnow().isoformat()
    }

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

def get_llm_reasoning(case_input: Dict, dossier: Dict) -> Optional[str]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or api_key.startswith("sk-your-key"):
        return None
        
    try:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=500, api_key=api_key)
        
        alert = case_input.get("alert", {})
        customer = case_input.get("customer_profile", {})
        deviation = dossier.get("deviation_analysis", {})
        risk_score = dossier.get("cross_source_risk_score", 0.0)
        
        prompt = f"""
        You are a BSA/AML compliance analyst. Review this alert and provide a 2-3 sentence assessment.
        
        Alert Type: {alert.get('alert_type')}
        Customer: {customer.get('name')} ({customer.get('occupation')}, Income: ${customer.get('annual_income')})
        
        Risk Factors:
        - Volume Deviation: {deviation.get('volume_deviation_factor')}x baseline
        - New Counterparties: {deviation.get('new_counterparties_count')}
        - Cross-Source Risk Score: {risk_score}/100
        - Prior SARs: {len(case_input.get("risk_intelligence", {}).get("prior_sars", []))}
        - Deviation Summary: {deviation.get('deviation_summary')}
        
        Assess if this looks like TRUE_POSITIVE (suspicious) or FALSE_POSITIVE (explainable) or NEEDS_REVIEW.
        """
        
        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content
        
    except Exception as e:
        print(f"LLM Error: {e}")
        return None

def node2_triage_classify(state: Dict[str, Any]) -> Dict[str, Any]:
    print("[Node 2] Triaging alert...")
    
    case_input = state.get("case_input", {})
    dossier = state.get("enriched_dossier", {})
    alert = case_input.get("alert", {})
    
    # Layer 1: Rules
    rule_class, rule_id = apply_rule_based_triage(case_input, dossier)
    
    # Layer 2: Behavioral Score
    beh_score = compute_behavioral_anomaly_score(case_input, dossier)
    
    # Composite Score
    risk_score = dossier.get("cross_source_risk_score", 0.0)
    alert_risk = float(alert.get("risk_score", 0.0))
    
    composite_score = (beh_score * 0.4) + (risk_score * 0.2) + (alert_risk * 0.4)
    
    classification = "NEEDS_REVIEW"
    confidence = 0.4
    explanation = "Data inconclusive, manual review required."
    
    if rule_class:
        classification = rule_class
        confidence = 0.95 if rule_class == "TRUE_POSITIVE" else 0.90
        explanation = f"Matched hard triage rule {rule_id}."
    elif composite_score >= 60:
        classification = "TRUE_POSITIVE"
        confidence = min(0.5 + (composite_score - 60) * 0.01, 0.95)
        explanation = f"High composite risk score ({composite_score:.1f})."
    elif composite_score <= 30:
        classification = "FALSE_POSITIVE"
        confidence = min(0.5 + (30 - composite_score) * 0.015, 0.90)
        explanation = f"Low composite risk score ({composite_score:.1f})."
        
    # Typology
    typology_assessment = None
    if classification == "TRUE_POSITIVE":
        typology_assessment = classify_typology(case_input, dossier)
        if typology_assessment:
            explanation += f" Primary typology: {typology_assessment['primary_typology']}."

    triage_decision = {
        "unified_alert_id": alert.get("alert_id"),
        "classification": classification,
        "composite_risk_score": round(composite_score, 2),
        "confidence": round(confidence, 2),
        "rule_based_result": rule_class,
        "rule_matched": rule_id,
        "behavioral_anomaly_score": round(beh_score, 2),
        "llm_reasoning": None,
        "explanation": explanation,
        "triage_timestamp": datetime.utcnow().isoformat(),
        "rules_evaluated": 4,
        "decision_factors": [
            {"factor": "Behavioral Anomaly Score", "weight": "High", "direction": f"{beh_score}/100", "evidence": f"Score based on volume/velocity deviations."},
            {"factor": "Rule Match", "weight": "Critical", "direction": str(rule_id), "evidence": f"Triggered rule {rule_id}"} if rule_id else {"factor": "Rule Match", "weight": "None", "direction": "None", "evidence": "No hard rules matched."},
            {"factor": "Composite Risk Score", "weight": "High", "direction": f"{composite_score:.1f}/100", "evidence": "Combined risk assessment."}
        ]
    }
    
    print(f"Classification: {classification}")
    print(f"Rule Matched: {rule_id if rule_id else 'None'}")
    print(f"Composite Score: {composite_score:.2f}")
    if typology_assessment:
        print(f"Typology: {typology_assessment['primary_typology']}")

    return {**state, "triage_decision": triage_decision, "typology_assessment": typology_assessment}
