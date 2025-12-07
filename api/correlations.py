"""
Telara Correlation Engine
Discovers patterns and correlations between health metrics.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import math

from database import get_db, VitalsRepository


@dataclass
class CorrelationResult:
    """Result of a correlation analysis."""
    metric1: str
    metric2: str
    correlation: float
    strength: str  # weak, moderate, strong
    direction: str  # positive, negative
    data_points: int
    insight: str
    lagged: bool = False
    lag_hours: int = 0


class CorrelationEngine:
    """
    Engine for discovering correlations between health metrics.
    Supports immediate correlations and lagged correlations (e.g., sleep vs next-day HRV).
    """
    
    # Pre-defined interesting correlation pairs
    CORRELATION_PAIRS = [
        ("heart_rate", "hrv_ms"),
        ("heart_rate", "activity_level"),
        ("hrv_ms", "activity_level"),
        ("spo2_percent", "heart_rate"),
        ("skin_temp_c", "heart_rate"),
        ("skin_temp_c", "hrv_ms"),
        ("activity_level", "spo2_percent"),
    ]
    
    # Lagged correlations (metric1 from period1 vs metric2 from period2)
    LAGGED_PAIRS = [
        ("sleep_hours", "hrv_ms", 8),  # Sleep vs next-day HRV (8 hour lag)
        ("activity_level", "hrv_ms", 12),  # Activity vs later HRV
        ("heart_rate", "sleep_hours", 16),  # Evening HR vs sleep quality
    ]
    
    METRIC_LABELS = {
        "heart_rate": "Heart Rate",
        "hrv_ms": "HRV",
        "spo2_percent": "Blood Oxygen",
        "skin_temp_c": "Temperature",
        "activity_level": "Activity Level",
        "sleep_hours": "Sleep Duration",
        "respiratory_rate": "Respiratory Rate",
    }
    
    @staticmethod
    def _calculate_pearson(values1: List[float], values2: List[float]) -> float:
        """Calculate Pearson correlation coefficient."""
        if len(values1) != len(values2) or len(values1) < 3:
            return 0.0
        
        n = len(values1)
        mean1 = sum(values1) / n
        mean2 = sum(values2) / n
        
        numerator = sum((v1 - mean1) * (v2 - mean2) for v1, v2 in zip(values1, values2))
        denom1 = math.sqrt(sum((v - mean1) ** 2 for v in values1))
        denom2 = math.sqrt(sum((v - mean2) ** 2 for v in values2))
        
        if denom1 == 0 or denom2 == 0:
            return 0.0
        
        return numerator / (denom1 * denom2)
    
    @staticmethod
    def _get_strength(correlation: float) -> str:
        """Categorize correlation strength."""
        abs_corr = abs(correlation)
        if abs_corr >= 0.7:
            return "strong"
        elif abs_corr >= 0.4:
            return "moderate"
        elif abs_corr >= 0.2:
            return "weak"
        return "negligible"
    
    @staticmethod
    def _generate_insight(
        metric1: str,
        metric2: str,
        correlation: float,
        strength: str,
        lagged: bool = False,
        lag_hours: int = 0
    ) -> str:
        """Generate natural language insight for a correlation."""
        label1 = CorrelationEngine.METRIC_LABELS.get(metric1, metric1)
        label2 = CorrelationEngine.METRIC_LABELS.get(metric2, metric2)
        
        direction = "increases" if correlation > 0 else "decreases"
        inverse_dir = "decreases" if correlation > 0 else "increases"
        
        if strength == "negligible":
            return f"No significant relationship found between {label1} and {label2}."
        
        if lagged:
            time_phrase = f"{lag_hours} hours later"
            if strength == "strong":
                return f"Strong pattern: When your {label1} is higher, your {label2} tends to be {'higher' if correlation > 0 else 'lower'} {time_phrase}."
            elif strength == "moderate":
                return f"Notable pattern: {label1} appears to influence your {label2} {time_phrase}."
            else:
                return f"Slight trend: {label1} may have a small effect on {label2} {time_phrase}."
        else:
            if strength == "strong":
                return f"Strong correlation: As your {label1} {direction}, your {label2} tends to {'increase' if correlation > 0 else 'decrease'} significantly."
            elif strength == "moderate":
                return f"Moderate correlation: Higher {label1} is associated with {'higher' if correlation > 0 else 'lower'} {label2}."
            else:
                return f"Weak correlation detected between {label1} and {label2}."
    
    @classmethod
    async def calculate_correlation(
        cls,
        metric1: str,
        metric2: str,
        hours: int = 24,
        user_id: str = "user_001"
    ) -> CorrelationResult:
        """Calculate correlation between two metrics."""
        async with get_db() as db:
            valid_metrics = ["heart_rate", "hrv_ms", "spo2_percent", "skin_temp_c", 
                           "activity_level", "respiratory_rate", "sleep_hours"]
            
            if metric1 not in valid_metrics or metric2 not in valid_metrics:
                return CorrelationResult(
                    metric1=metric1,
                    metric2=metric2,
                    correlation=0,
                    strength="error",
                    direction="none",
                    data_points=0,
                    insight=f"Invalid metric specified"
                )
            
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            
            # Map sleep_hours to the correct column name
            col1 = "sleep_hours" if metric1 == "sleep_hours" else metric1
            col2 = "sleep_hours" if metric2 == "sleep_hours" else metric2
            
            cursor = await db.execute(f"""
                SELECT {col1}, {col2}
                FROM vitals 
                WHERE user_id = ? AND timestamp > ?
                AND {col1} IS NOT NULL AND {col2} IS NOT NULL
            """, (user_id, cutoff.isoformat()))
            rows = await cursor.fetchall()
            
            if len(rows) < 10:
                return CorrelationResult(
                    metric1=metric1,
                    metric2=metric2,
                    correlation=0,
                    strength="insufficient_data",
                    direction="none",
                    data_points=len(rows),
                    insight="Not enough data to calculate correlation. Need at least 10 data points."
                )
            
            values1 = [row[0] for row in rows]
            values2 = [row[1] for row in rows]
            
            correlation = cls._calculate_pearson(values1, values2)
            strength = cls._get_strength(correlation)
            direction = "positive" if correlation > 0 else "negative"
            insight = cls._generate_insight(metric1, metric2, correlation, strength)
            
            return CorrelationResult(
                metric1=metric1,
                metric2=metric2,
                correlation=round(correlation, 3),
                strength=strength,
                direction=direction,
                data_points=len(rows),
                insight=insight
            )
    
    @classmethod
    async def calculate_lagged_correlation(
        cls,
        metric1: str,
        metric2: str,
        lag_hours: int,
        analysis_hours: int = 168,  # 7 days
        user_id: str = "user_001"
    ) -> CorrelationResult:
        """
        Calculate lagged correlation (e.g., sleep tonight vs HRV tomorrow).
        """
        async with get_db() as db:
            cutoff = datetime.utcnow() - timedelta(hours=analysis_hours)
            lag_delta = timedelta(hours=lag_hours)
            
            # Get all vitals in the analysis period
            cursor = await db.execute("""
                SELECT timestamp, heart_rate, hrv_ms, spo2_percent, skin_temp_c, 
                       activity_level, sleep_hours
                FROM vitals 
                WHERE user_id = ? AND timestamp > ?
                ORDER BY timestamp ASC
            """, (user_id, cutoff.isoformat()))
            rows = await cursor.fetchall()
            
            if len(rows) < 20:
                return CorrelationResult(
                    metric1=metric1,
                    metric2=metric2,
                    correlation=0,
                    strength="insufficient_data",
                    direction="none",
                    data_points=len(rows),
                    insight="Not enough data for lagged correlation analysis.",
                    lagged=True,
                    lag_hours=lag_hours
                )
            
            # Build time-indexed data
            metric_map = {
                "heart_rate": 1, "hrv_ms": 2, "spo2_percent": 3,
                "skin_temp_c": 4, "activity_level": 5, "sleep_hours": 6
            }
            
            idx1 = metric_map.get(metric1, 1)
            idx2 = metric_map.get(metric2, 2)
            
            # Pair values with lag
            paired_values1 = []
            paired_values2 = []
            
            for i, row1 in enumerate(rows):
                ts1 = datetime.fromisoformat(row1[0]) if isinstance(row1[0], str) else row1[0]
                target_ts = ts1 + lag_delta
                
                # Find closest row to target timestamp
                best_match = None
                min_diff = timedelta(hours=2)  # Allow 2 hour window
                
                for row2 in rows[i+1:]:
                    ts2 = datetime.fromisoformat(row2[0]) if isinstance(row2[0], str) else row2[0]
                    diff = abs(ts2 - target_ts)
                    if diff < min_diff:
                        min_diff = diff
                        best_match = row2
                
                if best_match and row1[idx1] is not None and best_match[idx2] is not None:
                    paired_values1.append(row1[idx1])
                    paired_values2.append(best_match[idx2])
            
            if len(paired_values1) < 5:
                return CorrelationResult(
                    metric1=metric1,
                    metric2=metric2,
                    correlation=0,
                    strength="insufficient_data",
                    direction="none",
                    data_points=len(paired_values1),
                    insight="Not enough paired data points for lagged analysis.",
                    lagged=True,
                    lag_hours=lag_hours
                )
            
            correlation = cls._calculate_pearson(paired_values1, paired_values2)
            strength = cls._get_strength(correlation)
            direction = "positive" if correlation > 0 else "negative"
            insight = cls._generate_insight(metric1, metric2, correlation, strength, True, lag_hours)
            
            return CorrelationResult(
                metric1=metric1,
                metric2=metric2,
                correlation=round(correlation, 3),
                strength=strength,
                direction=direction,
                data_points=len(paired_values1),
                insight=insight,
                lagged=True,
                lag_hours=lag_hours
            )
    
    @classmethod
    async def discover_all_correlations(
        cls,
        hours: int = 24,
        user_id: str = "user_001",
        include_lagged: bool = True
    ) -> Dict[str, Any]:
        """
        Discover all pre-defined correlations.
        Returns sorted by strength for easy consumption.
        """
        results = []
        
        # Calculate immediate correlations
        for metric1, metric2 in cls.CORRELATION_PAIRS:
            result = await cls.calculate_correlation(metric1, metric2, hours, user_id)
            if result.strength not in ["error", "insufficient_data"]:
                results.append(result)
        
        # Calculate lagged correlations
        if include_lagged:
            for metric1, metric2, lag in cls.LAGGED_PAIRS:
                result = await cls.calculate_lagged_correlation(
                    metric1, metric2, lag, hours * 7, user_id
                )
                if result.strength not in ["error", "insufficient_data"]:
                    results.append(result)
        
        # Sort by absolute correlation strength
        results.sort(key=lambda r: abs(r.correlation), reverse=True)
        
        # Generate summary insights
        strong_correlations = [r for r in results if r.strength == "strong"]
        moderate_correlations = [r for r in results if r.strength == "moderate"]
        
        top_insights = []
        for r in results[:3]:
            if r.strength in ["strong", "moderate"]:
                top_insights.append(r.insight)
        
        return {
            "correlations": [
                {
                    "metric1": r.metric1,
                    "metric2": r.metric2,
                    "correlation": r.correlation,
                    "strength": r.strength,
                    "direction": r.direction,
                    "data_points": r.data_points,
                    "insight": r.insight,
                    "lagged": r.lagged,
                    "lag_hours": r.lag_hours if r.lagged else None
                }
                for r in results
            ],
            "summary": {
                "total_analyzed": len(results),
                "strong_count": len(strong_correlations),
                "moderate_count": len(moderate_correlations),
                "top_insights": top_insights
            },
            "analysis_period_hours": hours,
            "calculated_at": datetime.utcnow().isoformat()
        }


async def get_correlation_insights(
    hours: int = 24,
    user_id: str = "user_001"
) -> Dict[str, Any]:
    """
    Get correlation insights for the API endpoint.
    """
    return await CorrelationEngine.discover_all_correlations(
        hours=hours,
        user_id=user_id,
        include_lagged=True
    )

