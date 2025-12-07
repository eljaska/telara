# Agent Handoff: Telara Tiers 2 & 3 Implementation

## Context

You are continuing development on **Telara**, a Personal Health Aggregator ("SOC for the Human Body") built for the Palo Alto Networks Product Engineering Hackathon. The project has a working foundation with real-time streaming infrastructure.

## Current State (Completed)

### Infrastructure (Working)
- Docker Compose orchestrating: Kafka, Zookeeper, Flink, FastAPI, React
- Data generator producing biometric events at 2Hz
- PyFlink with MATCH_RECOGNIZE patterns detecting: Tachycardia, Hypoxia, Fever
- WebSocket streaming to React dashboard
- SQLite database storing vitals, alerts, baselines

### Tier 1 Features (Implemented)
1. **Claude AI Integration** (`api/claude_agent.py`) - Multi-turn health coach with tool calling
2. **Wellness Score** (`api/wellness.py`) - 0-100 composite score with breakdown
3. **Alert Insight Enrichment** - LLM-generated actionable insights for each alert
4. **Generator Control API** - Start/stop/inject anomalies via HTTP
5. **Frontend Components**:
   - `WellnessGauge.tsx` - Circular score visualization
   - `HealthChat.tsx` - AI chat interface
   - `ControlPanel.tsx` - Generator controls
   - `Timeline.tsx` - 24-hour historical view

### Known Issues to Address
1. **Flink MATCH_RECOGNIZE patterns** use `PATTERN (A{5,}? B)` with terminating conditions - verify this works correctly in production
2. **MCP dependency removed** - Using Anthropic native tool calling instead

## Your Task: Implement Tiers 2 & 3

### Tier 2: Medium Effort, High Value (2-4 hours each)

**1. Simple Correlation Engine**
- Discover patterns like: "On days you sleep < 6 hours, your next-day HRV drops 25%"
- Use Pearson correlation on historical data in SQLite
- Store 7 days of data minimum
- Add "Correlation Insights" section to dashboard
- Location: Create `api/correlations.py`, add endpoint `/correlations`

**2. Personalized Baseline Learning**
- Track user's rolling 7-day averages (already have schema in `user_baselines` table)
- Alert when current value is X% above THEIR normal
- Enhance alerts: "Your HR is 95 bpm - 20% higher than YOUR typical 78 bpm"
- Update `BaselinesRepository` in `database.py` to auto-update from incoming vitals

**3. Daily Health Digest**
- Summary card: "Your Day at a Glance"
- Key metrics vs yesterday
- Top 3 observations
- One actionable recommendation
- Create `api/digest.py` and `/digest/daily` endpoint
- Add `DailyDigest.tsx` component

**4. Recommendation Engine**
- Rule-based suggestions tied to alerts and wellness score:
  - High HR + Low Activity → "Consider hydration"
  - Low HRV → "Your recovery is low, consider light activity"
  - Elevated Temp → "Monitor for illness, rest recommended"
- Add to wellness score response and alert enrichment

### Tier 3: Differentiators (4+ hours, demo-worthy)

**5. Predictive Alerts**
- "Based on your current trajectory, you may experience fatigue around 3pm"
- Simple linear projection models on HR, HRV trends
- Add `api/predictions.py`

**6. Multi-Source Integration Demo**
- Add mock OAuth screens for Apple HealthKit, Google Fit, Oura Ring
- Show data normalization pipeline (even if mocked)
- Demonstrates architecture thinking for judges
- Create `frontend/src/components/IntegrationDemo.tsx`

**7. Historical Comparison View**
- "This week vs last week" dashboard section
- Side-by-side charts
- Highlight improvements/regressions
- Add `frontend/src/components/WeekComparison.tsx`

## Key Files Reference

```
telara/
├── docker-compose.yml          # Service orchestration
├── .env                        # ANTHROPIC_API_KEY stored here
├── api/
│   ├── main.py                 # FastAPI endpoints, WebSocket handlers
│   ├── claude_agent.py         # AI agent with tool calling
│   ├── database.py             # SQLite repositories
│   ├── wellness.py             # Score calculation
│   └── kafka_consumer.py       # Kafka → WebSocket bridge
├── data-generator/
│   ├── producer.py             # Biometrics generator
│   ├── control_server.py       # HTTP control API (port 8001)
│   └── schemas.py              # Data models, anomaly patterns
├── stream-processor/
│   └── flink_job.py            # PyFlink MATCH_RECOGNIZE patterns
└── frontend/src/
    ├── components/
    │   ├── Dashboard.tsx       # Main layout
    │   ├── WellnessGauge.tsx   # Score gauge
    │   ├── HealthChat.tsx      # AI chat
    │   ├── ControlPanel.tsx    # Generator controls
    │   └── Timeline.tsx        # Historical view
    └── hooks/
        └── useWebSocket.ts     # Real-time data hook
```

## API Endpoints Available

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ws/vitals` | WS | Real-time vitals + alerts stream |
| `/ws/chat` | WS | AI health coach chat |
| `/wellness/score` | GET | Current wellness score + breakdown |
| `/vitals/recent` | GET | Recent vital readings |
| `/alerts/recent` | GET | Recent alerts |
| `/generator/status` | GET | Generator running state |
| `/generator/start` | POST | Start data generation |
| `/generator/stop` | POST | Stop data generation |
| `/generator/inject/{type}` | POST | Inject anomaly pattern |
| `/chat` | POST | Non-streaming chat endpoint |

## Running the System

```bash
cd C:\dev\telara\telara
docker compose up --build
```

- Dashboard: http://localhost:5173
- API Docs: http://localhost:8000/docs
- Flink UI: http://localhost:8081

## Success Criteria (Hackathon Judging)

1. **Actionable Insights** - Does it help users make health decisions?
2. **Data Unification** - Multi-source correlation and normalization
3. **Holistic View** - Dashboard tells a coherent health story
4. **AI Application** - Effective use of LLM for analysis
5. **Code Quality** - Clean architecture, error handling

## Recommended Priority

1. **Correlation Engine** (⭐⭐⭐⭐⭐) - Directly addresses "AI-Powered Correlation Discovery"
2. **Recommendation Engine** (⭐⭐⭐⭐) - Makes insights actionable
3. **Personalized Baselines** (⭐⭐⭐⭐) - "Proactive Anomaly Detection"
4. **Daily Digest** (⭐⭐⭐) - "Unified Health Story"
5. **Integration Demo** (⭐⭐⭐⭐⭐) - Shows data unification architecture

## Notes

- The Anthropic API key is in `.env` file, referenced in docker-compose.yml as `${ANTHROPIC_API_KEY}`
- Model to use: `claude-opus-4-5-20251101` (or alias `claude-opus-4-5`)
- Frontend uses Tailwind CSS with custom SOC dark theme (see `tailwind.config.js`)
- Keep UI consistent with existing "security operations center" aesthetic

