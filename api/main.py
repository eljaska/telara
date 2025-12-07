"""
Telara API Server
FastAPI application with WebSocket support for real-time biometrics streaming
and AI-powered health coaching.
"""

import asyncio
import json
import os
import httpx
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Set, Optional
from uuid import uuid4

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from kafka_consumer import MultiSourceKafkaConsumer, MessageBuffer, SOURCE_CONFIGS
from database import (
    init_database,
    VitalsRepository,
    AlertsRepository,
    BaselinesRepository
)
from claude_agent import get_agent, HealthCoachAgent
from wellness import calculate_wellness_score, get_wellness_recommendations
from correlations import get_correlation_insights
from recommendations import get_recommendations
from digest import generate_daily_digest
from predictions import get_predictions
from historical import get_week_comparison


# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
KAFKA_RAW_TOPIC = os.environ.get("KAFKA_RAW_TOPIC", "biometrics-raw")
KAFKA_ALERTS_TOPIC = os.environ.get("KAFKA_ALERTS_TOPIC", "biometrics-alerts")
GENERATOR_CONTROL_URL = os.environ.get("GENERATOR_CONTROL_URL", "http://data-generator:8001")


# Pydantic models
class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None


class AnomalyInjectRequest(BaseModel):
    anomaly_type: str
    duration_seconds: int = 30


