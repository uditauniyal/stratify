import json
import random
import os
from datetime import datetime, timedelta

# Set seed for reproducibility
random.seed(42)

def _txn(
    txn_id,
    date,
    amount,
    type,
    memo,
    currency="USD",
    channel=None,
    counterparty_name=None,
    counterparty_account=None,
    counterparty_bank=None,
    counterparty_country=None,
    branch_id=None,
    direction="inbound"
):
    """
    Helper to build a transaction dict.
    """
    return {
        "txn_id": txn_id,
        "date": date,
        "type": type,
        "amount": amount,
        "currency": currency,
        "channel": channel,
        "counterparty_name": counterparty_name,
        "counterparty_account": counterparty_account,
        "counterparty_bank": counterparty_bank,
        "counterparty_country": counterparty_country,
        "branch_id": branch_id,
        "memo": memo,
        "direction": direction
    }

def generate_scenario_1():
    """
    SCENARIO 1 — "Classic Structuring + Layering" (TRUE_POSITIVE)
    Rajesh Kumar Sharma - Import/Export
    """
    scenario_id = "SCN-001"
    customer_name = "Rajesh Kumar Sharma"
    
    # Customer Profile
    customer_profile = {
        "customer_id": "CUST-78234",
        "name": customer_name,
        "occupation": "Business Owner - Import/Export",
        "employer": "Sharma International Traders",
        "annual_income": 1200000,
        "kyc_id_type": "PAN",
        "kyc_id_value": "ABCDE1234F", # Dummy
        "account_opened_date": "2019-06-15",
        "risk_rating": "Medium",
        "address": "Pune, Maharashtra, India"
    }

    # Credit Profile
    credit_profile = {
        "score": 720,
        "total_loans": 500000,
        "credit_utilization": 0.35,
        "payment_history": "current"
    }

    # Risk Intelligence
    risk_intelligence = {
        "sanctions_hit": False,
        "pep_status": False,
        "adverse_media_hits": [],
        "prior_sars": []
    }

    # Transactions
    transactions = []
    txn_counter = 1
    
    # Baseline: Jul-Dec 2025
    start_date = datetime(2025, 7, 1)
    end_date = datetime(2025, 12, 31)
    
    known_counterparties = ["Mehta Traders", "Patel Exports", "Singh Fabrics", "Gupta Imports"]
    
    current_date = start_date
    while current_date <= end_date:
        # 8-12 inbound 
        num_inbound = random.randint(8, 12)
        for _ in range(num_inbound):
            amt = random.randint(30000, 150000)
            cp = random.choice(known_counterparties)
            day_offset = random.randint(0, 28) # simpler logic, just spread in month
            txn_date = (current_date.replace(day=1) + timedelta(days=day_offset)).isoformat().split('T')[0]
            
            transactions.append(_txn(
                txn_id=f"TXN-{txn_counter:04d}",
                date=txn_date,
                amount=amt,
                type="transfer_in",
                memo=f"Payment from {cp}",
                channel="online",
                counterparty_name=cp,
                counterparty_country="US",
                direction="inbound"
            ))
            txn_counter += 1
            
        # 3-6 outbound
        num_outbound = random.randint(3, 6)
        for _ in range(num_outbound):
            amt = random.randint(20000, 80000)
            day_offset = random.randint(0, 28)
            txn_date = (current_date.replace(day=1) + timedelta(days=day_offset)).isoformat().split('T')[0]
            
            transactions.append(_txn(
                txn_id=f"TXN-{txn_counter:04d}",
                date=txn_date,
                amount=amt,
                type="transfer_out",
                memo="Vendor Payment",
                channel="online",
                counterparty_country="US",
                direction="outbound"
            ))
            txn_counter += 1

        # Move to next month
        if current_date.month == 12:
            break
        current_date = current_date.replace(month=current_date.month+1)

    # Suspicious Period: Jan 3-10, 2026
    # 47 cash deposits
    suspicious_txns_ids = []
    branches = ["BR-PUNE-042", "BR-PUNE-017", "BR-MUM-003", "BR-DEL-011"]
    
    for i in range(1, 48):
        amt = random.randint(80000, 130000)
        day = random.randint(3, 10)
        txn_date = f"2026-01-{day:02d}"
        branch = branches[i % 4]
        cp_acc = f"ACC-UNK-{i:04d}"
        
        t = _txn(
            txn_id=f"TXN-{txn_counter:04d}",
            date=txn_date,
            amount=amt,
            type="cash_deposit",
            memo="Cash Deposit",
            channel="branch",
            branch_id=branch,
            counterparty_name="Unknown Sender",
            counterparty_account=cp_acc,
            direction="inbound"
        )
        transactions.append(t)
        suspicious_txns_ids.append(t["txn_id"])
        txn_counter += 1
        
    # Wire out
    wire_txn = _txn(
        txn_id=f"TXN-{txn_counter:04d}",
        date="2026-01-11",
        amount=4600000,
        type="wire_out",
        memo="Trade settlement",
        channel="branch",
        counterparty_name="Gulf Trading LLC",
        counterparty_bank="Emirates NBD",
        counterparty_country="AE",
        counterparty_account="ACC-DUBAI-78923",
        direction="outbound"
    )
    transactions.append(wire_txn)
    suspicious_txns_ids.append(wire_txn["txn_id"])
    txn_counter += 1

    transactions.sort(key=lambda x: x['date'])

    # Alert
    alert = {
        "alert_id": "ALT-2026-00523",
        "source": "NICE Actimize",
        "type": "structuring",
        "rule_id": "RULE-STR-001",
        "rule_description": "Multiple sub-threshold cash deposits from unique sources",
        "risk_score": 82.5,
        "generated_at": "2026-01-11T06:00:00",
        "jurisdiction": "US",
        "flagged_transaction_ids": suspicious_txns_ids
    }

    return {
        "scenario_id": scenario_id,
        "scenario_name": "Classic Structuring + Layering",
        "expected_triage": "TRUE_POSITIVE",
        "expected_typology": "structuring_with_layering",
        "customer_profile": customer_profile,
        "credit_profile": credit_profile,
        "risk_intelligence": risk_intelligence,
        "alert": alert,
        "investigator_notes": None,
        "transaction_history": transactions
    }

