from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class TransactionRiskRequest(BaseModel):
    transactionId: UUID
    sourceAccountId: UUID
    destinationAccountId: UUID
    amount: Decimal = Field(gt=Decimal("0"))
    createdAt: datetime

    @model_validator(mode="after")
    def accounts_must_be_different(self) -> "TransactionRiskRequest":
        if self.sourceAccountId == self.destinationAccountId:
            raise ValueError("sourceAccountId and destinationAccountId must be different")
        return self


class RiskAssessmentResponse(BaseModel):
    transactionId: UUID
    riskScore: float = Field(ge=0, le=100)
    riskLevel: RiskLevel
    anomaly: bool
    reasons: list[str]
    modelVersion: str
    evaluatedAt: datetime


class HealthResponse(BaseModel):
    status: str
    service: str
    modelVersion: str