# Global state
class ConnectionManager:
    """Manages WebSocket connections and broadcasts."""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.chat_connections: dict[str, WebSocket] = {}
        self.message_buffer = MessageBuffer()
        self.stats = {
            "total_vitals": 0,
            "total_alerts": 0,
            "connections_total": 0,
        }
        
        # Write buffer for batching database operations
        self._write_buffer: list = []
        self._write_lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._flush_interval = 2.0  # Flush every 2 seconds
        self._max_buffer_size = 50  # Or when buffer reaches 50 items
    
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
    
    async def connect_chat(self, websocket: WebSocket, session_id: str):
        """Accept a chat WebSocket connection."""
        await websocket.accept()
        self.chat_connections[session_id] = websocket
    
    def disconnect_chat(self, session_id: str):
        """Disconnect a chat session."""
        self.chat_connections.pop(session_id, None)
    
    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients (non-blocking)."""
        # Update buffer (synchronous, fast)
        self.message_buffer.add_message(message)
        
        # Update stats (synchronous, fast)
        if message["type"] == "vital":
            self.stats["total_vitals"] += 1
        elif message["type"] == "alert":
            self.stats["total_alerts"] += 1
            # Enrich alert with AI insight (async, non-blocking)
            asyncio.create_task(self._enrich_alert(message["data"]))
        
        # Store to database (non-blocking, runs in background)
        asyncio.create_task(self._store_message(message))
        
        if not self.active_connections:
            return
        
        # Broadcast to all connections in parallel (don't wait for slow clients)
        async def safe_send(ws: WebSocket) -> WebSocket | None:
            try:
                await asyncio.wait_for(ws.send_json(message), timeout=1.0)
                return None
            except Exception:
                return ws
        
        # Send to all clients concurrently with timeout
        results = await asyncio.gather(
            *[safe_send(conn) for conn in self.active_connections],
            return_exceptions=True
        )
        
        # Clean up disconnected/slow clients
        for result in results:
            if isinstance(result, WebSocket):
                self.active_connections.discard(result)
    
    def start_flush_loop(self):
        """Start the background flush loop for batched database writes."""
        if self._flush_task is None or self._flush_task.done():
            self._flush_task = asyncio.create_task(self._flush_loop())
    
    async def _flush_loop(self):
        """Background loop that periodically flushes the write buffer."""
        while True:
            try:
                await asyncio.sleep(self._flush_interval)
                await self._flush_write_buffer()
            except asyncio.CancelledError:
                # Final flush on shutdown
                await self._flush_write_buffer()
                break
            except Exception as e:
                print(f"Error in flush loop: {e}")
    
    async def _flush_write_buffer(self):
        """Flush accumulated messages to database in a batch."""
        async with self._write_lock:
            if not self._write_buffer:
                return
            
            # Grab all messages and clear buffer
            messages = self._write_buffer.copy()
            self._write_buffer.clear()
        
        # Separate vitals and alerts
        vitals = [m["data"] for m in messages if m["type"] == "vital"]
        alerts = [m["data"] for m in messages if m["type"] == "alert"]
        
        # Batch insert vitals
        if vitals:
            try:
                await VitalsRepository.bulk_insert_vitals(vitals)
            except Exception as e:
                print(f"Error batch inserting vitals: {e}")
        
        # Insert alerts individually (usually few)
        for alert in alerts:
            try:
                await AlertsRepository.insert(alert)
            except Exception as e:
                print(f"Error inserting alert: {e}")
        
        # Update baseline with last vital (occasional)
        if vitals and len(vitals) > 0:
            try:
                user_id = vitals[-1].get("user_id", "user_001")
                await BaselinesRepository.auto_update_baseline(user_id, vitals[-1])
            except Exception as e:
                print(f"Error updating baseline: {e}")
    
    async def _store_message(self, message: dict):
        """Queue message for batched database storage."""
        async with self._write_lock:
            self._write_buffer.append(message)
            
            # Force flush if buffer is full
            if len(self._write_buffer) >= self._max_buffer_size:
                # Schedule immediate flush
                asyncio.create_task(self._flush_write_buffer())
    
    async def _enrich_alert(self, alert_data: dict):
        """Enrich alert with AI-generated insight."""
        try:
            agent = await get_agent()
            insight = await agent.generate_alert_insight(alert_data)
            
            if insight:
                # Update in database
                await AlertsRepository.update_insight(alert_data.get("alert_id"), insight)
                
                # Broadcast enriched alert
                enriched_alert = {**alert_data, "ai_insight": insight}
                for connection in self.active_connections:
                    try:
                        await connection.send_json({
                            "type": "alert_enriched",
                            "data": enriched_alert
                        })
                    except:
                        pass
        except Exception as e:
            print(f"Error enriching alert: {e}")


# Global instances
manager = ConnectionManager()
kafka_consumer: MultiSourceKafkaConsumer = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global kafka_consumer
    
    print("=" * 60)
    print("TELARA API SERVER STARTING")
    print(f"  Kafka: {KAFKA_BOOTSTRAP_SERVERS}")
    print(f"  Multi-Source Mode: Enabled")
    print(f"  Sources: Apple, Google, Oura")
    print(f"  Alerts Topic: {KAFKA_ALERTS_TOPIC}")
    print("=" * 60)
    
    # Initialize database
    await init_database()
    
    # Initialize multi-source Kafka consumer
    kafka_consumer = MultiSourceKafkaConsumer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        alerts_topic=KAFKA_ALERTS_TOPIC,
    )
    
    # Register broadcast callback
    kafka_consumer.register_callback(manager.broadcast)
    
    # Start consuming from all source topics
    loop = asyncio.get_event_loop()
    await kafka_consumer.start(loop)
    
    # Start the database write buffer flush loop
    manager.start_flush_loop()
    
    print("✓ Telara API Server ready (multi-source mode)")
    
    yield
    
    # Shutdown
    print("Shutting down Telara API Server...")
    await kafka_consumer.stop()


# Create FastAPI app
app = FastAPI(
    title="Telara API",
    description="Personal Health SOC - Real-time biometrics streaming with AI insights",
    version="2.0.0",
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


# ==============================================================================
# REST Endpoints - Health & Stats
# ==============================================================================

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "Telara API",
        "version": "2.0.0",
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
    source_status = kafka_consumer.get_source_status() if kafka_consumer else {}
    
    return {
        "vitals_processed": manager.stats["total_vitals"],
        "alerts_generated": manager.stats["total_alerts"],
        "active_connections": len(manager.active_connections),
        "total_connections": manager.stats["connections_total"],
        "buffer": {
            "vitals_buffered": len(manager.message_buffer.vitals),
            "alerts_buffered": len(manager.message_buffer.alerts),
        },
        "sources": {
            source_id: {
                "connected": s.get("connected", False),
                "events_received": s.get("events_received", 0),
            }
            for source_id, s in source_status.items()
        }
    }


# ==============================================================================
# REST Endpoints - Data Queries
# ==============================================================================

@app.get("/vitals/recent")
async def get_recent_vitals(minutes: int = Query(default=30, le=1440)):
    """Get recent vital readings."""
    vitals = await VitalsRepository.get_recent(minutes=minutes)
    return {
        "count": len(vitals),
        "period_minutes": minutes,
        "vitals": vitals
    }


@app.get("/vitals/stats")
async def get_vital_stats(hours: int = Query(default=24, le=168)):
    """Get vital statistics."""
    stats = await VitalsRepository.get_stats(hours=hours)
    return stats


@app.get("/alerts/recent")
async def get_recent_alerts(
    hours: int = Query(default=24, le=168),
    severity: Optional[str] = None
):
    """Get recent alerts from database."""
    alerts = await AlertsRepository.get_recent(hours=hours, severity=severity)
    return {
        "count": len(alerts),
        "alerts": alerts,
    }


@app.get("/alerts/summary")
async def get_alert_summary(hours: int = Query(default=24, le=168)):
    """Get alert summary by severity."""
    counts = await AlertsRepository.get_count_by_severity(hours=hours)
    return counts


# ==============================================================================
# REST Endpoints - Wellness Score
# ==============================================================================

@app.get("/wellness/score")
async def get_wellness_score():
    """Get current wellness score with breakdown."""
    vitals = await VitalsRepository.get_recent(minutes=60)
    alerts = await AlertsRepository.get_recent(hours=24)
    baseline = await BaselinesRepository.get()
    
    score, breakdown = await calculate_wellness_score(vitals, alerts, baseline)
    recommendations = get_wellness_recommendations(score, breakdown)
    
    return {
        "score": score,
        "breakdown": breakdown,
        "recommendations": recommendations,
        "calculated_at": datetime.utcnow().isoformat()
    }


@app.get("/wellness/baseline")
async def get_baseline():
    """Get user baseline data."""
    baseline = await BaselinesRepository.get()
    return baseline or {"message": "No baseline established yet"}


@app.get("/wellness/deviation")
async def get_baseline_deviation():
    """
    Check if current vitals deviate from user's personal baseline.
    Returns personalized alerts like 'Your HR is 95 bpm - 20% higher than YOUR typical 78 bpm'.
    """
    latest_vital = await VitalsRepository.get_latest()
    if not latest_vital:
        return {"has_deviation": False, "message": "No recent vitals"}
    
    deviation = await BaselinesRepository.get_deviation_alert("user_001", latest_vital)
    if not deviation:
        return {"has_deviation": False, "message": "Vitals are within your normal range"}
    
    return deviation


# ==============================================================================
# REST Endpoints - Correlations
# ==============================================================================

@app.get("/correlations")
async def get_correlations(hours: int = Query(default=24, le=168)):
    """
    Get correlation insights between health metrics.
    Discovers patterns like 'sleep < 6 hours correlates with 25% lower HRV next day'.
    """
    insights = await get_correlation_insights(hours=hours)
    return insights


# ==============================================================================
# REST Endpoints - Recommendations
# ==============================================================================

@app.get("/recommendations")
async def get_health_recommendations(limit: int = Query(default=5, le=10)):
    """
    Get personalized health recommendations based on current vitals, alerts, and wellness score.
    Returns actionable suggestions prioritized by urgency.
    """
    # Get current data
    vitals = await VitalsRepository.get_recent(minutes=30)
    latest_vital = vitals[0] if vitals else {}
    alerts = await AlertsRepository.get_recent(hours=24)
    baseline = await BaselinesRepository.get()
    
    # Get wellness breakdown
    score, breakdown = await calculate_wellness_score(vitals, alerts, baseline)
    
    # Generate recommendations
    recs = await get_recommendations(
        vitals=latest_vital,
        alerts=alerts,
        wellness_breakdown=breakdown,
        baseline=baseline,
        limit=limit
    )
    
    return recs


# ==============================================================================
# REST Endpoints - Daily Digest
# ==============================================================================

@app.get("/digest/daily")
async def get_daily_digest():
    """
    Get daily health digest - 'Your Day at a Glance'.
    Includes key metrics vs yesterday, AI observations, and recommendations.
    """
    digest = await generate_daily_digest()
    return digest


# ==============================================================================
# REST Endpoints - Predictions
# ==============================================================================

@app.get("/predictions")
async def get_health_predictions(max_hours: float = Query(default=6, le=12)):
    """
    Get predictive health alerts based on current trends.
    Predicts threshold crossings, fatigue, and stress states.
    """
    predictions = await get_predictions(max_hours=max_hours)
    return predictions


# ==============================================================================
# REST Endpoints - Historical Comparison
# ==============================================================================

@app.get("/comparison/weekly")
async def get_weekly_comparison():
    """
    Get week-over-week health comparison.
    Compares this week vs last week with improvements/regressions analysis.
    """
    comparison = await get_week_comparison()
    return comparison


# ==============================================================================
# REST Endpoints - Chat (non-streaming)
# ==============================================================================

@app.post("/chat")
async def chat_endpoint(request: ChatMessage):
    """Send a message to the health coach and get a response."""
    session_id = request.session_id or str(uuid4())
    
    try:
        agent = await get_agent()
        result = await agent.chat(session_id, request.message)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/chat/{session_id}")
async def clear_chat_session(session_id: str):
    """Clear a chat session."""
    agent = await get_agent()
    agent.clear_session(session_id)
    return {"message": "Session cleared"}


# ==============================================================================
# REST Endpoints - Generator Control
# ==============================================================================

@app.get("/generator/status")
async def get_generator_status():
    """Get data generator status."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{GENERATOR_CONTROL_URL}/status")
            return response.json()
    except Exception as e:
        return {"status": "unknown", "error": str(e)}


