"""
Telara Wellness Score Calculator
Computes a holistic wellness score from vitals and alerts.
"""

from typing import List, Dict, Tuple, Optional
from datetime import datetime


async def calculate_wellness_score(
    vitals: List[Dict],
    alerts: List[Dict],
    baseline: Optional[Dict] = None
) -> Tuple[int, Dict]:
    """
    Calculate overall wellness score (0-100) with component breakdown.
    
    Components:
    - Heart Health (25%): Based on HRV and resting HR
    - Recovery (20%): Sleep quality + HRV trends
    - Activity (20%): Activity level and steps
    - Vitals Stability (20%): Deviation from baseline
    - Alert Status (15%): Penalty for active alerts
    """
    breakdown = {}
    
    # Handle empty data
    if not vitals:
        return 50, {
            "heart_health": {"score": 50, "status": "no_data"},
            "recovery": {"score": 50, "status": "no_data"},
            "activity": {"score": 50, "status": "no_data"},
            "stability": {"score": 50, "status": "no_data"},
            "alert_status": {"score": 100, "status": "no_alerts"},
            "message": "Insufficient data for accurate scoring"
        }
    
    # 1. Heart Health Score (25%)
    heart_score = calculate_heart_health(vitals, baseline)
    breakdown["heart_health"] = heart_score
    
    # 2. Recovery Score (20%)
    recovery_score = calculate_recovery(vitals)
    breakdown["recovery"] = recovery_score
    
    # 3. Activity Score (20%)
    activity_score = calculate_activity(vitals)
    breakdown["activity"] = activity_score
    
    # 4. Vitals Stability Score (20%)
    stability_score = calculate_stability(vitals, baseline)
    breakdown["stability"] = stability_score
    
    # 5. Alert Status Score (15%)
    alert_score = calculate_alert_score(alerts)
    breakdown["alert_status"] = alert_score
    
    # Calculate weighted total
    weighted_score = (
        heart_score["score"] * 0.25 +
        recovery_score["score"] * 0.20 +
        activity_score["score"] * 0.20 +
        stability_score["score"] * 0.20 +
        alert_score["score"] * 0.15
    )
    
    return int(weighted_score), breakdown


def calculate_heart_health(vitals: List[Dict], baseline: Optional[Dict] = None) -> Dict:
    """Calculate heart health score based on HR and HRV."""
    if not vitals:
        return {"score": 50, "status": "no_data"}
    
    # Get average values
    hr_values = [v["heart_rate"] for v in vitals if v.get("heart_rate")]
    hrv_values = [v["hrv_ms"] for v in vitals if v.get("hrv_ms")]
    
    if not hr_values or not hrv_values:
        return {"score": 50, "status": "incomplete_data"}
    
    avg_hr = sum(hr_values) / len(hr_values)
    avg_hrv = sum(hrv_values) / len(hrv_values)
    
    # Score components
    # HR score: 60-80 is optimal
    if 60 <= avg_hr <= 80:
        hr_score = 100
    elif 55 <= avg_hr <= 90:
        hr_score = 80
    elif 50 <= avg_hr <= 100:
        hr_score = 60
    else:
        hr_score = 40
    
    # HRV score: higher is generally better (40-70 is good for adults)
    if avg_hrv >= 60:
        hrv_score = 100
    elif avg_hrv >= 45:
        hrv_score = 85
    elif avg_hrv >= 30:
        hrv_score = 65
    elif avg_hrv >= 20:
        hrv_score = 45
    else:
        hrv_score = 30
    
    combined = (hr_score * 0.4 + hrv_score * 0.6)  # HRV weighted more
    
    status = "excellent" if combined >= 85 else "good" if combined >= 70 else "fair" if combined >= 50 else "needs_attention"
    
    return {
        "score": int(combined),
        "status": status,
        "avg_heart_rate": round(avg_hr, 1),
        "avg_hrv": round(avg_hrv, 1),
        "hr_score": hr_score,
        "hrv_score": hrv_score
    }


