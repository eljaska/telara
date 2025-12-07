"""
Telara Claude Health Coach Agent
Multi-turn conversational agent with MCP tool access.
"""

import os
import json
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
from anthropic import Anthropic

from database import (
    VitalsRepository,
    AlertsRepository,
    BaselinesRepository,
    get_anomaly_context,
    calculate_correlations
)
from wellness import calculate_wellness_score, get_wellness_recommendations

# Configuration
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-opus-4-5-20251101"

# System prompt for the health coach
SYSTEM_PROMPT = """You are TELARA, an AI health coach integrated into a personal health monitoring dashboard. You have access to real-time biometric data from the user's wearable devices.

Your role is to:
1. Answer questions about the user's health data with specific, data-backed insights
2. Detect patterns and correlations in their vitals
3. Provide actionable, personalized wellness recommendations
4. Alert them to concerning trends while remaining calm and supportive

Communication style:
- Be warm, supportive, and professional
- Use data to back up your observations
- Provide specific, actionable advice
- When concerning patterns appear, be direct but not alarmist
- Use medical terminology appropriately but explain it

You have access to these tools:
- query_recent_vitals: Get recent vital signs data
- query_alerts: Get detected health anomalies
- get_wellness_score: Calculate current wellness score
- get_metric_trend: Analyze trends for specific metrics
- get_correlations: Find correlations between metrics
- compare_to_baseline: Compare current values to user's personal norms
- get_vital_statistics: Get statistical summary
- get_alert_summary: Get summary of alerts

Always use your tools to query actual data before making claims about the user's health. Never guess or make up data.

When starting a conversation, proactively check the user's current status to provide contextual responses."""


@dataclass
class ConversationSession:
    """Manages a conversation session with history."""
    session_id: str
    user_id: str = "user_001"
    messages: List[Dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    
    def add_message(self, role: str, content: str):
        """Add a message to the conversation."""
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        })
        self.last_activity = datetime.utcnow()
        
        # Keep only last 20 messages to manage context window
        if len(self.messages) > 20:
            self.messages = self.messages[-20:]
    
    def get_messages_for_api(self) -> List[Dict]:
        """Get messages formatted for Anthropic API."""
        return [{"role": m["role"], "content": m["content"]} for m in self.messages]