@app.post("/generator/start")
async def start_generator():
    """Start the data generator."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(f"{GENERATOR_CONTROL_URL}/start")
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generator/stop")
async def stop_generator():
    """Stop the data generator."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(f"{GENERATOR_CONTROL_URL}/stop")
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generator/inject/{anomaly_type}")
async def inject_anomaly(anomaly_type: str, duration: int = Query(default=30, le=120)):
    """Inject a specific anomaly pattern."""
    valid_types = ["tachycardia_at_rest", "hypoxia", "fever_onset", "burnout_stress", "dehydration"]
    
    if anomaly_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid anomaly type. Valid types: {valid_types}"
        )
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{GENERATOR_CONTROL_URL}/inject",
                json={"anomaly_type": anomaly_type, "duration_seconds": duration}
            )
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class HistoricalDataRequest(BaseModel):
    days: int = 7
    events_per_hour: int = 60  # Reduced default for faster generation
    include_anomalies: bool = True
    anomaly_probability: float = 0.05
    pattern: str = "normal"


@app.post("/generator/historical")
async def generate_historical_data(request: HistoricalDataRequest):
    """
    Generate historical biometric data for AI insights (daily digest, weekly comparison).
    
    This endpoint proxies to the data generator to create backdated events,
    then bulk inserts them into the database for immediate availability.
    """
    try:
        # Request historical data from generator with increased timeout
        async with httpx.AsyncClient(timeout=600.0) as client:
            response = await client.post(
                f"{GENERATOR_CONTROL_URL}/generate/historical",
                json={
                    "days": request.days,
                    "events_per_hour": request.events_per_hour,
                    "include_anomalies": request.include_anomalies,
                    "anomaly_probability": request.anomaly_probability,
                    "pattern": request.pattern
                }
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="Generator error")
            
            data = response.json()
            
            if data.get("status") != "generated":
                raise HTTPException(status_code=500, detail=data.get("message", "Generation failed"))
            
            # Bulk insert events into database
            events = data.get("events", [])
            
            if not events:
                return {
                    "status": "success",
                    "message": "No events generated",
                    "inserted": 0
                }
            
            # Bulk insert without updating baselines during insert (avoids locks)
            result = await VitalsRepository.bulk_insert_vitals(events)
            
            return {
                "status": "success",
                "message": f"Generated and inserted {result.get('inserted', 0)} historical events",
                "days": request.days,
                "pattern": request.pattern,
                "inserted": result.get("inserted", 0),
                "failed": result.get("failed", 0)
            }
            
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Generator timeout - try fewer days or events_per_hour")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==============================================================================
# REST Endpoints - Source Management (Multi-Source Integration)
# ==============================================================================