def generate_scenario_2():
    """
    SCENARIO 2 — "Salary Bonus False Positive"
    Priya Nair - Senior Software Engineer
    """
    scenario_id = "SCN-002"
    
    customer_profile = {
        "customer_id": "CUST-45112",
        "name": "Priya Nair",
        "occupation": "Senior Software Engineer",
        "employer": "Tata Consultancy Services",
        "annual_income": 2800000,
        "kyc_id_type": "PAN",
        "kyc_id_value": "XYZ789",
        "account_opened_date": "2018-04-10",
        "risk_rating": "Low",
        "address": "Bangalore, Karnataka, India"
    }
    
    credit_profile = {
        "score": 810,
        "total_loans": 2500000,
        "credit_utilization": 0.15,
        "payment_history": "current"
    }
    
    risk_intelligence = {
        "sanctions_hit": False,
        "pep_status": False,
        "adverse_media_hits": [],
        "prior_sars": []
    }
    
    transactions = []
    txn_counter = 1
    
    # Baseline: Jul-Dec 2025
    months = [("2025-07-31", "July Salary"), ("2025-08-31", "August Salary"), 
              ("2025-09-30", "September Salary"), ("2025-10-31", "October Salary"),
              ("2025-11-30", "November Salary"), ("2025-12-31", "December Salary")]
    
    for date_str, desc in months:
        # Salary
        transactions.append(_txn(
            txn_id=f"TXN-{txn_counter:04d}",
            date=date_str,
            amount=180000,
            type="ach_in",
            memo="Monthly Salary",
            channel="ach",
            counterparty_name="Tata Consultancy Services",
            counterparty_account="ACC-TCS-PAYROLL",
            direction="inbound"
        ))
        txn_counter += 1
        
        # Expenses
        num_exp = random.randint(5, 8)
        for _ in range(num_exp):
            amt = random.randint(5000, 40000)
            # Random date within month
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            day = random.randint(1, 28)
            txn_date = dt.replace(day=day).strftime("%Y-%m-%d")
            
            transactions.append(_txn(
                txn_id=f"TXN-{txn_counter:04d}",
                date=txn_date,
                amount=amt,
                type="pos_purchase",
                memo=random.choice(["Rent", "Groceries", "Amazon", "SIP"]),
                channel="pos",
                direction="outbound"
            ))
            txn_counter += 1

    # Last year bonus
    transactions.append(_txn(
        txn_id=f"TXN-{txn_counter:04d}",
        date="2025-01-15",
        amount=1400000,
        type="ach_in",
        memo="Annual Performance Bonus FY2024",
        channel="ach",
        counterparty_name="Tata Consultancy Services",
        counterparty_account="ACC-TCS-PAYROLL",
        direction="inbound"
    ))
    txn_counter += 1
    
    # Suspicious / Flagged Transaction
    flagged_txn = _txn(
        txn_id=f"TXN-{txn_counter:04d}",
        date="2026-01-14",
        amount=1500000,
        type="ach_in",
        memo="Annual Performance Bonus FY2025",
        channel="ach",
        counterparty_name="Tata Consultancy Services",
        counterparty_account="ACC-TCS-PAYROLL",
        direction="inbound"
    )
    transactions.append(flagged_txn)
    txn_counter += 1
    
    transactions.sort(key=lambda x: x['date'])
    
    alert = {
        "alert_id": "ALT-2026-00601",
        "source": "Transaction Monitoring",
        "type": "velocity_anomaly",
        "rule_id": "RULE-VEL-003",
        "rule_description": "Single large deposit exceeding 3x monthly average",
        "risk_score": 45.0,
        "generated_at": "2026-01-14T12:00:00",
        "jurisdiction": "US",
        "flagged_transaction_ids": [flagged_txn["txn_id"]]
    }
    
    return {
        "scenario_id": scenario_id,
        "scenario_name": "Salary Bonus False Positive",
        "expected_triage": "FALSE_POSITIVE",
        "expected_typology": None,
        "customer_profile": customer_profile,
        "credit_profile": credit_profile,
        "risk_intelligence": risk_intelligence,
        "alert": alert,
        "investigator_notes": None,
        "transaction_history": transactions
    }

