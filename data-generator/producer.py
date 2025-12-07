"""
Telara Biometric Data Generator
Simulates IoT device streams with anomaly injection capability.
Multi-source architecture: Each health device publishes to its own Kafka topic.

Ground Truth Architecture:
- A single PhysiologicalState maintains the user's actual health metrics
- Each source (Apple, Google, Oura) samples this state with device-specific noise
- This ensures consistent values across sources at similar times
"""

import os
import json
import time
import random
import signal
import sys
import threading
import math
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
import uuid

from confluent_kafka import Producer
from schemas import (
    BiometricEvent, Vitals, Activity, Sleep, Environment,
    DeviceSource, Posture, SleepStage,
    NORMAL_RANGES, ANOMALY_PATTERNS,
    SOURCE_PROFILES, SourceProfile, FIELD_SOURCES
)
from ground_truth import get_ground_truth, PhysiologicalState, GroundTruthState


# Source-specific configurations
# Each source has unique characteristics and data variations
SOURCE_CONFIGS = {
    "apple": {
        "id": "apple",
        "name": "Apple HealthKit",
        "topic": "biometrics-apple",
        "device_source": DeviceSource.APPLE_WATCH.value,
        "enabled": True,
        # Apple Watch has excellent HR/HRV accuracy
        "hr_variance": 1,  # Low variance
        "hrv_accuracy": 0.95,  # High accuracy
        "data_types": ["heart_rate", "hrv_ms", "activity", "steps", "workouts"],
        "update_interval_ms": 500,  # Fast updates
    },
    "google": {
        "id": "google",
        "name": "Google Fit",
        "topic": "biometrics-google",
        "device_source": DeviceSource.FITBIT.value,  # Often Fitbit syncs to Google Fit
        "enabled": True,
        # Google Fit is activity-focused with good step tracking
        "hr_variance": 3,  # Slightly higher variance
        "hrv_accuracy": 0.85,
        "data_types": ["heart_rate", "activity", "steps", "calories"],
        "update_interval_ms": 1000,  # Slower updates
    },
    "oura": {
        "id": "oura",
        "name": "Oura Ring",
        "topic": "biometrics-oura",
        "device_source": DeviceSource.OURA_RING.value,
        "enabled": True,
        # Oura excels at sleep and recovery metrics
        "hr_variance": 2,
        "hrv_accuracy": 0.92,
        "temp_accuracy": 0.98,  # Excellent temp accuracy
        "data_types": ["heart_rate", "hrv_ms", "sleep", "temperature", "readiness"],
        "update_interval_ms": 1000,
    },
}


