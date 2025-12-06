---
name: Telara SOC Health Dashboard
overview: Build a real-time Personal Health Aggregator ("SOC for the Human Body") using Python data generators, Kafka, PyFlink for pattern detection, FastAPI WebSockets, and a React dashboard. The system detects health anomalies like "Tachycardia at Rest" using streaming CEP patterns.
todos:
  - id: infra-compose
    content: Create docker-compose.yml with Kafka, Zookeeper, Flink cluster, API, and frontend services
    status: completed
  - id: data-generator
    content: Build Python data generator with standardized biometric schema and anomaly injection
    status: completed
  - id: pyflink-job
    content: Create PyFlink job with MATCH_RECOGNIZE for Tachycardia at Rest detection
    status: completed
  - id: fastapi-ws
    content: Build FastAPI WebSocket server consuming both Kafka topics
    status: completed
  - id: react-dashboard
    content: Create React SOC-style dashboard with real-time charts and threat log
    status: completed
  - id: e2e-test
    content: "End-to-end verification: trigger anomaly, see alert in dashboard"
    status: completed
---

# Telara - Personal Health SOC Implementation Plan

## Folder Structure

```
telara/
├── docker-compose.yml
├── .env
├── infrastructure/
│   └── flink/
│       └── Dockerfile
├── data-generator/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── producer.py
│   └── schemas.py
├── stream-processor/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── flink_job.py
├── api/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   └── kafka_consumer.py
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── src/
    │   ├── App.tsx
    │   ├── components/
    │   │   ├── Dashboard.tsx
    │   │   ├── VitalChart.tsx
    │   │   └── ThreatLog.tsx
    │   └── hooks/
    │       └── useWebSocket.ts
    └── index.html
```

---

## 1. Standardized Biometric Event Schema

A unified JSON payload simulating aggregated IoT sources:

```json
{
  "event_id": "uuid",
  "timestamp": "2025-12-06T14:30:00.000Z",
  "user_id": "user_001",
  "device_sources": ["apple_watch", "oura_ring", "withings_scale"],
  "vitals": {
    "heart_rate": 72,
    "hrv_ms": 45,
    "spo2_percent": 98,
    "skin_temp_c": 36.2,
    "respiratory_rate": 14,
    "blood_pressure_systolic": 120,
    "blood_pressure_diastolic": 80
  },
  "activity": {
    "steps_per_minute": 0,
    "activity_level": 5,
    "calories_per_minute": 1.2,
    "posture": "seated"
  },
  "sleep": {
    "stage": null,
    "hours_last_night": 6.5
  },
  "environment": {
    "room_temp_c": 22,
    "humidity_percent": 45
  }
}
```

This standardized schema allows Flink to query flat fields while preserving source attribution.

---

## 2. Docker Compose Architecture

**Services:**
| Service | Image/Build | Ports | Purpose |
|---------|-------------|-------|---------|
| zookeeper | confluentinc/cp-zookeeper:7.5.0 | 2181 | Kafka coordination |
| kafka | confluentinc/cp-kafka:7.5.0 | 9092, 29092 | Message bus |
| flink-jobmanager | Custom PyFlink | 8081 | Flink master + job submission |
| flink-taskmanager | Custom PyFlink | - | Flink worker |
| data-generator | Python 3.11 | - | Produces biometrics-raw |
| api | FastAPI | 8000 | WebSocket server |
| frontend | Node/Vite | 5173 | React dashboard |

**Key networking:** All services on `telara-network` bridge. Kafka advertises `kafka:29092` internally.

---

## 3. PyFlink Job Design

### Source Table (biometrics-raw)
```sql
CREATE TABLE biometrics_raw (
    event_id STRING,
    ts TIMESTAMP(3),
    user_id STRING,
    heart_rate INT,
    hrv_ms INT,
    activity_level INT,
    steps_per_minute INT,
    skin_temp_c DOUBLE,
    spo2_percent INT,
    WATERMARK FOR ts AS ts - INTERVAL '5' SECOND
) WITH (
    'connector' = 'kafka',
    'topic' = 'biometrics-raw',
    'properties.bootstrap.servers' = 'kafka:29092',
    'format' = 'json',
    'scan.startup.mode' = 'latest-offset'
);
```