def generate_scenario_3():
    """
    SCENARIO 3 — "Student Mule Account"
    Arjun Mehta - Student
    """
    scenario_id = "SCN-003"
    
    customer_profile = {
        "customer_id": "CUST-91823",
        "name": "Arjun Mehta",
        "occupation": "Student",
        "employer": None,
        "annual_income": 0,
        "kyc_id_type": "Atheer", # Aadhaar
        "kyc_id_value": "1234-5678-9012",
        "account_opened_date": "2025-10-01",
        "risk_rating": "Low",
        "address": "DU Hostel, Delhi"
    }
    
    credit_profile = {
        "score": None,
        "total_loans": 0,
        "credit_utilization": None,
        "payment_history": None
    }
    
    risk_intelligence = {
        "sanctions_hit": False,
        "pep_status": False,
        "adverse_media_hits": [],
        "prior_sars": []
    }
    
    transactions = []
    txn_counter = 1
    
    # Baseline: Nov, Dec 2025
    transactions.append(_txn(
        txn_id=f"TXN-{txn_counter:04d}",
        date="2025-11-05",
        amount=25000,
        type="ach_in",
        memo="Monthly allowance",
        channel="ach",
        counterparty_name="Family Transfer",
        counterparty_account="ACC-FAMILY-001",
        direction="inbound"
    ))
    txn_counter += 1
    
    transactions.append(_txn(
        txn_id=f"TXN-{txn_counter:04d}",
        date="2025-12-05",
        amount=25000,
        type="ach_in",
        memo="Monthly allowance",
        channel="ach",
        counterparty_name="Family Transfer",
        counterparty_account="ACC-FAMILY-001",
        direction="inbound"
    ))
    txn_counter += 1
    
    # Suspicious
    suspicious_ids = []
    
    # 12 Deposits
    letters = "ABCDEFGHIJKL"
    for i, char in enumerate(letters):
        amt = random.randint(50000, 90000)
        day = random.randint(5, 14)
        txn_date = f"2026-01-{day:02d}"
        
        t = _txn(
            txn_id=f"TXN-{txn_counter:04d}",
            date=txn_date,
            amount=amt,
            type="cash_deposit", # implied as deposits from external, could be transfers
            memo=f"Transfer from Person {char}",
            channel="branch",
            branch_id="BR-DEL-023",
            counterparty_name=f"Person {char}",
            direction="inbound"
        )
        transactions.append(t)
        suspicious_ids.append(t["txn_id"])
        txn_counter += 1
        
    # 6 Withdrawals
    atms = ["ATM-DEL-101", "ATM-DEL-205", "ATM-NOI-033"]
    for i in range(6):
        amt = random.randint(80000, 140000)
        day = random.randint(6, 16)
        txn_date = f"2026-01-{day:02d}"
        
        t = _txn(
            txn_id=f"TXN-{txn_counter:04d}",
            date=txn_date,
            amount=amt,
            type="cash_withdrawal",
            memo="ATM Withdrawal",
            channel="atm",
            branch_id=atms[i % 3],
            direction="outbound"
        )
        transactions.append(t)
        suspicious_ids.append(t["txn_id"])
        txn_counter += 1
        
    transactions.sort(key=lambda x: x['date'])
    
    alert = {
        "alert_id": "ALT-2026-00712",
        "source": "Transaction Monitoring",
        "type": "funnel_account",
        "rule_id": "RULE-FUN-001",
        "rule_description": "Multiple deposits from unique sources with rapid cash withdrawal",
        "risk_score": 78.0,
        "generated_at": "2026-01-16T18:00:00",
        "jurisdiction": "US",
        "flagged_transaction_ids": suspicious_ids
    }
    
    return {
        "scenario_id": scenario_id,
        "scenario_name": "Student Mule Account",
        "expected_triage": "TRUE_POSITIVE",
        "expected_typology": "funnel_account",
        "customer_profile": customer_profile,
        "credit_profile": credit_profile,
        "risk_intelligence": risk_intelligence,
        "alert": alert,
        "investigator_notes": None,
        "transaction_history": transactions
    }

