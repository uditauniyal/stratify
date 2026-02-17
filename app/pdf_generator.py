from fpdf import FPDF
import json
import textwrap

class SARPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Suspicious Activity Report (SAR) - STRATIFY', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')
        self.cell(0, 10, 'CONFIDENTIAL - FOR OFFICIAL USE ONLY', 0, 0, 'R')

    def chapter_title(self, label):
        self.set_font('Arial', 'B', 12)
        self.set_fill_color(200, 220, 255)
        self.cell(0, 6, label, 0, 1, 'L', 1)
        self.ln(4)

    def chapter_body(self, text):
        self.set_font('Arial', '', 11)
        self.multi_cell(0, 5, text)
        self.ln()

    def key_value_pair(self, key, value):
        self.set_font('Arial', 'B', 11)
        self.cell(50, 6, f"{key}:", 0, 0)
        self.set_font('Arial', '', 11)
        self.multi_cell(0, 6, str(value))

def create_sar_pdf(state: dict) -> bytes:
    """
    Generates a PDF SAR report from the pipeline state.
    Returns the PDF as bytes.
    """
    pdf = SARPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # --- Section 1: Alert Overview ---
    pdf.chapter_title("1. Alert & Subject Information")
    
    # Extract data safely
    case_input = state.get("case_input", {})
    alert_data = case_input.get("alert", {})
    customer = case_input.get("customer_profile", {})
    triage = state.get("triage_decision", {})
    enriched = state.get("enriched_dossier", {})
    typology_info = state.get("typology_assessment") or {}

    pdf.key_value_pair("Alert ID", alert_data.get("alert_id", "N/A"))
    pdf.key_value_pair("Customer Name", customer.get("name", "N/A"))
    pdf.key_value_pair("Customer ID", customer.get("customer_id", "N/A"))
    pdf.key_value_pair("Occupation", customer.get("occupation", "N/A"))
    pdf.ln(2)
    
    # Use composite risk score from triage, which matches the audit trail
    risk_score = triage.get("composite_risk_score", enriched.get("risk_score", 0))
    pdf.key_value_pair("Risk Score", f"{risk_score}/100")
    
    # Use primary typology from assessment
    typology = typology_info.get("primary_typology", triage.get("typology", "Unknown"))
    pdf.key_value_pair("Typology Detected", typology)
    pdf.ln(5)

    # --- Section 2: Narrative ---
    pdf.chapter_title("2. SAR Narrative")
    
    narrative = state.get("draft_narrative", {}).get("full_narrative", "No narrative generated.")
    
    # Basic markdown cleanup for PDF
    narrative_clean = narrative.replace("**", "").replace("##", "")
    pdf.chapter_body(narrative_clean)

    # --- Section 3: Validation & Quality Checks ---
    pdf.chapter_title("3. Quality Assurance Checks (5 Ws & How)")
    
    val_results = state.get("validation_result", {})
    checks = val_results.get("checks", [])
    
    pdf.set_font('Arial', 'B', 10)
    # Simple table header
    pdf.cell(140, 6, "Check Description", 1)
    pdf.cell(30, 6, "Status", 1)
    pdf.ln()
    
    pdf.set_font('Arial', '', 10)
    for check in checks:
        status = check.get("status", "FAIL")
        name = check.get("name", "Check")
        
        # Color code status
        if status == "PASS":
            pdf.set_text_color(0, 128, 0)
        elif status == "WARN":
            pdf.set_text_color(255, 165, 0)
        else:
            pdf.set_text_color(255, 0, 0)
            
        pdf.cell(140, 6, name, 1)
        pdf.cell(30, 6, status, 1)
        pdf.ln()
    
    pdf.set_text_color(0, 0, 0) # Reset color
    pdf.ln(5)

    # --- Section 4: Audit Trail (Summarized) ---
    pdf.chapter_title("4. Audit Trail Summary")
    
    audit = state.get("audit_package", {})
    
    # Add key audit metadata
    pdf.key_value_pair("Pipeline Version", audit.get("pipeline_version", "v1.0"))
    pdf.key_value_pair("Generated At", audit.get("generated_at", "Unknown"))
    pdf.ln(2)
    
    # Add risk factors from Triage
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 6, "Risk Factors Identified:", 0, 1)
    pdf.set_font('Arial', '', 10)
    
    factors = triage.get("decision_factors", [])
    for factor in factors:
        factor_text = f"- {factor.get('factor')} ({factor.get('direction')})"
        pdf.cell(0, 5, factor_text, 0, 1)

    # Return PDF as bytes
    return pdf.output(dest='S').encode('latin-1')
