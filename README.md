# TELARA - Personal Health SOC

> "A Security Operations Center for the Human Body"

Real-time health analytics platform that detects anomalies in biometric data using enterprise-grade streaming infrastructure and AI-powered insights. Built for the Palo Alto Networks Product Engineering Hackathon 2025.

![Architecture](https://img.shields.io/badge/Architecture-Event%20Driven-blue)
![Kafka](https://img.shields.io/badge/Apache%20Kafka-7.5.0-orange)
![Flink](https://img.shields.io/badge/Apache%20Flink-1.18-purple)
![Claude](https://img.shields.io/badge/Claude%20AI-Opus%204-green)
![React](https://img.shields.io/badge/React-18.2-cyan)

## Key Features

### Real-Time Health Monitoring
- Live streaming of biometric data (HR, HRV, SpO2, Temperature, Activity)
- Complex Event Processing with Apache Flink MATCH_RECOGNIZE
- Sub-second anomaly detection and alerting

### AI-Powered Health Coach
- Multi-turn conversational interface powered by Claude claude-opus-4-5
- MCP (Model Context Protocol) integration for database queries
- Personalized health insights and recommendations

### Wellness Score
- Composite 0-100 wellness score with component breakdown
- Heart health, recovery, activity, stability, and alert status
- Personalized baselines and trend analysis

### Control Panel
- Start/Stop data generation
- Manual anomaly injection for testing
- Five anomaly patterns: Tachycardia, Hypoxia, Fever, Stress, Dehydration

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React)                            │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────────────┐│
│  │ Vital      │ │ Wellness   │ │ Health     │ │ Control            ││
│  │ Charts     │ │ Gauge      │ │ Coach Chat │ │ Panel              ││
│  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────────┬──────────┘│
└────────┼──────────────┼──────────────┼──────────────────┼───────────┘
         │              │              │                  │
         │ WebSocket    │ REST         │ WebSocket        │ REST
         │              │              │                  │
┌────────▼──────────────▼──────────────▼──────────────────▼───────────┐
│                         API LAYER (FastAPI)                         │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────────────┐│
│  │ /ws/vitals │ │ /wellness  │ │ /ws/chat   │ │ /generator/control ││
│  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────────┬──────────┘│
│        │              │              │                  │           │
│  ┌─────▼──────────────▼──────────────▼──────────────────┴──────────┐│
│  │                   Claude Agent (claude-opus-4-5)                          ││
│  │  MCP Tools: query_vitals, query_alerts, get_wellness, etc.     ││
│  └─────────────────────────────────┬───────────────────────────────┘│
└────────────────────────────────────┼────────────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────────────┐
│                         SQLite Database                             │
│  Tables: vitals, alerts, user_baselines                             │
└────────────────────────────────────▲────────────────────────────────┘
                                     │
┌─────────────────┐    ┌─────────────┴─────────────┐    ┌─────────────┐
│  Data Generator │───▶│      Apache Kafka         │◀───│   PyFlink   │
│    (Python)     │    │  biometrics-raw/alerts    │    │     CEP     │
└─────────────────┘    └───────────────────────────┘    └─────────────┘
```

## Quick Start

### Prerequisites

- Docker Desktop with Docker Compose v2
- At least 8GB RAM allocated to Docker
- Ports available: 2181, 9092, 8081, 8000, 8001, 5173

### 1. Start All Services

```bash
cd telara
docker compose up --build
```

### 2. Access the Dashboard

Open your browser to: **http://localhost:5173**

### 3. Interact with the AI Health Coach

1. Click "AI Coach" button in the header
2. Ask questions like:
   - "How are my vitals looking?"
   - "What's my wellness score?"
   - "Are there any concerning patterns?"

### 4. Trigger Anomalies

1. Click "Control" button in the header
2. Select an anomaly type
3. Click to inject and watch the dashboard react

## Service URLs

| Service | URL | Description |
|---------|-----|-------------|
| **Dashboard** | http://localhost:5173 | Main health SOC UI |
| **API Docs** | http://localhost:8000/docs | OpenAPI documentation |
| **Flink UI** | http://localhost:8081 | Job monitoring |
| **Generator Control** | http://localhost:8001 | Data generator API |

## Anomaly Detection Patterns

### 1. Tachycardia at Rest (MATCH_RECOGNIZE)
```sql
PATTERN (A{5,}) WHERE HR > 100 AND activity < 10
```

### 2. Low SpO2 / Hypoxia
```sql
PATTERN (A{3,}) WHERE SpO2 < 94%
```

### 3. Elevated Temperature
```sql
PATTERN (A{3,}) WHERE temp > 37.5°C
```

## AI Agent Tools

The Claude health coach has access to these MCP tools:

| Tool | Description |
|------|-------------|
| `query_recent_vitals` | Get vitals from last N minutes |
| `query_alerts` | Get alerts from last N hours |
| `get_wellness_score` | Calculate current wellness score |
| `get_metric_trend` | Analyze trends for a metric |
| `get_correlations` | Find correlations between metrics |
| `compare_to_baseline` | Compare to personal baselines |

## Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Message Bus | Apache Kafka 7.5 | High-throughput event streaming |
| Stream Processing | Apache Flink 1.18 (PyFlink) | Real-time CEP with MATCH_RECOGNIZE |
| AI Agent | Claude claude-opus-4-5 + MCP | Conversational health coach |
| API Server | FastAPI + WebSockets | Real-time data serving |
| Database | SQLite + aiosqlite | Vitals and alert storage |
| Frontend | React 18 + TypeScript + Recharts | SOC-style dashboard |

## Project Structure

```
telara/
├── docker-compose.yml
├── data-generator/
│   ├── producer.py          # Biometrics generator
│   ├── control_server.py    # HTTP control API
│   └── schemas.py           # Data models
├── stream-processor/
│   └── flink_job.py          # PyFlink CEP patterns
├── api/
│   ├── main.py               # FastAPI server
│   ├── claude_agent.py       # AI agent with MCP
│   ├── database.py           # SQLite layer
│   └── wellness.py           # Score calculator
└── frontend/
    └── src/
        ├── components/
        │   ├── Dashboard.tsx
        │   ├── VitalChart.tsx
        │   ├── ThreatLog.tsx
        │   ├── WellnessGauge.tsx
        │   ├── HealthChat.tsx
        │   ├── Timeline.tsx
        │   └── ControlPanel.tsx
        └── hooks/
            └── useWebSocket.ts
```

## License

MIT License - Built for Palo Alto Networks Hackathon 2025
