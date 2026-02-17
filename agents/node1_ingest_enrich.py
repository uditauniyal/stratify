from datetime import datetime
from typing import Dict, Any, List, Tuple
from collections import defaultdict

def compute_behavioral_baseline(transactions: List[Dict], alert_date_str: str) -> Dict:
    """
    Compute baseline metrics from transactions BEFORE the alert month.
    """
    try:
        # Handle ISO format with Z
        alert_date = datetime.fromisoformat(alert_date_str.replace("Z", "+00:00"))
    except ValueError:
        # Fallback if parsing fails, though ISO is expected
        alert_date = datetime.now()

    alert_year = alert_date.year
    alert_month = alert_date.month

    baseline_txns = []
    for t in transactions:
        try:
            t_date = datetime.fromisoformat(t["date"].replace("Z", "+00:00"))
            # Filter for BEFORE alert month
            if t_date.year < alert_year or (t_date.year == alert_year and t_date.month < alert_month):
                baseline_txns.append(t)
        except (ValueError, KeyError):
            continue

    if not baseline_txns:
        return {
            "avg_monthly_inflow": 0.0,
            "avg_monthly_outflow": 0.0,
            "avg_txn_count_per_month": 0,
            "usual_counterparties": [],
            "usual_geographies": [],
            "usual_channels": [],
            "baseline_period": "No baseline data",
            "max_single_txn": 0.0
        }

    # Group by month string "YYYY-MM"
    monthly_stats = defaultdict(lambda: {"inflow": 0.0, "outflow": 0.0, "count": 0})
    
    usual_counterparties = set()
    usual_geographies = set()
    usual_channels = set()
    max_txn = 0.0
    
    start_date = None
    end_date = None

    for t in baseline_txns:
        t_date = datetime.fromisoformat(t["date"].replace("Z", "+00:00"))
        if start_date is None or t_date < start_date:
            start_date = t_date
        if end_date is None or t_date > end_date:
            end_date = t_date

        month_key = f"{t_date.year}-{t_date.month:02d}"
        amount = float(t.get("amount", 0.0))
        
        if amount > max_txn:
            max_txn = amount

        if t.get("direction") == "inbound":
            monthly_stats[month_key]["inflow"] += amount
        else:
            monthly_stats[month_key]["outflow"] += amount
            
        monthly_stats[month_key]["count"] += 1
        
        if t.get("counterparty_name"):
            usual_counterparties.add(t["counterparty_name"])
        if t.get("counterparty_country"):
            usual_geographies.add(t["counterparty_country"])
        if t.get("channel"):
            usual_channels.add(t["channel"])

    num_months = len(monthly_stats) if monthly_stats else 1
    
    total_inflow = sum(m["inflow"] for m in monthly_stats.values())
    total_outflow = sum(m["outflow"] for m in monthly_stats.values())
    total_count = sum(m["count"] for m in monthly_stats.values())

    period_str = ""
    if start_date and end_date:
        period_str = f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"

    return {
        "avg_monthly_inflow": round(total_inflow / num_months, 2),
        "avg_monthly_outflow": round(total_outflow / num_months, 2),
        "avg_txn_count_per_month": int(total_count / num_months),
        "usual_counterparties": list(usual_counterparties),
        "usual_geographies": list(usual_geographies),
        "usual_channels": list(usual_channels),
        "baseline_period": period_str,
        "max_single_txn": max_txn
    }

