"""
Telara API Server
FastAPI application with WebSocket support for real-time biometrics streaming.
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from kafka_consumer import KafkaStreamConsumer, MessageBuffer


# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
KAFKA_RAW_TOPIC = os.environ.get("KAFKA_RAW_TOPIC", "biometrics-raw")
KAFKA_ALERTS_TOPIC = os.environ.get("KAFKA_ALERTS_TOPIC", "biometrics-alerts")


# Global state
class ConnectionManager:
    """Manages WebSocket connections and broadcasts."""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.message_buffer = MessageBuffer()
        self.stats = {
            "total_vitals": 0,
            "total_alerts": 0,
            "connections_total": 0,
        }
    
    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        self.stats["connections_total"] += 1
        
        # Send initial state with recent data
        initial_state = self.message_buffer.get_initial_state()
        await websocket.send_json(initial_state)
        
        print(f"WebSocket connected. Active connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Unregister a WebSocket connection."""
        self.active_connections.discard(websocket)
        print(f"WebSocket disconnected. Active connections: {len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients."""
        if not self.active_connections:
            return
        
        # Update buffer
        self.message_buffer.add_message(message)
        
        # Update stats
        if message["type"] == "vital":
            self.stats["total_vitals"] += 1
        elif message["type"] == "alert":
            self.stats["total_alerts"] += 1
        
        # Broadcast to all connections
        disconnected = set()
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.add(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.active_connections.discard(conn)


# Global instances
manager = ConnectionManager()
kafka_consumer: KafkaStreamConsumer = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global kafka_consumer
    
    print("=" * 60)
    print("TELARA API SERVER STARTING")
    print(f"  Kafka: {KAFKA_BOOTSTRAP_SERVERS}")
    print(f"  Raw Topic: {KAFKA_RAW_TOPIC}")
    print(f"  Alerts Topic: {KAFKA_ALERTS_TOPIC}")
    print("=" * 60)
    
    # Initialize Kafka consumer
    kafka_consumer = KafkaStreamConsumer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        raw_topic=KAFKA_RAW_TOPIC,
        alerts_topic=KAFKA_ALERTS_TOPIC,
    )
    
    # Register broadcast callback
    kafka_consumer.register_callback(manager.broadcast)
    
    # Start consuming
    loop = asyncio.get_event_loop()
    await kafka_consumer.start(loop)
    
    print("✓ Telara API Server ready")
    
    yield
    
    # Shutdown
    print("Shutting down Telara API Server...")
    await kafka_consumer.stop()


# Create FastAPI app
app = FastAPI(
    title="Telara API",
    description="Personal Health SOC - Real-time biometrics streaming API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# REST Endpoints
@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "Telara API",
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/health")
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "kafka_connected": kafka_consumer is not None and kafka_consumer.running,
        "websocket_connections": len(manager.active_connections),
        "stats": manager.stats,
    }


@app.get("/stats")
async def get_stats():
    """Get streaming statistics."""
    return {
        "vitals_processed": manager.stats["total_vitals"],
        "alerts_generated": manager.stats["total_alerts"],
        "active_connections": len(manager.active_connections),
        "total_connections": manager.stats["connections_total"],
        "buffer": {
            "vitals_buffered": len(manager.message_buffer.vitals),
            "alerts_buffered": len(manager.message_buffer.alerts),
        }
    }


@app.get("/alerts/recent")
async def get_recent_alerts(limit: int = 20):
    """Get recent alerts from buffer."""
    alerts = manager.message_buffer.get_recent_alerts(limit)
    return {
        "count": len(alerts),
        "alerts": [a["data"] for a in alerts],
    }


@app.post("/anomaly/inject/{anomaly_type}")
async def inject_anomaly(anomaly_type: str, duration: int = 30):
    """
    API endpoint to trigger anomaly injection in the data generator.
    Note: This requires the data generator to expose an HTTP endpoint.
    For the hackathon, anomalies are auto-triggered in the generator.
    """
    valid_types = ["tachycardia_at_rest", "hypoxia", "fever_onset", "burnout_stress", "dehydration"]
    
    if anomaly_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid anomaly type. Valid types: {valid_types}"
        )
    
    # In a full implementation, this would call the data generator
    return {
        "message": f"Anomaly injection requested: {anomaly_type}",
        "duration": duration,
        "note": "Auto-anomaly injection is enabled in the data generator",
    }


# WebSocket Endpoint
@app.websocket("/ws/vitals")
async def websocket_vitals(websocket: WebSocket):
    """
    WebSocket endpoint for real-time biometrics streaming.
    
    Message format (outbound):
    - {"type": "vital", "data": {...}}  - Real-time vital signs
    - {"type": "alert", "data": {...}}  - Anomaly alerts from Flink
    - {"type": "initial_state", "data": {"vitals": [...], "alerts": [...]}}
    """
    await manager.connect(websocket)
    
    try:
        while True:
            # Keep connection alive and handle client messages
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0
                )
                
                # Handle ping/pong
                if data == "ping":
                    await websocket.send_text("pong")
                    
            except asyncio.TimeoutError:
                # Send heartbeat
                try:
                    await websocket.send_json({"type": "heartbeat", "timestamp": datetime.utcnow().isoformat()})
                except:
                    break
                    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)


# Alternative WebSocket for alerts only
@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """WebSocket endpoint for alerts only (lighter bandwidth)."""
    await websocket.accept()
    
    # Create a filtered callback for alerts only
    async def alert_callback(message: dict):
        if message["type"] == "alert":
            try:
                await websocket.send_json(message)
            except:
                pass
    
    kafka_consumer.register_callback(alert_callback)
    
    try:
        while True:
            await asyncio.sleep(30)
            await websocket.send_json({"type": "heartbeat"})
    except WebSocketDisconnect:
        pass
    finally:
        kafka_consumer.unregister_callback(alert_callback)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )

