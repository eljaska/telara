"""
Telara Kafka Consumer
Async consumer for biometrics and alerts topics.
"""

import asyncio
import json
import os
from typing import AsyncGenerator, Callable, Optional, Set
from confluent_kafka import Consumer, KafkaError, KafkaException
import threading


class KafkaStreamConsumer:
    """
    Async Kafka consumer that streams messages to WebSocket clients.
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
    
    def add_message(self, message: dict):
        """Add a message to the appropriate buffer."""
        with self._lock:
            if message["type"] == "vital":
                self.vitals.append(message)
                if len(self.vitals) > self.max_vitals:
                    self.vitals.pop(0)
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
    
    def get_initial_state(self) -> dict:
        """Get initial state for new WebSocket connections."""
        with self._lock:
            return {
                "type": "initial_state",
                "data": {
                    "vitals": self.vitals[-50:].copy(),
                    "alerts": self.alerts[-20:].copy(),
                }
            }

