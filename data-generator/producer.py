"""
Telara Biometric Data Generator
Simulates IoT device streams with anomaly injection capability.
Multi-source architecture: Each health device publishes to its own Kafka topic.
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
    NORMAL_RANGES, ANOMALY_PATTERNS
)


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
    Multi-source biometric producer that publishes to separate Kafka topics
    for each health data source (Apple, Google, Oura).
    """
    
    def __init__(
        self,
        bootstrap_servers: str = "kafka:29092",
        user_id: str = "user_001",
        base_interval_ms: int = 500,
    ):
        self.bootstrap_servers = bootstrap_servers
        self.user_id = user_id
        self.base_interval_ms = base_interval_ms
        self.running = False
        
        # Source states - all enabled by default
        self.sources = {
            source_id: {**config, "enabled": True, "events_generated": 0}
            for source_id, config in SOURCE_CONFIGS.items()
        }
        
        # Single underlying producer for efficiency
        self.producer = BiometricProducer(
            bootstrap_servers=bootstrap_servers,
            user_id=user_id,
            interval_ms=base_interval_ms,
        )
        
        # Locks for thread safety
        self._lock = threading.Lock()
    
    def connect(self) -> bool:
        """Connect to Kafka."""
        return self.producer.connect()
    
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
                    "id": source["id"],
                    "name": source["name"],
                    "topic": source["topic"],
                    "enabled": source["enabled"],
                    "events_generated": source["events_generated"],
                    "data_types": source["data_types"],
                }
                for source_id, source in self.sources.items()
            }
    
    def inject_anomaly(self, anomaly_type: str, duration_seconds: int = 30):
        """Inject an anomaly that affects all sources."""
        self.producer.inject_anomaly(anomaly_type, duration_seconds)
    
    def generate_and_publish(self):
        """Generate events for all enabled sources and publish to their topics."""
        with self._lock:
            enabled_sources = [s for s in self.sources.values() if s["enabled"]]
        
        for source_config in enabled_sources:
            try:
                # Generate source-specific event
                event = self.producer.generate_source_event(source_config)
                
                # Add source identifier to the flat dict
                event_dict = event.to_flat_dict()
                event_dict["source"] = source_config["id"]
                event_dict["source_name"] = source_config["name"]
                
                # Publish to source-specific topic
                payload = json.dumps(event_dict)
                self.producer.producer.produce(
                    topic=source_config["topic"],
                    key=event.user_id.encode('utf-8'),
                    value=payload.encode('utf-8'),
                    callback=self.producer.delivery_callback,
                )
                self.producer.producer.poll(0)
                
                # Update stats
                with self._lock:
                    self.sources[source_config["id"]]["events_generated"] += 1
                
            except Exception as e:
                print(f"✗ Error publishing to {source_config['topic']}: {e}")
    
    def print_status(self):
        """Print current status to console."""
        with self._lock:
            enabled = [s["id"] for s in self.sources.values() if s["enabled"]]
            total_events = sum(s["events_generated"] for s in self.sources.values())
        
        anomaly_indicator = f" ⚠ [{self.producer.anomaly_active}]" if self.producer.anomaly_active else ""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        print(f"[{timestamp}] Sources: {','.join(enabled)} | Events: {total_events}{anomaly_indicator}")
    
    def run(self):
        """Main loop to generate and publish events from all sources."""
        if not self.connect():
            return
        
        self.running = True
        self.producer.running = True
        
        print(f"\n{'='*60}")
        print(f"TELARA MULTI-SOURCE DATA GENERATOR STARTED")
        print(f"  User: {self.user_id}")
        print(f"  Base Interval: {self.base_interval_ms}ms")
        print(f"  Sources:")
        for source in self.sources.values():
            status = "✓" if source["enabled"] else "✗"
            print(f"    {status} {source['name']} -> {source['topic']}")
        print(f"{'='*60}\n")
        
        interval_sec = self.base_interval_ms / 1000.0
        last_print_time = 0
        
        while self.running:
            try:
                self.generate_and_publish()
                
                # Print status every 5 seconds
                current_time = time.time()
                if current_time - last_print_time >= 5:
                    self.print_status()
                    last_print_time = current_time
                
                time.sleep(interval_sec)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"✗ Error in main loop: {e}")
                time.sleep(1)
        
        self.shutdown()
    
    def shutdown(self):
        """Clean shutdown."""
        self.running = False
        self.producer.running = False
        
        print(f"\n{'='*60}")
        print(f"TELARA MULTI-SOURCE DATA GENERATOR SHUTDOWN")
        for source in self.sources.values():
            print(f"  {source['name']}: {source['events_generated']} events")
        print(f"{'='*60}")
        
        if self.producer.producer:
            self.producer.producer.flush(timeout=5)


