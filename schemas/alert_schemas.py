"""
STRATIFY - Alert & Input Data Schemas
All Pydantic models for raw alert data, transactions, KYC, and risk intelligence.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, date
from enum import Enum


class AlertType(str, Enum):
    STRUCTURING = "structuring"
    VELOCITY = "velocity_anomaly"
    GEOGRAPHIC = "geographic_risk"
    COUNTERPARTY = "counterparty_concentration"
    DORMANT_REACTIVATION = "dormant_reactivation"
    ROUND_TRIP = "round_trip"
    FUNNEL = "funnel_account"


class Jurisdiction(str, Enum):
    US = "US"
    IN = "IN"
    UK = "UK"


class RiskRating(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    PEP = "PEP"


class Transaction(BaseModel):
    txn_id: str
    date: datetime
    type: str = Field(description="deposit, withdrawal, wire_in, wire_out, ach_in, ach_out, cash_deposit, cash_withdrawal, internal_transfer")
    amount: float
    currency: str = "USD"
    channel: str = Field(description="branch, online, atm, mobile, wire")
    counterparty_name: Optional[str] = None
    counterparty_account: Optional[str] = None
    counterparty_bank: Optional[str] = None
    counterparty_country: Optional[str] = None
    branch_id: Optional[str] = None
    memo: Optional[str] = None
    direction: str = Field(description="inbound or outbound")


class CustomerProfile(BaseModel):
    customer_id: str
    full_name: str
    dob: date
    id_type: str
    id_number: str
    occupation: str
    employer: Optional[str] = None
    annual_income: float
    source_of_funds: str
    account_open_date: date
    customer_risk_rating: RiskRating
    last_kyc_refresh: date
    related_accounts: List[str] = []
    address: str = ""
    phone: str = ""
    email: str = ""


class CreditProfile(BaseModel):
    customer_id: str
    credit_score: Optional[int] = None
    outstanding_loans: float = 0.0
    credit_card_utilization: Optional[float] = None
    recent_credit_inquiries: int = 0
    payment_history: str = "current"


class PriorSAR(BaseModel):
    dcn: str
    filed_date: date
    activity_type: str
    amount_involved: float
    status: str = "initial"


class RiskIntelligence(BaseModel):
    customer_id: str
    sanctions_hits: List[str] = []
    pep_status: bool = False
    adverse_media_hits: List[str] = []
    prior_sars: List[PriorSAR] = []
    law_enforcement_requests: int = 0
    internal_referrals: List[str] = []


class RawAlert(BaseModel):
    alert_id: str
    source_system: str
    alert_type: AlertType
    triggered_rule: str
    customer_id: str
    account_ids: List[str]
    flagged_transaction_ids: List[str]
    risk_score: float = Field(ge=0, le=100)
    generated_at: datetime
    jurisdiction: Jurisdiction = Jurisdiction.US


class CaseInput(BaseModel):
    """Complete case input combining alert with all supporting data."""
    alert: RawAlert
    customer_profile: CustomerProfile
    transaction_history: List[Transaction]
    credit_profile: Optional[CreditProfile] = None
    risk_intelligence: Optional[RiskIntelligence] = None
    investigator_notes: Optional[str] = None