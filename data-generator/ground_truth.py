"""
Ground Truth State Machine for Telara Biometric Data Generation.

Maintains a single evolving physiological state that all sources observe.
This ensures consistent data across Apple, Google, and Oura at similar timestamps.

Key Features:
- Smooth random walk evolution of physiological parameters
- Circadian rhythm adjustments based on time of day
- Anomaly injection affects all sources via ground truth
- Thread-safe singleton per user
"""

import math
import random
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any

from schemas import NORMAL_RANGES, ANOMALY_PATTERNS


@dataclass
class PhysiologicalState:
    """
    Represents the user's true physiological state at a moment in time.
    
    All health data sources observe this state with their own noise/accuracy.
    """
    timestamp: str
    heart_rate: float
    hrv_ms: float
    spo2_percent: float
    skin_temp_c: float
    respiratory_rate: float
    activity_level: float
    steps_per_minute: float
    calories_per_minute: float
    sleep_quality: float  # 0-100 readiness/quality score
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for sampling."""
        return {
            "timestamp": self.timestamp,
            "heart_rate": self.heart_rate,
            "hrv_ms": self.hrv_ms,
            "spo2_percent": self.spo2_percent,
            "skin_temp_c": self.skin_temp_c,
            "respiratory_rate": self.respiratory_rate,
            "activity_level": self.activity_level,
            "steps_per_minute": self.steps_per_minute,
            "calories_per_minute": self.calories_per_minute,
            "sleep_quality": self.sleep_quality,
        }


class GroundTruthState:
    """
    State machine that maintains and evolves the ground truth physiological state.
    
    Uses random walk with mean reversion for smooth, realistic evolution.
    Applies circadian rhythm adjustments based on time of day.
    """
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self._lock = threading.Lock()
        
        # Current state values (start at midpoint of normal ranges)
        self._heart_rate = (NORMAL_RANGES["heart_rate"][0] + NORMAL_RANGES["heart_rate"][1]) / 2
        self._hrv_ms = (NORMAL_RANGES["hrv_ms"][0] + NORMAL_RANGES["hrv_ms"][1]) / 2
        self._spo2_percent = 98.0
        self._skin_temp_c = 36.5
        self._respiratory_rate = 14.0
        self._activity_level = 10.0
        self._steps_per_minute = 0.0
        self._calories_per_minute = 1.2
        self._sleep_quality = 75.0
        
        # Last update time for smooth evolution
        self._last_update = time.time()
        
        # Anomaly state
        self._anomaly_type: Optional[str] = None
        self._anomaly_end_time: Optional[float] = None
        
        # Baseline "personality" for this user (slight individual variation)
        self._baseline_hr_offset = random.uniform(-5, 5)
        self._baseline_hrv_offset = random.uniform(-5, 5)
        self._baseline_temp_offset = random.uniform(-0.2, 0.2)
    
    def _clamp(self, value: float, min_val: float, max_val: float) -> float:
        """Clamp value to range."""
        return max(min_val, min(max_val, value))
    
    def _random_walk(self, current: float, target: float, volatility: float, dt: float) -> float:
        """
        Random walk with mean reversion.
        
        Args:
            current: Current value
            target: Target value to revert towards
            volatility: How much random variation per second
            dt: Time step in seconds
        """
        # Mean reversion component
        reversion_strength = 0.1
        reversion = reversion_strength * (target - current) * dt
        
        # Random walk component
        noise = random.gauss(0, volatility * math.sqrt(dt))
        
        return current + reversion + noise
    
    def _get_circadian_adjustments(self, hour: int) -> Dict[str, float]:
        """
        Get circadian rhythm adjustments based on hour of day.
        
        Returns multipliers/offsets for each metric.
        """
        adjustments = {
            "heart_rate": 0,
            "hrv_ms": 0,
            "activity_level": 0,
            "sleep_quality": 0,
        }
        
        # Deep night (2-5 AM) - lowest HR, highest HRV
        if 2 <= hour <= 5:
            adjustments["heart_rate"] = -12
            adjustments["hrv_ms"] = 15
            adjustments["activity_level"] = -8
            adjustments["sleep_quality"] = 10
        
        # Early morning (6-8 AM) - waking up
        elif 6 <= hour <= 8:
            adjustments["heart_rate"] = -5
            adjustments["hrv_ms"] = 5
            adjustments["activity_level"] = 5
        
        # Mid-morning (9-11 AM) - peak alertness
        elif 9 <= hour <= 11:
            adjustments["heart_rate"] = 3
            adjustments["hrv_ms"] = 0
            adjustments["activity_level"] = 10
        
        # Post-lunch (12-14 PM) - slight dip
        elif 12 <= hour <= 14:
            adjustments["heart_rate"] = 5
            adjustments["hrv_ms"] = -5
            adjustments["activity_level"] = 0
        
        # Afternoon (15-17 PM) - second wind
        elif 15 <= hour <= 17:
            adjustments["heart_rate"] = 5
            adjustments["activity_level"] = 8
        
        # Evening (18-20 PM) - exercise window for many
        elif 18 <= hour <= 20:
            adjustments["heart_rate"] = 8
            adjustments["hrv_ms"] = -8
            adjustments["activity_level"] = 15
        
        # Night wind-down (21-23 PM)
        elif 21 <= hour <= 23:
            adjustments["heart_rate"] = -5
            adjustments["hrv_ms"] = 5
            adjustments["activity_level"] = -5
        
        # Late night (0-1 AM)
        else:
            adjustments["heart_rate"] = -8
            adjustments["hrv_ms"] = 10
            adjustments["activity_level"] = -7
        
        return adjustments
    
    def _apply_anomaly(self) -> Dict[str, tuple]:
        """Get anomaly overrides if active, otherwise empty dict."""
        if not self._anomaly_type or not self._anomaly_end_time:
            return {}
        
        if time.time() > self._anomaly_end_time:
            print(f"✓ Anomaly '{self._anomaly_type}' ended.")
            self._anomaly_type = None
            self._anomaly_end_time = None
            return {}
        
        return ANOMALY_PATTERNS.get(self._anomaly_type, {})
    
    def _evolve_state(self):
        """Evolve the physiological state based on time elapsed."""
        current_time = time.time()
        dt = current_time - self._last_update
        
        # Cap dt to prevent huge jumps after long pauses
        dt = min(dt, 5.0)
        
        if dt < 0.05:  # Skip if less than 50ms
            return
        
        # Get current hour for circadian adjustments
        now = datetime.now(timezone.utc)
        hour = now.hour
        circadian = self._get_circadian_adjustments(hour)
        
        # Get anomaly overrides
        anomaly_ranges = self._apply_anomaly()
        
        # Target values (normal ranges + circadian + user baseline)
        hr_target = 70 + circadian["heart_rate"] + self._baseline_hr_offset
        hrv_target = 55 + circadian["hrv_ms"] + self._baseline_hrv_offset
        activity_target = 10 + circadian["activity_level"]
        
        # Apply anomaly targets if active
        if "heart_rate" in anomaly_ranges:
            hr_range = anomaly_ranges["heart_rate"]
            hr_target = (hr_range[0] + hr_range[1]) / 2
        
        if "hrv_ms" in anomaly_ranges:
            hrv_range = anomaly_ranges["hrv_ms"]
            hrv_target = (hrv_range[0] + hrv_range[1]) / 2
        
        if "spo2_percent" in anomaly_ranges:
            spo2_range = anomaly_ranges["spo2_percent"]
            self._spo2_percent = random.uniform(spo2_range[0], spo2_range[1])
        
        if "skin_temp_c" in anomaly_ranges:
            temp_range = anomaly_ranges["skin_temp_c"]
            self._skin_temp_c = random.uniform(temp_range[0], temp_range[1])
        
        if "activity_level" in anomaly_ranges:
            act_range = anomaly_ranges["activity_level"]
            activity_target = (act_range[0] + act_range[1]) / 2
        
        # Evolve each metric with random walk + mean reversion
        self._heart_rate = self._random_walk(self._heart_rate, hr_target, 2.0, dt)
        self._heart_rate = self._clamp(self._heart_rate, 45, 180)
        
        self._hrv_ms = self._random_walk(self._hrv_ms, hrv_target, 3.0, dt)
        self._hrv_ms = self._clamp(self._hrv_ms, 10, 120)
        
        # SpO2 is very stable unless anomaly
        if "spo2_percent" not in anomaly_ranges:
            self._spo2_percent = self._random_walk(self._spo2_percent, 98, 0.2, dt)
            self._spo2_percent = self._clamp(self._spo2_percent, 94, 100)
        
        # Temperature is stable with slight variation
        if "skin_temp_c" not in anomaly_ranges:
            temp_target = 36.5 + self._baseline_temp_offset
            self._skin_temp_c = self._random_walk(self._skin_temp_c, temp_target, 0.05, dt)
            self._skin_temp_c = self._clamp(self._skin_temp_c, 35.5, 38.5)
        
        # Respiratory rate tracks with HR loosely
        resp_target = 14 + (self._heart_rate - 70) * 0.05
        self._respiratory_rate = self._random_walk(self._respiratory_rate, resp_target, 0.5, dt)
        self._respiratory_rate = self._clamp(self._respiratory_rate, 10, 30)
        
        # Activity level
        self._activity_level = self._random_walk(self._activity_level, activity_target, 5.0, dt)
        self._activity_level = self._clamp(self._activity_level, 0, 100)
        
        # Steps correlate with activity level
        if self._activity_level < 20:
            steps_target = 0
        elif self._activity_level < 40:
            steps_target = random.randint(0, 10)
        else:
            steps_target = self._activity_level * 0.5
        
        self._steps_per_minute = self._random_walk(self._steps_per_minute, steps_target, 2.0, dt)
        self._steps_per_minute = self._clamp(self._steps_per_minute, 0, 120)
        
        # Calories correlate with activity
        cal_target = 1.0 + self._activity_level * 0.05
        self._calories_per_minute = self._random_walk(self._calories_per_minute, cal_target, 0.1, dt)
        self._calories_per_minute = self._clamp(self._calories_per_minute, 0.8, 15)
        
        # Sleep quality is stable during the day
        self._sleep_quality = self._random_walk(self._sleep_quality, 75, 1.0, dt)
        self._sleep_quality = self._clamp(self._sleep_quality, 40, 100)
        
        self._last_update = current_time
    
    def get_current_state(self) -> PhysiologicalState:
        """
        Get the current ground truth state.
        Evolves the state based on elapsed time.
        """
        with self._lock:
            self._evolve_state()
            
            return PhysiologicalState(
                timestamp=datetime.now(timezone.utc).isoformat(),
                heart_rate=round(self._heart_rate, 1),
                hrv_ms=round(self._hrv_ms, 1),
                spo2_percent=round(self._spo2_percent, 1),
                skin_temp_c=round(self._skin_temp_c, 2),
                respiratory_rate=round(self._respiratory_rate, 1),
                activity_level=round(self._activity_level, 1),
                steps_per_minute=round(self._steps_per_minute, 1),
                calories_per_minute=round(self._calories_per_minute, 2),
                sleep_quality=round(self._sleep_quality, 1),
            )
    
    def get_state_at_time(self, target_time: datetime) -> PhysiologicalState:
        """
        Generate a plausible state for a specific historical time.
        Used for bulk historical data generation.
        
        Note: This doesn't actually evolve state, it synthesizes a plausible
        snapshot for the given time based on circadian patterns.
        """
        hour = target_time.hour
        circadian = self._get_circadian_adjustments(hour)
        
        # Generate state based on time of day
        base_hr = 70 + circadian["heart_rate"] + self._baseline_hr_offset
        base_hrv = 55 + circadian["hrv_ms"] + self._baseline_hrv_offset
        base_activity = 10 + circadian["activity_level"]
        
        # Add some randomness for realism
        hr = base_hr + random.gauss(0, 3)
        hrv = base_hrv + random.gauss(0, 4)
        activity = max(0, base_activity + random.gauss(0, 5))
        
        # Steps based on activity and time
        if 0 <= hour <= 6:  # Night/early morning
            steps = 0
        elif activity < 20:
            steps = random.randint(0, 5)
        else:
            steps = activity * 0.4 + random.gauss(0, 3)
        
        return PhysiologicalState(
            timestamp=target_time.isoformat(),
            heart_rate=self._clamp(hr, 45, 180),
            hrv_ms=self._clamp(hrv, 10, 120),
            spo2_percent=random.uniform(97, 99),
            skin_temp_c=round(36.5 + self._baseline_temp_offset + random.gauss(0, 0.1), 2),
            respiratory_rate=self._clamp(14 + random.gauss(0, 1), 10, 25),
            activity_level=self._clamp(activity, 0, 100),
            steps_per_minute=self._clamp(steps, 0, 120),
            calories_per_minute=round(1.0 + activity * 0.05 + random.gauss(0, 0.1), 2),
            sleep_quality=round(75 + circadian.get("sleep_quality", 0) + random.gauss(0, 3), 1),
        )
    
    def inject_anomaly(self, anomaly_type: str, duration_seconds: int = 30):
        """
        Inject an anomaly into the ground truth.
        All sources will observe this anomaly.
        """
        if anomaly_type not in ANOMALY_PATTERNS:
            print(f"✗ Unknown anomaly type: {anomaly_type}")
            print(f"  Available: {list(ANOMALY_PATTERNS.keys())}")
            return
        
        with self._lock:
            self._anomaly_type = anomaly_type
            self._anomaly_end_time = time.time() + duration_seconds
        
        print(f"\n{'='*60}")
        print(f"⚠ ANOMALY INJECTION (Ground Truth): {anomaly_type.upper()}")
        print(f"  Duration: {duration_seconds} seconds")
        print(f"  Pattern: {ANOMALY_PATTERNS[anomaly_type]}")
        print(f"{'='*60}\n")
    
    def get_anomaly_status(self) -> Dict[str, Any]:
        """Get current anomaly status."""
        with self._lock:
            if self._anomaly_type and self._anomaly_end_time:
                remaining = max(0, self._anomaly_end_time - time.time())
                return {
                    "active": remaining > 0,
                    "type": self._anomaly_type,
                    "remaining_seconds": round(remaining, 1),
                }
            return {"active": False, "type": None, "remaining_seconds": 0}


# Singleton instances per user
_ground_truth_instances: Dict[str, GroundTruthState] = {}
_instances_lock = threading.Lock()


def get_ground_truth(user_id: str) -> GroundTruthState:
    """
    Get or create the ground truth state machine for a user.
    Thread-safe singleton pattern.
    """
    with _instances_lock:
        if user_id not in _ground_truth_instances:
            _ground_truth_instances[user_id] = GroundTruthState(user_id)
        return _ground_truth_instances[user_id]
