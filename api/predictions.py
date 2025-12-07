"""
Telara Predictive Alerts
Predicts future health states using trend analysis and linear regression.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import math

from database import VitalsRepository, BaselinesRepository


@dataclass
class Prediction:
    """A health prediction."""
    metric: str
    label: str
    prediction_type: str  # threshold_crossing, fatigue, stress, trend
    severity: str  # low, moderate, high
    predicted_time: str
    hours_until: float
    current_value: float
    predicted_value: float
    threshold: Optional[float]
    confidence: float  # 0-1
    message: str
    recommendation: str


class PredictionEngine:
    """
    Engine for predicting future health states using simple linear regression
    and pattern recognition.
    """
    
    # Thresholds for predictions
    THRESHOLDS = {
        "heart_rate": {"high": 100, "very_high": 120, "low": 50},
        "hrv_ms": {"low": 30, "very_low": 20},
        "spo2_percent": {"low": 95, "very_low": 92},
        "skin_temp_c": {"high": 37.5, "very_high": 38.5},
    }
    
    # Metric labels
    METRIC_LABELS = {
        "heart_rate": "Heart Rate",
        "hrv_ms": "HRV",
        "spo2_percent": "Blood Oxygen",
        "skin_temp_c": "Temperature",
        "activity_level": "Activity Level",
    }
    
    @staticmethod
    def linear_regression(
        x_values: List[float],
        y_values: List[float]
    ) -> Tuple[float, float, float]:
        """
        Simple linear regression.
        Returns: (slope, intercept, r_squared)
        """
        n = len(x_values)
        if n < 2:
            return 0, 0, 0
        
        sum_x = sum(x_values)
        sum_y = sum(y_values)
        sum_xy = sum(x * y for x, y in zip(x_values, y_values))
        sum_x2 = sum(x * x for x in x_values)
        sum_y2 = sum(y * y for y in y_values)
        
        denominator = n * sum_x2 - sum_x * sum_x
        if denominator == 0:
            return 0, sum_y / n if n > 0 else 0, 0
        
        slope = (n * sum_xy - sum_x * sum_y) / denominator
        intercept = (sum_y - slope * sum_x) / n
        
        # Calculate R-squared
        y_mean = sum_y / n
        ss_tot = sum((y - y_mean) ** 2 for y in y_values)
        ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(x_values, y_values))
        
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        return slope, intercept, max(0, r_squared)
    
    @classmethod
    def predict_metric_value(
        cls,
        timestamps: List[datetime],
        values: List[float],
        hours_ahead: float
    ) -> Tuple[float, float, float]:
        """
        Predict a metric value N hours in the future.
        Returns: (predicted_value, slope_per_hour, confidence)
        """
        if len(values) < 5:
            return values[-1] if values else 0, 0, 0
        
        # Convert timestamps to hours from start
        base_time = timestamps[0]
        x_values = [(ts - base_time).total_seconds() / 3600 for ts in timestamps]
        
        slope, intercept, r_squared = cls.linear_regression(x_values, values)
        
        # Predict future value
        future_x = x_values[-1] + hours_ahead
        predicted = slope * future_x + intercept
        
        # Calculate confidence based on R-squared and data recency
        data_span_hours = (timestamps[-1] - timestamps[0]).total_seconds() / 3600
        recency_factor = min(1.0, data_span_hours / 2)  # More data = more confidence
        
        confidence = r_squared * recency_factor * 0.8  # Cap at 80%
        
        return predicted, slope, confidence
    
    @classmethod
    async def predict_threshold_crossing(
        cls,
        metric: str,
        vitals: List[Dict],
        max_hours: float = 6
    ) -> Optional[Prediction]:
        """
        Predict when a metric will cross a threshold.
        """
        if not vitals or metric not in cls.THRESHOLDS:
            return None
        
        # Extract values and timestamps
        data_points = [
            (datetime.fromisoformat(v["timestamp"]) if isinstance(v["timestamp"], str) else v["timestamp"], 
             v.get(metric))
            for v in vitals
            if v.get(metric) is not None
        ]
        
        if len(data_points) < 5:
            return None
        
        data_points.sort(key=lambda x: x[0])
        timestamps = [dp[0] for dp in data_points]
        values = [dp[1] for dp in data_points]
        
        current_value = values[-1]
        
        # Get trend
        predicted, slope, confidence = cls.predict_metric_value(
            timestamps, values, hours_ahead=1
        )
        
        if confidence < 0.3:
            return None  # Not enough confidence
        
        thresholds = cls.THRESHOLDS[metric]
        
        # Check which threshold might be crossed
        for threshold_name, threshold_value in thresholds.items():
            is_high_threshold = "high" in threshold_name
            
            if is_high_threshold:
                # Check if we're heading toward this threshold
                if slope > 0 and current_value < threshold_value:
                    # Calculate time to threshold
                    if slope > 0:
                        hours_to_threshold = (threshold_value - current_value) / (slope * 1)
                        
                        if 0 < hours_to_threshold <= max_hours:
                            predicted_time = datetime.utcnow() + timedelta(hours=hours_to_threshold)
                            
                            severity = "high" if "very" in threshold_name else "moderate"
                            
                            return Prediction(
                                metric=metric,
                                label=cls.METRIC_LABELS.get(metric, metric),
                                prediction_type="threshold_crossing",
                                severity=severity,
                                predicted_time=predicted_time.isoformat(),
                                hours_until=round(hours_to_threshold, 1),
                                current_value=current_value,
                                predicted_value=threshold_value,
                                threshold=threshold_value,
                                confidence=round(confidence, 2),
                                message=f"Your {cls.METRIC_LABELS.get(metric, metric)} may exceed {threshold_value} in approximately {round(hours_to_threshold, 1)} hours",
                                recommendation=cls._get_threshold_recommendation(metric, threshold_name)
                            )
            else:
                # Low threshold - check if we're heading down
                if slope < 0 and current_value > threshold_value:
                    hours_to_threshold = (current_value - threshold_value) / abs(slope)
                    
                    if 0 < hours_to_threshold <= max_hours:
                        predicted_time = datetime.utcnow() + timedelta(hours=hours_to_threshold)
                        
                        severity = "high" if "very" in threshold_name else "moderate"
                        
                        return Prediction(
                            metric=metric,
                            label=cls.METRIC_LABELS.get(metric, metric),
                            prediction_type="threshold_crossing",
                            severity=severity,
                            predicted_time=predicted_time.isoformat(),
                            hours_until=round(hours_to_threshold, 1),
                            current_value=current_value,
                            predicted_value=threshold_value,
                            threshold=threshold_value,
                            confidence=round(confidence, 2),
                            message=f"Your {cls.METRIC_LABELS.get(metric, metric)} may drop below {threshold_value} in approximately {round(hours_to_threshold, 1)} hours",
                            recommendation=cls._get_threshold_recommendation(metric, threshold_name)
                        )
        
        return None
    
    @staticmethod
    def _get_threshold_recommendation(metric: str, threshold_type: str) -> str:
        """Get recommendation for a threshold crossing."""
        recommendations = {
            ("heart_rate", "high"): "Consider reducing activity and practicing calm breathing.",
            ("heart_rate", "very_high"): "Take a break, hydrate, and monitor your stress levels.",
            ("heart_rate", "low"): "This is usually healthy at rest, but monitor for dizziness.",
            ("hrv_ms", "low"): "Your recovery may be declining. Prioritize rest and sleep.",
            ("hrv_ms", "very_low"): "Your body needs recovery. Avoid strenuous activity today.",
            ("spo2_percent", "low"): "Take deep breaths and ensure good ventilation.",
            ("spo2_percent", "very_low"): "Seek fresh air. If persistent, consult a healthcare provider.",
            ("skin_temp_c", "high"): "Monitor for other symptoms. Stay hydrated and rest.",
            ("skin_temp_c", "very_high"): "You may be developing a fever. Rest and monitor closely.",
        }
        return recommendations.get((metric, threshold_type), "Monitor this trend and adjust your activities accordingly.")
    
    @classmethod
    async def predict_fatigue(
        cls,
        vitals: List[Dict],
        baseline: Optional[Dict]
    ) -> Optional[Prediction]:
        """
        Predict fatigue based on HRV decline and activity patterns.
        """
        if not vitals or len(vitals) < 10:
            return None
        
        # Get HRV trend
        hrv_data = [
            (datetime.fromisoformat(v["timestamp"]) if isinstance(v["timestamp"], str) else v["timestamp"],
             v.get("hrv_ms"))
            for v in vitals
            if v.get("hrv_ms") is not None
        ]
        
        if len(hrv_data) < 5:
            return None
        
        hrv_data.sort(key=lambda x: x[0])
        timestamps = [dp[0] for dp in hrv_data]
        hrv_values = [dp[1] for dp in hrv_data]
        
        # Calculate HRV trend
        predicted_hrv, hrv_slope, confidence = cls.predict_metric_value(
            timestamps, hrv_values, hours_ahead=2
        )
        
        current_hrv = hrv_values[-1]
        baseline_hrv = baseline.get("avg_hrv", 50) if baseline else 50
        
        # Fatigue indicators: declining HRV below personal baseline
        if hrv_slope < -1 and current_hrv < baseline_hrv * 0.85:
            # Calculate when HRV might hit critical low
            hours_to_low_hrv = abs((current_hrv - 30) / hrv_slope) if hrv_slope < 0 else 4
            hours_to_low_hrv = min(hours_to_low_hrv, 6)
            
            predicted_time = datetime.utcnow() + timedelta(hours=hours_to_low_hrv)
            
            # Determine time of day message
            predicted_hour = predicted_time.hour
            if 12 <= predicted_hour < 14:
                time_msg = "around lunchtime"
            elif 14 <= predicted_hour < 17:
                time_msg = f"around {predicted_hour - 12}pm"
            elif predicted_hour >= 17:
                time_msg = "this evening"
            else:
                time_msg = f"around {predicted_hour}am"
            
            return Prediction(
                metric="fatigue",
                label="Energy Level",
                prediction_type="fatigue",
                severity="moderate",
                predicted_time=predicted_time.isoformat(),
                hours_until=round(hours_to_low_hrv, 1),
                current_value=current_hrv,
                predicted_value=predicted_hrv,
                threshold=30,
                confidence=round(confidence * 0.8, 2),
                message=f"Based on your current HRV trajectory, you may experience fatigue {time_msg}",
                recommendation="Consider a short break, light stretching, or a brief walk to boost energy."
            )
        
        return None
    
    @classmethod
    async def predict_stress(
        cls,
        vitals: List[Dict],
        baseline: Optional[Dict]
    ) -> Optional[Prediction]:
        """
        Predict stress based on HR elevation and HRV compression.
        """
        if not vitals or len(vitals) < 10:
            return None
        
        # Get recent HR and HRV data
        recent = vitals[:min(20, len(vitals))]
        
        hr_values = [v["heart_rate"] for v in recent if v.get("heart_rate")]
        hrv_values = [v["hrv_ms"] for v in recent if v.get("hrv_ms")]
        activity_values = [v["activity_level"] for v in recent if v.get("activity_level") is not None]
        
        if not hr_values or not hrv_values:
            return None
        
        avg_hr = sum(hr_values) / len(hr_values)
        avg_hrv = sum(hrv_values) / len(hrv_values)
        avg_activity = sum(activity_values) / len(activity_values) if activity_values else 20
        
        baseline_hr = baseline.get("avg_heart_rate", 72) if baseline else 72
        baseline_hrv = baseline.get("avg_hrv", 50) if baseline else 50
        
        # Stress indicators: elevated HR + low HRV + low activity (not exercising)
        hr_elevated = avg_hr > baseline_hr * 1.15
        hrv_compressed = avg_hrv < baseline_hrv * 0.75
        low_activity = avg_activity < 30
        
        if hr_elevated and hrv_compressed and low_activity:
            confidence = 0.6 + (0.1 if hr_elevated else 0) + (0.1 if hrv_compressed else 0)
            
            return Prediction(
                metric="stress",
                label="Stress Level",
                prediction_type="stress",
                severity="moderate" if avg_hr < baseline_hr * 1.25 else "high",
                predicted_time=(datetime.utcnow() + timedelta(hours=1)).isoformat(),
                hours_until=1,
                current_value=avg_hr,
                predicted_value=avg_hr * 1.05,
                threshold=None,
                confidence=round(confidence, 2),
                message=f"Your vitals suggest elevated stress: HR {round(avg_hr)} bpm (elevated) with compressed HRV ({round(avg_hrv)} ms)",
                recommendation="Try a 5-minute breathing exercise or step away from stressors. Consider a short walk."
            )
        
        return None
    
    @classmethod
    async def generate_all_predictions(
        cls,
        user_id: str = "user_001",
        max_hours: float = 6
    ) -> Dict[str, Any]:
        """
        Generate all available predictions for a user.
        """
        # Get recent vitals (2 hours for trend analysis)
        vitals = await VitalsRepository.get_recent(minutes=120, user_id=user_id)
        baseline = await BaselinesRepository.get(user_id)
        
        if not vitals:
            return {
                "predictions": [],
                "data_available": False,
                "message": "Not enough data for predictions"
            }
        
        predictions = []
        
        # Threshold crossing predictions
        for metric in ["heart_rate", "hrv_ms", "spo2_percent", "skin_temp_c"]:
            pred = await cls.predict_threshold_crossing(metric, vitals, max_hours)
            if pred:
                predictions.append(pred)
        
        # Fatigue prediction
        fatigue_pred = await cls.predict_fatigue(vitals, baseline)
        if fatigue_pred:
            predictions.append(fatigue_pred)
        
        # Stress prediction
        stress_pred = await cls.predict_stress(vitals, baseline)
        if stress_pred:
            predictions.append(stress_pred)
        
        # Sort by severity and time
        severity_order = {"high": 0, "moderate": 1, "low": 2}
        predictions.sort(key=lambda p: (severity_order.get(p.severity, 2), p.hours_until))
        
        # Convert to dict for JSON serialization
        return {
            "predictions": [
                {
                    "metric": p.metric,
                    "label": p.label,
                    "prediction_type": p.prediction_type,
                    "severity": p.severity,
                    "predicted_time": p.predicted_time,
                    "hours_until": p.hours_until,
                    "current_value": p.current_value,
                    "predicted_value": p.predicted_value,
                    "threshold": p.threshold,
                    "confidence": p.confidence,
                    "message": p.message,
                    "recommendation": p.recommendation
                }
                for p in predictions
            ],
            "data_available": True,
            "data_points_analyzed": len(vitals),
            "prediction_horizon_hours": max_hours,
            "generated_at": datetime.utcnow().isoformat()
        }


async def get_predictions(
    user_id: str = "user_001",
    max_hours: float = 6
) -> Dict[str, Any]:
    """Get health predictions."""
    return await PredictionEngine.generate_all_predictions(user_id, max_hours)