def generate_scenario_4():
    """
    SCENARIO 4 — "Seasonal Business Spike (Diwali)"
    Deepa Patel - Retail Business Owner
    """
    scenario_id = "SCN-004"
    
    customer_profile = {
        "customer_id": "CUST-33456",
        "name": "Deepa Patel",
        "occupation": "Retail Business Owner",
        "employer": "Patel Gift Emporium",
        "annual_income": 4800000,
        "kyc_id_type": "PAN",
        "kyc_id_value": "DEEPA1234G",
        "account_opened_date": "2015-03-10",
        "risk_rating": "Low",
        "address": "Ahmedabad, Gujarat"
    }
    
    credit_profile = {
        "score": 750,
        "total_loans": 1200000,
        "credit_utilization": 0.20,
        "payment_history": "current"
    }
    
    risk_intelligence = {
        "sanctions_hit": False,
        "pep_status": False,
        "adverse_media_hits": [],
        "prior_sars": []
    }
    
    transactions = []
    txn_counter = 1
    
    # Helper to generate months
    def gen_month(year, month, is_diwali=False):
        nonlocal txn_counter
        txns = []
        num_deps = random.randint(40, 60) if is_diwali else random.randint(15, 25)
        
        for _ in range(num_deps):
            amt = random.randint(15000, 65000) if is_diwali else random.randint(10000, 40000)
            day = random.randint(1, 28)
            date_str = f"{year}-{month:02d}-{day:02d}"
            
            memo = "Diwali Sales" if is_diwali else "Sales Deposit"
            cp = "Walk-in Customer" if is_diwali else f"Customer {random.randint(1,100)}"
            
            txns.append(_txn(
                txn_id=f"TXN-{txn_counter:04d}",
                date=date_str,
                amount=amt,
                type="cash_deposit",
                memo=memo,
                channel="branch",
                branch_id="BR-AHM-008",
                counterparty_name=cp,
                direction="inbound"
            ))
            txn_counter += 1
            
        # Outbound expenses
        num_exp = random.randint(5, 10)
        for _ in range(num_exp):
            amt = random.randint(2000, 15000)
            day = random.randint(1, 28)
            date_str = f"{year}-{month:02d}-{day:02d}"
            txns.append(_txn(
               txn_id=f"TXN-{txn_counter:04d}",
               date=date_str,
               amount=amt,
               type="transfer_out",
               memo="Business Expense",
               channel="online",
               direction="outbound"
            ))
            txn_counter += 1
            
        return txns

    # Diwali 2024 (Last Year)
    transactions.extend(gen_month(2024, 10, is_diwali=True))
    transactions.extend(gen_month(2024, 11, is_diwali=True))
    
    # Normal 2025 (Apr-Sep)
    for m in range(4, 10):
        transactions.extend(gen_month(2025, m, is_diwali=False))
        
    # Diwali 2025 (This Year - Flagged)
    diwali_2025_txns = []
    diwali_2025_txns.extend(gen_month(2025, 10, is_diwali=True))
    diwali_2025_txns.extend(gen_month(2025, 11, is_diwali=True))
    transactions.extend(diwali_2025_txns)
    
    transactions.sort(key=lambda x: x['date'])
    
    # Flag all 2025 Diwali deposits
    flagged_ids = [t['txn_id'] for t in diwali_2025_txns if t['type'] == 'cash_deposit']

    alert = {
        "alert_id": "ALT-2025-04821",
        "source": "Transaction Monitoring",
        "type": "velocity_anomaly",
        "rule_id": "RULE-VEL-002",
        "rule_description": "Monthly volume exceeds 3x rolling 6-month average",
        "risk_score": 52.0,
        "generated_at": "2025-12-01T06:00:00",
        "jurisdiction": "US",
        "flagged_transaction_ids": flagged_ids
    }
    
    return {
        "scenario_id": scenario_id,
        "scenario_name": "Seasonal Business Spike (Diwali)",
        "expected_triage": "FALSE_POSITIVE",
        "expected_typology": None,
        "customer_profile": customer_profile,
        "credit_profile": credit_profile,
        "risk_intelligence": risk_intelligence,
        "alert": alert,
        "investigator_notes": None,
        "transaction_history": transactions
    }