class BiometricProducer:
    """Generates and publishes synthetic biometric data to Kafka."""
    
    def __init__(
        self,
        bootstrap_servers: str = "kafka:29092",
        topic: str = "biometrics-raw",
        user_id: str = "user_001",
        interval_ms: int = 500,
    ):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.user_id = user_id
        self.interval_ms = interval_ms
        self.running = False
        self.anomaly_active: Optional[str] = None
        self.anomaly_end_time: Optional[float] = None
        self.events_generated = 0
        self.alerts_triggered = 0
        
        # Kafka producer configuration
        self.producer_config = {
            'bootstrap.servers': bootstrap_servers,
            'client.id': f'telara-generator-{user_id}',
            'acks': 'all',
        }
        self.producer: Optional[Producer] = None
        
        # Device sources for this user
        self.device_sources = [
            DeviceSource.APPLE_WATCH.value,
            DeviceSource.OURA_RING.value,
        ]
        
        # Baseline state (simulates person's current condition)
        self.baseline_state = {
            "hours_slept": random.uniform(6.0, 8.0),
            "stress_level": random.uniform(0.2, 0.4),
            "hydration": random.uniform(0.7, 0.9),
        }
        
    def connect(self) -> bool:
        """Establish connection to Kafka."""
        max_retries = 30
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                print(f"[{attempt + 1}/{max_retries}] Connecting to Kafka at {self.bootstrap_servers}...")
                self.producer = Producer(self.producer_config)
                # Test the connection
                self.producer.list_topics(timeout=5)
                print(f"✓ Connected to Kafka successfully!")
                return True
            except Exception as e:
                print(f"  Connection failed: {e}")
                if attempt < max_retries - 1:
                    print(f"  Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                else:
                    print("✗ Max retries reached. Could not connect to Kafka.")
                    return False
        return False
    
    def generate_normal_vitals(self) -> Vitals:
        """Generate normal baseline vital signs."""
        stress = self.baseline_state["stress_level"]
        
        return Vitals(
            heart_rate=random.randint(
                NORMAL_RANGES["heart_rate"][0] + int(stress * 10),
                NORMAL_RANGES["heart_rate"][1] + int(stress * 10)
            ),
            hrv_ms=random.randint(
                NORMAL_RANGES["hrv_ms"][0] - int(stress * 20),
                NORMAL_RANGES["hrv_ms"][1] - int(stress * 10)
            ),
            spo2_percent=random.randint(
                NORMAL_RANGES["spo2_percent"][0],
                NORMAL_RANGES["spo2_percent"][1]
            ),
            skin_temp_c=round(random.uniform(
                NORMAL_RANGES["skin_temp_c"][0],
                NORMAL_RANGES["skin_temp_c"][1]
            ), 1),
            respiratory_rate=random.randint(
                NORMAL_RANGES["respiratory_rate"][0],
                NORMAL_RANGES["respiratory_rate"][1]
            ),
            blood_pressure_systolic=random.randint(
                NORMAL_RANGES["blood_pressure_systolic"][0],
                NORMAL_RANGES["blood_pressure_systolic"][1]
            ),
            blood_pressure_diastolic=random.randint(
                NORMAL_RANGES["blood_pressure_diastolic"][0],
                NORMAL_RANGES["blood_pressure_diastolic"][1]
            ),
        )
    
    def generate_anomaly_vitals(self, anomaly_type: str) -> Vitals:
        """Generate vital signs reflecting an anomaly pattern."""
        pattern = ANOMALY_PATTERNS.get(anomaly_type, {})
        normal = self.generate_normal_vitals()
        
        return Vitals(
            heart_rate=random.randint(
                pattern.get("heart_rate", NORMAL_RANGES["heart_rate"])[0],
                pattern.get("heart_rate", NORMAL_RANGES["heart_rate"])[1]
            ),
            hrv_ms=random.randint(
                pattern.get("hrv_ms", (normal.hrv_ms - 5, normal.hrv_ms + 5))[0],
                pattern.get("hrv_ms", (normal.hrv_ms - 5, normal.hrv_ms + 5))[1]
            ),
            spo2_percent=random.randint(
                pattern.get("spo2_percent", NORMAL_RANGES["spo2_percent"])[0],
                pattern.get("spo2_percent", NORMAL_RANGES["spo2_percent"])[1]
            ),
            skin_temp_c=round(random.uniform(
                pattern.get("skin_temp_c", NORMAL_RANGES["skin_temp_c"])[0],
                pattern.get("skin_temp_c", NORMAL_RANGES["skin_temp_c"])[1]
            ), 1),
            respiratory_rate=random.randint(
                pattern.get("respiratory_rate", NORMAL_RANGES["respiratory_rate"])[0],
                pattern.get("respiratory_rate", NORMAL_RANGES["respiratory_rate"])[1]
            ),
            blood_pressure_systolic=random.randint(
                pattern.get("blood_pressure_systolic", NORMAL_RANGES["blood_pressure_systolic"])[0],
                pattern.get("blood_pressure_systolic", NORMAL_RANGES["blood_pressure_systolic"])[1]
            ),
            blood_pressure_diastolic=normal.blood_pressure_diastolic,
        )
    
    def generate_activity(self, anomaly_type: Optional[str] = None) -> Activity:
        """Generate activity metrics."""
        if anomaly_type in ["tachycardia_at_rest"]:
            # At rest during tachycardia
            pattern = ANOMALY_PATTERNS[anomaly_type]
            return Activity(
                steps_per_minute=random.randint(
                    pattern.get("steps_per_minute", (0, 3))[0],
                    pattern.get("steps_per_minute", (0, 3))[1]
                ),
                activity_level=random.randint(
                    pattern.get("activity_level", (0, 8))[0],
                    pattern.get("activity_level", (0, 8))[1]
                ),
                calories_per_minute=round(random.uniform(0.8, 1.5), 1),
                posture=Posture.SEATED.value,
            )
        
        # Normal activity (mostly sedentary for office worker simulation)
        return Activity(
            steps_per_minute=random.randint(0, 10),
            activity_level=random.randint(5, 25),
            calories_per_minute=round(random.uniform(1.0, 2.5), 1),
            posture=random.choice([Posture.SEATED.value, Posture.STANDING.value]),
        )
    
    def generate_sleep(self) -> Sleep:
        """Generate sleep metrics."""
        return Sleep(
            stage=None,  # Not sleeping during day
            hours_last_night=round(self.baseline_state["hours_slept"], 1),
        )
    
    def generate_environment(self) -> Environment:
        """Generate environmental sensor data."""
        return Environment(
            room_temp_c=round(random.uniform(
                NORMAL_RANGES["room_temp_c"][0],
                NORMAL_RANGES["room_temp_c"][1]
            ), 1),
            humidity_percent=random.randint(
                NORMAL_RANGES["humidity_percent"][0],
                NORMAL_RANGES["humidity_percent"][1]
            ),
        )
    
    def generate_event(self) -> BiometricEvent:
        """Generate a complete biometric event."""
        # Check if anomaly is still active
        if self.anomaly_active and self.anomaly_end_time:
            if time.time() > self.anomaly_end_time:
                print(f"\n✓ Anomaly '{self.anomaly_active}' injection completed.")
                self.anomaly_active = None
                self.anomaly_end_time = None
        
        # Generate vitals based on current state
        if self.anomaly_active:
            vitals = self.generate_anomaly_vitals(self.anomaly_active)
            activity = self.generate_activity(self.anomaly_active)
        else:
            vitals = self.generate_normal_vitals()
            activity = self.generate_activity()
        
        return BiometricEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            user_id=self.user_id,
            device_sources=self.device_sources,
            vitals=vitals,
            activity=activity,
            sleep=self.generate_sleep(),
            environment=self.generate_environment(),
        )
    
    def inject_anomaly(self, anomaly_type: str, duration_seconds: int = 30):
        """
        Inject an anomaly pattern for the specified duration.
        
        Available anomaly types:
        - tachycardia_at_rest: High HR while sedentary
        - hypoxia: Low blood oxygen
        - fever_onset: Elevated temperature
        - burnout_stress: Low HRV, poor sleep indicators
        - dehydration: Elevated HR, low BP
        """
        if anomaly_type not in ANOMALY_PATTERNS:
            print(f"✗ Unknown anomaly type: {anomaly_type}")
            print(f"  Available types: {list(ANOMALY_PATTERNS.keys())}")
            return
        
        self.anomaly_active = anomaly_type
        self.anomaly_end_time = time.time() + duration_seconds
        self.alerts_triggered += 1
        
        print(f"\n{'='*60}")
        print(f"⚠ ANOMALY INJECTION: {anomaly_type.upper()}")
        print(f"  Duration: {duration_seconds} seconds")
        print(f"  Pattern: {ANOMALY_PATTERNS[anomaly_type]}")
        print(f"{'='*60}\n")
    
    def delivery_callback(self, err, msg):
        """Callback for Kafka message delivery."""
        if err:
            print(f"✗ Delivery failed: {err}")
        # Silent on success for cleaner logs
    
    def publish_event(self, event: BiometricEvent, topic: Optional[str] = None):
        """Publish a biometric event to Kafka."""
        try:
            # Use flattened format for Flink SQL compatibility
            payload = json.dumps(event.to_flat_dict())
            target_topic = topic or self.topic
            
            self.producer.produce(
                topic=target_topic,
                key=event.user_id.encode('utf-8'),
                value=payload.encode('utf-8'),
                callback=self.delivery_callback,
            )
            self.producer.poll(0)
            self.events_generated += 1
            
        except Exception as e:
            print(f"✗ Failed to publish event: {e}")
    
    def generate_source_event(self, source_config: Dict[str, Any]) -> BiometricEvent:
        """Generate a source-specific biometric event with realistic variations."""
        source_id = source_config["id"]
        hr_variance = source_config.get("hr_variance", 2)
        hrv_accuracy = source_config.get("hrv_accuracy", 0.9)
        
        # Check if anomaly is still active
        if self.anomaly_active and self.anomaly_end_time:
            if time.time() > self.anomaly_end_time:
                print(f"\n✓ Anomaly '{self.anomaly_active}' injection completed.")
                self.anomaly_active = None
                self.anomaly_end_time = None
        
        # Generate base vitals
        if self.anomaly_active:
            vitals = self.generate_anomaly_vitals(self.anomaly_active)
            activity = self.generate_activity(self.anomaly_active)
        else:
            vitals = self.generate_normal_vitals()
            activity = self.generate_activity()
        
        # Apply source-specific variations
        # Add realistic noise based on device accuracy
        vitals.heart_rate = max(40, min(200, vitals.heart_rate + random.randint(-hr_variance, hr_variance)))
        
        # HRV varies by device accuracy
        hrv_noise = int((1 - hrv_accuracy) * 10)
        vitals.hrv_ms = max(10, min(120, vitals.hrv_ms + random.randint(-hrv_noise, hrv_noise)))
        
        # Oura has better temperature accuracy
        if source_id == "oura":
            temp_accuracy = source_config.get("temp_accuracy", 0.95)
            temp_noise = (1 - temp_accuracy) * 0.5
            vitals.skin_temp_c = round(vitals.skin_temp_c + random.uniform(-temp_noise, temp_noise), 2)
        
        # Google Fit has better step accuracy
        if source_id == "google":
            activity.steps_per_minute = max(0, activity.steps_per_minute + random.randint(-1, 2))
        
        return BiometricEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            user_id=self.user_id,
            device_sources=[source_config["device_source"]],
            vitals=vitals,
            activity=activity,
            sleep=self.generate_sleep(),
            environment=self.generate_environment(),
        )
    
    def print_status(self, event: BiometricEvent):
        """Print current status to console."""
        anomaly_indicator = f" ⚠ [{self.anomaly_active}]" if self.anomaly_active else ""
        print(
            f"[{event.timestamp[:19]}] "
            f"HR:{event.vitals.heart_rate:3d} "
            f"HRV:{event.vitals.hrv_ms:2d} "
            f"SpO2:{event.vitals.spo2_percent}% "
            f"Temp:{event.vitals.skin_temp_c}°C "
            f"Act:{event.activity.activity_level:2d} "
            f"Steps:{event.activity.steps_per_minute:2d}"
            f"{anomaly_indicator}"
        )
    
    def run(self):
        """Main loop to generate and publish events."""
        if not self.connect():
            return
        
        self.running = True
        print(f"\n{'='*60}")
        print(f"TELARA DATA GENERATOR STARTED")
        print(f"  Topic: {self.topic}")
        print(f"  User: {self.user_id}")
        print(f"  Interval: {self.interval_ms}ms")
        print(f"{'='*60}\n")
        
        interval_sec = self.interval_ms / 1000.0
        
        while self.running:
            try:
                event = self.generate_event()
                self.publish_event(event)
                self.print_status(event)
                time.sleep(interval_sec)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"✗ Error in main loop: {e}")
                time.sleep(1)
        
        self.shutdown()
    
    def shutdown(self):
        """Clean shutdown of the producer."""
        self.running = False
        print(f"\n{'='*60}")
        print(f"TELARA DATA GENERATOR SHUTDOWN")
        print(f"  Events generated: {self.events_generated}")
        print(f"  Anomalies triggered: {self.alerts_triggered}")
        print(f"{'='*60}")
        
        if self.producer:
            self.producer.flush(timeout=5)
    
    def generate_historical_event(
        self,
        timestamp: datetime,
        hour_of_day: int,
        pattern: str = "normal",
        day_offset: int = 0,
        include_anomaly: bool = False,
        anomaly_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a historical biometric event with circadian rhythm simulation.
        
        Args:
            timestamp: The backdated timestamp for the event
            hour_of_day: Hour (0-23) for circadian adjustments
            pattern: One of 'normal', 'improving', 'declining', 'variable'
            day_offset: Days from today (negative for past)
            include_anomaly: Whether this event should be anomalous
            anomaly_type: Type of anomaly if include_anomaly is True
        """
        # Circadian rhythm adjustments
        # HR lower at night (2-5 AM), higher during day
        # HRV higher during sleep, lower during stress
        circadian_hr_adjust = 0
        circadian_hrv_adjust = 0
        
        if 2 <= hour_of_day <= 5:
            # Deep sleep - lowest HR, highest HRV
            circadian_hr_adjust = -15
            circadian_hrv_adjust = 15
        elif 6 <= hour_of_day <= 8:
            # Waking up
            circadian_hr_adjust = -5
            circadian_hrv_adjust = 5
        elif 12 <= hour_of_day <= 14:
            # Post-lunch dip
            circadian_hr_adjust = 5
            circadian_hrv_adjust = -5
        elif 17 <= hour_of_day <= 19:
            # Evening activity
            circadian_hr_adjust = 8
            circadian_hrv_adjust = -8
        elif 22 <= hour_of_day <= 23:
            # Winding down
            circadian_hr_adjust = -8
            circadian_hrv_adjust = 8
        
        # Pattern-based trend adjustments
        trend_adjust = 0
        if pattern == "improving":
            # Gradual improvement over days
            trend_adjust = min(day_offset * 0.5, 10)  # Caps at 10
        elif pattern == "declining":
            # Gradual decline
            trend_adjust = max(day_offset * -0.5, -10)
        elif pattern == "variable":
            # Random day-to-day variation
            trend_adjust = random.uniform(-5, 5)
        
        # Generate base vitals
        if include_anomaly and anomaly_type:
            vitals = self.generate_anomaly_vitals(anomaly_type)
            activity = self.generate_activity(anomaly_type)
        else:
            vitals = self.generate_normal_vitals()
            activity = self.generate_activity()
        
        # Apply circadian and trend adjustments
        adjusted_hr = max(50, min(120, vitals.heart_rate + circadian_hr_adjust + int(trend_adjust)))
        adjusted_hrv = max(15, min(100, vitals.hrv_ms + circadian_hrv_adjust - int(trend_adjust)))
        
        # Sleep stage based on hour
        sleep_stage = None
        if 0 <= hour_of_day <= 2 or 23 <= hour_of_day:
            sleep_stage = SleepStage.LIGHT.value
        elif 2 < hour_of_day <= 4:
            sleep_stage = SleepStage.DEEP.value
        elif 4 < hour_of_day <= 6:
            sleep_stage = random.choice([SleepStage.REM.value, SleepStage.LIGHT.value])
        
        # Activity level based on hour (lower at night)
        if 0 <= hour_of_day <= 6:
            activity_level = random.randint(0, 5)
            steps = 0
        elif 7 <= hour_of_day <= 9:
            activity_level = random.randint(20, 40)  # Morning routine
            steps = random.randint(5, 15)
        elif 12 <= hour_of_day <= 13:
            activity_level = random.randint(15, 30)  # Lunch
            steps = random.randint(3, 10)
        elif 17 <= hour_of_day <= 19:
            activity_level = random.randint(25, 50)  # Evening activity
            steps = random.randint(10, 30)
        else:
            activity_level = random.randint(5, 25)
            steps = random.randint(0, 10)
        
        # Build the flat dict format for database insertion
        return {
            "event_id": str(uuid.uuid4()),
            "timestamp": timestamp.isoformat(),
            "user_id": self.user_id,
            "heart_rate": adjusted_hr,
            "hrv_ms": adjusted_hrv,
            "spo2_percent": vitals.spo2_percent,
            "skin_temp_c": vitals.skin_temp_c,
            "respiratory_rate": vitals.respiratory_rate,
            "activity_level": activity_level if not include_anomaly else activity.activity_level,
            "steps_per_minute": steps if not include_anomaly else activity.steps_per_minute,
            "calories_per_minute": activity.calories_per_minute,
            "posture": activity.posture,
            "hours_last_night": round(self.baseline_state["hours_slept"] + random.uniform(-1, 1), 1),
            "room_temp_c": round(random.uniform(20, 24), 1),
            "humidity_percent": random.randint(40, 60),
            "sleep_stage": sleep_stage,
        }


class MultiSourceProducer:
    """
    Multi-source biometric producer using Ground Truth architecture.
    
    All sources observe a single evolving PhysiologicalState, ensuring
    consistent data across sources at similar timestamps. Each source
    adds device-specific noise based on its accuracy profile.
    
    Key Features:
    - Ground truth ensures HR from Apple ≈ HR from Google
    - Each source only reports fields it supports (Oura has no HR)
    - Device-specific noise levels for realistic simulation
    - Anomaly injection affects all sources via ground truth
    """
    
    def __init__(
        self,
        bootstrap_servers: str = "kafka:29092",
        user_id: str = "user_001",
        base_interval_ms: int = 1000,
    ):
        self.bootstrap_servers = bootstrap_servers
        self.user_id = user_id
        self.base_interval_ms = base_interval_ms
        self.running = False
        
        # Get ground truth state machine
        self.ground_truth = get_ground_truth(user_id)
        
        # Source states using new SOURCE_PROFILES
        self.sources: Dict[str, Dict[str, Any]] = {}
        for source_id, profile in SOURCE_PROFILES.items():
            self.sources[source_id] = {
                "profile": profile,
                "enabled": True,
                "events_generated": 0,
                "last_sample_time": 0,
            }
        
        # Kafka producer
        self.producer_config = {
            'bootstrap.servers': bootstrap_servers,
            'client.id': f'telara-generator-{user_id}',
            'acks': 'all',
        }
        self.producer: Optional[Producer] = None
        
        # Locks for thread safety
        self._lock = threading.Lock()
        
        # Anomaly tracking (delegated to ground truth)
        self.anomaly_active: Optional[str] = None
    
    def connect(self) -> bool:
        """Connect to Kafka."""
        max_retries = 30
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                print(f"[{attempt + 1}/{max_retries}] Connecting to Kafka at {self.bootstrap_servers}...")
                self.producer = Producer(self.producer_config)
                self.producer.list_topics(timeout=5)
                print(f"✓ Connected to Kafka successfully!")
                return True
            except Exception as e:
                print(f"  Connection failed: {e}")
                if attempt < max_retries - 1:
                    print(f"  Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
        
        print("✗ Max retries reached. Could not connect to Kafka.")
        return False
    
    def enable_source(self, source_id: str) -> bool:
        """Enable a data source."""
        with self._lock:
            if source_id in self.sources:
                self.sources[source_id]["enabled"] = True
                print(f"✓ Enabled source: {source_id}")
                return True
            return False
    
    def disable_source(self, source_id: str) -> bool:
        """Disable a data source."""
        with self._lock:
            if source_id in self.sources:
                self.sources[source_id]["enabled"] = False
                print(f"✗ Disabled source: {source_id}")
                return True
            return False
    
    def get_source_status(self) -> Dict[str, Any]:
        """Get status of all sources."""
        with self._lock:
            return {
                source_id: {
                    "id": source["profile"].id,
                    "name": source["profile"].name,
                    "topic": source["profile"].topic,
                    "enabled": source["enabled"],
                    "events_generated": source["events_generated"],
                    "supported_fields": list(source["profile"].supported_fields),
                }
                for source_id, source in self.sources.items()
            }
    
    def inject_anomaly(self, anomaly_type: str, duration_seconds: int = 30):
        """Inject an anomaly into the ground truth (affects all sources)."""
        self.ground_truth.inject_anomaly(anomaly_type, duration_seconds)
        self.anomaly_active = anomaly_type
    
    def sample_from_ground_truth(self, profile: SourceProfile) -> Dict[str, Any]:
        """
        Sample the current ground truth state through a device's "lens".
        
        Each device:
        - Only reports fields it supports
        - Adds device-specific noise to values
        - Has its own sampling characteristics
        """
        # Get current ground truth state
        state = self.ground_truth.get_current_state()
        state_dict = state.to_dict()
        
        # Build event with only fields this source supports
        event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": state.timestamp,
            "user_id": self.user_id,
            "source": profile.id,
            "source_name": profile.name,
            "device_sources": [profile.device_source],
        }
        
        # Sample each supported field with device-specific noise
        for field in profile.supported_fields:
            if field in state_dict:
                ground_truth_value = state_dict[field]
                # Add device-specific noise
                sampled_value = profile.sample_field(field, ground_truth_value)
                if sampled_value is not None:
                    # Round appropriately based on field type
                    if field in ["heart_rate", "hrv_ms", "respiratory_rate", "activity_level", "steps_per_minute", "spo2_percent", "sleep_quality"]:
                        event[field] = round(sampled_value)
                    else:
                        event[field] = round(sampled_value, 2)
        
        return event
    
    def generate_and_publish(self):
        """
        Generate events for all enabled sources by sampling ground truth.
        
        All sources sample the same underlying state, ensuring consistent
        values across sources at similar times.
        """
        current_time = time.time()
        
        with self._lock:
            enabled_sources = [
                (source_id, source) 
                for source_id, source in self.sources.items() 
                if source["enabled"]
            ]
        
        if not enabled_sources:
            return
        
        for source_id, source_state in enabled_sources:
            profile = source_state["profile"]
            
            # Check if it's time for this source to sample
            # (Each source has its own sampling interval)
            last_sample = source_state["last_sample_time"]
            interval_sec = profile.sample_interval_ms / 1000.0
            
            if current_time - last_sample < interval_sec:
                continue  # Not time yet for this source
            
            try:
                # Sample ground truth through this device's lens
                event = self.sample_from_ground_truth(profile)
                
                # Publish to source-specific topic
                payload = json.dumps(event)
                self.producer.produce(
                    topic=profile.topic,
                    key=self.user_id.encode('utf-8'),
                    value=payload.encode('utf-8'),
                )
                self.producer.poll(0)
                
                # Update stats
                with self._lock:
                    self.sources[source_id]["events_generated"] += 1
                    self.sources[source_id]["last_sample_time"] = current_time
                
            except Exception as e:
                print(f"✗ Error publishing to {profile.topic}: {e}")
    
    def print_status(self):
        """Print current status to console."""
        with self._lock:
            enabled = [s["profile"].id for s in self.sources.values() if s["enabled"]]
            total_events = sum(s["events_generated"] for s in self.sources.values())
        
        anomaly_status = self.ground_truth.get_anomaly_status()
        anomaly_indicator = f" ⚠ [{anomaly_status['type']}]" if anomaly_status["active"] else ""
        
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        print(f"[{timestamp}] Sources: {','.join(enabled)} | Events: {total_events}{anomaly_indicator}")
    
    def run(self):
        """Main loop to generate and publish events from all sources."""
        if not self.connect():
            return
        
        self.running = True
        
        # Print startup info
        print(f"\n{'='*60}")
        print(f"TELARA GROUND TRUTH DATA GENERATOR")
        print(f"  User: {self.user_id}")
        print(f"  Architecture: Ground Truth + Device Lens")
        print(f"  Sources:")
        for source_id, source in self.sources.items():
            profile = source["profile"]
            status = "✓" if source["enabled"] else "✗"
            fields = ", ".join(sorted(profile.supported_fields)[:4]) + "..."
            print(f"    {status} {profile.icon} {profile.name}")
            print(f"        Topic: {profile.topic}")
            print(f"        Fields: {fields}")
            print(f"        Interval: {profile.sample_interval_ms}ms")
        print(f"{'='*60}\n")
        
        # Main loop - run at high frequency, let sources sample at their own rate
        loop_interval = 0.1  # 100ms loop for responsive sampling
        last_print_time = 0
        
        while self.running:
            try:
                self.generate_and_publish()
                
                # Print status every 10 seconds
                current_time = time.time()
                if current_time - last_print_time >= 10:
                    self.print_status()
                    last_print_time = current_time
                
                time.sleep(loop_interval)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"✗ Error in main loop: {e}")
                time.sleep(1)
        
        self.shutdown()
    
    def shutdown(self):
        """Clean shutdown."""
        self.running = False
        
        print(f"\n{'='*60}")
        print(f"TELARA GROUND TRUTH DATA GENERATOR SHUTDOWN")
        for source_id, source in self.sources.items():
            profile = source["profile"]
            print(f"  {profile.icon} {profile.name}: {source['events_generated']} events")
        print(f"{'='*60}")
        
        if self.producer:
            self.producer.flush(timeout=5)


def generate_historical_data(
    user_id: str = "user_001",
    days: int = 7,
    events_per_hour: int = 60,
    include_anomalies: bool = True,
    anomaly_probability: float = 0.05,
    pattern: str = "normal"
) -> List[Dict[str, Any]]:
    """
    Generate historical biometric data using Ground Truth architecture.
    
    Fast bulk generation:
    - Creates ground truth timeline first
    - Simulates what each source would have observed
    - Returns raw events from all sources for database insertion
    
    Args:
        user_id: User ID for the generated data
        days: Number of days of history to generate
        events_per_hour: Events per source per hour (default 60 = 1/min)
        include_anomalies: Whether to randomly include anomalies
        anomaly_probability: Probability of an event being anomalous
        pattern: One of 'normal', 'improving', 'declining', 'variable'
    
    Returns:
        List of raw event dictionaries from all sources
    """
    ground_truth = get_ground_truth(user_id)
    events = []
    
    now = datetime.now(timezone.utc)
    anomaly_types = list(ANOMALY_PATTERNS.keys())
    
    print(f"\n{'='*60}")
    print(f"GENERATING HISTORICAL DATA (Ground Truth)")
    print(f"  User: {user_id}")
    print(f"  Days: {days}")
    print(f"  Events/hour per source: {events_per_hour}")
    print(f"  Pattern: {pattern}")
    print(f"  Include anomalies: {include_anomalies}")
    print(f"  Sources: {', '.join(SOURCE_PROFILES.keys())}")
    print(f"{'='*60}\n")
    
    # Generate data for each day
    for day_offset in range(days, 0, -1):
        day_start = now - timedelta(days=day_offset)
        day_start = day_start.replace(hour=0, minute=0, second=0, microsecond=0)
        
        day_events = []
        
        # Generate events for each hour of the day
        for hour in range(24):
            hour_start = day_start + timedelta(hours=hour)
            
            # Calculate interval between events
            interval_seconds = 3600 / events_per_hour
            
            for event_idx in range(events_per_hour):
                # Calculate exact timestamp
                event_time = hour_start + timedelta(seconds=event_idx * interval_seconds)
                
                # Get ground truth state at this time
                state = ground_truth.get_state_at_time(event_time)
                state_dict = state.to_dict()
                
                # Determine if this should be an anomaly period
                is_anomaly = include_anomalies and random.random() < anomaly_probability
                if is_anomaly:
                    anomaly_type = random.choice(anomaly_types)
                    # Apply anomaly modifiers to state
                    if anomaly_type in ANOMALY_PATTERNS:
                        pattern_data = ANOMALY_PATTERNS[anomaly_type]
                        for field, (low, high) in pattern_data.items():
                            if field in state_dict:
                                state_dict[field] = random.uniform(low, high)
                
                # Generate event for each source by sampling this state
                for source_id, profile in SOURCE_PROFILES.items():
                    event = {
                        "event_id": str(uuid.uuid4()),
                        "timestamp": event_time.isoformat(),
                        "user_id": user_id,
                        "source": source_id,
                        "source_name": profile.name,
                    }
                    
                    # Sample each supported field with device noise
                    for field in profile.supported_fields:
                        if field in state_dict:
                            value = state_dict[field]
                            sampled = profile.sample_field(field, value)
                            if sampled is not None:
                                if field in ["heart_rate", "hrv_ms", "respiratory_rate", 
                                            "activity_level", "steps_per_minute", "spo2_percent"]:
                                    event[field] = round(sampled)
                                else:
                                    event[field] = round(sampled, 2)
                    
                    day_events.append(event)
        
        events.extend(day_events)
        print(f"  Generated day {days - day_offset + 1}/{days}: {day_start.date()} ({len(day_events)} events)")
    
    total_events = len(events)
    print(f"\n✓ Generated {total_events} events across {len(SOURCE_PROFILES)} sources")
    
    return events


def setup_anomaly_trigger(producer: MultiSourceProducer):
    """Set up automatic anomaly injection for demo purposes."""
    def trigger_loop():
        time.sleep(60)  # Wait 1 minute before first anomaly
        
        anomaly_sequence = [
            ("tachycardia_at_rest", 30),
            ("hypoxia", 20),
            ("fever_onset", 25),
        ]
        
        while producer.running:
            for anomaly_type, duration in anomaly_sequence:
                if not producer.running:
                    break
                producer.inject_anomaly(anomaly_type, duration)
                # Wait for anomaly to complete + cooldown
                time.sleep(duration + 90)
    
    thread = threading.Thread(target=trigger_loop, daemon=True)
    thread.start()
    return thread


def main():
    """Entry point for the data generator."""
    # Configuration from environment
    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
    user_id = os.environ.get("USER_ID", "user_001")
    auto_anomaly = os.environ.get("AUTO_ANOMALY", "true").lower() == "true"
    
    # Always use multi-source ground truth producer
    producer = MultiSourceProducer(
        bootstrap_servers=bootstrap_servers,
        user_id=user_id,
    )
    
    # Handle shutdown signals
    def signal_handler(signum, frame):
        print("\nReceived shutdown signal...")
        producer.running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start automatic anomaly injection for demo
    if auto_anomaly:
        print("Auto-anomaly injection enabled. First anomaly in 60 seconds.")
        setup_anomaly_trigger(producer)
    
    # Run the multi-source ground truth producer
    producer.run()


# Global multi-source producer for control server access
_multi_source_producer: Optional[MultiSourceProducer] = None


def get_multi_source_producer() -> Optional[MultiSourceProducer]:
    """Get the global multi-source producer instance."""
    return _multi_source_producer


def set_multi_source_producer(producer: MultiSourceProducer):
    """Set the global multi-source producer instance."""
    global _multi_source_producer
    _multi_source_producer = producer


if __name__ == "__main__":
    main()