def calculate_recovery(vitals: List[Dict]) -> Dict:
    """Calculate recovery score based on HRV and sleep."""
    if not vitals:
        return {"score": 50, "status": "no_data"}
    
    hrv_values = [v["hrv_ms"] for v in vitals if v.get("hrv_ms")]
    sleep_values = [v["sleep_hours"] for v in vitals if v.get("sleep_hours")]
    
    # HRV trend component
    hrv_score = 50
    if len(hrv_values) >= 5:
        avg_hrv = sum(hrv_values) / len(hrv_values)
        if avg_hrv >= 50:
            hrv_score = 90
        elif avg_hrv >= 40:
            hrv_score = 75
        elif avg_hrv >= 30:
            hrv_score = 55
        else:
            hrv_score = 35
    
    # Sleep component (if available)
    sleep_score = 70  # Default if no sleep data
    if sleep_values:
        avg_sleep = sum(sleep_values) / len(sleep_values)
        if 7 <= avg_sleep <= 9:
            sleep_score = 100
        elif 6 <= avg_sleep <= 10:
            sleep_score = 80
        elif 5 <= avg_sleep <= 11:
            sleep_score = 60
        else:
            sleep_score = 40
    
    combined = (hrv_score * 0.6 + sleep_score * 0.4)
    
    status = "excellent" if combined >= 85 else "good" if combined >= 70 else "fair" if combined >= 50 else "needs_attention"
    
    return {
        "score": int(combined),
        "status": status,
        "hrv_score": hrv_score,
        "sleep_score": sleep_score
    }


def calculate_activity(vitals: List[Dict]) -> Dict:
    """Calculate activity score based on activity level and steps."""
    if not vitals:
        return {"score": 50, "status": "no_data"}
    
    activity_values = [v["activity_level"] for v in vitals if v.get("activity_level") is not None]
    steps_values = [v["steps_per_minute"] for v in vitals if v.get("steps_per_minute") is not None]
    
    if not activity_values:
        return {"score": 50, "status": "incomplete_data"}
    
    avg_activity = sum(activity_values) / len(activity_values)
    avg_steps = sum(steps_values) / len(steps_values) if steps_values else 0
    
    # Activity level score (0-100 scale input)
    if avg_activity >= 50:
        activity_score = 95
    elif avg_activity >= 35:
        activity_score = 80
    elif avg_activity >= 20:
        activity_score = 65
    elif avg_activity >= 10:
        activity_score = 50
    else:
        activity_score = 35
    
    # Steps score
    if avg_steps >= 50:
        steps_score = 100
    elif avg_steps >= 30:
        steps_score = 85
    elif avg_steps >= 15:
        steps_score = 65
    elif avg_steps >= 5:
        steps_score = 45
    else:
        steps_score = 30
    
    combined = (activity_score * 0.6 + steps_score * 0.4)
    
    status = "active" if combined >= 80 else "moderate" if combined >= 60 else "sedentary" if combined >= 40 else "very_sedentary"
    
    return {
        "score": int(combined),
        "status": status,
        "avg_activity_level": round(avg_activity, 1),
        "avg_steps_per_minute": round(avg_steps, 1)
    }


def calculate_stability(vitals: List[Dict], baseline: Optional[Dict] = None) -> Dict:
    """Calculate vitals stability score based on deviation from baseline."""
    if not vitals:
        return {"score": 50, "status": "no_data"}
    
    # If no baseline, use standard ranges
    if not baseline:
        baseline = {
            "avg_heart_rate": 72,
            "avg_hrv": 50,
            "avg_spo2": 98,
            "avg_temp": 36.5
        }
    
    deviations = []
    
    # Check HR deviation
    hr_values = [v["heart_rate"] for v in vitals if v.get("heart_rate")]
    if hr_values and baseline.get("avg_heart_rate"):
        avg_hr = sum(hr_values) / len(hr_values)
        hr_dev = abs(avg_hr - baseline["avg_heart_rate"]) / baseline["avg_heart_rate"]
        deviations.append(hr_dev)
    
    # Check HRV deviation
    hrv_values = [v["hrv_ms"] for v in vitals if v.get("hrv_ms")]
    if hrv_values and baseline.get("avg_hrv"):
        avg_hrv = sum(hrv_values) / len(hrv_values)
        hrv_dev = abs(avg_hrv - baseline["avg_hrv"]) / baseline["avg_hrv"]
        deviations.append(hrv_dev)
    
    # Check SpO2 deviation
    spo2_values = [v["spo2_percent"] for v in vitals if v.get("spo2_percent")]
    if spo2_values and baseline.get("avg_spo2"):
        avg_spo2 = sum(spo2_values) / len(spo2_values)
        spo2_dev = abs(avg_spo2 - baseline["avg_spo2"]) / baseline["avg_spo2"]
        deviations.append(spo2_dev * 2)  # SpO2 deviations are more significant
    
    # Check temperature deviation
    temp_values = [v["skin_temp_c"] for v in vitals if v.get("skin_temp_c")]
    if temp_values and baseline.get("avg_temp"):
        avg_temp = sum(temp_values) / len(temp_values)
        temp_dev = abs(avg_temp - baseline["avg_temp"]) / baseline["avg_temp"]
        deviations.append(temp_dev * 3)  # Temperature deviations are very significant
    
    if not deviations:
        return {"score": 50, "status": "no_baseline"}
    
    avg_deviation = sum(deviations) / len(deviations)
    
    # Convert deviation to score (lower deviation = higher score)
    if avg_deviation <= 0.05:
        score = 100
        status = "very_stable"
    elif avg_deviation <= 0.10:
        score = 85
        status = "stable"
    elif avg_deviation <= 0.20:
        score = 70
        status = "slight_variance"
    elif avg_deviation <= 0.35:
        score = 50
        status = "moderate_variance"
    else:
        score = 30
        status = "high_variance"
    
    return {
        "score": score,
        "status": status,
        "avg_deviation_percent": round(avg_deviation * 100, 1)
    }


