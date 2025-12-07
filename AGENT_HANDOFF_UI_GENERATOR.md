# Agent Handoff: UI Refinements & Data Generator Enhancements

## Context

You are continuing development on **Telara**, a Personal Health Aggregator ("SOC for the Human Body") built for the Palo Alto Networks Product Engineering Hackathon. The application has a complete feature set but needs UI refinements and data generator enhancements for better demo experience.

## Architecture Overview

### System Components
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Data Generator │───▶│     Kafka       │───▶│   Flink CEP     │
│  (port 8001)    │    │   (port 9092)   │    │  (port 8081)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │                       │
                              ▼                       ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   FastAPI       │◀───│  Alerts Topic   │
                       │  (port 8000)    │    └─────────────────┘
                       └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │  React Frontend │
                       │  (port 5173)    │
                       └─────────────────┘
```

### Data Flow
1. **Data Generator** (`data-generator/producer.py`) produces synthetic biometric events to Kafka
2. **Kafka** queues messages on `biometrics-raw` topic
3. **Flink CEP** (`stream-processor/flink_job.py`) processes patterns, produces alerts to `biometrics-alerts`
4. **FastAPI** (`api/main.py`) consumes both topics, broadcasts via WebSocket to frontend
5. **React Dashboard** displays real-time vitals, alerts, AI insights

### Key Files

| Component | File | Purpose |
|-----------|------|---------|
| Data Generator | `data-generator/producer.py` | Generates synthetic biometrics |
| Generator Control | `data-generator/control_server.py` | HTTP API to control generation |
| Generator Schemas | `data-generator/schemas.py` | Data models & anomaly patterns |
| API Server | `api/main.py` | FastAPI endpoints + WebSocket |
| Database | `api/database.py` | SQLite repositories for vitals/alerts |
| Dashboard | `frontend/src/components/Dashboard.tsx` | Main UI layout |
| Integrations | `frontend/src/components/IntegrationDemo.tsx` | Mock OAuth flows |
| Control Panel | `frontend/src/components/ControlPanel.tsx` | Generator controls |
| AI Insights | `frontend/src/components/CorrelationInsights.tsx`, `DailyDigest.tsx`, `PredictiveInsights.tsx`, `WeekComparison.tsx` |
| AI Chat | `frontend/src/components/HealthChat.tsx` | Claude-powered health coach |

---

## Current State

### What's Working
- Real-time biometric streaming at 2Hz
- Flink MATCH_RECOGNIZE pattern detection (Tachycardia, Hypoxia, Fever)
- Claude AI health coaching with tool calling
- Wellness score calculation with breakdown
- Correlation discovery engine
- Daily digest with AI observations
- Predictive alerts (fatigue, stress, threshold crossings)
- Week-over-week comparison
- Mock integration demo for Apple Health, Google Fit, Oura

### Current UI Structure
- **Dashboard tab**: Main vitals view with all components crammed together
- **AI Insights tab**: Shows DailyDigest, PredictiveInsights, WeekComparison, CorrelationInsights
- **Integrations tab**: Mock OAuth connection demo
- **AI Coach toggle**: Shows/hides chat panel on right side
- **Control toggle**: Shows/hides ControlPanel inline in left column

---

## Your Tasks

### 1. Integration-Controlled Data Flow

**Current Behavior**: The "Connect" buttons in `IntegrationDemo.tsx` simulate OAuth but don't affect data flow. Data always flows from the generator.

**Required Changes**:

**Frontend (`IntegrationDemo.tsx`)**:
- Change initial state to `connected: true` for all sources
- Add prop or context to communicate connected sources to parent
- When a source is disconnected, it should stop contributing to the data stream
- Visual indication of which sources are actively providing data

**Backend (`data-generator/producer.py` or `control_server.py`)**:
- Add endpoint to enable/disable data sources: `POST /sources/{source_id}/enable` and `POST /sources/{source_id}/disable`
- Modify data generation to tag events with source: `{ "source": "apple_health", ... }`
- Only generate data for enabled sources

**API (`api/main.py`)**:
- Add endpoints to proxy source control to generator
- Store source state and return in status endpoint

### 2. Dedicated Control Panel View

**Current Behavior**: The "Control" button toggles visibility of `ControlPanel` inline within the left column, making it easy to miss.

**Required Changes**:

**Option A - Modal/Popup (Recommended for demo impact)**:
- Create new `ControlModal.tsx` component
- Center overlay with backdrop blur
- Contains all generator controls + enhanced options
- Open via Control button, close via X or backdrop click

**Option B - Dedicated Tab**:
- Add "Control" as a full view mode like "Insights" and "Integrations"
- Full-width layout for control panel
- More space for additional controls

**Dashboard.tsx changes**:
- Remove inline ControlPanel rendering
- Add modal state management or new view mode
- Style the control view prominently

### 3. Enhanced Data Generation Controls

**Current Controls** (`ControlPanel.tsx`):
- Start/Stop generator
- Inject anomaly (dropdown with 5 types)

**Required New Controls**:

**A. Data Source Selection**:
```tsx
// Which sources to simulate
☑ Apple HealthKit  ☑ Google Fit  ☑ Oura Ring
```

**B. Generation Rate Control**:
```tsx
// Events per second slider
Rate: [====●=====] 2 Hz
```

**C. Metric Range Controls**:
```tsx
// Override normal ranges for demo
Heart Rate: [60] - [100] bpm
HRV: [30] - [70] ms
SpO2: [95] - [100] %
Temperature: [36.0] - [37.2] °C
```

**D. Anomaly Scheduling**:
```tsx
// Schedule anomalies
☐ Auto-inject anomalies every [30] seconds
Anomaly type: [Random ▾]
```

**E. Data Profile Presets**:
```tsx
// Quick presets for demo scenarios
[😴 Sleeping] [🏃 Exercise] [😰 Stressed] [😊 Healthy] [🤒 Sick]
```

**Backend Changes** (`data-generator/control_server.py`):
- Add `/config` endpoint to get/set generation parameters
- Add `/rate` endpoint to control events per second
- Add `/ranges` endpoint to set metric bounds
- Add `/presets/{preset}` endpoint to apply preset configurations

**Backend Changes** (`data-generator/schemas.py`):
- Add preset definitions with metric ranges and behaviors

### 4. Historical Data Generation

**Purpose**: The Daily Digest and Weekly Comparison features need historical data to be meaningful. Currently, they only work after running for extended periods.

**Required New Feature**:

**Backend (`data-generator/control_server.py`)**:
- Add `POST /generate/historical` endpoint:
```json
{
  "days": 14,
  "events_per_hour": 120,
  "include_anomalies": true,
  "anomaly_probability": 0.05,
  "pattern": "normal" | "improving" | "declining" | "variable"
}
```

**Backend (`data-generator/producer.py`)**:
- Add `generate_historical_data()` function
- Create backdated events with realistic timestamps
- Insert directly into database (not Kafka) for immediate availability
- Apply time-of-day patterns (lower HR at night, etc.)

**API (`api/database.py`)**:
- Add `bulk_insert_vitals()` for efficient historical data insertion

**Frontend (`ControlPanel.tsx` or `ControlModal.tsx`)**:
```tsx
// Historical Data Section
Generate Historical Data
Days: [7] [14] [30]
Pattern: [Normal ▾]
[Generate]
```

### 5. UI Reorganization

**Current Layout Issues**:
- Dashboard is cluttered with AI insights, chat, and controls mixed together
- AI Coach competes for space with threat log
- Predictive insights are shown in center column (takes chart space)

**New Layout**:

**Dashboard Tab** (Clean data focus):
```
┌─────────────────────────────────────────────────────────────────┐
│ Header: Logo | Dashboard | AI Insights | Integrations | Control │
├───────────────┬─────────────────────────────┬───────────────────┤
│ Quick Stats   │         Quick Stats         │    Quick Stats    │
├───────────────┼─────────────────────────────┼───────────────────┤
│               │                             │                   │
│ Wellness      │      Heart Rate Chart       │   Threat Log      │
│ Gauge         │                             │   (Alerts)        │
│               ├─────────────────────────────┤                   │
│ Timeline      │        HRV Chart            │                   │
│ (Historical)  │                             │                   │
│               ├─────────────────────────────┤                   │
│               │      SpO2 Chart             │                   │
│               │                             │                   │
│               ├─────────────────────────────┤                   │
│               │    Temperature Chart        │                   │
│               │                             │                   │
│               ├─────────────────────────────┤                   │
│               │     System Status Bar       │                   │
└───────────────┴─────────────────────────────┴───────────────────┘
```

**AI Insights Tab** (All AI features):
```
┌─────────────────────────────────────────────────────────────────┐
│ Header                                                          │
├─────────────────────────────────────────────────────────────────┤
│                    AI Health Coach (Chat)                       │
│                    [Full width, taller]                         │
├───────────────┬─────────────────────────────┬───────────────────┤
│ Daily Digest  │   Predictive Insights       │ Week Comparison   │
│               │                             │                   │
├───────────────┴─────────────────────────────┴───────────────────┤
│                  Correlation Insights (Full width)              │
└─────────────────────────────────────────────────────────────────┘
```

**Integrations Tab** (unchanged, but sources default connected)

**Control** (Modal overlay OR dedicated tab)

---

## Implementation Priority

1. **Historical Data Generation** (Critical for demo - enables digest/weekly features)
2. **UI Reorganization** (Clean separation of concerns)
3. **Control Panel Modal** (Better visibility for demo)
4. **Enhanced Generation Controls** (Demo flexibility)
5. **Integration-Controlled Flow** (Polish feature)

---

## Running the System

```bash
cd C:\dev\telara\telara
docker-compose up --build
```

- Dashboard: http://localhost:5173
- API Docs: http://localhost:8000/docs
- Generator Control: http://localhost:8001/docs
- Flink UI: http://localhost:8081

---

## Key API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ws/vitals` | WS | Real-time vitals + alerts stream |
| `/ws/chat` | WS | AI health coach chat |
| `/wellness/score` | GET | Current wellness score |
| `/correlations` | GET | Correlation insights |
| `/predictions` | GET | Predictive alerts |
| `/digest/daily` | GET | Daily health digest |
| `/comparison/weekly` | GET | Week-over-week comparison |
| `/generator/status` | GET | Generator state |
| `/generator/start` | POST | Start generation |
| `/generator/stop` | POST | Stop generation |
| `/generator/inject/{type}` | POST | Inject anomaly |

---

## Styling Notes

- Use existing Tailwind classes and SOC dark theme
- Colors defined in `frontend/tailwind.config.js`:
  - `soc-bg`: #0a0e14, `soc-panel`: #0d1117, `soc-border`: #1c2128
  - `vital-normal`: #3fb950, `vital-warning`: #d29922, `vital-critical`: #f85149
  - `accent-cyan`: #39c5cf, `accent-purple`: #a371f7
- Font: JetBrains Mono for data, Orbitron for headers
- Maintain "security operations center" aesthetic throughout

---

## Notes

- The Anthropic API key is in `.env` file, referenced as `${ANTHROPIC_API_KEY}`
- Model: `claude-opus-4-5-20251101`
- SQLite database is stored in Docker volume at `/app/data/telara.db`
- The data generator runs independently and can be controlled via its HTTP API

