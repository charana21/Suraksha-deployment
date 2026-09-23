"""
Evaluation metrics
"""
import numpy as np
from typing import List

def calculate_mae(predictions: List[float], targets: List[float]) -> float:
    """Mean Absolute Error"""
    return np.mean(np.abs(np.array(predictions) - np.array(targets)))


def calculate_mse(predictions: List[float], targets: List[float]) -> float:
    """Mean Squared Error"""
    return np.mean((np.array(predictions) - np.array(targets)) ** 2)


def calculate_rmse(predictions: List[float], targets: List[float]) -> float:
    """Root Mean Squared Error"""
    return np.sqrt(calculate_mse(predictions, targets))


def calculate_mape(predictions: List[float], targets: List[float]) -> float:
    """Mean Absolute Percentage Error"""
    return np.mean([
        abs(p - t) / max(t, 1) * 100
        for p, t in zip(predictions, targets)
    ])
