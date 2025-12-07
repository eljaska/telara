"""
Telara MCP Health Data Server
Exposes health data query tools for Claude agent via MCP protocol.
"""

import asyncio
import json
from datetime import datetime
from typing import Any
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Import database functions
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import (
    VitalsRepository,
    AlertsRepository,
    BaselinesRepository,
    get_anomaly_context,
    calculate_correlations,
    init_database
)
from wellness import calculate_wellness_score, get_wellness_breakdown

# Create MCP server
server = Server("telara-health-server")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available health data tools."""
    return [
        Tool(
            name="query_recent_vitals",
            description="Get the user's vital signs from the last N minutes. Returns heart rate, HRV, SpO2, temperature, activity level, and more.",
            inputSchema={
                "type": "object",
                "properties": {
                    "minutes": {
                        "type": "integer",
                        "description": "Number of minutes to look back (default: 30, max: 1440)",
                        "default": 30
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="query_alerts",
            description="Get health alerts/anomalies detected in the last N hours. Can filter by severity (CRITICAL, HIGH, MEDIUM, LOW).",
            inputSchema={
                "type": "object",
                "properties": {
                    "hours": {
                        "type": "integer",
                        "description": "Number of hours to look back (default: 24)",
                        "default": 24
                    },
                    "severity": {
                        "type": "string",
                        "description": "Filter by severity level (optional)",
                        "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_wellness_score",
            description="Calculate and return the current wellness score (0-100) with breakdown by component: heart health, recovery, activity, stability, and alert status.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_metric_trend",
            description="Get the trend data for a specific health metric over time. Useful for analyzing patterns.",
            inputSchema={
                "type": "object",
                "properties": {
                    "metric": {
                        "type": "string",
                        "description": "The metric to analyze",
                        "enum": ["heart_rate", "hrv_ms", "spo2_percent", "skin_temp_c", "activity_level"]
                    },
                    "hours": {
                        "type": "integer",
                        "description": "Number of hours to analyze (default: 24)",
                        "default": 24
                    }
                },
                "required": ["metric"]
            }
        ),
        Tool(
            name="get_correlations",
            description="Find statistical correlation between two health metrics. Returns correlation coefficient and interpretation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "metric1": {
                        "type": "string",
                        "description": "First metric",
                        "enum": ["heart_rate", "hrv_ms", "spo2_percent", "skin_temp_c", "activity_level"]
                    },
                    "metric2": {
                        "type": "string",
                        "description": "Second metric",
                        "enum": ["heart_rate", "hrv_ms", "spo2_percent", "skin_temp_c", "activity_level"]
                    },
                    "hours": {
                        "type": "integer",
                        "description": "Hours of data to analyze (default: 24)",
                        "default": 24
                    }
                },
                "required": ["metric1", "metric2"]
            }
        ),
        Tool(
            name="get_anomaly_context",
            description="Get detailed context around a specific alert/anomaly including surrounding vitals data.",
            inputSchema={
                "type": "object",
                "properties": {
                    "alert_id": {
                        "type": "string",
                        "description": "The ID of the alert to get context for"
                    }
                },
                "required": ["alert_id"]
            }
        ),
        Tool(
            name="compare_to_baseline",
            description="Compare current vital readings to the user's personal baseline averages. Shows how current values deviate from their normal.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_vital_statistics",
            description="Get statistical summary (min, max, average) of vital signs over a time period.",
            inputSchema={
                "type": "object",
                "properties": {
                    "hours": {
                        "type": "integer",
                        "description": "Hours to analyze (default: 24)",
                        "default": 24
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_alert_summary",
            description="Get a summary of alerts grouped by severity and type.",
            inputSchema={
                "type": "object",
                "properties": {
                    "hours": {
                        "type": "integer",
                        "description": "Hours to look back (default: 24)",
                        "default": 24
                    }
                },
                "required": []
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Execute a health data tool."""
    try:
        result = await execute_tool(name, arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def execute_tool(name: str, arguments: dict[str, Any]) -> dict:
    """Execute a specific tool and return results."""
    
    if name == "query_recent_vitals":
        minutes = min(arguments.get("minutes", 30), 1440)  # Max 24 hours
        vitals = await VitalsRepository.get_recent(minutes=minutes)
        
        if not vitals:
            return {"message": "No vital data found for the specified period", "count": 0}
        
        # Summarize the data for Claude
        latest = vitals[0] if vitals else {}
        return {
            "count": len(vitals),
            "period_minutes": minutes,
            "latest_reading": {
                "timestamp": latest.get("timestamp"),
                "heart_rate": latest.get("heart_rate"),
                "hrv_ms": latest.get("hrv_ms"),
                "spo2_percent": latest.get("spo2_percent"),
                "skin_temp_c": latest.get("skin_temp_c"),
                "activity_level": latest.get("activity_level"),
                "respiratory_rate": latest.get("respiratory_rate")
            },
            "summary": {
                "avg_heart_rate": round(sum(v["heart_rate"] for v in vitals if v.get("heart_rate")) / len(vitals), 1) if vitals else None,
                "avg_hrv": round(sum(v["hrv_ms"] for v in vitals if v.get("hrv_ms")) / len(vitals), 1) if vitals else None,
                "avg_spo2": round(sum(v["spo2_percent"] for v in vitals if v.get("spo2_percent")) / len(vitals), 1) if vitals else None,
            }
        }
    
    elif name == "query_alerts":
        hours = arguments.get("hours", 24)
        severity = arguments.get("severity")
        alerts = await AlertsRepository.get_recent(hours=hours, severity=severity)
        
        return {
            "count": len(alerts),
            "period_hours": hours,
            "severity_filter": severity,
            "alerts": [
                {
                    "alert_id": a.get("alert_id"),
                    "type": a.get("alert_type"),
                    "severity": a.get("severity"),
                    "description": a.get("description"),
                    "timestamp": a.get("timestamp"),
                    "ai_insight": a.get("ai_insight")
                }
                for a in alerts[:10]  # Limit to 10 most recent
            ]
        }
    
    elif name == "get_wellness_score":
        vitals = await VitalsRepository.get_recent(minutes=60)
        alerts = await AlertsRepository.get_recent(hours=24)
        baseline = await BaselinesRepository.get()
        
        score, breakdown = await calculate_wellness_score(vitals, alerts, baseline)
        
        return {
            "wellness_score": score,
            "breakdown": breakdown,
            "interpretation": get_score_interpretation(score),
            "calculated_at": datetime.utcnow().isoformat()
        }
    
    elif name == "get_metric_trend":
        metric = arguments.get("metric")
        hours = arguments.get("hours", 24)
        
        trend_data = await VitalsRepository.get_metric_trend(metric, hours)
        
        if not trend_data:
            return {"error": "No data available for this metric"}
        
        values = [d["value"] for d in trend_data if d.get("value") is not None]
        
        if len(values) < 2:
            return {"error": "Insufficient data points"}
        
        # Calculate trend direction
        first_half = values[:len(values)//2]
        second_half = values[len(values)//2:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        
        if avg_second > avg_first * 1.05:
            trend = "increasing"
        elif avg_second < avg_first * 0.95:
            trend = "decreasing"
        else:
            trend = "stable"
        
        return {
            "metric": metric,
            "period_hours": hours,
            "data_points": len(values),
            "current": values[-1] if values else None,
            "min": min(values),
            "max": max(values),
            "average": round(sum(values) / len(values), 2),
            "trend": trend,
            "percent_change": round(((avg_second - avg_first) / avg_first) * 100, 1) if avg_first else 0
        }
    
    elif name == "get_correlations":
        metric1 = arguments.get("metric1")
        metric2 = arguments.get("metric2")
        hours = arguments.get("hours", 24)
        
        result = await calculate_correlations(metric1, metric2, hours)
        return result
    
    elif name == "get_anomaly_context":
        alert_id = arguments.get("alert_id")
        context = await get_anomaly_context(alert_id)
        
        if not context:
            return {"error": "Alert not found"}
        
        return context
    
    elif name == "compare_to_baseline":
        latest = await VitalsRepository.get_latest()
        
        if not latest:
            return {"error": "No current vital data available"}
        
        comparison = await BaselinesRepository.compare_to_current("user_001", latest)
        
        if not comparison.get("has_baseline"):
            return {"message": "No baseline established yet. More data needed to establish personal norms."}
        
        return comparison
    
    elif name == "get_vital_statistics":
        hours = arguments.get("hours", 24)
        stats = await VitalsRepository.get_stats(hours)
        
        return {
            "period_hours": hours,
            "statistics": stats
        }
    
    elif name == "get_alert_summary":
        hours = arguments.get("hours", 24)
        counts = await AlertsRepository.get_count_by_severity(hours)
        alerts = await AlertsRepository.get_recent(hours)
        
        # Group by type
        type_counts = {}
        for alert in alerts:
            alert_type = alert.get("alert_type", "UNKNOWN")
            type_counts[alert_type] = type_counts.get(alert_type, 0) + 1
        
        return {
            "period_hours": hours,
            "total_alerts": sum(counts.values()),
            "by_severity": counts,
            "by_type": type_counts
        }
    
    else:
        return {"error": f"Unknown tool: {name}"}


def get_score_interpretation(score: int) -> str:
    """Get human-readable interpretation of wellness score."""
    if score >= 85:
        return "Excellent - Your vitals are well within healthy ranges and showing positive patterns."
    elif score >= 70:
        return "Good - Overall healthy with some minor areas that could be optimized."
    elif score >= 55:
        return "Fair - Some metrics are outside optimal ranges. Consider reviewing recent lifestyle factors."
    elif score >= 40:
        return "Needs Attention - Multiple metrics are showing concerning patterns. Consider consulting a healthcare provider."
    else:
        return "Critical - Significant health concerns detected. Immediate attention recommended."


async def main():
    """Run the MCP server."""
    # Initialize database
    await init_database()
    
    # Run server
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())

