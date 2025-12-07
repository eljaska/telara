"""
Telara Kafka Consumer
Multi-source async consumer for biometrics from multiple health data sources.
"""

import asyncio
import json
import os
from typing import AsyncGenerator, Callable, Optional, Set, Dict, Any, List
from confluent_kafka import Consumer, KafkaError, KafkaException
import threading
from datetime import datetime


# Source configurations matching the data generator
SOURCE_CONFIGS = {
    "apple": {
        "id": "apple",
        "name": "Apple HealthKit",
        "topic": "biometrics-apple",
        "icon": "🍎",
        "color": "#FF3B30",
    },
    "google": {
        "id": "google",
        "name": "Google Fit",
        "topic": "biometrics-google",
        "icon": "🏃",
        "color": "#4285F4",
    },
    "oura": {
        "id": "oura",
        "name": "Oura Ring",
        "topic": "biometrics-oura",
        "icon": "💍",
        "color": "#8B5CF6",
    },
}


class MultiSourceKafkaConsumer:
    """
    Async Kafka consumer that streams messages from multiple health data sources.
    Each source has its own topic and can be enabled/disabled independently.
    """
    
    def __init__(
        self,
        bootstrap_servers: str = "kafka:29092",
        alerts_topic: str = "biometrics-alerts",
        group_id: str = "telara-api-consumer",
    ):
        self.bootstrap_servers = bootstrap_servers
        self.alerts_topic = alerts_topic
        self.group_id = group_id
        
        self.running = False
        self.message_callbacks: Set[Callable] = set()
        self._consumer_threads: List[threading.Thread] = []
        self._consumers: Dict[str, Consumer] = {}
        self._lock = threading.RLock()
        
        # Source states - all enabled by default
        self.sources: Dict[str, Dict[str, Any]] = {}
        for source_id, config in SOURCE_CONFIGS.items():
            self.sources[source_id] = {
                **config,
                "enabled": True,
                "connected": True,
                "events_received": 0,
                "last_event_time": None,
            }
    
    def _create_consumer(self, topics: List[str], suffix: str = "") -> Consumer:
        """Create a Kafka consumer for the specified topics."""
        config = {
            'bootstrap.servers': self.bootstrap_servers,
            'group.id': f"{self.group_id}-{suffix}",
            'auto.offset.reset': 'latest',
            'enable.auto.commit': True,
            'session.timeout.ms': 10000,
        }
        consumer = Consumer(config)
        consumer.subscribe(topics)
        return consumer
    
    def enable_source(self, source_id: str) -> bool:
        """Enable consuming from a data source."""
        with self._lock:
            if source_id in self.sources:
                self.sources[source_id]["enabled"] = True
                self.sources[source_id]["connected"] = True
                print(f"✓ Enabled source: {source_id}")
                return True
            return False
    
    def disable_source(self, source_id: str) -> bool:
        """Disable consuming from a data source."""
        with self._lock:
            if source_id in self.sources:
                self.sources[source_id]["enabled"] = False
                self.sources[source_id]["connected"] = False
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
                    "icon": source["icon"],
                    "color": source["color"],
                    "enabled": source["enabled"],
                    "connected": source["connected"],
                    "events_received": source["events_received"],
                    "last_event_time": source["last_event_time"],
                }
                for source_id, source in self.sources.items()
            }
    
    def register_callback(self, callback: Callable):
        """Register a callback function to receive messages."""
        self.message_callbacks.add(callback)
        
    def unregister_callback(self, callback: Callable):
        """Unregister a callback function."""
        self.message_callbacks.discard(callback)
    
    async def _dispatch_message(self, message_type: str, data: dict, source_id: Optional[str] = None):
        """Dispatch message to all registered callbacks."""
        # Add source info to message
        if source_id and source_id in self.sources:
            data["source"] = source_id
            data["source_name"] = self.sources[source_id]["name"]
        
        message = {
            "type": message_type,
            "data": data,
        }
        
        for callback in list(self.message_callbacks):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(message)
                else:
                    callback(message)
            except Exception as e:
                print(f"Error in callback: {e}")
    
    def _source_consume_loop(
        self, 
        consumer: Consumer, 
        source_id: str, 
        loop: asyncio.AbstractEventLoop
    ):
        """Consumer loop for a specific source running in a separate thread."""
        print(f"Starting consumer loop for source: {source_id}...")
        
        while self.running:
            try:
                # Check if source is enabled
                with self._lock:
                    if not self.sources.get(source_id, {}).get("enabled", False):
                        # Source disabled, just sleep and continue
                        import time
                        time.sleep(0.5)
                        continue
                
                # Reduced poll timeout (100ms) for smoother real-time delivery
                # Lower timeout = less batching = more even event distribution to UI
                msg = consumer.poll(timeout=0.1)
                
                if msg is None:
                    continue
                    
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        print(f"Consumer error ({source_id}): {msg.error()}")
                        continue
                
                try:
                    value = json.loads(msg.value().decode('utf-8'))
                    
                    # Update source stats
                    with self._lock:
                        self.sources[source_id]["events_received"] += 1
                        self.sources[source_id]["last_event_time"] = datetime.utcnow().isoformat()
                    
                    # Normalize the message (ensure consistent field names)
                    normalized = self._normalize_message(value, source_id)
                    
                    # Dispatch to callbacks via event loop
                    asyncio.run_coroutine_threadsafe(
                        self._dispatch_message("vital", normalized, source_id),
                        loop
                    )
                    
                except json.JSONDecodeError as e:
                    print(f"JSON decode error ({source_id}): {e}")
                    
            except Exception as e:
                if self.running:
                    print(f"Error in consume loop ({source_id}): {e}")
                    
        consumer.close()
        print(f"Consumer loop for source {source_id} stopped.")
    
    def _alerts_consume_loop(self, consumer: Consumer, loop: asyncio.AbstractEventLoop):
        """Consumer loop for alerts topic."""
        print("Starting consumer loop for alerts...")
        
        while self.running:
            try:
                # Reduced poll timeout (100ms) for smoother real-time delivery
                msg = consumer.poll(timeout=0.1)
                
                if msg is None:
                    continue
                    
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        print(f"Consumer error (alerts): {msg.error()}")
                        continue
                
                try:
                    value = json.loads(msg.value().decode('utf-8'))
                    
                    # Dispatch to callbacks via event loop
                    asyncio.run_coroutine_threadsafe(
                        self._dispatch_message("alert", value),
                        loop
                    )
                    
                except json.JSONDecodeError as e:
                    print(f"JSON decode error (alerts): {e}")
                    
            except Exception as e:
                if self.running:
                    print(f"Error in alerts consume loop: {e}")
                    
        consumer.close()
        print("Consumer loop for alerts stopped.")
    
    def _normalize_message(self, data: dict, source_id: str) -> dict:
        """
        Normalize message from different sources to a unified schema.
        This handles any source-specific field mappings.
        """
        # The data generator already provides normalized data,
        # but this is where we'd handle real-world variations like:
        # - Apple: HKQuantityTypeIdentifierHeartRate -> heart_rate
        # - Google: com.google.heart_rate.bpm -> heart_rate
        # - Oura: hr -> heart_rate
        
        normalized = data.copy()
        
        # Ensure source is set
        if "source" not in normalized:
            normalized["source"] = source_id
        if "source_name" not in normalized:
            normalized["source_name"] = self.sources.get(source_id, {}).get("name", source_id)
        
        return normalized
    
    async def start(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        """Start consuming from all source topics."""
        if loop is None:
            loop = asyncio.get_event_loop()
            
        self.running = True
        
        # Wait for Kafka to be ready
        await self._wait_for_kafka()
        
        # Create consumers for each source topic
        for source_id, source in self.sources.items():
            topic = source["topic"]
            consumer = self._create_consumer([topic], suffix=f"source-{source_id}")
            self._consumers[source_id] = consumer
            
            thread = threading.Thread(
                target=self._source_consume_loop,
                args=(consumer, source_id, loop),
                daemon=True
            )
            self._consumer_threads.append(thread)
            thread.start()
        
        # Create consumer for alerts topic
        alerts_consumer = self._create_consumer([self.alerts_topic], suffix="alerts")
        self._consumers["alerts"] = alerts_consumer
        
        alerts_thread = threading.Thread(
            target=self._alerts_consume_loop,
            args=(alerts_consumer, loop),
            daemon=True
        )
        self._consumer_threads.append(alerts_thread)
        alerts_thread.start()
        
        source_topics = [s["topic"] for s in self.sources.values()]
        print(f"Kafka consumers started for topics: {', '.join(source_topics)}, {self.alerts_topic}")
    
    async def _wait_for_kafka(self, max_retries: int = 30, retry_delay: float = 2.0):
        """Wait for Kafka to become available."""
        from confluent_kafka.admin import AdminClient
        
        admin_config = {'bootstrap.servers': self.bootstrap_servers}
        
        for attempt in range(max_retries):
            try:
                admin = AdminClient(admin_config)
                admin.list_topics(timeout=5)
                print(f"✓ Connected to Kafka at {self.bootstrap_servers}")
                return
            except Exception as e:
                print(f"[{attempt + 1}/{max_retries}] Waiting for Kafka: {e}")
                await asyncio.sleep(retry_delay)
        
        raise Exception("Could not connect to Kafka after max retries")
    
    async def stop(self):
        """Stop consuming."""
        self.running = False
        
        # Wait for consumer threads to finish
        for thread in self._consumer_threads:
            thread.join(timeout=5)
        
        print("Kafka consumers stopped.")


# Legacy single-topic consumer for backwards compatibility
class KafkaStreamConsumer:
    """
    Legacy Kafka consumer - kept for backwards compatibility.
    Use MultiSourceKafkaConsumer for new code.
    """
    
    def __init__(
        self,
        bootstrap_servers: str = "kafka:29092",
        raw_topic: str = "biometrics-raw",
        alerts_topic: str = "biometrics-alerts",
        group_id: str = "telara-api-consumer",
    ):
        self.bootstrap_servers = bootstrap_servers
        self.raw_topic = raw_topic
        self.alerts_topic = alerts_topic
        self.group_id = group_id
        
        self.running = False
        self.consumers: dict = {}
        self.message_callbacks: Set[Callable] = set()
        self._consumer_threads: list = []
        
    def _create_consumer(self, topics: list) -> Consumer:
        """Create a Kafka consumer for the specified topics."""
        config = {
            'bootstrap.servers': self.bootstrap_servers,
            'group.id': f"{self.group_id}-{'-'.join(topics)}",
            'auto.offset.reset': 'latest',
            'enable.auto.commit': True,
            'session.timeout.ms': 10000,
        }
        consumer = Consumer(config)
        consumer.subscribe(topics)
        return consumer
    
    def register_callback(self, callback: Callable):
        """Register a callback function to receive messages."""
        self.message_callbacks.add(callback)
        
    def unregister_callback(self, callback: Callable):
        """Unregister a callback function."""
        self.message_callbacks.discard(callback)
    
    async def _dispatch_message(self, message_type: str, data: dict):
        """Dispatch message to all registered callbacks."""
        message = {
            "type": message_type,
            "data": data,
        }
        
        for callback in list(self.message_callbacks):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(message)
                else:
                    callback(message)
            except Exception as e:
                print(f"Error in callback: {e}")
    
    def _consume_loop(self, consumer: Consumer, message_type: str, loop: asyncio.AbstractEventLoop):
        """Consumer loop running in a separate thread."""
        print(f"Starting consumer loop for {message_type}...")
        
        while self.running:
            try:
                msg = consumer.poll(timeout=0.5)
                
                if msg is None:
                    continue
                    
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        print(f"Consumer error: {msg.error()}")
                        continue
                
                try:
                    value = json.loads(msg.value().decode('utf-8'))
                    
                    # Dispatch to callbacks via event loop
                    asyncio.run_coroutine_threadsafe(
                        self._dispatch_message(message_type, value),
                        loop
                    )
                    
                except json.JSONDecodeError as e:
                    print(f"JSON decode error: {e}")
                    
            except Exception as e:
                if self.running:
                    print(f"Error in consume loop: {e}")
                    
        consumer.close()
        print(f"Consumer loop for {message_type} stopped.")
    
    async def start(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        """Start consuming from Kafka topics."""
        if loop is None:
            loop = asyncio.get_event_loop()
            
        self.running = True
        
        # Wait for Kafka to be ready
        await self._wait_for_kafka()
        
        # Create consumers for each topic type
        raw_consumer = self._create_consumer([self.raw_topic])
        alerts_consumer = self._create_consumer([self.alerts_topic])
        
        # Start consumer threads
        raw_thread = threading.Thread(
            target=self._consume_loop,
            args=(raw_consumer, "vital", loop),
            daemon=True
        )
        alerts_thread = threading.Thread(
            target=self._consume_loop,
            args=(alerts_consumer, "alert", loop),
            daemon=True
        )
        
        self._consumer_threads = [raw_thread, alerts_thread]
        
        raw_thread.start()
        alerts_thread.start()
        
        print(f"Kafka consumers started for topics: {self.raw_topic}, {self.alerts_topic}")
    
    async def _wait_for_kafka(self, max_retries: int = 30, retry_delay: float = 2.0):
        """Wait for Kafka to become available."""
        from confluent_kafka.admin import AdminClient
        
        admin_config = {'bootstrap.servers': self.bootstrap_servers}
        
        for attempt in range(max_retries):
            try:
                admin = AdminClient(admin_config)
                admin.list_topics(timeout=5)
                print(f"✓ Connected to Kafka at {self.bootstrap_servers}")
                return
            except Exception as e:
                print(f"[{attempt + 1}/{max_retries}] Waiting for Kafka: {e}")
                await asyncio.sleep(retry_delay)
        
        raise Exception("Could not connect to Kafka after max retries")
    
    async def stop(self):
        """Stop consuming."""
        self.running = False
        
        # Wait for consumer threads to finish
        for thread in self._consumer_threads:
            thread.join(timeout=5)
        
        print("Kafka consumers stopped.")


class MessageBuffer:
    """
    Buffers recent messages for new WebSocket connections.
    Provides historical context when clients connect.
    """
    
    def __init__(self, max_vitals: int = 100, max_alerts: int = 50):
        self.max_vitals = max_vitals
        self.max_alerts = max_alerts
        self.vitals: list = []
        self.alerts: list = []
        self._lock = threading.Lock()
        
        # Per-source stats
        self.source_stats: Dict[str, Dict[str, Any]] = {
            source_id: {"count": 0, "last_time": None}
            for source_id in SOURCE_CONFIGS.keys()
        }
    
    def add_message(self, message: dict):
        """Add a message to the appropriate buffer."""
        with self._lock:
            if message["type"] == "vital":
                self.vitals.append(message)
                if len(self.vitals) > self.max_vitals:
                    self.vitals.pop(0)
                
                # Update source stats
                source = message.get("data", {}).get("source")
                if source and source in self.source_stats:
                    self.source_stats[source]["count"] += 1
                    self.source_stats[source]["last_time"] = datetime.utcnow().isoformat()
                    
            elif message["type"] == "alert":
                self.alerts.append(message)
                if len(self.alerts) > self.max_alerts:
                    self.alerts.pop(0)
    
    def get_recent_vitals(self, count: int = 50) -> list:
        """Get recent vital messages."""
        with self._lock:
            return self.vitals[-count:].copy()
    
    def get_recent_alerts(self, count: int = 20) -> list:
        """Get recent alert messages."""
        with self._lock:
            return self.alerts[-count:].copy()
    
    def get_source_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get per-source message statistics."""
        with self._lock:
            return self.source_stats.copy()
    
    def get_initial_state(self) -> dict:
        """Get initial state for new WebSocket connections."""
        with self._lock:
            return {
                "type": "initial_state",
                "data": {
                    "vitals": self.vitals[-50:].copy(),
                    "alerts": self.alerts[-20:].copy(),
                    "source_stats": self.source_stats.copy(),
                }
            }