class HealthCoachAgent:
    """Claude-powered health coach with tool access."""
    
    def __init__(self):
        self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.sessions: Dict[str, ConversationSession] = {}
        self.tools = self._define_tools()
    
    def _define_tools(self) -> List[Dict]:
        """Define available tools for Claude."""
        return [
            {
                "name": "query_recent_vitals",
                "description": "Get the user's vital signs from the last N minutes. Returns heart rate, HRV, SpO2, temperature, activity level.",
                "input_schema": {
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
            },
            {
                "name": "query_alerts",
                "description": "Get health alerts/anomalies detected in the last N hours. Can filter by severity.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "hours": {
                            "type": "integer",
                            "description": "Number of hours to look back (default: 24)",
                            "default": 24
                        },
                        "severity": {
                            "type": "string",
                            "description": "Filter by severity level",
                            "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "get_wellness_score",
                "description": "Calculate current wellness score (0-100) with breakdown by heart health, recovery, activity, stability, and alerts.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "get_metric_trend",
                "description": "Get trend analysis for a specific health metric over time.",
                "input_schema": {
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
            },
            {
                "name": "get_correlations",
                "description": "Find statistical correlation between two health metrics.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "metric1": {
                            "type": "string",
                            "enum": ["heart_rate", "hrv_ms", "spo2_percent", "skin_temp_c", "activity_level"]
                        },
                        "metric2": {
                            "type": "string",
                            "enum": ["heart_rate", "hrv_ms", "spo2_percent", "skin_temp_c", "activity_level"]
                        }
                    },
                    "required": ["metric1", "metric2"]
                }
            },
            {
                "name": "compare_to_baseline",
                "description": "Compare current vitals to user's personal baseline averages.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "get_vital_statistics",
                "description": "Get statistical summary (min, max, avg) of vitals over a time period.",
                "input_schema": {
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
            },
            {
                "name": "get_alert_summary",
                "description": "Get summary of alerts grouped by severity and type.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "hours": {
                            "type": "integer",
                            "default": 24
                        }
                    },
                    "required": []
                }
            }
        ]
    
    async def _execute_tool(self, name: str, arguments: Dict) -> str:
        """Execute a tool and return results as JSON string."""
        try:
            result = await self._call_tool(name, arguments)
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    async def _call_tool(self, name: str, arguments: Dict) -> Dict:
        """Execute tool logic."""
        
        if name == "query_recent_vitals":
            minutes = min(arguments.get("minutes", 30), 1440)
            vitals = await VitalsRepository.get_recent(minutes=minutes)
            
            if not vitals:
                return {"message": "No vital data found", "count": 0}
            
            latest = vitals[0]
            return {
                "count": len(vitals),
                "period_minutes": minutes,
                "latest_reading": {
                    "timestamp": latest.get("timestamp"),
                    "heart_rate": latest.get("heart_rate"),
                    "hrv_ms": latest.get("hrv_ms"),
                    "spo2_percent": latest.get("spo2_percent"),
                    "skin_temp_c": latest.get("skin_temp_c"),
                    "activity_level": latest.get("activity_level")
                },
                "summary": {
                    "avg_heart_rate": round(sum(v["heart_rate"] for v in vitals if v.get("heart_rate")) / len(vitals), 1),
                    "avg_hrv": round(sum(v["hrv_ms"] for v in vitals if v.get("hrv_ms")) / len(vitals), 1),
                    "avg_spo2": round(sum(v["spo2_percent"] for v in vitals if v.get("spo2_percent")) / len(vitals), 1),
                }
            }
        
        elif name == "query_alerts":
            hours = arguments.get("hours", 24)
            severity = arguments.get("severity")
            alerts = await AlertsRepository.get_recent(hours=hours, severity=severity)
            
            return {
                "count": len(alerts),
                "period_hours": hours,
                "alerts": [
                    {
                        "type": a.get("alert_type"),
                        "severity": a.get("severity"),
                        "description": a.get("description"),
                        "timestamp": a.get("timestamp")
                    }
                    for a in alerts[:10]
                ]
            }
        
        elif name == "get_wellness_score":
            vitals = await VitalsRepository.get_recent(minutes=60)
            alerts = await AlertsRepository.get_recent(hours=24)
            baseline = await BaselinesRepository.get()
            
            score, breakdown = await calculate_wellness_score(vitals, alerts, baseline)
            recommendations = get_wellness_recommendations(score, breakdown)
            
            return {
                "wellness_score": score,
                "breakdown": breakdown,
                "recommendations": recommendations
            }
        
        elif name == "get_metric_trend":
            metric = arguments.get("metric")
            hours = arguments.get("hours", 24)
            
            trend_data = await VitalsRepository.get_metric_trend(metric, hours)
            
            if not trend_data:
                return {"error": "No data available"}
            
            values = [d["value"] for d in trend_data if d.get("value") is not None]
            
            if len(values) < 2:
                return {"error": "Insufficient data"}
            
            first_half = values[:len(values)//2]
            second_half = values[len(values)//2:]
            avg_first = sum(first_half) / len(first_half)
            avg_second = sum(second_half) / len(second_half)
            
            trend = "increasing" if avg_second > avg_first * 1.05 else "decreasing" if avg_second < avg_first * 0.95 else "stable"
            
            return {
                "metric": metric,
                "period_hours": hours,
                "data_points": len(values),
                "current": values[-1],
                "min": min(values),
                "max": max(values),
                "average": round(sum(values) / len(values), 2),
                "trend": trend,
                "percent_change": round(((avg_second - avg_first) / avg_first) * 100, 1) if avg_first else 0
            }
        
        elif name == "get_correlations":
            metric1 = arguments.get("metric1")
            metric2 = arguments.get("metric2")
            return await calculate_correlations(metric1, metric2)
        
        elif name == "compare_to_baseline":
            latest = await VitalsRepository.get_latest()
            if not latest:
                return {"error": "No current vital data"}
            return await BaselinesRepository.compare_to_current("user_001", latest)
        
        elif name == "get_vital_statistics":
            hours = arguments.get("hours", 24)
            return await VitalsRepository.get_stats(hours)
        
        elif name == "get_alert_summary":
            hours = arguments.get("hours", 24)
            counts = await AlertsRepository.get_count_by_severity(hours)
            alerts = await AlertsRepository.get_recent(hours)
            
            type_counts = {}
            for alert in alerts:
                t = alert.get("alert_type", "UNKNOWN")
                type_counts[t] = type_counts.get(t, 0) + 1
            
            return {
                "period_hours": hours,
                "total_alerts": sum(counts.values()),
                "by_severity": counts,
                "by_type": type_counts
            }
        
        return {"error": f"Unknown tool: {name}"}
    
    def get_or_create_session(self, session_id: str) -> ConversationSession:
        """Get existing session or create new one."""
        if session_id not in self.sessions:
            self.sessions[session_id] = ConversationSession(session_id=session_id)
        return self.sessions[session_id]
    
    async def chat(
        self,
        session_id: str,
        user_message: str,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        Process a chat message and return response.
        
        Returns:
            Dict with keys: response, tool_calls, session_id
        """
        session = self.get_or_create_session(session_id)
        session.add_message("user", user_message)
        
        tool_calls_made = []
        
        # Make initial API call
        response = self.client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=self.tools,
            messages=session.get_messages_for_api()
        )
        
        # Handle tool use loop
        while response.stop_reason == "tool_use":
            # Extract tool calls
            tool_use_blocks = [block for block in response.content if block.type == "tool_use"]
            
            tool_results = []
            for tool_use in tool_use_blocks:
                tool_name = tool_use.name
                tool_input = tool_use.input
                
                # Execute tool
                result = await self._execute_tool(tool_name, tool_input)
                
                tool_calls_made.append({
                    "tool": tool_name,
                    "input": tool_input,
                    "output_preview": result[:200] + "..." if len(result) > 200 else result
                })
                
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": result
                })
            
            # Continue conversation with tool results
            messages = session.get_messages_for_api()
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
            
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                tools=self.tools,
                messages=messages
            )
        
        # Extract final text response
        text_response = ""
        for block in response.content:
            if hasattr(block, "text"):
                text_response += block.text
        
        session.add_message("assistant", text_response)
        
        return {
            "response": text_response,
            "tool_calls": tool_calls_made,
            "session_id": session_id
        }
    
    async def generate_alert_insight(self, alert_data: Dict) -> str:
        """Generate an AI insight for an alert."""
        # Get context
        vitals = await VitalsRepository.get_recent(minutes=30)
        baseline = await BaselinesRepository.get()
        
        context = {
            "alert": alert_data,
            "recent_vitals_summary": {
                "count": len(vitals),
                "avg_hr": round(sum(v["heart_rate"] for v in vitals if v.get("heart_rate")) / len(vitals), 1) if vitals else None,
                "avg_hrv": round(sum(v["hrv_ms"] for v in vitals if v.get("hrv_ms")) / len(vitals), 1) if vitals else None,
            } if vitals else None,
            "baseline": baseline
        }
        
        prompt = f"""Based on this health alert, generate a brief 2-3 sentence insight for the user:

Alert Type: {alert_data.get('alert_type')}
Severity: {alert_data.get('severity')}
Description: {alert_data.get('description')}

Context:
- Recent vitals: {json.dumps(context['recent_vitals_summary'])}
- User baseline: HR {baseline.get('avg_heart_rate', 'N/A')}, HRV {baseline.get('avg_hrv', 'N/A')} if baseline else 'Not established'

Provide:
1. A brief explanation of what this means
2. One specific action they can take right now

Keep it concise and actionable. Don't be alarmist but be direct."""

        response = self.client.messages.create(
            model=MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text if response.content else ""
    
    def clear_session(self, session_id: str):
        """Clear a conversation session."""
        if session_id in self.sessions:
            del self.sessions[session_id]


# Singleton instance
agent = HealthCoachAgent()


async def get_agent() -> HealthCoachAgent:
    """Get the health coach agent instance."""
    return agent

