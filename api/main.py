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

from kafka_consumer import KafkaStreamConsumer, MessageBuffer
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
        """Broadcast a message to all connected clients."""
        if not self.active_connections:
            return
        
        # Update buffer
        self.message_buffer.add_message(message)
        
        # Store to database
        await self._store_message(message)
        
        # Update stats
        if message["type"] == "vital":
            self.stats["total_vitals"] += 1
        elif message["type"] == "alert":
            self.stats["total_alerts"] += 1
            # Enrich alert with AI insight
            asyncio.create_task(self._enrich_alert(message["data"]))
        
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
    
    async def _store_message(self, message: dict):
        """Store message to database and update baselines."""
        try:
            if message["type"] == "vital":
                await VitalsRepository.insert(message["data"])
                # Auto-update user baseline with each vital reading
                user_id = message["data"].get("user_id", "user_001")
                await BaselinesRepository.auto_update_baseline(user_id, message["data"])
            elif message["type"] == "alert":
                await AlertsRepository.insert(message["data"])
        except Exception as e:
            print(f"Error storing message: {e}")
    
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
    
    # Initialize database
    await init_database()
    
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
