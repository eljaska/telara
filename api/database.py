"""
Telara SQLite Database Layer
Stores vitals, alerts, and user baselines for AI analysis.
Uses in-memory storage for real-time vitals to avoid SQLite locking issues.
"""

import aiosqlite
import asyncio
from collections import deque
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
import threading
import json
import os

DATABASE_PATH = os.environ.get("DATABASE_PATH", "/app/data/telara.db")

# Global connection pool settings
_db_lock = asyncio.Lock()


class InMemoryVitalsStore:
    """
    Thread-safe in-memory store for real-time vitals data.
    Uses a ring buffer (deque) to store the last N vitals, avoiding SQLite locking.
    """
    
    def __init__(self, max_size: int = 2000):
        self._vitals: deque = deque(maxlen=max_size)
        self._lock = threading.Lock()
        self._baseline_data: Dict[str, Dict] = {}  # user_id -> baseline stats
    
    def add(self, vital_data: Dict[str, Any]) -> None:
        """Add a vital reading to the store."""
        with self._lock:
            # Add timestamp if not present
            if "stored_at" not in vital_data:
                vital_data["stored_at"] = datetime.utcnow().isoformat()
            self._vitals.append(vital_data)
            
            # Update in-memory baseline
            user_id = vital_data.get("user_id", "user_001")
            self._update_baseline(user_id, vital_data)
    
    def _update_baseline(self, user_id: str, vital_data: Dict) -> None:
        """Update running baseline statistics for a user."""
        alpha = 0.1  # EMA smoothing factor
        
        if user_id not in self._baseline_data:
            self._baseline_data[user_id] = {
                "avg_heart_rate": vital_data.get("heart_rate", 72),
                "avg_hrv": vital_data.get("hrv_ms", 50),
                "avg_spo2": vital_data.get("spo2_percent", 98),
                "avg_temp": vital_data.get("skin_temp_c", 36.5),
                "avg_activity": vital_data.get("activity_level", 20),
                "data_points": 1,
            }
            return
        
        baseline = self._baseline_data[user_id]
        
        # EMA update for each metric
        if vital_data.get("heart_rate"):
            baseline["avg_heart_rate"] = alpha * vital_data["heart_rate"] + (1 - alpha) * baseline["avg_heart_rate"]
        if vital_data.get("hrv_ms"):
            baseline["avg_hrv"] = alpha * vital_data["hrv_ms"] + (1 - alpha) * baseline["avg_hrv"]
        if vital_data.get("spo2_percent"):
            baseline["avg_spo2"] = alpha * vital_data["spo2_percent"] + (1 - alpha) * baseline["avg_spo2"]
        if vital_data.get("skin_temp_c"):
            baseline["avg_temp"] = alpha * vital_data["skin_temp_c"] + (1 - alpha) * baseline["avg_temp"]
        if vital_data.get("activity_level"):
            baseline["avg_activity"] = alpha * vital_data["activity_level"] + (1 - alpha) * baseline["avg_activity"]
        
        baseline["data_points"] += 1
    
    def get_recent(self, minutes: int = 60, user_id: str = "user_001") -> List[Dict]:
        """Get vitals from the last N minutes."""
        with self._lock:
            cutoff = datetime.utcnow() - timedelta(minutes=minutes)
            result = []
            for vital in reversed(self._vitals):
                # Parse timestamp
                ts_str = vital.get("timestamp") or vital.get("stored_at")
                if ts_str:
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00").replace("+00:00", ""))
                    except:
                        continue
                    
                    if ts < cutoff:
                        break  # Since we're iterating in reverse, we can stop here
                    
                    if vital.get("user_id") == user_id:
                        result.append(vital)
            
            return result
    
    def get_latest(self, user_id: str = "user_001") -> Optional[Dict]:
        """Get the most recent vital reading."""
        with self._lock:
            for vital in reversed(self._vitals):
                if vital.get("user_id") == user_id:
                    return vital
            return None
    
    def get_all(self) -> List[Dict]:
        """Get all vitals in the store."""
        with self._lock:
            return list(self._vitals)
    
    def get_stats(self, minutes: int = 60, user_id: str = "user_001") -> Dict:
        """Get statistical summary of recent vitals."""
        vitals = self.get_recent(minutes=minutes, user_id=user_id)
        
        if not vitals:
            return {"count": 0}
        
        hr_values = [v.get("heart_rate") for v in vitals if v.get("heart_rate")]
        hrv_values = [v.get("hrv_ms") for v in vitals if v.get("hrv_ms")]
        spo2_values = [v.get("spo2_percent") for v in vitals if v.get("spo2_percent")]
        temp_values = [v.get("skin_temp_c") for v in vitals if v.get("skin_temp_c")]
        activity_values = [v.get("activity_level") for v in vitals if v.get("activity_level")]
        
        return {
            "count": len(vitals),
            "avg_hr": sum(hr_values) / len(hr_values) if hr_values else None,
            "min_hr": min(hr_values) if hr_values else None,
            "max_hr": max(hr_values) if hr_values else None,
            "avg_hrv": sum(hrv_values) / len(hrv_values) if hrv_values else None,
            "avg_spo2": sum(spo2_values) / len(spo2_values) if spo2_values else None,
            "avg_temp": sum(temp_values) / len(temp_values) if temp_values else None,
            "avg_activity": sum(activity_values) / len(activity_values) if activity_values else None,
        }
    
    def get_baseline(self, user_id: str = "user_001") -> Optional[Dict]:
        """Get baseline data for a user."""
        with self._lock:
            return self._baseline_data.get(user_id)
    
    def clear(self) -> None:
        """Clear all data from the store."""
        with self._lock:
            self._vitals.clear()
            self._baseline_data.clear()
    
    def count(self) -> int:
        """Get the number of vitals in the store."""
        with self._lock:
            return len(self._vitals)
    
    def get_time_range(self) -> Dict[str, Optional[str]]:
        """Get the oldest and newest event timestamps."""
        with self._lock:
            if not self._vitals:
                return {"oldest": None, "newest": None}
            
            oldest = self._vitals[0].get("timestamp") or self._vitals[0].get("stored_at")
            newest = self._vitals[-1].get("timestamp") or self._vitals[-1].get("stored_at")
            return {"oldest": oldest, "newest": newest}