@app.get("/sources")
async def list_sources():
    """
    List all available data sources and their connection status.
    Returns status for Apple HealthKit, Google Fit, and Oura Ring.
    """
    # Get consumer-side status
    consumer_status = kafka_consumer.get_source_status() if kafka_consumer else {}
    
    # Get generator-side status
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{GENERATOR_CONTROL_URL}/sources")
            generator_status = response.json() if response.status_code == 200 else {}
    except:
        generator_status = {}
    
    # Merge statuses
    sources = []
    for source_id, config in SOURCE_CONFIGS.items():
        consumer_source = consumer_status.get(source_id, {})
        generator_source = generator_status.get("sources", {})
        gen_info = next((s for s in generator_source if isinstance(generator_source, list) and s.get("id") == source_id), {}) if isinstance(generator_source, list) else {}
        
        sources.append({
            "id": source_id,
            "name": config["name"],
            "icon": config["icon"],
            "color": config["color"],
            "topic": config["topic"],
            "connected": consumer_source.get("connected", True),
            "enabled": consumer_source.get("enabled", True),
            "events_received": consumer_source.get("events_received", 0),
            "last_event_time": consumer_source.get("last_event_time"),
            "data_types": gen_info.get("data_types", []),
        })
    
    return {
        "sources": sources,
        "total": len(sources),
        "connected_count": sum(1 for s in sources if s["connected"]),
    }


