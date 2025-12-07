"""
Telara SQLite Database Layer
Stores vitals, alerts, and user baselines for AI analysis.
"""

import aiosqlite
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
import json
import os

DATABASE_PATH = os.environ.get("DATABASE_PATH", "/app/data/telara.db")

# Global connection pool settings
_db_lock = asyncio.Lock()


async def init_database():
    """Initialize the database with required tables."""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    
    async with aiosqlite.connect(DATABASE_PATH, timeout=30.0) as db:
        # Enable WAL mode for better concurrent access
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        await db.execute("PRAGMA busy_timeout=30000")
        
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
        print("✓ Database initialized successfully (WAL mode enabled)")


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
    """Repository for vital signs data operations."""
    
    @staticmethod
    async def insert(vital_data: Dict[str, Any]) -> bool:
        """Insert a new vital reading."""
        try:
            async with get_db() as db:
                await db.execute("""
                    INSERT OR REPLACE INTO vitals (
                        event_id, timestamp, user_id, heart_rate, hrv_ms,
                        spo2_percent, skin_temp_c, respiratory_rate,
                        activity_level, steps_per_minute, calories_per_minute,
                        posture, sleep_hours, room_temp_c, humidity_percent
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
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
                await db.commit()
                return True
        except Exception as e:
            print(f"Error inserting vital: {e}")
            return False
    
    @staticmethod
    async def get_recent(minutes: int = 60, user_id: str = "user_001") -> List[Dict]:
        """Get vitals from the last N minutes."""
        async with get_db() as db:
            cutoff = datetime.utcnow() - timedelta(minutes=minutes)
            cursor = await db.execute("""
                SELECT * FROM vitals 
                WHERE user_id = ? AND timestamp > ?
                ORDER BY timestamp DESC
            """, (user_id, cutoff.isoformat()))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
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
        """Get the most recent vital reading."""
        async with get_db() as db:
            cursor = await db.execute("""
                SELECT * FROM vitals 
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, (user_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    @staticmethod
    async def get_stats(hours: int = 24, user_id: str = "user_001") -> Dict:
        """Get statistical summary of vitals."""
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
            return dict(row) if row else {}
    
    @staticmethod
    async def cleanup_old_data(hours: int = 48):
        """Remove data older than N hours."""
        async with get_db() as db:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            await db.execute("DELETE FROM vitals WHERE timestamp < ?", (cutoff.isoformat(),))
            await db.commit()
    
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

