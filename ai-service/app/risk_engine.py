from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

from app.feature_engineering import FeatureEngineer
from app.schemas import RiskAssessmentResponse, RiskLevel, TransactionRiskRequest

LOGGER = logging.getLogger(__name__)

MODEL_VERSION = "isolation-forest-v1"
RANDOM_STATE = 42
LOW_RISK_MAX = 34.0
MEDIUM_RISK_MAX = 64.0


class RiskEngine:
    """Demo-only anomaly scoring based on a synthetic, reproducible baseline.

    IsolationForest does not provide causal explanations or fraud probabilities.
    Explanations below are derived independently from observable input features.
    """

    def __init__(
        self,
        model: IsolationForest,
        score_floor: float,
        score_ceiling: float,
        high_amount_threshold: float,
    ) -> None:
        self._model = model
        self._score_floor = score_floor
        self._score_ceiling = score_ceiling
        self._high_amount_threshold = high_amount_threshold
        self._feature_engineer = FeatureEngineer()

    @classmethod
    def load_or_train_demo_model(cls, artifact_path: Path) -> "RiskEngine":
        if artifact_path.exists():
            LOGGER.info("Loading demo risk model from %s", artifact_path)
            artifact = joblib.load(artifact_path)
            return cls(**artifact)

        LOGGER.info("Training DEMO MODEL with reproducible synthetic transaction data")
        training_data, normal_amounts = cls._generate_demo_training_data()
        model = IsolationForest(contamination=0.05, random_state=RANDOM_STATE, n_estimators=200)
        model.fit(training_data)

        anomaly_measure = -model.score_samples(training_data)
        artifact = {
            "model": model,
            "score_floor": float(np.quantile(anomaly_measure, 0.05)),
            "score_ceiling": float(np.quantile(anomaly_measure, 0.95)),
            "high_amount_threshold": float(np.quantile(normal_amounts, 0.95)),
        }
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(artifact, artifact_path)
        LOGGER.info("Saved demo risk model to %s", artifact_path)
        return cls(**artifact)

    @staticmethod
    def _generate_demo_training_data() -> tuple[np.ndarray, np.ndarray]:
        """Create deterministic synthetic data only to demonstrate the ML pipeline."""
        random = np.random.default_rng(RANDOM_STATE)

        normal_amounts = np.clip(random.lognormal(mean=4.2, sigma=0.45, size=950), 5, 500)
        normal_hours = random.integers(8, 20, size=950)
        normal_night = np.zeros(950)

        unusual_amounts = np.clip(random.lognormal(mean=7.4, sigma=0.35, size=50), 800, 5000)
        unusual_hours = random.choice(np.array([0, 1, 2, 3, 4, 5, 22, 23]), size=50)
        unusual_night = np.ones(50)

        amounts = np.concatenate((normal_amounts, unusual_amounts))
        hours = np.concatenate((normal_hours, unusual_hours))
        night_flags = np.concatenate((normal_night, unusual_night))
        return np.column_stack((amounts, hours, night_flags)), normal_amounts

    def assess(self, transaction: TransactionRiskRequest) -> RiskAssessmentResponse:
        features = self._feature_engineer.transform(transaction)
        anomaly_measure = float(-self._model.score_samples(features)[0])
        risk_score = self._to_risk_score(anomaly_measure)
        anomaly = bool(self._model.predict(features)[0] == -1)
        risk_level = self._risk_level(risk_score)

        reasons = self._feature_engineer.explanations(transaction, self._high_amount_threshold)
        if anomaly and not reasons:
            reasons.append("The demo model found an unusual combination of amount and transaction hour")
        if not reasons:
            reasons.append("Transaction is consistent with the expected demo behavior")

        return RiskAssessmentResponse(
            transactionId=transaction.transactionId,
            riskScore=risk_score,
            riskLevel=risk_level,
            anomaly=anomaly,
            reasons=reasons,
            modelVersion=MODEL_VERSION,
            evaluatedAt=datetime.now(timezone.utc),
        )

    def _to_risk_score(self, anomaly_measure: float) -> float:
        """Maps demo baseline anomaly measures to 0-100; it is not a probability."""
        score_range = self._score_ceiling - self._score_floor
        if score_range <= 0:
            return 50.0
        normalized = (anomaly_measure - self._score_floor) / score_range
        return round(float(np.clip(normalized * 100, 0, 100)), 2)

    @staticmethod
    def _risk_level(risk_score: float) -> RiskLevel:
        if risk_score <= LOW_RISK_MAX:
            return RiskLevel.LOW
        if risk_score <= MEDIUM_RISK_MAX:
            return RiskLevel.MEDIUM
        return RiskLevel.HIGH