class SpeedLayerAggregator:
    """
    Aggregates multi-source health data for real-time display.
    
    The clever part of our Lambda architecture:
    - Tracks latest value from each source for each metric
    - Computes "best" display value (most recent within freshness window)
    - Shows source attribution (which devices contributed)
    
    Example:
        Apple reports HR=73, Google reports HR=75 at similar times.
        Aggregator shows: HR=75 (most recent), sources: [apple, google]
    """
    
    # Metrics that can come from multiple sources
    AGGREGATABLE_METRICS = [
        "heart_rate", "hrv_ms", "spo2_percent", "skin_temp_c",
        "respiratory_rate", "activity_level", "steps_per_minute",
        "calories_per_minute", "sleep_quality"
    ]
    
    # Source icons for display
    SOURCE_ICONS = {
        "apple": "🍎",
        "google": "📱",
        "oura": "💍",
    }
    
    # Freshness window - values older than this are considered stale
    FRESHNESS_WINDOW_MS = 10000  # 10 seconds
    
    def __init__(self):
        self._lock = threading.Lock()
        
        # Latest reading per source per metric
        # Structure: {metric: {source: {"value": x, "timestamp": t}}}
        self._latest_by_source: Dict[str, Dict[str, Dict[str, Any]]] = {
            metric: {} for metric in self.AGGREGATABLE_METRICS
        }
        
        # Cached aggregated state
        self._aggregated_state: Dict[str, Dict[str, Any]] = {}
        self._last_update = datetime.utcnow()
    
    def add_event(self, event: Dict[str, Any]) -> None:
        """
        Process an incoming event and update the aggregated state.
        
        Args:
            event: Raw event with source field and metric values
        """
        source = event.get("source")
        if not source:
            return
        
        timestamp = event.get("timestamp") or datetime.utcnow().isoformat()
        
        with self._lock:
            # Update latest value for each metric from this source
            for metric in self.AGGREGATABLE_METRICS:
                if metric in event and event[metric] is not None:
                    if metric not in self._latest_by_source:
                        self._latest_by_source[metric] = {}
                    
                    self._latest_by_source[metric][source] = {
                        "value": event[metric],
                        "timestamp": timestamp,
                        "source_name": event.get("source_name", source),
                    }
            
            # Recompute aggregated state
            self._recompute_aggregated_state()
    
    def _recompute_aggregated_state(self) -> None:
        """Recompute the aggregated display state from latest readings."""
        now = datetime.utcnow()
        cutoff = now - timedelta(milliseconds=self.FRESHNESS_WINDOW_MS)
        
        new_state = {}
        
        for metric, sources in self._latest_by_source.items():
            # Get fresh readings only
            fresh_readings = []
            for source, data in sources.items():
                try:
                    ts_str = data["timestamp"]
                    # Parse ISO timestamp
                    if "+" in ts_str or ts_str.endswith("Z"):
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00").replace("+00:00", ""))
                    else:
                        ts = datetime.fromisoformat(ts_str)
                    
                    # Check freshness
                    if ts > cutoff or (now - ts).total_seconds() < self.FRESHNESS_WINDOW_MS / 1000:
                        fresh_readings.append({
                            "source": source,
                            "value": data["value"],
                            "timestamp": ts,
                            "age_ms": int((now - ts).total_seconds() * 1000),
                        })
                except Exception:
                    # Include if we can't parse timestamp (assume fresh)
                    fresh_readings.append({
                        "source": source,
                        "value": data["value"],
                        "timestamp": now,
                        "age_ms": 0,
                    })
            
            if not fresh_readings:
                continue
            
            # Sort by timestamp (most recent first)
            fresh_readings.sort(key=lambda x: x["timestamp"], reverse=True)
            
            # Best value = most recent
            best = fresh_readings[0]
            
            new_state[metric] = {
                "value": best["value"],
                "sources": [r["source"] for r in fresh_readings],
                "source_icons": [self.SOURCE_ICONS.get(r["source"], "📊") for r in fresh_readings],
                "freshness_ms": best["age_ms"],
                "reading_count": len(fresh_readings),
            }
        
        self._aggregated_state = new_state
        self._last_update = now
    
    def get_aggregated_state(self) -> Dict[str, Any]:
        """
        Get the current aggregated state for display.
        
        Returns:
            Dict with best values, source attribution, and freshness info.
        """
        with self._lock:
            # Recompute to ensure freshness is current
            self._recompute_aggregated_state()
            
            return {
                "vitals": self._aggregated_state.copy(),
                "last_update": self._last_update.isoformat(),
                "source_count": self._count_active_sources(),
            }
    
    def _count_active_sources(self) -> int:
        """Count sources that have contributed fresh data."""
        active = set()
        now = datetime.utcnow()
        cutoff_sec = self.FRESHNESS_WINDOW_MS / 1000
        
        for metric, sources in self._latest_by_source.items():
            for source, data in sources.items():
                try:
                    ts_str = data["timestamp"]
                    if "+" in ts_str or ts_str.endswith("Z"):
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00").replace("+00:00", ""))
                    else:
                        ts = datetime.fromisoformat(ts_str)
                    
                    if (now - ts).total_seconds() < cutoff_sec:
                        active.add(source)
                except:
                    active.add(source)
        
        return len(active)
    
    def get_source_breakdown(self, metric: str) -> List[Dict[str, Any]]:
        """Get detailed breakdown of all source readings for a metric."""
        with self._lock:
            if metric not in self._latest_by_source:
                return []
            
            readings = []
            for source, data in self._latest_by_source[metric].items():
                readings.append({
                    "source": source,
                    "source_name": data.get("source_name", source),
                    "icon": self.SOURCE_ICONS.get(source, "📊"),
                    "value": data["value"],
                    "timestamp": data["timestamp"],
                })
            
            return sorted(readings, key=lambda x: x["timestamp"], reverse=True)
    
    def clear(self) -> None:
        """Clear all aggregated data."""
        with self._lock:
            self._latest_by_source = {metric: {} for metric in self.AGGREGATABLE_METRICS}
            self._aggregated_state = {}