### Sink Table (biometrics-alerts)
```sql
CREATE TABLE biometrics_alerts (
    alert_id STRING,
    alert_type STRING,
    user_id STRING,
    severity STRING,
    start_time TIMESTAMP(3),
    end_time TIMESTAMP(3),
    avg_heart_rate DOUBLE,
    event_count BIGINT,
    description STRING
) WITH (
    'connector' = 'kafka',
    'topic' = 'biometrics-alerts',
    'properties.bootstrap.servers' = 'kafka:29092',
    'format' = 'json'
);
```

### MATCH_RECOGNIZE Query (Tachycardia at Rest)
```sql
INSERT INTO biometrics_alerts
SELECT 
    UUID() as alert_id,
    'TACHYCARDIA_AT_REST' as alert_type,
    user_id,
    'HIGH' as severity,
    start_ts,
    end_ts,
    avg_hr,
    match_count,
    'Sustained elevated HR (>100 bpm) detected while at rest for 5+ consecutive readings'
FROM biometrics_raw
MATCH_RECOGNIZE (
    PARTITION BY user_id
    ORDER BY ts
    MEASURES
        FIRST(A.ts) AS start_ts,
        LAST(A.ts) AS end_ts,
        AVG(A.heart_rate) AS avg_hr,
        COUNT(A.event_id) AS match_count
    ONE ROW PER MATCH
    AFTER MATCH SKIP PAST LAST ROW
    PATTERN (A{5,})
    DEFINE
        A AS heart_rate > 100 AND activity_level < 10 AND steps_per_minute < 5
) AS T
WHERE end_ts - start_ts < INTERVAL '1' MINUTE;
```

---

## 4. Data Generator (producer.py)

**Normal Mode:** Generates realistic baseline vitals (HR 60-80, activity varies by time-of-day simulation).

**Anomaly Injection:** `inject_anomaly("tachycardia_at_rest")` function that:
- Spikes HR to 110-130 bpm
- Keeps activity_level at 2-5 (sedentary)
- Runs for 30 seconds (generates ~15-30 events at 2Hz)

**Event Rate:** 2 events/second (500ms interval) for responsive real-time demo.

---

## 5. FastAPI WebSocket Layer

- **Endpoint:** `ws://localhost:8000/ws/vitals`
- Consumes from both `biometrics-raw` and `biometrics-alerts` Kafka topics
- Broadcasts to all connected WebSocket clients
- Message format:
```json
{"type": "vital", "data": {...}}
{"type": "alert", "data": {...}}
```

---

## 6. React Dashboard (Dark SOC Theme)

**Layout:**
- Header: "TELARA HEALTH SOC" + connection status indicator
- Left Panel: Real-time vital charts (HR, HRV, SpO2, Temp) using Recharts
- Right Panel: "Threat Log" - scrolling alert feed with severity badges
- Bottom: System status bar (Kafka lag, event rate)

**Aesthetic:** Dark theme inspired by security operations centers - deep navy/charcoal background, cyan/green accent for normal, amber/red for alerts.

---

## 7. Step-by-Step Build Order (First Hour Target)

**Phase 1: Infrastructure (15 min)**
1. Create `docker-compose.yml` with Zookeeper + Kafka only
2. `docker compose up -d kafka zookeeper`
3. Verify: `docker exec kafka kafka-topics --list --bootstrap-server localhost:9092`

**Phase 2: Data Producer (15 min)**
4. Create `data-generator/producer.py` with Kafka producer
5. Create `data-generator/Dockerfile`
6. Run producer, verify messages: `docker exec kafka kafka-console-consumer --topic biometrics-raw --bootstrap-server localhost:9092`

**Phase 3: Flink Pipeline (20 min)**
7. Create PyFlink Dockerfile with kafka connector JARs
8. Create `stream-processor/flink_job.py`
9. Start Flink services, submit job
10. Verify Flink UI at `http://localhost:8081`

**Phase 4: End-to-End Verification (10 min)**
11. Trigger anomaly injection
12. Verify alerts appear in `biometrics-alerts` topic
13. "Hello World" complete - data flows Python → Kafka → Flink → Kafka

---

## Implementation Notes

**PyFlink Connector Setup:** The Flink Dockerfile must download:
- `flink-sql-connector-kafka-3.0.2-1.18.jar`
- Ensure Flink 1.18.x for best MATCH_RECOGNIZE support

**Kafka Topic Auto-Creation:** Enable `KAFKA_AUTO_CREATE_TOPICS_ENABLE=true` for hackathon simplicity.

**WebSocket Reconnection:** Frontend should auto-reconnect with exponential backoff for demo resilience.