from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.schemas import TransactionRiskRequest


@dataclass(frozen=True)
class FeatureEngineer:
    """Builds only features observable in an individual transaction.

    Historical features are intentionally absent until a reliable transaction
    history source is introduced.
    """

    feature_names: tuple[str, ...] = ("amount", "hourOfDay", "isNightTransaction")

    def transform(self, transaction: TransactionRiskRequest) -> np.ndarray:
        hour_of_day = transaction.createdAt.hour
        is_night_transaction = int(hour_of_day < 6 or hour_of_day >= 22)
        return np.array(
            [[float(transaction.amount), float(hour_of_day), float(is_night_transaction)]],
            dtype=float,
        )

    def explanations(self, transaction: TransactionRiskRequest, high_amount_threshold: float) -> list[str]:
        reasons: list[str] = []
        if float(transaction.amount) >= high_amount_threshold:
            reasons.append("Transaction amount is unusually high relative to the demo baseline")
        if transaction.createdAt.hour < 6 or transaction.createdAt.hour >= 22:
            reasons.append("Transaction occurred during an unusual hour")
        return reasons
