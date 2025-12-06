# TELARA - Personal Health SOC

> "A Security Operations Center for the Human Body"

Real-time health analytics platform that detects anomalies in biometric data using enterprise-grade streaming infrastructure. Built for the Palo Alto Networks Product Engineering Hackathon 2025.

![Architecture](https://img.shields.io/badge/Architecture-Event%20Driven-blue)
![Kafka](https://img.shields.io/badge/Apache%20Kafka-7.5.0-orange)
![Flink](https://img.shields.io/badge/Apache%20Flink-1.18-purple)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104-green)
![React](https://img.shields.io/badge/React-18.2-cyan)

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Data Generator │───▶│   Apache Kafka  │◀───│   PyFlink CEP   │
│    (Python)     │    │   biometrics-   │    │ MATCH_RECOGNIZE │
└─────────────────┘    │      raw        │    └────────┬────────┘
                       └────────┬────────┘             │
                                │                      │
                       ┌────────▼────────┐    ┌────────▼────────┐
                       │  FastAPI + WS   │◀───│  biometrics-    │
                       │   API Server    │    │     alerts      │
                       └────────┬────────┘    └─────────────────┘
                                │
                       ┌────────▼────────┐
                       │  React Dashboard │
                       │   (SOC Theme)   │
                       └─────────────────┘
```

## Quick Start

### Prerequisites

- Docker Desktop with Docker Compose v2
- At least 8GB RAM allocated to Docker
- Ports available: 2181, 9092, 8081, 8000, 5173

### 1. Start All Services

```bash
# Clone and enter directory
cd telara

# Start the entire stack
docker compose up --build
```

### 2. Access the Dashboard

Open your browser to: **http://localhost:5173**

### 3. Monitor Services

| Service | URL | Description |
|---------|-----|-------------|
| Dashboard | http://localhost:5173 | Main health SOC dashboard |
| API | http://localhost:8000 | FastAPI server |
| API Docs | http://localhost:8000/docs | OpenAPI documentation |
| Flink UI | http://localhost:8081 | Flink job monitoring |

## Anomaly Detection Patterns

The PyFlink processor detects the following health anomalies using `MATCH_RECOGNIZE` pattern matching:

### 1. Tachycardia at Rest
- **Pattern**: 5+ consecutive events where HR > 100 bpm while activity_level < 10
- **Severity**: HIGH/CRITICAL based on HR level
- **Clinical relevance**: May indicate cardiac stress, anxiety, or fever

### 2. Low SpO2 (Hypoxia)
- **Pattern**: 3+ consecutive events where SpO2 < 94%
- **Severity**: CRITICAL if < 90%, HIGH if < 92%
- **Clinical relevance**: Respiratory distress, altitude sickness, or illness

### 3. Elevated Temperature
- **Pattern**: 3+ consecutive events where skin_temp > 37.5°C
- **Severity**: CRITICAL if > 38.5°C
- **Clinical relevance**: Fever onset, infection indicator

## Data Schema

### Biometric Event (biometrics-raw topic)

```json
{
  "event_id": "uuid",
  "timestamp": "2025-12-06T14:30:00.000Z",
  "user_id": "user_001",
  "device_sources": ["apple_watch", "oura_ring"],
  "heart_rate": 72,
  "hrv_ms": 45,
  "spo2_percent": 98,
  "skin_temp_c": 36.2,
  "respiratory_rate": 14,
  "activity_level": 5,
  "steps_per_minute": 0,
  "posture": "seated"
}
```

### Alert Event (biometrics-alerts topic)

```json
{
  "alert_id": "uuid",
  "alert_type": "TACHYCARDIA_AT_REST",
  "user_id": "user_001",
  "severity": "HIGH",
  "start_time": "2025-12-06T14:30:00.000Z",
  "end_time": "2025-12-06T14:30:15.000Z",
  "avg_heart_rate": 115.4,
  "event_count": 5,
  "description": "Sustained elevated HR detected while at rest"
}
```

## Development

### Project Structure

```
telara/
├── docker-compose.yml      # Orchestration
├── data-generator/         # Python biometrics producer
│   ├── producer.py
│   └── schemas.py
├── stream-processor/       # PyFlink CEP job
│   └── flink_job.py
├── api/                    # FastAPI WebSocket server
│   ├── main.py
│   └── kafka_consumer.py
└── frontend/               # React dashboard
    └── src/
        ├── components/
        │   ├── Dashboard.tsx
        │   ├── VitalChart.tsx
        │   └── ThreatLog.tsx
        └── hooks/
            └── useWebSocket.ts
```

### Manual Anomaly Injection

The data generator automatically triggers anomalies every ~2 minutes for demo purposes. To manually trigger:

```bash
# View current data flow
docker logs -f telara-data-generator

# The generator cycles through anomaly patterns automatically
```

### Kafka CLI Commands

```bash
# List topics
docker exec telara-kafka kafka-topics --list --bootstrap-server localhost:9092

# Watch raw biometrics
docker exec telara-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic biometrics-raw \
  --from-latest

# Watch alerts
docker exec telara-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic biometrics-alerts \
  --from-latest
```

### Service Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f flink-jobmanager
docker compose logs -f data-generator
docker compose logs -f api
```

## Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Message Bus | Apache Kafka 7.5 | High-throughput event streaming |
| Stream Processing | Apache Flink 1.18 (PyFlink) | Real-time CEP with MATCH_RECOGNIZE |
| API Server | FastAPI + WebSockets | Real-time data serving |
| Frontend | React 18 + TypeScript + Recharts | SOC-style dashboard |
| Orchestration | Docker Compose | Local development environment |

## Building for Production

```bash
# Build optimized images
docker compose -f docker-compose.prod.yml build

# Run in detached mode
docker compose up -d
```

## License

MIT License - Built for Palo Alto Networks Hackathon 2025