@app.get("/sources/{source_id}")
async def get_source_status(source_id: str):
    """Get detailed status for a specific data source."""
    if source_id not in SOURCE_CONFIGS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown source: {source_id}. Valid sources: {list(SOURCE_CONFIGS.keys())}"
        )
    
    consumer_status = kafka_consumer.get_source_status() if kafka_consumer else {}
    source = consumer_status.get(source_id, {})
    
    return {
        "id": source_id,
        "name": SOURCE_CONFIGS[source_id]["name"],
        "icon": SOURCE_CONFIGS[source_id]["icon"],
        "color": SOURCE_CONFIGS[source_id]["color"],
        "topic": SOURCE_CONFIGS[source_id]["topic"],
        "connected": source.get("connected", True),
        "enabled": source.get("enabled", True),
        "events_received": source.get("events_received", 0),
        "last_event_time": source.get("last_event_time"),
    }


@app.post("/sources/{source_id}/connect")
async def connect_source(source_id: str):
    """
    Connect/enable a data source.
    This enables both consuming from the topic and tells the generator to produce.
    """
    if source_id not in SOURCE_CONFIGS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown source: {source_id}. Valid sources: {list(SOURCE_CONFIGS.keys())}"
        )
    
    # Enable on consumer side
    if kafka_consumer:
        kafka_consumer.enable_source(source_id)
    
    # Enable on generator side
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(f"{GENERATOR_CONTROL_URL}/sources/{source_id}/enable")
            generator_result = response.json() if response.status_code == 200 else {"status": "unknown"}
    except Exception as e:
        generator_result = {"status": "error", "message": str(e)}
    
    return {
        "status": "connected",
        "source_id": source_id,
        "source_name": SOURCE_CONFIGS[source_id]["name"],
        "message": f"Source '{source_id}' is now connected",
        "generator_status": generator_result.get("status", "unknown")
    }