class BatchWriteBuffer:
    """
    Batch layer for Lambda Architecture.
    Accumulates real-time events and periodically flushes to SQLite.
    Runs in background, never blocks the speed layer.
    """
    
    def __init__(self, flush_interval: float = 5.0, batch_size: int = 100):
        self._buffer: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._flush_interval = flush_interval
        self._batch_size = batch_size
        self._enabled = True
        self._paused = False
        self._flush_task: Optional[asyncio.Task] = None
        self._total_flushed = 0
        self._last_flush_time: Optional[datetime] = None
    
    def add(self, event: Dict[str, Any]) -> None:
        """Queue event for batch write (non-blocking)."""
        if not self._enabled or self._paused:
            return
        
        with self._lock:
            self._buffer.append(event.copy())
    
    def pause(self) -> None:
        """Pause batch writes (used during historical data generation)."""
        self._paused = True
        print("BatchWriteBuffer: Paused")
    
    def resume(self) -> None:
        """Resume batch writes."""
        self._paused = False
        print("BatchWriteBuffer: Resumed")
    
    def is_paused(self) -> bool:
        """Check if buffer is paused."""
        return self._paused
    
    def clear(self) -> None:
        """Clear the pending buffer."""
        with self._lock:
            self._buffer.clear()
    
    def pending_count(self) -> int:
        """Get number of events waiting to be flushed."""
        with self._lock:
            return len(self._buffer)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get buffer statistics."""
        with self._lock:
            return {
                "pending": len(self._buffer),
                "total_flushed": self._total_flushed,
                "last_flush": self._last_flush_time.isoformat() if self._last_flush_time else None,
                "enabled": self._enabled,
                "paused": self._paused,
            }
    
    def start_flush_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Start the background flush loop."""
        if self._flush_task is None or self._flush_task.done():
            self._flush_task = loop.create_task(self._flush_loop())
            print(f"BatchWriteBuffer: Started (interval={self._flush_interval}s, batch_size={self._batch_size})")
    
    async def stop(self) -> None:
        """Stop the flush loop and do a final flush."""
        self._enabled = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        # Final flush
        await self.flush()
        print("BatchWriteBuffer: Stopped")
    
    async def _flush_loop(self) -> None:
        """Background loop that periodically flushes the buffer."""
        while self._enabled:
            try:
                await asyncio.sleep(self._flush_interval)
                if not self._paused:
                    await self.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"BatchWriteBuffer: Error in flush loop: {e}")
    
    async def flush(self) -> int:
        """Flush accumulated events to SQLite. Returns number of events flushed."""
        # Grab events to flush
        with self._lock:
            if not self._buffer:
                return 0
            events_to_flush = self._buffer[:self._batch_size]
            self._buffer = self._buffer[self._batch_size:]
        
        if not events_to_flush:
            return 0
        
        # Write to SQLite
        try:
            async with aiosqlite.connect(DATABASE_PATH, timeout=30.0) as db:
                await db.execute("PRAGMA busy_timeout=30000")
                
                data_tuples = []
                for event in events_to_flush:
                    data_tuples.append((
                        event.get("event_id"),
                        event.get("timestamp"),
                        event.get("user_id"),
                        event.get("heart_rate"),
                        event.get("hrv_ms"),
                        event.get("spo2_percent"),
                        event.get("skin_temp_c"),
                        event.get("respiratory_rate"),
                        event.get("activity_level"),
                        event.get("steps_per_minute"),
                        event.get("calories_per_minute"),
                        event.get("posture"),
                        event.get("hours_last_night"),
                        event.get("room_temp_c"),
                        event.get("humidity_percent"),
                    ))
                
                await db.executemany("""
                    INSERT OR REPLACE INTO vitals (
                        event_id, timestamp, user_id, heart_rate, hrv_ms,
                        spo2_percent, skin_temp_c, respiratory_rate,
                        activity_level, steps_per_minute, calories_per_minute,
                        posture, sleep_hours, room_temp_c, humidity_percent
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, data_tuples)
                
                await db.commit()
            
            with self._lock:
                self._total_flushed += len(events_to_flush)
                self._last_flush_time = datetime.utcnow()
            
            return len(events_to_flush)
            
        except Exception as e:
            print(f"BatchWriteBuffer: Error flushing to SQLite: {e}")
            # Put events back in buffer for retry
            with self._lock:
                self._buffer = events_to_flush + self._buffer
            return 0


# Global in-memory vitals store (Speed Layer)
vitals_store = InMemoryVitalsStore(max_size=2000)

# Global batch write buffer (Batch Layer)
batch_buffer = BatchWriteBuffer(flush_interval=5.0, batch_size=100)

# Global speed layer aggregator (Multi-source fusion)
speed_aggregator = SpeedLayerAggregator()


async def init_database():
    """Initialize the database with required tables.
    
    Drops existing tables on startup for a fresh state (acceptable for demo).
    This prevents stale data issues and SQLite corruption from previous runs.
    """
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    
    # Clear in-memory store for fresh start
    vitals_store.clear()
    print("✓ In-memory vitals store cleared")
    
    async with aiosqlite.connect(DATABASE_PATH, timeout=30.0) as db:
        # Enable WAL mode for better concurrent access
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        await db.execute("PRAGMA busy_timeout=30000")
        
        # Drop existing tables for fresh state on each launch (hackathon demo mode)
        print("  Dropping existing tables for fresh state...")
        await db.execute("DROP TABLE IF EXISTS vitals")
        await db.execute("DROP TABLE IF EXISTS alerts")
        await db.execute("DROP TABLE IF EXISTS user_baselines")
        
        # Vitals table - stores recent biometric data
        await db.execute("""
            CREATE TABLE IF NOT EXISTS vitals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE,
                timestamp DATETIME,
                user_id TEXT,
                heart_rate INTEGER,
                hrv_ms INTEGER,
                spo2_percent INTEGER,
                skin_temp_c REAL,
                respiratory_rate INTEGER,
                activity_level INTEGER,
                steps_per_minute INTEGER,
                calories_per_minute REAL,
                posture TEXT,
                sleep_hours REAL,
                room_temp_c REAL,
                humidity_percent INTEGER,
                wellness_score INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Alerts table - stores detected anomalies
        await db.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id TEXT UNIQUE,
                timestamp DATETIME,
                user_id TEXT,
                alert_type TEXT,
                severity TEXT,
                description TEXT,
                avg_heart_rate REAL,
                event_count INTEGER,
                ai_insight TEXT,
                resolved BOOLEAN DEFAULT FALSE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # User baselines - rolling averages for personalization
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_baselines (
                user_id TEXT PRIMARY KEY,
                avg_heart_rate REAL,
                avg_hrv REAL,
                avg_spo2 REAL,
                avg_temp REAL,
                avg_activity REAL,
                avg_respiratory_rate REAL,
                std_heart_rate REAL DEFAULT 0,
                std_hrv REAL DEFAULT 0,
                std_spo2 REAL DEFAULT 0,
                std_temp REAL DEFAULT 0,
                data_points INTEGER DEFAULT 0,
                updated_at DATETIME
            )
        """)
        
        # Migration: Add missing columns to user_baselines if they don't exist
        try:
            await db.execute("ALTER TABLE user_baselines ADD COLUMN std_heart_rate REAL DEFAULT 0")
        except:
            pass  # Column already exists
        try:
            await db.execute("ALTER TABLE user_baselines ADD COLUMN std_hrv REAL DEFAULT 0")
        except:
            pass
        try:
            await db.execute("ALTER TABLE user_baselines ADD COLUMN std_spo2 REAL DEFAULT 0")
        except:
            pass
        try:
            await db.execute("ALTER TABLE user_baselines ADD COLUMN std_temp REAL DEFAULT 0")
        except:
            pass
        
        # Create indexes for faster queries
        await db.execute("CREATE INDEX IF NOT EXISTS idx_vitals_timestamp ON vitals(timestamp)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_vitals_user ON vitals(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity)")
        
        await db.commit()
        print("✓ Database initialized (fresh tables, WAL mode, in-memory vitals store ready)")


@asynccontextmanager
async def get_db():
    """Get database connection context manager with proper settings."""
    db = await aiosqlite.connect(DATABASE_PATH, timeout=30.0)
    await db.execute("PRAGMA busy_timeout=30000")
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


class VitalsRepository:
    """Repository for vital signs data operations.
    
    Lambda Architecture Query Routing:
    - Speed Layer (memory): Real-time queries (<=30 min)
    - Batch Layer (SQLite): Historical queries (>30 min)
    """
    
    # Threshold for routing queries to memory vs SQLite
    REALTIME_THRESHOLD_MINUTES = 30
    
    @staticmethod
    async def insert(vital_data: Dict[str, Any]) -> bool:
        """Insert a new vital reading into the in-memory store.
        
        Note: This only writes to Speed Layer. Batch Layer writes happen
        via BatchWriteBuffer in the background.
        """
        try:
            vitals_store.add(vital_data)
            return True
        except Exception as e:
            print(f"Error inserting vital to memory: {e}")
            return False
    
    @staticmethod
    async def get_recent(minutes: int = 60, user_id: str = "user_001") -> List[Dict]:
        """Get vitals from the last N minutes.
        
        Query Routing:
        - minutes <= 30: Speed Layer (memory) only
        - minutes > 30: Batch Layer (SQLite) only (historical data)
        """
        if minutes <= VitalsRepository.REALTIME_THRESHOLD_MINUTES:
            # SPEED LAYER: Real-time data from memory
            return vitals_store.get_recent(minutes=minutes, user_id=user_id)
        else:
            # BATCH LAYER: Historical data from SQLite
            return await VitalsRepository._get_recent_from_sqlite(minutes, user_id)
    
    @staticmethod
    async def _get_recent_from_sqlite(minutes: int, user_id: str) -> List[Dict]:
        """Get historical vitals from SQLite (Batch Layer)."""
        try:
            async with get_db() as db:
                cutoff = datetime.utcnow() - timedelta(minutes=minutes)
                cursor = await db.execute("""
                    SELECT * FROM vitals 
                    WHERE user_id = ? AND timestamp > ?
                    ORDER BY timestamp DESC
                """, (user_id, cutoff.isoformat()))
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            print(f"SQLite get_recent failed: {e}")
            return []
    
    @staticmethod
    async def get_metric_trend(metric: str, hours: int = 24, user_id: str = "user_001") -> List[Dict]:
        """Get trend data for a specific metric."""
        valid_metrics = ["heart_rate", "hrv_ms", "spo2_percent", "skin_temp_c", "activity_level"]
        if metric not in valid_metrics:
            return []
        
        async with get_db() as db:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            cursor = await db.execute(f"""
                SELECT timestamp, {metric} as value
                FROM vitals 
                WHERE user_id = ? AND timestamp > ?
                ORDER BY timestamp ASC
            """, (user_id, cutoff.isoformat()))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    @staticmethod
    async def get_latest(user_id: str = "user_001") -> Optional[Dict]:
        """Get the most recent vital reading.
        
        Always uses Speed Layer (memory) - this is always real-time.
        """
        return vitals_store.get_latest(user_id=user_id)
    
    @staticmethod
    async def get_stats(hours: int = 24, user_id: str = "user_001") -> Dict:
        """Get statistical summary of vitals.
        
        Query Routing:
        - hours <= 1: Speed Layer (memory)
        - hours > 1: Batch Layer (SQLite)
        """
        if hours <= 1:
            # SPEED LAYER: Real-time stats from memory
            minutes = hours * 60
            return vitals_store.get_stats(minutes=minutes, user_id=user_id)
        
        # BATCH LAYER: Historical stats from SQLite
        try:
            async with get_db() as db:
                cutoff = datetime.utcnow() - timedelta(hours=hours)
                cursor = await db.execute("""
                    SELECT 
                        COUNT(*) as count,
                        AVG(heart_rate) as avg_hr,
                        MIN(heart_rate) as min_hr,
                        MAX(heart_rate) as max_hr,
                        AVG(hrv_ms) as avg_hrv,
                        AVG(spo2_percent) as avg_spo2,
                        AVG(skin_temp_c) as avg_temp,
                        AVG(activity_level) as avg_activity
                    FROM vitals 
                    WHERE user_id = ? AND timestamp > ?
                """, (user_id, cutoff.isoformat()))
                row = await cursor.fetchone()
                return dict(row) if row else stats
        except Exception as e:
            print(f"SQLite get_stats failed: {e}")
            return stats
    
    @staticmethod
    async def cleanup_old_data(hours: int = 48):
        """Remove data older than N hours."""
        async with get_db() as db:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            await db.execute("DELETE FROM vitals WHERE timestamp < ?", (cutoff.isoformat(),))
            await db.commit()
    
    @staticmethod
    async def get_historical_stats() -> Dict[str, Any]:
        """Get statistics about historical data in SQLite (Batch Layer)."""
        try:
            async with get_db() as db:
                # Count total events
                cursor = await db.execute("SELECT COUNT(*) as count FROM vitals")
                row = await cursor.fetchone()
                count = row[0] if row else 0
                
                # Get time range
                cursor = await db.execute("""
                    SELECT MIN(timestamp) as oldest, MAX(timestamp) as newest 
                    FROM vitals
                """)
                row = await cursor.fetchone()
                oldest = row[0] if row else None
                newest = row[1] if row else None
                
                return {
                    "events_in_database": count,
                    "oldest_event": oldest,
                    "newest_event": newest,
                }
        except Exception as e:
            print(f"Error getting historical stats: {e}")
            return {
                "events_in_database": 0,
                "oldest_event": None,
                "newest_event": None,
                "error": str(e)
            }
    
    @staticmethod
    async def wipe_historical_data() -> Dict[str, Any]:
        """Wipe all historical vitals from SQLite (Batch Layer)."""
        try:
            async with get_db() as db:
                cursor = await db.execute("SELECT COUNT(*) FROM vitals")
                row = await cursor.fetchone()
                count_before = row[0] if row else 0
                
                await db.execute("DELETE FROM vitals")
                await db.commit()
                
                return {
                    "success": True,
                    "events_deleted": count_before,
                }
        except Exception as e:
            print(f"Error wiping historical data: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    async def bulk_insert_vitals(vitals_list: List[Dict[str, Any]], batch_size: int = 1000) -> Dict[str, Any]:
        """
        Efficiently insert a large batch of historical vitals into the database.
        Uses executemany for better performance and less locking.
        
        Args:
            vitals_list: List of vital event dictionaries
            batch_size: Number of records per batch commit
        
        Returns:
            Dict with insertion statistics
        """
        if not vitals_list:
            return {"success": True, "inserted": 0, "failed": 0, "total": 0}
        
        inserted = 0
        failed = 0
        
        try:
            # Use a single connection with WAL mode for the entire operation
            async with aiosqlite.connect(DATABASE_PATH, timeout=60.0) as db:
                await db.execute("PRAGMA journal_mode=WAL")
                await db.execute("PRAGMA synchronous=OFF")  # Faster for bulk inserts
                await db.execute("PRAGMA cache_size=10000")
                
                # Prepare data tuples for executemany
                for i in range(0, len(vitals_list), batch_size):
                    batch = vitals_list[i:i + batch_size]
                    
                    data_tuples = []
                    for vital_data in batch:
                        data_tuples.append((
                            vital_data.get("event_id"),
                            vital_data.get("timestamp"),
                            vital_data.get("user_id"),
                            vital_data.get("heart_rate"),
                            vital_data.get("hrv_ms"),
                            vital_data.get("spo2_percent"),
                            vital_data.get("skin_temp_c"),
                            vital_data.get("respiratory_rate"),
                            vital_data.get("activity_level"),
                            vital_data.get("steps_per_minute"),
                            vital_data.get("calories_per_minute"),
                            vital_data.get("posture"),
                            vital_data.get("hours_last_night"),
                            vital_data.get("room_temp_c"),
                            vital_data.get("humidity_percent"),
                        ))
                    
                    try:
                        await db.executemany("""
                            INSERT OR REPLACE INTO vitals (
                                event_id, timestamp, user_id, heart_rate, hrv_ms,
                                spo2_percent, skin_temp_c, respiratory_rate,
                                activity_level, steps_per_minute, calories_per_minute,
                                posture, sleep_hours, room_temp_c, humidity_percent
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, data_tuples)
                        inserted += len(data_tuples)
                    except Exception as e:
                        print(f"Error in batch insert: {e}")
                        failed += len(data_tuples)
                    
                    # Commit after each batch to release locks
                    await db.commit()
                    
                    # Small yield to allow other operations
                    await asyncio.sleep(0.01)
                    
                    print(f"  Inserted batch {i // batch_size + 1}: {min(i + batch_size, len(vitals_list))}/{len(vitals_list)}")
                
                # Final commit
                await db.commit()
                
            return {
                "success": True,
                "inserted": inserted,
                "failed": failed,
                "total": len(vitals_list)
            }
        except Exception as e:
            print(f"Error in bulk insert: {e}")
            return {
                "success": False,
                "inserted": inserted,
                "failed": failed,
                "total": len(vitals_list),
                "error": str(e)
            }


class AlertsRepository:
    """Repository for alert data operations."""
    
    @staticmethod
    async def insert(alert_data: Dict[str, Any]) -> bool:
        """Insert a new alert."""
        try:
            async with get_db() as db:
                await db.execute("""
                    INSERT OR REPLACE INTO alerts (
                        alert_id, timestamp, user_id, alert_type, severity,
                        description, avg_heart_rate, event_count, ai_insight
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    alert_data.get("alert_id"),
                    alert_data.get("start_time") or alert_data.get("timestamp"),
                    alert_data.get("user_id"),
                    alert_data.get("alert_type"),
                    alert_data.get("severity"),
                    alert_data.get("description"),
                    alert_data.get("avg_heart_rate"),
                    alert_data.get("event_count"),
                    alert_data.get("ai_insight"),
                ))
                await db.commit()
                return True
        except Exception as e:
            print(f"Error inserting alert: {e}")
            return False
    
    @staticmethod
    async def update_insight(alert_id: str, insight: str) -> bool:
        """Update the AI insight for an alert."""
        try:
            async with get_db() as db:
                await db.execute(
                    "UPDATE alerts SET ai_insight = ? WHERE alert_id = ?",
                    (insight, alert_id)
                )
                await db.commit()
                return True
        except Exception as e:
            print(f"Error updating insight: {e}")
            return False
    
    @staticmethod
    async def get_recent(hours: int = 24, severity: Optional[str] = None, user_id: str = "user_001") -> List[Dict]:
        """Get alerts from the last N hours."""
        async with get_db() as db:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            
            if severity:
                cursor = await db.execute("""
                    SELECT * FROM alerts 
                    WHERE user_id = ? AND timestamp > ? AND severity = ?
                    ORDER BY timestamp DESC
                """, (user_id, cutoff.isoformat(), severity))
            else:
                cursor = await db.execute("""
                    SELECT * FROM alerts 
                    WHERE user_id = ? AND timestamp > ?
                    ORDER BY timestamp DESC
                """, (user_id, cutoff.isoformat()))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    @staticmethod
    async def get_by_id(alert_id: str) -> Optional[Dict]:
        """Get a specific alert by ID."""
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM alerts WHERE alert_id = ?",
                (alert_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    @staticmethod
    async def get_unresolved(user_id: str = "user_001") -> List[Dict]:
        """Get all unresolved alerts."""
        async with get_db() as db:
            cursor = await db.execute("""
                SELECT * FROM alerts 
                WHERE user_id = ? AND resolved = FALSE
                ORDER BY timestamp DESC
            """, (user_id,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    @staticmethod
    async def get_count_by_severity(hours: int = 24, user_id: str = "user_001") -> Dict[str, int]:
        """Get alert counts grouped by severity."""
        async with get_db() as db:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            cursor = await db.execute("""
                SELECT severity, COUNT(*) as count
                FROM alerts 
                WHERE user_id = ? AND timestamp > ?
                GROUP BY severity
            """, (user_id, cutoff.isoformat()))
            rows = await cursor.fetchall()
            return {row["severity"]: row["count"] for row in rows}


class BaselinesRepository:
    """Repository for user baseline operations."""
    
    # Exponential moving average alpha (weight for new values)
    # Lower = slower adaptation, higher = faster adaptation
    EMA_ALPHA = 0.1
    
    @staticmethod
    async def update(user_id: str, vitals_stats: Dict) -> bool:
        """Update user baselines with new data."""
        try:
            async with get_db() as db:
                # Get existing baseline
                cursor = await db.execute(
                    "SELECT * FROM user_baselines WHERE user_id = ?",
                    (user_id,)
                )
                existing = await cursor.fetchone()
                
                if existing:
                    # Rolling average update
                    n = existing["data_points"]
                    await db.execute("""
                        UPDATE user_baselines SET
                            avg_heart_rate = (avg_heart_rate * ? + ?) / ?,
                            avg_hrv = (avg_hrv * ? + ?) / ?,
                            avg_spo2 = (avg_spo2 * ? + ?) / ?,
                            avg_temp = (avg_temp * ? + ?) / ?,
                            avg_activity = (avg_activity * ? + ?) / ?,
                            data_points = data_points + 1,
                            updated_at = ?
                        WHERE user_id = ?
                    """, (
                        n, vitals_stats.get("avg_hr", 72), n + 1,
                        n, vitals_stats.get("avg_hrv", 50), n + 1,
                        n, vitals_stats.get("avg_spo2", 98), n + 1,
                        n, vitals_stats.get("avg_temp", 36.5), n + 1,
                        n, vitals_stats.get("avg_activity", 20), n + 1,
                        datetime.utcnow().isoformat(),
                        user_id
                    ))
                else:
                    # Insert new baseline
                    await db.execute("""
                        INSERT INTO user_baselines (
                            user_id, avg_heart_rate, avg_hrv, avg_spo2,
                            avg_temp, avg_activity, data_points, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                    """, (
                        user_id,
                        vitals_stats.get("avg_hr", 72),
                        vitals_stats.get("avg_hrv", 50),
                        vitals_stats.get("avg_spo2", 98),
                        vitals_stats.get("avg_temp", 36.5),
                        vitals_stats.get("avg_activity", 20),
                        datetime.utcnow().isoformat()
                    ))
                
                await db.commit()
                return True
        except Exception as e:
            print(f"Error updating baseline: {e}")
            return False
    
    @staticmethod
    async def auto_update_baseline(user_id: str, vital_data: Dict) -> bool:
        """
        Automatically update baseline with a single vital reading.
        Uses exponential moving average for smooth updates.
        Called on each incoming vital to maintain real-time baselines.
        """
        try:
            alpha = BaselinesRepository.EMA_ALPHA
            
            async with get_db() as db:
                cursor = await db.execute(
                    "SELECT * FROM user_baselines WHERE user_id = ?",
                    (user_id,)
                )
                existing = await cursor.fetchone()
                
                hr = vital_data.get("heart_rate")
                hrv = vital_data.get("hrv_ms")
                spo2 = vital_data.get("spo2_percent")
                temp = vital_data.get("skin_temp_c")
                activity = vital_data.get("activity_level")
                
                if existing:
                    # Convert Row to dict for easier access
                    existing_dict = dict(existing)
                    
                    # EMA update: new_avg = alpha * new_value + (1 - alpha) * old_avg
                    new_hr = alpha * hr + (1 - alpha) * existing_dict["avg_heart_rate"] if hr else existing_dict["avg_heart_rate"]
                    new_hrv = alpha * hrv + (1 - alpha) * existing_dict["avg_hrv"] if hrv else existing_dict["avg_hrv"]
                    new_spo2 = alpha * spo2 + (1 - alpha) * existing_dict["avg_spo2"] if spo2 else existing_dict["avg_spo2"]
                    new_temp = alpha * temp + (1 - alpha) * existing_dict["avg_temp"] if temp else existing_dict["avg_temp"]
                    new_activity = alpha * activity + (1 - alpha) * existing_dict["avg_activity"] if activity else existing_dict["avg_activity"]
                    
                    # Update variance estimates using Welford's online algorithm (simplified)
                    n = existing_dict["data_points"] + 1
                    old_std_hr = existing_dict.get("std_heart_rate") or 0
                    old_std_hrv = existing_dict.get("std_hrv") or 0
                    old_std_spo2 = existing_dict.get("std_spo2") or 0
                    old_std_temp = existing_dict.get("std_temp") or 0
                    
                    # Simple running std estimate
                    new_std_hr = ((1 - alpha) * old_std_hr**2 + alpha * (hr - new_hr)**2)**0.5 if hr else old_std_hr
                    new_std_hrv = ((1 - alpha) * old_std_hrv**2 + alpha * (hrv - new_hrv)**2)**0.5 if hrv else old_std_hrv
                    new_std_spo2 = ((1 - alpha) * old_std_spo2**2 + alpha * (spo2 - new_spo2)**2)**0.5 if spo2 else old_std_spo2
                    new_std_temp = ((1 - alpha) * old_std_temp**2 + alpha * (temp - new_temp)**2)**0.5 if temp else old_std_temp
                    
                    await db.execute("""
                        UPDATE user_baselines SET
                            avg_heart_rate = ?,
                            avg_hrv = ?,
                            avg_spo2 = ?,
                            avg_temp = ?,
                            avg_activity = ?,
                            std_heart_rate = ?,
                            std_hrv = ?,
                            std_spo2 = ?,
                            std_temp = ?,
                            data_points = ?,
                            updated_at = ?
                        WHERE user_id = ?
                    """, (
                        new_hr, new_hrv, new_spo2, new_temp, new_activity,
                        new_std_hr, new_std_hrv, new_std_spo2, new_std_temp,
                        n, datetime.utcnow().isoformat(), user_id
                    ))
                else:
                    # Insert initial baseline
                    await db.execute("""
                        INSERT INTO user_baselines (
                            user_id, avg_heart_rate, avg_hrv, avg_spo2,
                            avg_temp, avg_activity, std_heart_rate, std_hrv,
                            std_spo2, std_temp, data_points, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, 5, 5, 1, 0.2, 1, ?)
                    """, (
                        user_id,
                        hr or 72, hrv or 50, spo2 or 98, temp or 36.5, activity or 20,
                        datetime.utcnow().isoformat()
                    ))
                
                await db.commit()
                return True
        except Exception as e:
            print(f"Error auto-updating baseline: {e}")
            return False
    
    @staticmethod
    async def get_deviation_alert(user_id: str, current_vitals: Dict) -> Optional[Dict]:
        """
        Check if current vitals deviate significantly from baseline.
        Returns personalized alert info if deviation detected.
        """
        baseline = await BaselinesRepository.get(user_id)
        if not baseline or baseline.get("data_points", 0) < 10:
            return None  # Not enough data for personalized alerts
        
        deviations = []
        
        # Check heart rate
        hr = current_vitals.get("heart_rate")
        if hr and baseline.get("avg_heart_rate"):
            baseline_hr = baseline["avg_heart_rate"]
            std_hr = baseline.get("std_heart_rate") or 8
            pct_change = ((hr - baseline_hr) / baseline_hr) * 100
            z_score = (hr - baseline_hr) / std_hr if std_hr > 0 else 0
            
            if abs(pct_change) > 15 or abs(z_score) > 2:
                deviations.append({
                    "metric": "heart_rate",
                    "label": "Heart Rate",
                    "current": hr,
                    "baseline": round(baseline_hr, 0),
                    "unit": "bpm",
                    "percent_change": round(pct_change, 1),
                    "direction": "higher" if pct_change > 0 else "lower",
                    "severity": "high" if abs(pct_change) > 25 else "moderate",
                    "message": f"Your HR is {hr} bpm - {abs(round(pct_change))}% {'higher' if pct_change > 0 else 'lower'} than YOUR typical {round(baseline_hr)} bpm"
                })
        
        # Check HRV
        hrv = current_vitals.get("hrv_ms")
        if hrv and baseline.get("avg_hrv"):
            baseline_hrv = baseline["avg_hrv"]
            std_hrv = baseline.get("std_hrv") or 10
            pct_change = ((hrv - baseline_hrv) / baseline_hrv) * 100
            z_score = (hrv - baseline_hrv) / std_hrv if std_hrv > 0 else 0
            
            if pct_change < -20 or z_score < -2:  # Low HRV is concerning
                deviations.append({
                    "metric": "hrv_ms",
                    "label": "HRV",
                    "current": hrv,
                    "baseline": round(baseline_hrv, 0),
                    "unit": "ms",
                    "percent_change": round(pct_change, 1),
                    "direction": "lower",
                    "severity": "high" if pct_change < -30 else "moderate",
                    "message": f"Your HRV is {hrv} ms - {abs(round(pct_change))}% lower than YOUR typical {round(baseline_hrv)} ms (indicates reduced recovery)"
                })
        
        # Check SpO2
        spo2 = current_vitals.get("spo2_percent")
        if spo2 and baseline.get("avg_spo2"):
            baseline_spo2 = baseline["avg_spo2"]
            if spo2 < 95 or (spo2 < baseline_spo2 - 2):
                pct_change = ((spo2 - baseline_spo2) / baseline_spo2) * 100
                deviations.append({
                    "metric": "spo2_percent",
                    "label": "Blood Oxygen",
                    "current": spo2,
                    "baseline": round(baseline_spo2, 0),
                    "unit": "%",
                    "percent_change": round(pct_change, 1),
                    "direction": "lower",
                    "severity": "high" if spo2 < 94 else "moderate",
                    "message": f"Your SpO2 is {spo2}% - below YOUR typical {round(baseline_spo2)}%"
                })
        
        # Check Temperature
        temp = current_vitals.get("skin_temp_c")
        if temp and baseline.get("avg_temp"):
            baseline_temp = baseline["avg_temp"]
            std_temp = baseline.get("std_temp") or 0.3
            diff = temp - baseline_temp
            
            if abs(diff) > 0.5:
                pct_change = (diff / baseline_temp) * 100
                deviations.append({
                    "metric": "skin_temp_c",
                    "label": "Temperature",
                    "current": round(temp, 1),
                    "baseline": round(baseline_temp, 1),
                    "unit": "°C",
                    "percent_change": round(pct_change, 1),
                    "direction": "higher" if diff > 0 else "lower",
                    "severity": "high" if abs(diff) > 1.0 else "moderate",
                    "message": f"Your temp is {round(temp, 1)}°C - {round(abs(diff), 1)}°C {'above' if diff > 0 else 'below'} YOUR typical {round(baseline_temp, 1)}°C"
                })
        
        if not deviations:
            return None
        
        # Sort by severity
        deviations.sort(key=lambda x: 0 if x["severity"] == "high" else 1)
        
        return {
            "has_deviation": True,
            "deviations": deviations,
            "baseline_data_points": baseline.get("data_points", 0),
            "primary_deviation": deviations[0] if deviations else None
        }
    
    @staticmethod
    async def get(user_id: str = "user_001") -> Optional[Dict]:
        """Get user baselines."""
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM user_baselines WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    @staticmethod
    async def compare_to_current(user_id: str, current_vitals: Dict) -> Dict:
        """Compare current vitals to user's baseline."""
        baseline = await BaselinesRepository.get(user_id)
        if not baseline:
            return {"has_baseline": False}
        
        comparisons = {}
        
        if current_vitals.get("heart_rate") and baseline.get("avg_heart_rate"):
            hr_diff = current_vitals["heart_rate"] - baseline["avg_heart_rate"]
            hr_pct = (hr_diff / baseline["avg_heart_rate"]) * 100
            comparisons["heart_rate"] = {
                "current": current_vitals["heart_rate"],
                "baseline": round(baseline["avg_heart_rate"], 1),
                "difference": round(hr_diff, 1),
                "percent_change": round(hr_pct, 1),
                "std": round(baseline.get("std_heart_rate") or 0, 1),
                "status": "elevated" if hr_pct > 15 else "low" if hr_pct < -15 else "normal"
            }
        
        if current_vitals.get("hrv_ms") and baseline.get("avg_hrv"):
            hrv_diff = current_vitals["hrv_ms"] - baseline["avg_hrv"]
            hrv_pct = (hrv_diff / baseline["avg_hrv"]) * 100
            comparisons["hrv"] = {
                "current": current_vitals["hrv_ms"],
                "baseline": round(baseline["avg_hrv"], 1),
                "difference": round(hrv_diff, 1),
                "percent_change": round(hrv_pct, 1),
                "std": round(baseline.get("std_hrv") or 0, 1),
                "status": "low" if hrv_pct < -20 else "high" if hrv_pct > 20 else "normal"
            }
        
        if current_vitals.get("spo2_percent") and baseline.get("avg_spo2"):
            spo2_diff = current_vitals["spo2_percent"] - baseline["avg_spo2"]
            comparisons["spo2"] = {
                "current": current_vitals["spo2_percent"],
                "baseline": round(baseline["avg_spo2"], 1),
                "difference": round(spo2_diff, 1),
                "std": round(baseline.get("std_spo2") or 0, 1),
                "status": "low" if current_vitals["spo2_percent"] < 95 else "normal"
            }
        
        if current_vitals.get("skin_temp_c") and baseline.get("avg_temp"):
            temp_diff = current_vitals["skin_temp_c"] - baseline["avg_temp"]
            comparisons["temperature"] = {
                "current": current_vitals["skin_temp_c"],
                "baseline": round(baseline["avg_temp"], 2),
                "difference": round(temp_diff, 2),
                "std": round(baseline.get("std_temp") or 0, 2),
                "status": "elevated" if temp_diff > 0.5 else "low" if temp_diff < -0.5 else "normal"
            }
        
        return {
            "has_baseline": True,
            "data_points": baseline.get("data_points", 0),
            "comparisons": comparisons
        }


# Utility functions
async def get_anomaly_context(alert_id: str) -> Dict:
    """Get context around an anomaly for AI analysis."""
    alert = await AlertsRepository.get_by_id(alert_id)
    if not alert:
        return {}
    
    # Get vitals from around the alert time
    recent_vitals = await VitalsRepository.get_recent(minutes=30, user_id=alert.get("user_id", "user_001"))
    baseline = await BaselinesRepository.get(alert.get("user_id", "user_001"))
    
    return {
        "alert": alert,
        "recent_vitals": recent_vitals[:20],  # Last 20 readings
        "baseline": baseline,
        "vitals_count": len(recent_vitals)
    }


async def calculate_correlations(metric1: str, metric2: str, hours: int = 24, user_id: str = "user_001") -> Dict:
    """Calculate correlation between two metrics."""
    async with get_db() as db:
        valid_metrics = ["heart_rate", "hrv_ms", "spo2_percent", "skin_temp_c", "activity_level"]
        if metric1 not in valid_metrics or metric2 not in valid_metrics:
            return {"error": "Invalid metric"}
        
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        cursor = await db.execute(f"""
            SELECT {metric1}, {metric2}
            FROM vitals 
            WHERE user_id = ? AND timestamp > ?
            AND {metric1} IS NOT NULL AND {metric2} IS NOT NULL
        """, (user_id, cutoff.isoformat()))
        rows = await cursor.fetchall()
        
        if len(rows) < 10:
            return {"error": "Insufficient data", "data_points": len(rows)}
        
        # Simple Pearson correlation calculation
        values1 = [row[metric1] for row in rows]
        values2 = [row[metric2] for row in rows]
        
        n = len(values1)
        mean1 = sum(values1) / n
        mean2 = sum(values2) / n
        
        numerator = sum((v1 - mean1) * (v2 - mean2) for v1, v2 in zip(values1, values2))
        denom1 = sum((v - mean1) ** 2 for v in values1) ** 0.5
        denom2 = sum((v - mean2) ** 2 for v in values2) ** 0.5
        
        if denom1 == 0 or denom2 == 0:
            correlation = 0
        else:
            correlation = numerator / (denom1 * denom2)
        
        strength = "strong" if abs(correlation) > 0.7 else "moderate" if abs(correlation) > 0.4 else "weak"
        direction = "positive" if correlation > 0 else "negative"
        
        return {
            "metric1": metric1,
            "metric2": metric2,
            "correlation": round(correlation, 3),
            "strength": strength,
            "direction": direction,
            "data_points": n,
            "interpretation": f"{strength.capitalize()} {direction} correlation between {metric1} and {metric2}"
        }

