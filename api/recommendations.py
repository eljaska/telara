"""
Telara Recommendation Engine
Rule-based health recommendations tied to alerts and wellness score.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class RecommendationPriority(Enum):
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


@dataclass
class Recommendation:
    """A health recommendation."""
    id: str
    category: str
    title: str
    description: str
    priority: RecommendationPriority
    icon: str  # Lucide icon name for frontend
    action_type: str  # immediate, short_term, lifestyle
    

class RecommendationEngine:
    """
    Rule-based recommendation engine that generates actionable suggestions
    based on vitals, alerts, wellness score, and time of day.
    """
    
    # Time-of-day contexts
    MORNING = range(5, 12)  # 5am - 12pm
    AFTERNOON = range(12, 17)  # 12pm - 5pm
    EVENING = range(17, 21)  # 5pm - 9pm
    NIGHT = list(range(21, 24)) + list(range(0, 5))  # 9pm - 5am
    
    @staticmethod
    def get_time_context() -> str:
        """Get current time of day context."""
        hour = datetime.now().hour
        if hour in RecommendationEngine.MORNING:
            return "morning"
        elif hour in RecommendationEngine.AFTERNOON:
            return "afternoon"
        elif hour in RecommendationEngine.EVENING:
            return "evening"
        else:
            return "night"
    
    @classmethod
    def generate_recommendations(
        cls,
        vitals: Dict[str, Any],
        alerts: List[Dict],
        wellness_breakdown: Dict[str, Any],
        baseline: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Generate recommendations based on current health state.
        
        Args:
            vitals: Latest vital readings
            alerts: Recent alerts
            wellness_breakdown: Wellness score breakdown
            baseline: User's baseline data
            
        Returns:
            List of recommendations sorted by priority
        """
        recommendations = []
        time_context = cls.get_time_context()
        
        # Extract key metrics
        hr = vitals.get("heart_rate", 72)
        hrv = vitals.get("hrv_ms", 50)
        spo2 = vitals.get("spo2_percent", 98)
        temp = vitals.get("skin_temp_c", 36.5)
        activity = vitals.get("activity_level", 20)
        
        # Rule 1: High HR + Low Activity = Possible stress/dehydration
        if hr > 90 and activity < 30:
            recommendations.append({
                "id": "high_hr_low_activity",
                "category": "hydration",
                "title": "Consider Hydration & Rest",
                "description": f"Your heart rate is elevated ({hr} bpm) while activity is low. This could indicate dehydration or stress. Try drinking water and taking a few deep breaths.",
                "priority": RecommendationPriority.HIGH.value,
                "icon": "Droplets",
                "action_type": "immediate",
                "metrics": {"heart_rate": hr, "activity_level": activity}
            })
        
        # Rule 2: Low HRV = Poor recovery
        if hrv < 35:
            if time_context in ["morning", "afternoon"]:
                recommendations.append({
                    "id": "low_hrv_recovery",
                    "category": "recovery",
                    "title": "Recovery Mode Recommended",
                    "description": f"Your HRV is low ({hrv} ms), indicating reduced recovery capacity. Consider lighter activities today and prioritize rest. Avoid intense exercise.",
                    "priority": RecommendationPriority.HIGH.value,
                    "icon": "Battery",
                    "action_type": "short_term",
                    "metrics": {"hrv_ms": hrv}
                })
            else:
                recommendations.append({
                    "id": "low_hrv_sleep",
                    "category": "sleep",
                    "title": "Prioritize Sleep Tonight",
                    "description": f"Your HRV ({hrv} ms) suggests your body needs recovery. Aim for 7-8 hours of quality sleep tonight.",
                    "priority": RecommendationPriority.MEDIUM.value,
                    "icon": "Moon",
                    "action_type": "short_term",
                    "metrics": {"hrv_ms": hrv}
                })
        
        # Rule 3: Elevated Temperature
        if temp > 37.5:
            recommendations.append({
                "id": "elevated_temp",
                "category": "health",
                "title": "Monitor for Illness",
                "description": f"Your temperature is elevated ({temp:.1f}°C). Rest is recommended. If symptoms persist or temperature rises above 38°C, consider consulting a healthcare provider.",
                "priority": RecommendationPriority.HIGH.value,
                "icon": "Thermometer",
                "action_type": "immediate",
                "metrics": {"skin_temp_c": temp}
            })
        
        # Rule 4: Low SpO2
        if spo2 < 95:
            priority = RecommendationPriority.CRITICAL if spo2 < 92 else RecommendationPriority.HIGH
            recommendations.append({
                "id": "low_spo2",
                "category": "breathing",
                "title": "Improve Oxygen Levels",
                "description": f"Your blood oxygen is low ({spo2}%). Take deep breaths, ensure good ventilation, and consider stepping outside for fresh air. If it remains low, seek medical attention.",
                "priority": priority.value,
                "icon": "Wind",
                "action_type": "immediate",
                "metrics": {"spo2_percent": spo2}
            })
        
        # Rule 5: High Activity + High HR for extended period
        if activity > 70 and hr > 140:
            recommendations.append({
                "id": "intense_activity",
                "category": "exercise",
                "title": "Consider a Recovery Break",
                "description": f"You've been exercising intensely (HR: {hr} bpm). Consider a cool-down period to allow your heart rate to recover gradually.",
                "priority": RecommendationPriority.MEDIUM.value,
                "icon": "Timer",
                "action_type": "immediate",
                "metrics": {"heart_rate": hr, "activity_level": activity}
            })
        
        # Rule 6: Very Low Activity (sedentary alert)
        if activity < 10 and time_context in ["morning", "afternoon"]:
            recommendations.append({
                "id": "sedentary_alert",
                "category": "activity",
                "title": "Time for Movement",
                "description": "You've been sedentary for a while. Try a short walk, some stretches, or just stand up and move around for a few minutes.",
                "priority": RecommendationPriority.LOW.value,
                "icon": "Footprints",
                "action_type": "immediate",
                "metrics": {"activity_level": activity}
            })
        
        # Rule 7: Alert-based recommendations
        recent_critical = [a for a in alerts if a.get("severity") == "CRITICAL"]
        recent_high = [a for a in alerts if a.get("severity") == "HIGH"]
        
        if recent_critical:
            recommendations.append({
                "id": "critical_alert_response",
                "category": "alert",
                "title": "Address Critical Alerts",
                "description": f"You have {len(recent_critical)} critical health alert(s). Review the alert details and consider consulting a healthcare provider if symptoms persist.",
                "priority": RecommendationPriority.CRITICAL.value,
                "icon": "AlertTriangle",
                "action_type": "immediate",
                "metrics": {"critical_alerts": len(recent_critical)}
            })
        
        # Rule 8: Wellness breakdown specific recommendations
        if wellness_breakdown:
            # Heart health component
            heart_health = wellness_breakdown.get("heart_health", {})
            if heart_health.get("score", 100) < 60:
                if hr > 85:
                    recommendations.append({
                        "id": "heart_health_hr",
                        "category": "cardiovascular",
                        "title": "Support Heart Health",
                        "description": "Your heart health score is lower than optimal. Consider reducing caffeine, staying hydrated, and practicing relaxation techniques.",
                        "priority": RecommendationPriority.MEDIUM.value,
                        "icon": "Heart",
                        "action_type": "lifestyle",
                        "metrics": {"heart_health_score": heart_health.get("score")}
                    })
            
            # Recovery component
            recovery = wellness_breakdown.get("recovery", {})
            if recovery.get("score", 100) < 60:
                recommendations.append({
                    "id": "recovery_support",
                    "category": "recovery",
                    "title": "Boost Your Recovery",
                    "description": "Your recovery score suggests your body needs extra support. Consider gentle activities like walking or yoga, and ensure adequate sleep.",
                    "priority": RecommendationPriority.MEDIUM.value,
                    "icon": "RefreshCw",
                    "action_type": "short_term",
                    "metrics": {"recovery_score": recovery.get("score")}
                })
            
            # Activity component
            activity_score = wellness_breakdown.get("activity", {})
            if activity_score.get("score", 100) < 50 and time_context != "night":
                recommendations.append({
                    "id": "increase_activity",
                    "category": "activity",
                    "title": "Increase Daily Movement",
                    "description": "Your activity level is low today. Even small movements help - try taking stairs, short walks, or desk stretches.",
                    "priority": RecommendationPriority.LOW.value,
                    "icon": "Activity",
                    "action_type": "short_term",
                    "metrics": {"activity_score": activity_score.get("score")}
                })
        
        # Rule 9: Time-based contextual recommendations
        if time_context == "evening" and hr > 80:
            recommendations.append({
                "id": "evening_wind_down",
                "category": "sleep_prep",
                "title": "Wind Down for Better Sleep",
                "description": f"It's evening and your heart rate is still elevated ({hr} bpm). Consider calming activities to prepare for restful sleep.",
                "priority": RecommendationPriority.LOW.value,
                "icon": "Moon",
                "action_type": "short_term",
                "metrics": {"heart_rate": hr, "time_context": time_context}
            })
        
        if time_context == "night" and activity > 30:
            recommendations.append({
                "id": "night_activity",
                "category": "sleep",
                "title": "Time to Rest",
                "description": "It's late and you're still active. Quality sleep is crucial for recovery. Consider winding down soon.",
                "priority": RecommendationPriority.MEDIUM.value,
                "icon": "Moon",
                "action_type": "immediate",
                "metrics": {"activity_level": activity, "time_context": time_context}
            })
        
        # Rule 10: Positive reinforcement when things are good
        if not recommendations and wellness_breakdown:
            overall_score = sum(
                comp.get("score", 0) for comp in wellness_breakdown.values() 
                if isinstance(comp, dict) and "score" in comp
            ) / max(len([c for c in wellness_breakdown.values() if isinstance(c, dict) and "score" in c]), 1)
            
            if overall_score > 75:
                recommendations.append({
                    "id": "positive_reinforcement",
                    "category": "motivation",
                    "title": "Keep It Up!",
                    "description": "Your health metrics are looking great! Maintain your current healthy habits.",
                    "priority": RecommendationPriority.LOW.value,
                    "icon": "ThumbsUp",
                    "action_type": "lifestyle",
                    "metrics": {"overall_score": round(overall_score)}
                })
        
        # Sort by priority
        recommendations.sort(key=lambda x: x["priority"])
        
        return recommendations


async def get_recommendations(
    vitals: Dict[str, Any],
    alerts: List[Dict],
    wellness_breakdown: Dict[str, Any],
    baseline: Optional[Dict] = None,
    limit: int = 5
) -> Dict[str, Any]:
    """
    Get health recommendations based on current state.
    
    Returns:
        Dict with recommendations list and summary
    """
    all_recs = RecommendationEngine.generate_recommendations(
        vitals=vitals,
        alerts=alerts,
        wellness_breakdown=wellness_breakdown,
        baseline=baseline
    )
    
    # Limit results
    recs = all_recs[:limit]
    
    # Categorize
    categories = {}
    for rec in all_recs:
        cat = rec["category"]
        if cat not in categories:
            categories[cat] = 0
        categories[cat] += 1
    
    return {
        "recommendations": recs,
        "total_generated": len(all_recs),
        "categories": categories,
        "time_context": RecommendationEngine.get_time_context(),
        "generated_at": datetime.utcnow().isoformat()
    }

