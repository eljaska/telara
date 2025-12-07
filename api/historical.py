"""
Telara Historical Comparison
Compares current week vs previous week health metrics.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from database import VitalsRepository, AlertsRepository, get_db


class HistoricalAnalyzer:
    """Analyzes historical health data for week-over-week comparisons."""
    
    METRICS = [
        ("heart_rate", "Heart Rate", "bpm", "lower_better"),
        ("hrv_ms", "HRV", "ms", "higher_better"),
        ("spo2_percent", "SpO2", "%", "higher_better"),
        ("skin_temp_c", "Temperature", "°C", "stable_better"),
        ("activity_level", "Activity", "lvl", "higher_better"),
    ]
    
    @classmethod
    async def get_period_stats(
        cls,
        start: datetime,
        end: datetime,
        user_id: str = "user_001"
    ) -> Dict[str, Any]:
        """Get aggregated stats for a specific time period."""
        async with get_db() as db:
            cursor = await db.execute("""
                SELECT 
                    COUNT(*) as data_points,
                    AVG(heart_rate) as avg_heart_rate,
                    MIN(heart_rate) as min_heart_rate,
                    MAX(heart_rate) as max_heart_rate,
                    AVG(hrv_ms) as avg_hrv,
                    MIN(hrv_ms) as min_hrv,
                    MAX(hrv_ms) as max_hrv,
                    AVG(spo2_percent) as avg_spo2,
                    MIN(spo2_percent) as min_spo2,
                    MAX(spo2_percent) as max_spo2,
                    AVG(skin_temp_c) as avg_temp,
                    MIN(skin_temp_c) as min_temp,
                    MAX(skin_temp_c) as max_temp,
                    AVG(activity_level) as avg_activity,
                    MAX(activity_level) as max_activity
                FROM vitals 
                WHERE user_id = ? AND timestamp >= ? AND timestamp < ?
            """, (user_id, start.isoformat(), end.isoformat()))
            row = await cursor.fetchone()
            
            if not row or row["data_points"] == 0:
                return {"data_available": False, "data_points": 0}
            
            return {
                "data_available": True,
                "data_points": row["data_points"],
                "period": {
                    "start": start.isoformat(),
                    "end": end.isoformat()
                },
                "heart_rate": {
                    "avg": round(row["avg_heart_rate"], 1) if row["avg_heart_rate"] else None,
                    "min": row["min_heart_rate"],
                    "max": row["max_heart_rate"]
                },
                "hrv_ms": {
                    "avg": round(row["avg_hrv"], 1) if row["avg_hrv"] else None,
                    "min": row["min_hrv"],
                    "max": row["max_hrv"]
                },
                "spo2_percent": {
                    "avg": round(row["avg_spo2"], 1) if row["avg_spo2"] else None,
                    "min": row["min_spo2"],
                    "max": row["max_spo2"]
                },
                "skin_temp_c": {
                    "avg": round(row["avg_temp"], 2) if row["avg_temp"] else None,
                    "min": round(row["min_temp"], 2) if row["min_temp"] else None,
                    "max": round(row["max_temp"], 2) if row["max_temp"] else None
                },
                "activity_level": {
                    "avg": round(row["avg_activity"], 1) if row["avg_activity"] else None,
                    "max": row["max_activity"]
                }
            }
    
    @classmethod
    async def get_period_alerts(
        cls,
        start: datetime,
        end: datetime,
        user_id: str = "user_001"
    ) -> Dict[str, Any]:
        """Get alert summary for a period."""
        async with get_db() as db:
            cursor = await db.execute("""
                SELECT 
                    severity,
                    COUNT(*) as count
                FROM alerts 
                WHERE user_id = ? AND timestamp >= ? AND timestamp < ?
                GROUP BY severity
            """, (user_id, start.isoformat(), end.isoformat()))
            rows = await cursor.fetchall()
            
            counts = {row["severity"]: row["count"] for row in rows}
            total = sum(counts.values())
            
            return {
                "total": total,
                "by_severity": counts
            }
    
    @classmethod
    def calculate_comparison(
        cls,
        current: Dict[str, Any],
        previous: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Calculate comparison between two periods."""
        comparisons = []
        
        for metric_key, label, unit, direction in cls.METRICS:
            current_data = current.get(metric_key, {})
            previous_data = previous.get(metric_key, {})
            
            current_avg = current_data.get("avg")
            previous_avg = previous_data.get("avg")
            
            if current_avg is None or previous_avg is None:
                continue
            
            difference = current_avg - previous_avg
            
            if previous_avg != 0:
                percent_change = (difference / previous_avg) * 100
            else:
                percent_change = 0
            
            # Determine if change is improvement
            if direction == "higher_better":
                improved = difference > 0
            elif direction == "lower_better":
                improved = difference < 0
            else:  # stable_better
                improved = abs(difference) < 0.3  # For temperature
            
            comparisons.append({
                "metric": metric_key,
                "label": label,
                "unit": unit,
                "current": {
                    "avg": current_avg,
                    "min": current_data.get("min"),
                    "max": current_data.get("max")
                },
                "previous": {
                    "avg": previous_avg,
                    "min": previous_data.get("min"),
                    "max": previous_data.get("max")
                },
                "difference": round(difference, 2),
                "percent_change": round(percent_change, 1),
                "direction": "up" if difference > 0 else "down" if difference < 0 else "stable",
                "improved": improved,
                "trend_direction": direction
            })
        
        return comparisons
    
    @classmethod
    def generate_summary(
        cls,
        comparisons: List[Dict],
        current_alerts: Dict,
        previous_alerts: Dict
    ) -> Dict[str, Any]:
        """Generate a summary of the week comparison."""
        improvements = [c for c in comparisons if c["improved"]]
        regressions = [c for c in comparisons if not c["improved"] and abs(c["percent_change"]) > 5]
        
        # Find most significant changes
        sorted_by_change = sorted(comparisons, key=lambda x: abs(x["percent_change"]), reverse=True)
        
        # Generate insights
        insights = []
        
        if sorted_by_change:
            top_change = sorted_by_change[0]
            if abs(top_change["percent_change"]) > 5:
                direction = "improved" if top_change["improved"] else "declined"
                insights.append(
                    f"Your {top_change['label']} {direction} by {abs(top_change['percent_change'])}% compared to last week."
                )
        
        if len(improvements) > len(regressions):
            insights.append(f"Overall positive trend: {len(improvements)} metrics improved vs {len(regressions)} declined.")
        elif len(regressions) > len(improvements):
            insights.append(f"Consider focusing on recovery: {len(regressions)} metrics declined this week.")
        else:
            insights.append("Your metrics are relatively stable compared to last week.")
        
        # Alert comparison
        current_total = current_alerts.get("total", 0)
        previous_total = previous_alerts.get("total", 0)
        
        if current_total < previous_total:
            insights.append(f"Great progress! You had {previous_total - current_total} fewer alerts than last week.")
        elif current_total > previous_total:
            insights.append(f"You had {current_total - previous_total} more alerts than last week. Monitor your trends.")
        
        return {
            "improvements_count": len(improvements),
            "regressions_count": len(regressions),
            "stable_count": len(comparisons) - len(improvements) - len(regressions),
            "most_improved": improvements[0]["label"] if improvements else None,
            "needs_attention": regressions[0]["label"] if regressions else None,
            "insights": insights[:3]  # Top 3 insights
        }
    
    @classmethod
    async def get_week_comparison(
        cls,
        user_id: str = "user_001"
    ) -> Dict[str, Any]:
        """
        Get complete week-over-week comparison.
        Compares last 7 days to the 7 days before that.
        """
        now = datetime.utcnow()
        
        # Current week: last 7 days
        current_end = now
        current_start = now - timedelta(days=7)
        
        # Previous week: 7-14 days ago
        previous_end = current_start
        previous_start = previous_end - timedelta(days=7)
        
        # Get stats for both periods
        current_stats = await cls.get_period_stats(current_start, current_end, user_id)
        previous_stats = await cls.get_period_stats(previous_start, previous_end, user_id)
        
        # Get alerts for both periods
        current_alerts = await cls.get_period_alerts(current_start, current_end, user_id)
        previous_alerts = await cls.get_period_alerts(previous_start, previous_end, user_id)
        
        # Check data availability
        if not current_stats.get("data_available") and not previous_stats.get("data_available"):
            return {
                "data_available": False,
                "message": "Not enough historical data for comparison"
            }
        
        # Calculate comparisons
        comparisons = []
        if current_stats.get("data_available") and previous_stats.get("data_available"):
            comparisons = cls.calculate_comparison(current_stats, previous_stats)
        
        # Generate summary
        summary = cls.generate_summary(comparisons, current_alerts, previous_alerts)
        
        return {
            "data_available": True,
            "current_week": {
                "label": "This Week",
                "period": {
                    "start": current_start.isoformat(),
                    "end": current_end.isoformat()
                },
                "stats": current_stats,
                "alerts": current_alerts
            },
            "previous_week": {
                "label": "Last Week",
                "period": {
                    "start": previous_start.isoformat(),
                    "end": previous_end.isoformat()
                },
                "stats": previous_stats,
                "alerts": previous_alerts
            },
            "comparisons": comparisons,
            "summary": summary,
            "generated_at": datetime.utcnow().isoformat()
        }


async def get_week_comparison(user_id: str = "user_001") -> Dict[str, Any]:
    """Get week-over-week health comparison."""
    return await HistoricalAnalyzer.get_week_comparison(user_id)

