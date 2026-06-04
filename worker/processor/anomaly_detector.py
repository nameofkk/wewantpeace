"""Anomaly detection using Welford's online algorithm.

Maintains per-country streaming statistics (mean, variance) over a rolling window.
Detects anomalies when current tension significantly deviates from baseline.

Note: Requires ~90 days of hourly data (MIN_SAMPLES) to be meaningful.
Before that, detection is disabled (z_score returns 0.0).

Integration: called inline from tension_calculator.calculate_country_tension()
after final raw_score is computed. Lightweight -- just Redis get/set per country.
No separate beat schedule needed.
"""
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ~90 days of 1-hour samples (minimum for meaningful detection)
# Tension is calculated every 5 minutes, so 90 * 24 * 12 = 25920 at 5-min intervals.
# Using hourly granularity for baseline stability: 90 * 24 = 2160 samples.
MIN_SAMPLES = 90 * 24

# Standard deviations threshold for anomaly detection
Z_SCORE_THRESHOLD = 2.5


class WelfordState:
    """Streaming mean/variance using Welford's online algorithm.

    Maintains running count, mean, and M2 (sum of squared deviations)
    for numerically stable variance computation in a single pass.
    """

    def __init__(self, count: int = 0, mean: float = 0.0, m2: float = 0.0):
        self.count = count
        self.mean = mean
        self.m2 = m2

    def update(self, value: float) -> None:
        """Add a new observation to the running statistics."""
        self.count += 1
        delta = value - self.mean
        self.mean += delta / self.count
        delta2 = value - self.mean
        self.m2 += delta * delta2

    @property
    def variance(self) -> float:
        """Sample variance (Bessel's correction)."""
        if self.count < 2:
            return 0.0
        return self.m2 / (self.count - 1)

    @property
    def stddev(self) -> float:
        """Sample standard deviation."""
        return self.variance ** 0.5

    def z_score(self, value: float) -> float:
        """Compute z-score for a value against the accumulated baseline.

        Returns 0.0 if insufficient samples or near-zero stddev.
        """
        if self.count < MIN_SAMPLES or self.stddev < 0.01:
            return 0.0
        return (value - self.mean) / self.stddev

    def to_dict(self) -> dict:
        """Serialize state for Redis storage."""
        return {"count": self.count, "mean": self.mean, "m2": self.m2}

    @classmethod
    def from_dict(cls, d: dict) -> "WelfordState":
        """Deserialize state from Redis storage."""
        return cls(
            count=d.get("count", 0),
            mean=d.get("mean", 0.0),
            m2=d.get("m2", 0.0),
        )


async def update_baseline_and_detect(
    redis,
    country_code: str,
    current_tension: float,
) -> Optional[float]:
    """Update Welford baseline for a country and return z-score if anomalous.

    Reads/writes state from Redis key: anomaly:baseline:{country_code}

    Args:
        redis: async Redis client (from backend.app.core.redis.get_redis())
        country_code: ISO 3166-1 alpha-2 country code
        current_tension: current raw_score for the country

    Returns:
        z-score (float) if |z| > Z_SCORE_THRESHOLD, else None.
    """
    key = f"anomaly:baseline:{country_code}"
    raw = await redis.get(key)

    if raw:
        state = WelfordState.from_dict(json.loads(raw))
    else:
        state = WelfordState()

    # Compute z-score BEFORE updating (compare against existing baseline)
    z = state.z_score(current_tension)

    # Update baseline with current observation
    state.update(current_tension)

    # Persist to Redis (no TTL -- baseline accumulates indefinitely)
    await redis.set(key, json.dumps(state.to_dict()))

    if abs(z) > Z_SCORE_THRESHOLD:
        logger.warning(
            "Anomaly detected: %s tension=%.1f z=%.2f (mean=%.1f std=%.1f samples=%d)",
            country_code,
            current_tension,
            z,
            state.mean,
            state.stddev,
            state.count,
        )
        return z
    return None