def compute_deviation_analysis(transactions: List[Dict], baseline: Dict, flagged_ids: List[str]) -> Dict:
    """
    Compare flagged transactions against baseline metrics.
    """
    flagged_txns = [t for t in transactions if t["txn_id"] in flagged_ids]
    
    flagged_inflow = sum(float(t["amount"]) for t in flagged_txns if t.get("direction") == "inbound")
    flagged_outflow = sum(float(t["amount"]) for t in flagged_txns if t.get("direction") != "inbound")
    flagged_total_vol = flagged_inflow + flagged_outflow
    
    baseline_inflow = baseline.get("avg_monthly_inflow", 0.0)
    baseline_outflow = baseline.get("avg_monthly_outflow", 0.0)
    baseline_total_vol = baseline_inflow + baseline_outflow
    
    if baseline_total_vol > 0:
        volume_deviation_factor = round(flagged_total_vol / baseline_total_vol, 1)
    else:
        volume_deviation_factor = 999.0 if flagged_total_vol > 0 else 0.0

    usual_cps = set(baseline.get("usual_counterparties", []))
    usual_geos = set(baseline.get("usual_geographies", []))
    usual_chans = set(baseline.get("usual_channels", []))
    
    new_counterparties = set()
    new_geographies = set()
    new_channels = set()
    
    start_date = None
    end_date = None

    for t in flagged_txns:
        if t.get("counterparty_name") and t["counterparty_name"] not in usual_cps:
            new_counterparties.add(t["counterparty_name"])
        if t.get("counterparty_country") and t["counterparty_country"] not in usual_geos:
            new_geographies.add(t["counterparty_country"])
        if t.get("channel") and t["channel"] not in usual_chans:
            new_channels.add(t["channel"])
            
        try:
            t_date = datetime.fromisoformat(t["date"].replace("Z", "+00:00"))
            if start_date is None or t_date < start_date:
                start_date = t_date
            if end_date is None or t_date > end_date:
                end_date = t_date
        except:
            pass
            
    # Velocity spike check
    velocity_spike = False
    flagged_count = len(flagged_txns)
    baseline_avg_count = baseline.get("avg_txn_count_per_month", 0)
    
    if start_date and end_date:
        span_days = (end_date - start_date).days + 1
        if span_days < 1: span_days = 1
        
        # Normalize baseline to daily * span
        expected_for_span = (baseline_avg_count / 30.0) * span_days
        
        # 3x threshold
        if flagged_count > (expected_for_span * 3) and flagged_count > 5:
            velocity_spike = True
            
    # Build summary
    summary_parts = []
    if volume_deviation_factor > 2.0:
        summary_parts.append(f"Volume is {volume_deviation_factor}x baseline")
    if velocity_spike:
        summary_parts.append("Significant velocity spike detected")
    if new_counterparties:
        summary_parts.append(f"{len(new_counterparties)} new counterparties")
    if new_geographies:
        summary_parts.append(f"New geographies: {', '.join(list(new_geographies)[:3])}")
        
    deviation_summary = "; ".join(summary_parts) if summary_parts else "No significant deviation"

    return {
        "volume_deviation_factor": volume_deviation_factor,
        "velocity_spike": velocity_spike,
        "new_counterparties_count": len(new_counterparties),
        "new_geographies": list(new_geographies),
        "new_channels": list(new_channels),
        "deviation_summary": deviation_summary,
        "flagged_txn_count": len(flagged_txns)
    }

def compute_cross_source_risk(case_input: Dict) -> Tuple[float, List[Dict]]:
    """
    Aggregate risk score from all sources (0-100).
    """
    score = 0.0
    factors = []
    
    risk_intel = case_input.get("risk_intelligence") or {}
    alert = case_input.get("alert") or {}
    credit = case_input.get("credit_profile") or {}
    customer = case_input.get("customer_profile") or {}
    notes = case_input.get("investigator_notes")
    
    # 1. Sanctions (+40)
    if risk_intel.get("sanctions_hits"):
        score += 40
        factors.append({"factor": "Sanctions Hit", "source": "Risk Intel", "severity": "high", "detail": f"Hits: {len(risk_intel['sanctions_hits'])}"})

    # 2. PEP (+15)
    if risk_intel.get("pep_status"):
        score += 15
        factors.append({"factor": "PEP Status", "source": "Risk Intel", "severity": "high", "detail": "Subject is PEP"})

    # 3. Adverse Media (+10)
    if risk_intel.get("adverse_media_hits"):
        score += 10
        factors.append({"factor": "Adverse Media", "source": "Risk Intel", "severity": "medium", "detail": f"Hits: {len(risk_intel['adverse_media_hits'])}"})

    # 4. Prior SARs (+20)
    prior_sars = risk_intel.get("prior_sars", [])
    if prior_sars:
        score += 20
        most_recent = prior_sars[0] # Assume list, take first
        detail = "Prior SAR history found"
        if isinstance(most_recent, dict):
             detail = f"Prior SAR {most_recent.get('dcn', 'N/A')}"
        factors.append({"factor": "Prior SARs", "source": "Risk Intel", "severity": "high", "detail": detail})

    # 5. LE Requests (+15)
    if risk_intel.get("law_enforcement_requests", 0) > 0:
        score += 15
        factors.append({"factor": "LE Request", "source": "Risk Intel", "severity": "high", "detail": "Law enforcement inquiry on file"})

    # 6. Credit Deterioration (+5)
    history = credit.get("payment_history", "current")
    if history and history != "current":
        score += 5
        factors.append({"factor": "Credit Deterioration", "source": "Credit Bureau", "severity": "low", "detail": f"Status: {history}"})

    # 7. High Utilization (+3)
    util = credit.get("credit_card_utilization")
    if util and util > 0.80:
        score += 3
        factors.append({"factor": "High Utilization", "source": "Credit Bureau", "severity": "low", "detail": f"Utilization: {util:.2%}"})
        
    # 8. Internal Referrals (+10)
    if risk_intel.get("internal_referrals"):
        score += 10
        factors.append({"factor": "Internal Referral", "source": "Internal", "severity": "medium", "detail": "Referral on file"})
        
    # 9. Alert Risk Score (15%)
    alert_risk = float(alert.get("risk_score", 0))
    if alert_risk > 0:
        added_risk = alert_risk * 0.15
        score += added_risk
        # factors.append({"factor": "Alert Risk", "source": "TMS", "severity": "variable", "detail": f"Base score: {alert_risk}"})

    # 10. Notes Present (+5)
    if notes:
        score += 5
        factors.append({"factor": "Investigator Notes", "source": "Human", "severity": "medium", "detail": "Manual notes present"})

    # 11. Customer Risk Rating High (+8)
    rating = customer.get("risk_rating") # raw dict key, might be 'customer_risk_rating' in schema but 'risk_rating' in json? 
    # Check JSON structure: customer_profile has "risk_rating" in synth gen. Schema has customer_risk_rating. 
    # The helper says "risk_rating" in prompt. Let's check both or just 'risk_rating' from raw dict.
    if rating == "High" or customer.get("customer_risk_rating") == "High":
        score += 8
        factors.append({"factor": "High Risk Customer", "source": "KYC", "severity": "medium", "detail": "Rated High"})

    return min(score, 100.0), factors