def calculate_alert_score(alerts: List[Dict]) -> Dict:
    """Calculate score penalty based on active alerts."""
    if not alerts:
        return {"score": 100, "status": "no_alerts", "active_alerts": 0}
    
    # Count alerts by severity
    critical = len([a for a in alerts if a.get("severity") == "CRITICAL"])
    high = len([a for a in alerts if a.get("severity") == "HIGH"])
    medium = len([a for a in alerts if a.get("severity") == "MEDIUM"])
    low = len([a for a in alerts if a.get("severity") == "LOW"])
    
    # Calculate penalty
    penalty = (critical * 25) + (high * 15) + (medium * 8) + (low * 3)
    score = max(0, 100 - penalty)
    
    if critical > 0:
        status = "critical_alerts"
    elif high > 0:
        status = "high_alerts"
    elif medium > 0:
        status = "moderate_alerts"
    elif low > 0:
        status = "minor_alerts"
    else:
        status = "no_alerts"
    
    return {
        "score": score,
        "status": status,
        "active_alerts": len(alerts),
        "by_severity": {
            "critical": critical,
            "high": high,
            "medium": medium,
            "low": low
        }
    }


def get_wellness_breakdown(breakdown: Dict) -> str:
    """Generate human-readable wellness breakdown."""
    parts = []
    
    if breakdown.get("heart_health"):
        hh = breakdown["heart_health"]
        parts.append(f"Heart Health: {hh['score']}/100 ({hh['status']})")
    
    if breakdown.get("recovery"):
        rec = breakdown["recovery"]
        parts.append(f"Recovery: {rec['score']}/100 ({rec['status']})")
    
    if breakdown.get("activity"):
        act = breakdown["activity"]
        parts.append(f"Activity: {act['score']}/100 ({act['status']})")
    
    if breakdown.get("stability"):
        stab = breakdown["stability"]
        parts.append(f"Stability: {stab['score']}/100 ({stab['status']})")
    
    if breakdown.get("alert_status"):
        alert = breakdown["alert_status"]
        parts.append(f"Alert Status: {alert['score']}/100 ({alert['status']})")
    
    return "\n".join(parts)


def get_wellness_recommendations(score: int, breakdown: Dict) -> List[str]:
    """Generate actionable recommendations based on wellness breakdown."""
    recommendations = []
    
    # Heart health recommendations
    if breakdown.get("heart_health", {}).get("score", 100) < 70:
        hrv = breakdown["heart_health"].get("avg_hrv", 0)
        if hrv < 40:
            recommendations.append("Your HRV is below optimal. Consider stress-reduction techniques like deep breathing or meditation.")
        hr = breakdown["heart_health"].get("avg_heart_rate", 0)
        if hr > 85:
            recommendations.append("Your resting heart rate is elevated. Ensure you're well-hydrated and consider reducing caffeine intake.")
    
    # Recovery recommendations
    if breakdown.get("recovery", {}).get("score", 100) < 70:
        recommendations.append("Your recovery score is low. Prioritize sleep quality and consider lighter exercise today.")
    
    # Activity recommendations
    if breakdown.get("activity", {}).get("score", 100) < 60:
        recommendations.append("Your activity level is low. Try to incorporate short walks or stretching breaks.")
    
    # Stability recommendations
    if breakdown.get("stability", {}).get("score", 100) < 60:
        recommendations.append("Your vitals are showing unusual variance. Monitor for any symptoms and maintain regular routines.")
    
    # Alert-based recommendations
    alert_status = breakdown.get("alert_status", {})
    if alert_status.get("by_severity", {}).get("critical", 0) > 0:
        recommendations.insert(0, "⚠️ CRITICAL: You have critical health alerts. Consider consulting a healthcare provider.")
    
    if not recommendations:
        recommendations.append("Great job! Your wellness metrics are looking healthy. Keep up your current habits.")
    
    return recommendations