def generate_scenario_5():
    """
    SCENARIO 5 — "Continuing Activity - Prior SAR Recurrence"
    Vikram Reddy - Consultant
    """
    scenario_id = "SCN-005"
    
    customer_profile = {
        "customer_id": "CUST-62190",
        "name": "Vikram Reddy",
        "occupation": "Consultant",
        "employer": "Reddy Consulting Pvt. Ltd.",
        "annual_income": 3600000,
        "kyc_id_type": "PAN",
        "kyc_id_value": "VIKRAM999X",
        "account_opened_date": "2017-03-22",
        "risk_rating": "High",
        "address": "Hyderabad, Telangana"
    }
    
    credit_profile = {
        "score": 680,
        "total_loans": 3500000,
        "credit_utilization": 0.60,
        "payment_history": "30_days_late",
        "inquiries": 3
    }
    
    risk_intelligence = {
        "sanctions_hit": False,
        "pep_status": False,
        "adverse_media_hits": [{
            "date": "2023-05-10",
            "source": "Local News",
            "content": "Local news article mentioning subject in connection with land deal dispute (2023)"
        }],
        "prior_sars": [{
            "dcn": "DCN-2024-11234",
            "date_filed": "2024-06-15",
            "activity_type": "Structuring",
            "amount": 3200000,
            "status": "initial"
        }],
        "internal_referrals": ["REF-2024-089: Branch manager flagged unusual cash activity"]
    }
    
    transactions = []
    txn_counter = 1
    
    # Baseline: Jul-Dec 2025
    clients = ["Client A", "Client B", "Client C"]
    for m in range(7, 13):
        num_deps = random.randint(5, 8)
        for _ in range(num_deps):
            amt = random.randint(20000, 60000)
            day = random.randint(1, 28)
            date_str = f"2025-{m:02d}-{day:02d}"
            
            transactions.append(_txn(
                txn_id=f"TXN-{txn_counter:04d}",
                date=date_str,
                amount=amt,
                type="transfer_in",
                memo="Consulting Fee",
                channel="online",
                counterparty_name=random.choice(clients),
                direction="inbound"
            ))
            txn_counter += 1
            
    # Suspicious: Jan 2026
    suspicious_ids = []
    branches = ["BR-HYD-012", "BR-HYD-045", "BR-SEC-003"]
    
    # 22 Cash deposits
    for i in range(1, 23):
        amt = random.randint(85000, 120000)
        day = random.randint(2, 20)
        date_str = f"2026-01-{day:02d}"
        
        t = _txn(
             txn_id=f"TXN-{txn_counter:04d}",
             date=date_str,
             amount=amt,
             type="cash_deposit",
             memo="Cash Deposit",
             channel="branch",
             branch_id=branches[i % 3],
             counterparty_name="New Client",
             counterparty_account=f"ACC-NEW-{i:04d}",
             direction="inbound"
        )
        transactions.append(t)
        suspicious_ids.append(t["txn_id"])
        txn_counter += 1
        
    # Wire out
    wire_t = _txn(
        txn_id=f"TXN-{txn_counter:04d}",
        date="2026-01-25",
        amount=2100000,
        type="wire_out",
        memo="Consulting fees",
        channel="branch",
        counterparty_name="Reddy Holdings International",
        counterparty_bank="Cayman National Bank",
        counterparty_country="KY",
        direction="outbound"
    )
    transactions.append(wire_t)
    suspicious_ids.append(wire_t["txn_id"])
    txn_counter += 1
    
    transactions.sort(key=lambda x: x['date'])

    alert = {
        "alert_id": "ALT-2026-00891",
        "source": "Transaction Monitoring",
        "type": "structuring",
        "rule_id": "RULE-STR-002",
        "rule_description": "Structuring pattern from subject with prior SAR filing",
        "risk_score": 91.0,
        "generated_at": "2026-01-26T09:00:00",
        "jurisdiction": "US",
        "flagged_transaction_ids": suspicious_ids
    }
    
    notes = "Subject appears to be using different branch combinations this time. Wire destination is new - Cayman Islands entity not seen in prior activity."

    return {
        "scenario_id": scenario_id,
        "scenario_name": "Continuing Activity - Prior SAR Recurrence",
        "expected_triage": "TRUE_POSITIVE",
        "expected_typology": "structuring_continuing_activity",
        "customer_profile": customer_profile,
        "credit_profile": credit_profile,
        "risk_intelligence": risk_intelligence,
        "alert": alert,
        "investigator_notes": notes,
        "transaction_history": transactions
    }

def generate_all_scenarios():
    output_dir = "data/scenarios"
    os.makedirs(output_dir, exist_ok=True)
    
    generators = [
        generate_scenario_1(),
        generate_scenario_2(),
        generate_scenario_3(),
        generate_scenario_4(),
        generate_scenario_5()
    ]
    
    for i, scenario in enumerate(generators, 1):
        filename = f"{output_dir}/scenario_{i}.json"
        with open(filename, 'w') as f:
            json.dump(scenario, f, indent=2, default=str)
        print(f"Generated {filename}")

if __name__ == "__main__":
    generate_all_scenarios()
