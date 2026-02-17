import streamlit as st
import json
import os
import sys
import time

# Add project root to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pipeline.graph import run_pipeline
from app.pdf_generator import create_sar_pdf

# Page Config
st.set_page_config(
    page_title="STRATIFY - SAR Pipeline",
    layout="wide",
    page_icon="🛡️"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .reportview-container {
        background: #f0f2f6;
    }
    .main .block-container {
        padding-top: 2rem;
    }
    h1 {
        color: #0f2c4c;
    }
    h2 {
        color: #1c4e80;
    }
    .stMetric {
        background-color: #ffffff;
        padding: 10px;
        border-radius: 5px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.12);
    }
</style>
""", unsafe_allow_html=True)

# -----------------
# 1. Sidebar
# -----------------
st.sidebar.title("STRATIFY")
st.sidebar.caption("SAR Authoring & Traceability Hub with Intelligent Agents")
st.sidebar.divider()

# Scenario Selection
scenarios = [
    "Scenario 1: Classic Structuring + Layering (TRUE_POSITIVE)",
    "Scenario 2: Salary Bonus (FALSE_POSITIVE)",
    "Scenario 3: Student Mule Account (TRUE_POSITIVE)",
    "Scenario 4: Seasonal Business Spike (FALSE_POSITIVE)",
    "Scenario 5: Continuing Activity - Prior SAR (TRUE_POSITIVE)"
]

selected_scenario = st.sidebar.selectbox("Select Demo Scenario", scenarios)
scenario_num = int(selected_scenario.split(":")[0].split(" ")[1])

# Run Button
if st.sidebar.button("Run Pipeline", type="primary"):
    st.session_state["run_triggered"] = True
    st.session_state["scenario_num"] = scenario_num
    st.session_state["scenario_name"] = selected_scenario

st.sidebar.divider()
st.sidebar.info("""
**Pipeline Architecture:**
1. **Ingest & Enrich**: Build dossier.
2. **Triage**: Classify & Assess Risk.
3. **Generate**: Draft Narrative (RAG).
4. **Validate**: 5W Check + Audit.
""")

# -----------------
# 2. Main Logic
# -----------------

if "run_triggered" not in st.session_state:
    st.session_state["run_triggered"] = False
    st.session_state["pipeline_result"] = None

if st.session_state["run_triggered"]:
    # Reset trigger to prevent re-runs on interaction
    st.session_state["run_triggered"] = False
    
    scenario_file = f"data/scenarios/scenario_{st.session_state['scenario_num']}.json"
    
    with st.spinner(f"Running STRATIFY pipeline on {st.session_state['scenario_name']}..."):
        try:
            # Load Data
            with open(scenario_file, "r") as f:
                case_input = json.load(f)
            
            # Execute Pipeline
            start_time = time.time()
            final_state = run_pipeline(case_input)
            end_time = time.time()
            
            # Store Result in Session State
            result = final_state.get("final_output", {})
            result["processing_time"] = round(end_time - start_time, 2)
            result["expected_triage"] = case_input.get("expected_triage")
            
            # Persist state objects for raw view
            st.session_state["pipeline_state"] = final_state
            st.session_state["pipeline_result"] = result
            
        except Exception as e:
            st.error(f"Pipeline Execution Failed: {str(e)}")
            st.code(str(e)) # Show simplified first

# -----------------
# 3. Display Results
# -----------------

if st.session_state.get("pipeline_result"):
    res = st.session_state["pipeline_result"]
    state = st.session_state["pipeline_state"]
    
    st.divider()
    
    # -----------------
    # Tabs
    # -----------------
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Overview", "SAR Narrative", "Validation", "Audit Trail", "Raw Data"])
    
    # --- TAB 1: OVERVIEW ---
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            # Triage Classification
            classification = res.get("triage_decision")
            confidence = state.get("triage_decision", {}).get("confidence", "High")
            
            delta_color = "normal"
            if classification == "TRUE_POSITIVE":
                delta_color = "off" # Streamlit delta color logic is tricky, usually green for increase. 
                # Let's just use normal metric
            
            st.metric("Triage Result", classification, delta=f"{confidence} Confidence", delta_color=delta_color)
            st.metric("Risk Score", f"{res.get('risk_score', 0):.2f}/100")
            st.metric("Processing Time", f"{res.get('processing_time')}s")
            
        with col2:
            expected = res.get("expected_triage")
            is_match = classification == expected
            match_icon = "✅" if is_match else "❌"
            
            st.metric("Expected Result", expected)
            st.metric("Match", f"{match_icon} {'Correct' if is_match else 'Mismatch'}")
            
            if res.get("typology"):
                st.metric("Identified Typology", res.get("typology"))
        
        # --- PDF Download for True Positives ---
        if classification == "TRUE_POSITIVE":
            st.markdown("---")
            pdf_bytes = create_sar_pdf(state)
            st.download_button(
                label="📄 Download SAR Report (PDF)",
                data=pdf_bytes,
                file_name=f"SAR_{state['case_input']['alert']['alert_id']}.pdf",
                mime="application/pdf",
                type="primary"
            )
            st.markdown("---")
                
        st.subheader("Triage Explanation")
        st.info(res.get("triage_explanation"))
        
        # Decision Factors
        triage_data = state.get("triage_decision", {})
        if "decision_factors" in triage_data:
            st.subheader("Decision Factors")
            for factor in triage_data["decision_factors"]:
                with st.expander(f"{factor.get('factor')} ({factor.get('direction')})"):
                    st.write(f"**Weight:** {factor.get('weight')}")
                    st.write(f"**Evidence:** {factor.get('evidence')}")

    # --- TAB 2: SAR NARRATIVE ---
    with tab2:
        narrative = res.get("sar_narrative")
        if narrative:
            st.subheader(narrative.get("title", "Suspicious Activity Report Narrative"))
            st.caption(f"Filing Type: SAR | Model: {narrative.get('generation_model')}")
            
            st.markdown("---")
            # Render Markdown Narrative
            st.markdown(narrative.get("full_narrative", ""))
            st.markdown("---")
            
            # Metrics
            m1, m2 = st.columns(2)
            m1.metric("Word Count", narrative.get("word_count"))
            m2.metric("RAG Context Chunks", narrative.get("rag_chunks_used"))
        else:
            st.info(f"No SAR narrative generated. Case classified as {res.get('triage_decision')}.")

    # --- TAB 3: VALIDATION ---
    with tab3:
        val = res.get("validation_result")
        if val:
            # Stats Headers
            s1, s2, s3, s4 = st.columns(4)
            
            status_color = "off"
            if val['overall_status'] == "PASS": status_color = "normal"
            elif val['overall_status'] == "FAIL": status_color = "inverse"
            
            s1.metric("Overall Status", val['overall_status'])
            s2.metric("Passed", val['passed'])
            s3.metric("Warnings", val['warnings'])
            s4.metric("Failed", val['failed'])
            
            st.subheader("Validation Checks (5W+How)")
            
            for check in val.get("checks", []):
                icon = "✅"
                if check['status'] == "WARN": icon = "⚠️"
                if check['status'] == "FAIL": icon = "❌"
                
                with st.expander(f"{icon} {check['check']} ({check['severity'].upper()})"):
                    st.write(f"**Status:** {check['status']}")
                    st.write(f"**Detail:** {check['detail']}")
        else:
            if res.get("triage_decision") == "TRUE_POSITIVE":
                st.warning("Validation result missing.")
            else:
                st.info("Validation skipped (No Narrative).")

    # --- TAB 4: AUDIT TRAIL ---
    with tab4:
        audit = res.get("audit_package")
        if audit:
            st.caption(f"Pipeline Version: {audit.get('pipeline_version')} | Generated: {audit.get('generated_at')}")
            
            # Agent Logs
            logs = audit.get("audit_logs", {})
            
            with st.expander("Node 1: Ingestion & Enrichment Logs"):
                st.json(logs.get("ingestion"))
                st.json(logs.get("enrichment"))
                
            with st.expander("Node 2: Triage & Typology Logs"):
                st.json(logs.get("triage"))
                st.json(logs.get("typology"))
                
            with st.expander("Node 3: Generation Logs"):
                st.json(logs.get("generation"))
                
            with st.expander("Node 4: Validation Logs"):
                st.json(logs.get("validation"))
            
            # Sentence Tracing
            traces = audit.get("traceability", [])
            if traces:
                st.subheader(f"Sentence-Level Traceability ({len(traces)} traces)")
                with st.expander("View First 5 Traces"):
                    st.json(traces[:5])
        else:
             st.info("No audit package generated.")

    # --- TAB 5: RAW DATA ---
    with tab5:
        st.warning("Debugging View")
        with st.expander("Enriched Dossier"):
            st.json(state.get("enriched_dossier"))
        with st.expander("Triage Decision"):
            st.json(state.get("triage_decision"))
        if state.get("typology_assessment"):
            with st.expander("Typology Assessment"):
                st.json(state.get("typology_assessment"))
        if state.get("draft_narrative"):
             with st.expander("Draft Narrative Metadata"):
                 # exclude full text
                 meta = {k:v for k,v in state["draft_narrative"].items() if k != "full_narrative"}
                 st.json(meta)
        
        st.write("Full State Keys:")
        st.write(list(state.keys()))

# Footer
st.divider()
st.caption("STRATIFY v0.1 | Powered by LangGraph & Google Gemini (Antigravity)")