def deduplicate_transactions(transactions: List[Dict]) -> Tuple[List[Dict], int, int]:
    seen_ids = set()
    deduped = []
    dupes_count = 0
    quarantined_count = 0
    
    for t in transactions:
        tid = t.get("txn_id")
        if not tid:
            quarantined_count += 1
            continue
            
        if tid in seen_ids:
            dupes_count += 1
            continue
            
        if not t.get("date") or t.get("amount") is None:
            quarantined_count += 1
            continue
            
        seen_ids.add(tid)
        deduped.append(t)
        
    return deduped, dupes_count, quarantined_count

def node1_ingest_enrich(state: Dict[str, Any]) -> Dict[str, Any]:
    print("[Node 1] Ingesting and enriching case data...")
    
    case_input = state.get("case_input", {})
    alert = case_input.get("alert", {})
    customer = case_input.get("customer_profile", {})
    raw_txns = case_input.get("transaction_history", [])
    
    # 1. Deduplicate
    txns, dupes, quarantined = deduplicate_transactions(raw_txns)
    
    # 2. Get Alert Info
    alert_date_str = alert.get("generated_at", datetime.now().isoformat())
    flagged_ids = alert.get("flagged_transaction_ids", [])
    
    # 3. Behavioral Baseline
    baseline = compute_behavioral_baseline(txns, alert_date_str)
    
    # 4. Deviation Analysis
    deviations = compute_deviation_analysis(txns, baseline, flagged_ids)
    
    # 5. Cross Source Risk
    risk_score, risk_factors = compute_cross_source_risk(case_input)

    # Build Dossier
    enriched_dossier = {
        "unified_alert_id": alert.get("alert_id"),
        "customer_id": customer.get("customer_id"),
        "customer_name": customer.get("name"), # Synth gen uses 'name'
        "account_ids": alert.get("account_ids", []),
        "jurisdiction": alert.get("jurisdiction", "US"),
        "behavioral_baseline": baseline,
        "deviation_analysis": deviations,
        "cross_source_risk_score": risk_score,
        "risk_factors": risk_factors,
        
        # Booleans
        "has_prior_sars": len(case_input.get("risk_intelligence", {}).get("prior_sars", [])) > 0,
        "prior_sar_count": len(case_input.get("risk_intelligence", {}).get("prior_sars", [])),
        "is_pep": case_input.get("risk_intelligence", {}).get("pep_status", False),
        "has_sanctions_hits": len(case_input.get("risk_intelligence", {}).get("sanctions_hits", [])) > 0,
        "has_adverse_media": len(case_input.get("risk_intelligence", {}).get("adverse_media_hits", [])) > 0,
        
        "enrichment_timestamp": datetime.utcnow().isoformat(),
        "sources_consulted": ["TMS", "KYC", "Credit Bureau", "Watchlist", "Internal History"],
        "data_quality_score": 100.0 * (len(txns) / (len(raw_txns) if raw_txns else 1)),
        "transactions_validated": len(txns),
        "transactions_quarantined": quarantined,
        "duplicates_removed": dupes
    }
    
    # Print status
    print(f"Alert ID: {alert.get('alert_id')}")
    print(f"Customer: {customer.get('name')}")
    print(f"Txn Count: {len(txns)} (Dupes: {dupes}, Quar: {quarantined})")
    print(f"Baseline Avg Inflow: ${baseline.get('avg_monthly_inflow', 0):,.2f}")
    print(f"Deviation Factor: {deviations.get('volume_deviation_factor')}x")
    print(f"Risk Score: {risk_score}/100")

    return {**state, "enriched_dossier": enriched_dossier}