def generate_historical_data(
    user_id: str = "user_001",
    days: int = 7,
    events_per_hour: int = 120,
    include_anomalies: bool = True,
    anomaly_probability: float = 0.05,
    pattern: str = "normal"
) -> List[Dict[str, Any]]:
    """
    Generate historical biometric data for the specified number of days.
    
    Args:
        user_id: User ID for the generated data
        days: Number of days of history to generate
        events_per_hour: Events to generate per hour (default 120 = 2/min)
        include_anomalies: Whether to randomly include anomalies
        anomaly_probability: Probability of an event being anomalous
        pattern: One of 'normal', 'improving', 'declining', 'variable'
    
    Returns:
        List of vital event dictionaries ready for database insertion
    """
    producer = BiometricProducer(user_id=user_id)
    events = []
    
    now = datetime.now(timezone.utc)
    anomaly_types = list(ANOMALY_PATTERNS.keys())
    
    print(f"\n{'='*60}")
    print(f"GENERATING HISTORICAL DATA")
    print(f"  User: {user_id}")
    print(f"  Days: {days}")
    print(f"  Events/hour: {events_per_hour}")
    print(f"  Pattern: {pattern}")
    print(f"  Include anomalies: {include_anomalies}")
    print(f"{'='*60}\n")
    
    # Generate data for each day
    for day_offset in range(days, 0, -1):
        day_start = now - timedelta(days=day_offset)
        day_start = day_start.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Generate events for each hour of the day
        for hour in range(24):
            hour_start = day_start + timedelta(hours=hour)
            
            # Calculate interval between events
            interval_seconds = 3600 / events_per_hour
            
            for event_idx in range(events_per_hour):
                # Calculate exact timestamp
                event_time = hour_start + timedelta(seconds=event_idx * interval_seconds)
                
                # Determine if this event should be anomalous
                is_anomaly = include_anomalies and random.random() < anomaly_probability
                anomaly_type = random.choice(anomaly_types) if is_anomaly else None
                
                # Generate the event
                event = producer.generate_historical_event(
                    timestamp=event_time,
                    hour_of_day=hour,
                    pattern=pattern,
                    day_offset=-day_offset,
                    include_anomaly=is_anomaly,
                    anomaly_type=anomaly_type
                )
                events.append(event)
        
        print(f"  Generated day {days - day_offset + 1}/{days}: {day_start.date()}")
    
    total_events = len(events)
    anomaly_count = sum(1 for e in events if e.get("heart_rate", 0) > 100 or e.get("spo2_percent", 100) < 95)
    
    print(f"\n✓ Generated {total_events} events")
    print(f"  Estimated anomalies: {anomaly_count}")
    
    return events


def setup_anomaly_trigger(producer: BiometricProducer):
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
    interval_ms = int(os.environ.get("EVENT_INTERVAL_MS", "500"))
    user_id = os.environ.get("USER_ID", "user_001")
    auto_anomaly = os.environ.get("AUTO_ANOMALY", "true").lower() == "true"
    multi_source = os.environ.get("MULTI_SOURCE", "true").lower() == "true"
    
    if multi_source:
        # Use multi-source producer (publishes to separate topics per source)
        producer = MultiSourceProducer(
            bootstrap_servers=bootstrap_servers,
            user_id=user_id,
            base_interval_ms=interval_ms,
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
            setup_anomaly_trigger(producer.producer)
        
        # Run the multi-source producer
        producer.run()
    else:
        # Legacy single-topic mode
        topic = os.environ.get("KAFKA_TOPIC", "biometrics-raw")
        producer = BiometricProducer(
            bootstrap_servers=bootstrap_servers,
            topic=topic,
            user_id=user_id,
            interval_ms=interval_ms,
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
        
        # Run the producer
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

