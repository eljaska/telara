"""
Telara Biometric Event Schemas
Standardized data models for IoT device simulation.

Source Profiles define what fields each health device supports
and their accuracy characteristics for realistic multi-source simulation.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional, Dict, Any, Set
from enum import Enum
import uuid
import random


class Posture(str, Enum):
    LYING = "lying"
    SEATED = "seated"
    STANDING = "standing"
    WALKING = "walking"
    RUNNING = "running"


class SleepStage(str, Enum):
    AWAKE = "awake"
    LIGHT = "light"
    DEEP = "deep"
    REM = "rem"


class DeviceSource(str, Enum):
    APPLE_WATCH = "apple_watch"
    OURA_RING = "oura_ring"
    WITHINGS_SCALE = "withings_scale"
    FITBIT = "fitbit"
    GARMIN = "garmin"
    DEXCOM_CGM = "dexcom_cgm"
    OMRON_BP = "omron_bp"


# =============================================================================
# SOURCE PROFILES - Define what each health data source supports
# =============================================================================

@dataclass
class SourceProfile:
    """
    Defines a health data source's capabilities and accuracy.
    
    Each source:
    - Supports specific fields (e.g., Apple has HR, Oura doesn't)
    - Has different accuracy/noise levels per field
    - Samples at different intervals
    """
    id: str
    name: str
    icon: str
    color: str
    topic: str  # Kafka topic
    device_source: str
    sample_interval_ms: int
    supported_fields: Set[str]
    noise_levels: Dict[str, float]  # Standard deviation of noise per field
    
    def sample_field(self, field: str, ground_truth_value: float) -> Optional[float]:
        """
        Sample a field from ground truth with device-specific noise.
        Returns None if this source doesn't support the field.
        """
        if field not in self.supported_fields:
            return None
        
        noise_std = self.noise_levels.get(field, 0)
        return ground_truth_value + random.gauss(0, noise_std)
    
    def supports(self, field: str) -> bool:
        """Check if this source supports a given field."""
        return field in self.supported_fields


# Define the three main source profiles
APPLE_PROFILE = SourceProfile(
    id="apple",
    name="Apple HealthKit",
    icon="🍎",
    color="#FF3B30",
    topic="biometrics-apple",
    device_source=DeviceSource.APPLE_WATCH.value,
    sample_interval_ms=1000,  # 1 sample per second
    supported_fields={
        "heart_rate",
        "hrv_ms",
        "respiratory_rate",
        "activity_level",
        "steps_per_minute",
        "calories_per_minute",
        "spo2_percent",  # Apple Watch Series 6+
    },
    noise_levels={
        "heart_rate": 1.0,       # ±1 bpm (high accuracy)
        "hrv_ms": 2.0,           # ±2 ms
        "respiratory_rate": 0.5, # ±0.5 breaths/min
        "activity_level": 2.0,
        "steps_per_minute": 1.0,
        "calories_per_minute": 0.2,
        "spo2_percent": 0.5,
    }
)

GOOGLE_PROFILE = SourceProfile(
    id="google",
    name="Google Fit",
    icon="📱",
    color="#4285F4",
    topic="biometrics-google",
    device_source=DeviceSource.FITBIT.value,  # Often syncs from Fitbit
    sample_interval_ms=1500,  # Slightly slower
    supported_fields={
        "heart_rate",
        "activity_level",
        "steps_per_minute",
        "calories_per_minute",
    },
    noise_levels={
        "heart_rate": 3.0,       # ±3 bpm (lower accuracy than Apple)
        "activity_level": 3.0,
        "steps_per_minute": 2.0,
        "calories_per_minute": 0.3,
    }
)

OURA_PROFILE = SourceProfile(
    id="oura",
    name="Oura Ring",
    icon="💍",
    color="#8B5CF6",
    topic="biometrics-oura",
    device_source=DeviceSource.OURA_RING.value,
    sample_interval_ms=2000,  # Less frequent sampling
    supported_fields={
        "hrv_ms",
        "skin_temp_c",
        "respiratory_rate",
        "sleep_quality",  # Readiness score
        "activity_level",
    },
    noise_levels={
        "hrv_ms": 2.0,           # ±2 ms (excellent HRV accuracy)
        "skin_temp_c": 0.05,     # ±0.05°C (excellent temp accuracy)
        "respiratory_rate": 0.3,
        "sleep_quality": 3.0,
        "activity_level": 2.0,
    }
)

# All source profiles indexed by ID
SOURCE_PROFILES: Dict[str, SourceProfile] = {
    "apple": APPLE_PROFILE,
    "google": GOOGLE_PROFILE,
    "oura": OURA_PROFILE,
}

# Field to sources mapping (which sources support each field)
FIELD_SOURCES: Dict[str, List[str]] = {
    "heart_rate": ["apple", "google"],
    "hrv_ms": ["apple", "oura"],
    "spo2_percent": ["apple"],
    "skin_temp_c": ["oura"],
    "respiratory_rate": ["apple", "oura"],
    "activity_level": ["apple", "google", "oura"],
    "steps_per_minute": ["apple", "google"],
    "calories_per_minute": ["apple", "google"],
    "sleep_quality": ["oura"],
}


@dataclass
class Vitals:
    """Core vital signs from wearables."""
    heart_rate: int  # bpm (60-200)
    hrv_ms: int  # Heart Rate Variability in ms (20-100)
    spo2_percent: int  # Blood oxygen (90-100)
    skin_temp_c: float  # Skin temperature (35.0-40.0)
    respiratory_rate: int  # Breaths per minute (12-25)
    blood_pressure_systolic: Optional[int] = None  # (90-180)
    blood_pressure_diastolic: Optional[int] = None  # (60-120)


@dataclass
class Activity:
    """Activity and movement metrics."""
    steps_per_minute: int  # (0-200)
    activity_level: int  # 0-100 scale
    calories_per_minute: float  # (0.5-20)
    posture: str  # Posture enum value


@dataclass
class Sleep:
    """Sleep-related metrics."""
    stage: Optional[str]  # SleepStage enum value or None
    hours_last_night: float  # (4-10)


@dataclass
class Environment:
    """Environmental sensor data."""
    room_temp_c: float  # (15-30)
    humidity_percent: int  # (20-80)


@dataclass
class BiometricEvent:
    """
    Unified biometric event schema.
    Aggregates data from multiple IoT device sources.
    """
    event_id: str
    timestamp: str
    user_id: str
    device_sources: List[str]
    vitals: Vitals
    activity: Activity
    sleep: Sleep
    environment: Environment
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "device_sources": self.device_sources,
            "vitals": asdict(self.vitals),
            "activity": asdict(self.activity),
            "sleep": asdict(self.sleep),
            "environment": asdict(self.environment),
        }
    
    def to_flat_dict(self) -> dict:
        """
        Convert to flattened dictionary for Flink SQL processing.
        This format is easier to query with Flink SQL.
        """
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "device_sources": self.device_sources,
            # Vitals (flattened)
            "heart_rate": self.vitals.heart_rate,
            "hrv_ms": self.vitals.hrv_ms,
            "spo2_percent": self.vitals.spo2_percent,
            "skin_temp_c": self.vitals.skin_temp_c,
            "respiratory_rate": self.vitals.respiratory_rate,
            "blood_pressure_systolic": self.vitals.blood_pressure_systolic,
            "blood_pressure_diastolic": self.vitals.blood_pressure_diastolic,
            # Activity (flattened)
            "steps_per_minute": self.activity.steps_per_minute,
            "activity_level": self.activity.activity_level,
            "calories_per_minute": self.activity.calories_per_minute,
            "posture": self.activity.posture,
            # Sleep (flattened)
            "sleep_stage": self.sleep.stage,
            "hours_last_night": self.sleep.hours_last_night,
            # Environment (flattened)
            "room_temp_c": self.environment.room_temp_c,
            "humidity_percent": self.environment.humidity_percent,
        }


@dataclass
class AlertEvent:
    """Schema for anomaly alerts generated by Flink."""
    alert_id: str
    alert_type: str
    user_id: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    start_time: str
    end_time: str
    avg_heart_rate: float
    event_count: int
    description: str
    
    def to_dict(self) -> dict:
        return asdict(self)


# Baseline ranges for normal vital signs
NORMAL_RANGES = {
    "heart_rate": (60, 80),
    "hrv_ms": (40, 70),
    "spo2_percent": (96, 100),
    "skin_temp_c": (36.0, 37.0),
    "respiratory_rate": (12, 18),
    "blood_pressure_systolic": (110, 130),
    "blood_pressure_diastolic": (70, 85),
    "steps_per_minute": (0, 5),  # At rest
    "activity_level": (0, 15),  # Sedentary
    "room_temp_c": (20, 24),
    "humidity_percent": (40, 60),
}

# Anomaly patterns for injection
ANOMALY_PATTERNS = {
    "tachycardia_at_rest": {
        "heart_rate": (110, 140),
        "activity_level": (0, 8),
        "steps_per_minute": (0, 3),
        "hrv_ms": (20, 35),  # Lower HRV during stress
    },
    "hypoxia": {
        "spo2_percent": (88, 93),
        "respiratory_rate": (20, 28),
        "heart_rate": (85, 105),
    },
    "fever_onset": {
        "skin_temp_c": (37.8, 39.5),
        "heart_rate": (90, 110),
        "hrv_ms": (25, 40),
    },
    "burnout_stress": {
        "hrv_ms": (15, 30),
        "heart_rate": (85, 100),
        "sleep_hours": (4, 5.5),
    },
    "dehydration": {
        "heart_rate": (90, 110),
        "blood_pressure_systolic": (95, 110),
        "skin_temp_c": (37.0, 37.5),
    },
}