@app.post("/sources/{source_id}/disconnect")
async def disconnect_source(source_id: str):
    """
    Disconnect/disable a data source.
    This stops consuming from the topic and tells the generator to stop producing.
    """
    if source_id not in SOURCE_CONFIGS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown source: {source_id}. Valid sources: {list(SOURCE_CONFIGS.keys())}"
        )
    
    # Disable on consumer side
    if kafka_consumer:
        kafka_consumer.disable_source(source_id)
    
    # Disable on generator side
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(f"{GENERATOR_CONTROL_URL}/sources/{source_id}/disable")
            generator_result = response.json() if response.status_code == 200 else {"status": "unknown"}
    except Exception as e:
        generator_result = {"status": "error", "message": str(e)}
    
    return {
        "status": "disconnected",
        "source_id": source_id,
        "source_name": SOURCE_CONFIGS[source_id]["name"],
        "message": f"Source '{source_id}' is now disconnected",
        "generator_status": generator_result.get("status", "unknown")
    }


@app.get("/sources/stats/summary")
async def get_source_stats_summary():
    """Get aggregated statistics across all sources."""
    if not kafka_consumer:
        return {"error": "Consumer not initialized"}
    
    status = kafka_consumer.get_source_status()
    buffer_stats = manager.message_buffer.get_source_stats()
    
    total_events = sum(s.get("events_received", 0) for s in status.values())
    connected_count = sum(1 for s in status.values() if s.get("connected", False))
    
    return {
        "total_events": total_events,
        "connected_sources": connected_count,
        "total_sources": len(status),
        "per_source": {
            source_id: {
                "events_received": s.get("events_received", 0),
                "connected": s.get("connected", False),
                "last_event_time": s.get("last_event_time"),
            }
            for source_id, s in status.items()
        },
        "buffer_stats": buffer_stats,
    }


# ==============================================================================
# WebSocket Endpoints
# ==============================================================================

@app.websocket("/ws/vitals")
async def websocket_vitals(websocket: WebSocket):
    """
    WebSocket endpoint for real-time biometrics streaming.
    
    Message format (outbound):
    - {"type": "vital", "data": {...}}
    - {"type": "alert", "data": {...}}
    - {"type": "alert_enriched", "data": {...}} - Alert with AI insight
    - {"type": "initial_state", "data": {...}}
    """
    await manager.connect(websocket)
    
    try:
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0
                )
                
                if data == "ping":
                    await websocket.send_text("pong")
                    
            except asyncio.TimeoutError:
                try:
                    await websocket.send_json({
                        "type": "heartbeat",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                except:
                    break
                    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """
    WebSocket endpoint for streaming chat with health coach.
    
    Client sends: {"message": "...", "session_id": "..."}
    Server sends: 
      - {"type": "thinking", "tool": "..."} - When agent uses a tool
      - {"type": "response", "content": "...", "done": false}
      - {"type": "response", "content": "...", "done": true}
    """
    session_id = str(uuid4())
    await manager.connect_chat(websocket, session_id)
    
    try:
        # Send session ID to client
        await websocket.send_json({
            "type": "session_start",
            "session_id": session_id
        })
        
        agent = await get_agent()
        
        while True:
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                user_message = message.get("message", "")
                
                if not user_message:
                    continue
                
                # Use provided session_id if available
                sid = message.get("session_id", session_id)
                
                # Send thinking indicator
                await websocket.send_json({
                    "type": "thinking",
                    "message": "Analyzing your health data..."
                })
                
                # Get response from agent
                result = await agent.chat(sid, user_message)
                
                # Send tool call info if any
                for tool_call in result.get("tool_calls", []):
                    await websocket.send_json({
                        "type": "tool_use",
                        "tool": tool_call["tool"],
                        "preview": tool_call.get("output_preview", "")[:100]
                    })
                
                # Send final response
                await websocket.send_json({
                    "type": "response",
                    "content": result["response"],
                    "session_id": result["session_id"],
                    "done": True
                })
                
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON format"
                })
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"Chat WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass
    finally:
        manager.disconnect_chat(session_id)


@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """WebSocket endpoint for alerts only."""
    await websocket.accept()
    
    async def alert_callback(message: dict):
        if message["type"] in ["alert", "alert_enriched"]:
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
