"""
Telara Biometric Data Generator
Simulates IoT device streams with anomaly injection capability.
"""

import os
import json
import time
import random
import signal
import sys
import threading
from datetime import datetime, timezone
from typing import Optional
import uuid

from confluent_kafka import Producer
from schemas import (
    BiometricEvent, Vitals, Activity, Sleep, Environment,
    DeviceSource, Posture, SleepStage,
    NORMAL_RANGES, ANOMALY_PATTERNS
)


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
    
    def publish_event(self, event: BiometricEvent):
        """Publish a biometric event to Kafka."""
        try:
            # Use flattened format for Flink SQL compatibility
            payload = json.dumps(event.to_flat_dict())
            
            self.producer.produce(
                topic=self.topic,
                key=event.user_id.encode('utf-8'),
                value=payload.encode('utf-8'),
                callback=self.delivery_callback,
            )
            self.producer.poll(0)
            self.events_generated += 1
            
        except Exception as e:
            print(f"✗ Failed to publish event: {e}")
    
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
    topic = os.environ.get("KAFKA_TOPIC", "biometrics-raw")
    interval_ms = int(os.environ.get("EVENT_INTERVAL_MS", "500"))
    user_id = os.environ.get("USER_ID", "user_001")
    auto_anomaly = os.environ.get("AUTO_ANOMALY", "true").lower() == "true"
    
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


if __name__ == "__main__":
    main()

