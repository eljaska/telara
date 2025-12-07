"""
Telara Daily Health Digest
Generates "Your Day at a Glance" summary with AI observations.
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from anthropic import Anthropic

from database import VitalsRepository, AlertsRepository, BaselinesRepository


# Configuration
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-opus-4-5-20251101"


class DailyDigestGenerator:
    """Generates comprehensive daily health digests with AI insights."""
    
    def __init__(self):
        self.client = Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
    
    async def get_period_stats(
        self,
        hours: int,
        user_id: str = "user_001"
    ) -> Dict[str, Any]:
        """Get aggregated stats for a time period."""
        vitals = await VitalsRepository.get_recent(minutes=hours * 60, user_id=user_id)
        
        if not vitals:
            return {
                "data_available": False,
                "data_points": 0
            }
        
        # Calculate aggregates
        hr_values = [v["heart_rate"] for v in vitals if v.get("heart_rate")]
        hrv_values = [v["hrv_ms"] for v in vitals if v.get("hrv_ms")]
        spo2_values = [v["spo2_percent"] for v in vitals if v.get("spo2_percent")]
        temp_values = [v["skin_temp_c"] for v in vitals if v.get("skin_temp_c")]
        activity_values = [v["activity_level"] for v in vitals if v.get("activity_level") is not None]
        
        stats = {
            "data_available": True,
            "data_points": len(vitals),
            "period_hours": hours
        }
        
        if hr_values:
            stats["heart_rate"] = {
                "avg": round(sum(hr_values) / len(hr_values), 1),
                "min": min(hr_values),
                "max": max(hr_values),
                "readings": len(hr_values)
            }
        
        if hrv_values:
            stats["hrv"] = {
                "avg": round(sum(hrv_values) / len(hrv_values), 1),
                "min": min(hrv_values),
                "max": max(hrv_values),
                "readings": len(hrv_values)
            }
        
        if spo2_values:
            stats["spo2"] = {
                "avg": round(sum(spo2_values) / len(spo2_values), 1),
                "min": min(spo2_values),
                "max": max(spo2_values),
                "readings": len(spo2_values)
            }
        
        if temp_values:
            stats["temperature"] = {
                "avg": round(sum(temp_values) / len(temp_values), 2),
                "min": round(min(temp_values), 2),
                "max": round(max(temp_values), 2),
                "readings": len(temp_values)
            }
        
        if activity_values:
            stats["activity"] = {
                "avg": round(sum(activity_values) / len(activity_values), 1),
                "max": max(activity_values),
                "readings": len(activity_values)
            }
        
        return stats
    
    def calculate_delta(
        self,
        today: Dict[str, Any],
        yesterday: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate deltas between today and yesterday."""
        deltas = {}
        
        metrics = ["heart_rate", "hrv", "spo2", "temperature", "activity"]
        
        for metric in metrics:
            if metric in today and metric in yesterday:
                today_val = today[metric]["avg"]
                yesterday_val = yesterday[metric]["avg"]
                
                if yesterday_val and yesterday_val != 0:
                    diff = today_val - yesterday_val
                    pct_change = (diff / yesterday_val) * 100
                    
                    deltas[metric] = {
                        "today": today_val,
                        "yesterday": yesterday_val,
                        "difference": round(diff, 2),
                        "percent_change": round(pct_change, 1),
                        "direction": "up" if diff > 0 else "down" if diff < 0 else "stable",
                        "improved": self._is_improvement(metric, diff)
                    }
        
        return deltas
    
    def _is_improvement(self, metric: str, diff: float) -> bool:
        """Determine if a change is an improvement."""
        # For HRV, higher is better
        if metric == "hrv":
            return diff > 0
        # For heart rate, lower at rest is generally better
        elif metric == "heart_rate":
            return diff < 0
        # For SpO2, higher is better
        elif metric == "spo2":
            return diff > 0
        # For activity, higher is generally better
        elif metric == "activity":
            return diff > 0
        # For temperature, stable is best
        elif metric == "temperature":
            return abs(diff) < 0.3
        return True
    
    async def generate_ai_observations(
        self,
        today_stats: Dict,
        deltas: Dict,
        alerts: List[Dict],
        baseline: Optional[Dict]
    ) -> List[str]:
        """Generate AI-powered observations about the day's health data."""
        if not self.client:
            return self._generate_rule_based_observations(today_stats, deltas, alerts)
        
        # Prepare context for AI
        context = f"""
Based on today's health data, generate exactly 3 brief, insightful observations:

Today's Stats:
- Heart Rate: avg {today_stats.get('heart_rate', {}).get('avg', 'N/A')} bpm (range: {today_stats.get('heart_rate', {}).get('min', 'N/A')}-{today_stats.get('heart_rate', {}).get('max', 'N/A')})
- HRV: avg {today_stats.get('hrv', {}).get('avg', 'N/A')} ms
- SpO2: avg {today_stats.get('spo2', {}).get('avg', 'N/A')}%
- Temperature: avg {today_stats.get('temperature', {}).get('avg', 'N/A')}°C
- Activity Level: avg {today_stats.get('activity', {}).get('avg', 'N/A')}

Compared to Yesterday:
"""
        for metric, delta in deltas.items():
            direction = "↑" if delta["direction"] == "up" else "↓" if delta["direction"] == "down" else "→"
            context += f"- {metric}: {direction} {abs(delta['percent_change'])}%\n"
        
        context += f"\nAlerts Today: {len(alerts)} ({len([a for a in alerts if a.get('severity') == 'CRITICAL'])} critical)"
        
        if baseline:
            context += f"\nBaseline established from {baseline.get('data_points', 0)} data points"
        
        context += """

Requirements:
1. Each observation should be 1-2 sentences max
2. Focus on actionable insights
3. Be supportive and encouraging
4. Highlight the most significant patterns

Return ONLY the 3 observations, one per line, no numbering or bullets."""

        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=300,
                messages=[{"role": "user", "content": context}]
            )
            
            observations = response.content[0].text.strip().split('\n')
            return [obs.strip() for obs in observations if obs.strip()][:3]
        except Exception as e:
            print(f"Error generating AI observations: {e}")
            return self._generate_rule_based_observations(today_stats, deltas, alerts)
    
    def _generate_rule_based_observations(
        self,
        today_stats: Dict,
        deltas: Dict,
        alerts: List[Dict]
    ) -> List[str]:
        """Fallback rule-based observations when AI is unavailable."""
        observations = []
        
        # HRV observation
        if "hrv" in deltas:
            hrv_delta = deltas["hrv"]
            if hrv_delta["direction"] == "up" and hrv_delta["percent_change"] > 5:
                observations.append(f"Your HRV improved by {hrv_delta['percent_change']}% compared to yesterday, indicating better recovery.")
            elif hrv_delta["direction"] == "down" and abs(hrv_delta["percent_change"]) > 10:
                observations.append(f"Your HRV decreased by {abs(hrv_delta['percent_change'])}% - consider prioritizing rest today.")
        
        # Heart rate observation
        if "heart_rate" in today_stats:
            hr_range = today_stats["heart_rate"]["max"] - today_stats["heart_rate"]["min"]
            if hr_range > 60:
                observations.append(f"Your heart rate varied significantly today (range of {hr_range} bpm), likely reflecting periods of activity and rest.")
            elif today_stats["heart_rate"]["avg"] < 70:
                observations.append("Your average heart rate is in a healthy resting range, suggesting good cardiovascular fitness.")
        
        # Activity observation
        if "activity" in today_stats:
            avg_activity = today_stats["activity"]["avg"]
            if avg_activity > 40:
                observations.append("You've been quite active today - great for your overall health!")
            elif avg_activity < 15:
                observations.append("Your activity level has been low - try incorporating some movement for better energy.")
        
        # Alert observation
        if alerts:
            critical = len([a for a in alerts if a.get("severity") == "CRITICAL"])
            if critical > 0:
                observations.append(f"There were {critical} critical health alerts today - please review them carefully.")
            else:
                observations.append(f"You had {len(alerts)} health alerts today, all non-critical.")
        
        # Fill with generic if needed
        while len(observations) < 3:
            if "spo2" in today_stats and today_stats["spo2"]["avg"] >= 96:
                observations.append("Your blood oxygen levels have remained healthy throughout the day.")
            elif "temperature" in today_stats and 36.0 <= today_stats["temperature"]["avg"] <= 37.2:
                observations.append("Your body temperature has been stable and within normal range.")
            else:
                observations.append("Keep up your healthy habits for continued wellness improvements.")
            if len(observations) >= 3:
                break
        
        return observations[:3]
    
    def generate_recommendation(
        self,
        today_stats: Dict,
        deltas: Dict,
        alerts: List[Dict]
    ) -> str:
        """Generate a primary actionable recommendation."""
        # Priority-based recommendation selection
        
        # Check for critical issues first
        critical_alerts = [a for a in alerts if a.get("severity") == "CRITICAL"]
        if critical_alerts:
            return "Review and address your critical health alerts. Consider consulting a healthcare provider if symptoms persist."
        
        # Check HRV trend
        if "hrv" in deltas and deltas["hrv"]["direction"] == "down" and abs(deltas["hrv"]["percent_change"]) > 15:
            return "Your recovery markers are lower than yesterday. Prioritize quality sleep tonight and consider lighter activities."
        
        # Check activity level
        if "activity" in today_stats and today_stats["activity"]["avg"] < 20:
            return "Increase your activity level today - even a 15-minute walk can boost your energy and mood."
        
        # Check heart rate
        if "heart_rate" in today_stats and today_stats["heart_rate"]["avg"] > 85:
            return "Your resting heart rate is elevated. Focus on stress reduction techniques like deep breathing or meditation."
        
        # Check temperature
        if "temperature" in today_stats and today_stats["temperature"]["avg"] > 37.5:
            return "Your temperature is slightly elevated. Rest, stay hydrated, and monitor for any symptoms."
        
        # Default positive recommendation
        if "hrv" in deltas and deltas["hrv"]["improved"]:
            return "Your recovery looks good! Maintain your current sleep and activity patterns."
        
        return "Continue your healthy habits: stay hydrated, move regularly, and aim for 7-8 hours of sleep."
    
    async def generate_digest(self, user_id: str = "user_001") -> Dict[str, Any]:
        """Generate a complete daily health digest."""
        # Get today's stats (last 24 hours, but we'll label it as "today")
        today_stats = await self.get_period_stats(hours=12, user_id=user_id)
        
        # Get yesterday's stats (24-48 hours ago)
        yesterday_vitals = await VitalsRepository.get_recent(minutes=48 * 60, user_id=user_id)
        
        # Filter for yesterday only (24-48 hours ago)
        now = datetime.utcnow()
        yesterday_start = now - timedelta(hours=48)
        yesterday_end = now - timedelta(hours=24)
        
        yesterday_filtered = [
            v for v in yesterday_vitals
            if yesterday_start <= datetime.fromisoformat(v["timestamp"]) <= yesterday_end
        ]
        
        # Calculate yesterday's stats manually
        yesterday_stats = {"data_available": False}
        if yesterday_filtered:
            hr_values = [v["heart_rate"] for v in yesterday_filtered if v.get("heart_rate")]
            hrv_values = [v["hrv_ms"] for v in yesterday_filtered if v.get("hrv_ms")]
            spo2_values = [v["spo2_percent"] for v in yesterday_filtered if v.get("spo2_percent")]
            temp_values = [v["skin_temp_c"] for v in yesterday_filtered if v.get("skin_temp_c")]
            activity_values = [v["activity_level"] for v in yesterday_filtered if v.get("activity_level") is not None]
            
            yesterday_stats = {"data_available": True}
            if hr_values:
                yesterday_stats["heart_rate"] = {"avg": sum(hr_values) / len(hr_values)}
            if hrv_values:
                yesterday_stats["hrv"] = {"avg": sum(hrv_values) / len(hrv_values)}
            if spo2_values:
                yesterday_stats["spo2"] = {"avg": sum(spo2_values) / len(spo2_values)}
            if temp_values:
                yesterday_stats["temperature"] = {"avg": sum(temp_values) / len(temp_values)}
            if activity_values:
                yesterday_stats["activity"] = {"avg": sum(activity_values) / len(activity_values)}
        
        # Calculate deltas
        deltas = {}
        if today_stats.get("data_available") and yesterday_stats.get("data_available"):
            deltas = self.calculate_delta(today_stats, yesterday_stats)
        
        # Get alerts for today
        alerts = await AlertsRepository.get_recent(hours=24, user_id=user_id)
        
        # Get baseline for context
        baseline = await BaselinesRepository.get(user_id)
        
        # Generate AI observations
        observations = await self.generate_ai_observations(
            today_stats, deltas, alerts, baseline
        )
        
        # Generate primary recommendation
        recommendation = self.generate_recommendation(today_stats, deltas, alerts)
        
        # Compile digest
        digest = {
            "title": "Your Day at a Glance",
            "generated_at": datetime.utcnow().isoformat(),
            "period": {
                "start": (datetime.utcnow() - timedelta(hours=12)).isoformat(),
                "end": datetime.utcnow().isoformat(),
                "hours": 12
            },
            "summary": {
                "data_points": today_stats.get("data_points", 0),
                "alerts_count": len(alerts),
                "critical_alerts": len([a for a in alerts if a.get("severity") == "CRITICAL"]),
            },
            "metrics": today_stats,
            "comparisons": deltas,
            "observations": observations,
            "recommendation": recommendation,
            "yesterday_available": yesterday_stats.get("data_available", False)
        }
        
        return digest


# Module-level instance
digest_generator = DailyDigestGenerator()


async def generate_daily_digest(user_id: str = "user_001") -> Dict[str, Any]:
    """Generate daily health digest."""
    return await digest_generator.generate_digest(user_id)

