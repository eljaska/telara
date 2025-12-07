"""
Telara Data Generator Control Server
HTTP API for controlling the multi-source biometric data generator.
"""

import os
import threading
import time
from flask import Flask, jsonify, request
from producer import (
    BiometricProducer, 
    MultiSourceProducer, 
    SOURCE_CONFIGS,
    generate_historical_data,
    set_multi_source_producer,
    get_multi_source_producer
)

app = Flask(__name__)

# Global producer instances
multi_producer: MultiSourceProducer = None
legacy_producer: BiometricProducer = None
producer_thread: threading.Thread = None
producer_lock = threading.Lock()


def get_multi_producer() -> MultiSourceProducer:
    """Get or create the multi-source producer instance."""
    global multi_producer
    if multi_producer is None:
        bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
        interval_ms = int(os.environ.get("EVENT_INTERVAL_MS", "500"))
        user_id = os.environ.get("USER_ID", "user_001")
        
        multi_producer = MultiSourceProducer(
            bootstrap_servers=bootstrap_servers,
            user_id=user_id,
            base_interval_ms=interval_ms,
        )
        set_multi_source_producer(multi_producer)
    return multi_producer


def get_legacy_producer() -> BiometricProducer:
    """Get or create the legacy single-topic producer instance."""
    global legacy_producer
    if legacy_producer is None:
        bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
        topic = os.environ.get("KAFKA_TOPIC", "biometrics-raw")
        interval_ms = int(os.environ.get("EVENT_INTERVAL_MS", "500"))
        user_id = os.environ.get("USER_ID", "user_001")
        
        legacy_producer = BiometricProducer(
            bootstrap_servers=bootstrap_servers,
            topic=topic,
            user_id=user_id,
            interval_ms=interval_ms,
        )
    return legacy_producer


# ============================================
# Source Management Endpoints
# ============================================

@app.route('/sources', methods=['GET'])
def list_sources():
    """List all available data sources and their status."""
    p = get_multi_producer()
    sources = p.get_source_status()
    
    return jsonify({
        "sources": list(sources.values()),
        "total": len(sources),
        "enabled_count": sum(1 for s in sources.values() if s["enabled"]),
        "running": p.running
    })


@app.route('/sources/<source_id>', methods=['GET'])
def get_source(source_id: str):
    """Get status of a specific source."""
    p = get_multi_producer()
    sources = p.get_source_status()
    
    if source_id not in sources:
        return jsonify({
            "status": "error",
            "message": f"Unknown source: {source_id}. Valid sources: {list(sources.keys())}"
        }), 404
    
    return jsonify(sources[source_id])


@app.route('/sources/<source_id>/enable', methods=['POST'])
def enable_source(source_id: str):
    """Enable a data source (start publishing to its topic)."""
    p = get_multi_producer()
    
    if source_id not in SOURCE_CONFIGS:
        return jsonify({
            "status": "error",
            "message": f"Unknown source: {source_id}. Valid sources: {list(SOURCE_CONFIGS.keys())}"
        }), 404
    
    success = p.enable_source(source_id)
    
    if success:
        return jsonify({
            "status": "enabled",
            "source_id": source_id,
            "message": f"Source '{source_id}' is now enabled"
        })
    else:
        return jsonify({
            "status": "error",
            "message": f"Failed to enable source: {source_id}"
        }), 500


@app.route('/sources/<source_id>/disable', methods=['POST'])
def disable_source(source_id: str):
    """Disable a data source (stop publishing to its topic)."""
    p = get_multi_producer()
    
    if source_id not in SOURCE_CONFIGS:
        return jsonify({
            "status": "error",
            "message": f"Unknown source: {source_id}. Valid sources: {list(SOURCE_CONFIGS.keys())}"
        }), 404
    
    success = p.disable_source(source_id)
    
    if success:
        return jsonify({
            "status": "disabled",
            "source_id": source_id,
            "message": f"Source '{source_id}' is now disabled"
        })
    else:
        return jsonify({
            "status": "error",
            "message": f"Failed to disable source: {source_id}"
        }), 500


# ============================================
# Generator Control Endpoints
# ============================================

@app.route('/status', methods=['GET'])
def get_status():
    """Get current generator status."""
    p = get_multi_producer()
    sources = p.get_source_status()
    
    # Get anomaly status from ground truth
    anomaly_status = p.ground_truth.get_anomaly_status() if hasattr(p, 'ground_truth') else {"active": False, "type": None}
    
    return jsonify({
        "running": p.running,
        "mode": "multi-source",
        "user_id": p.user_id,
        "interval_ms": p.base_interval_ms,
        "anomaly_active": anomaly_status.get("active", False),
        "anomaly_type": anomaly_status.get("type"),
        "sources": sources,
        "total_events": sum(s["events_generated"] for s in sources.values()),
    })


@app.route('/start', methods=['POST'])
def start_generator():
    """Start the multi-source data generator."""
    global producer_thread
    
    with producer_lock:
        p = get_multi_producer()
        
        if p.running:
            return jsonify({
                "status": "already_running",
                "message": "Generator is already running"
            })
        
        # Connect if not connected
        if not p.producer:
            if not p.connect():
                return jsonify({
                    "status": "error",
                    "message": "Failed to connect to Kafka"
                }), 500
        
        # Start in background thread
        p.running = True
        producer_thread = threading.Thread(target=run_multi_producer_loop, daemon=True)
        producer_thread.start()
        
        return jsonify({
            "status": "started",
            "message": "Multi-source generator started successfully",
            "sources": list(p.get_source_status().keys())
        })


@app.route('/stop', methods=['POST'])
def stop_generator():
    """Stop the data generator."""
    with producer_lock:
        p = get_multi_producer()
        
        if not p.running:
            return jsonify({
                "status": "already_stopped",
                "message": "Generator is not running"
            })
        
        p.running = False
        
        return jsonify({
            "status": "stopped",
            "message": "Generator stopped"
        })


@app.route('/inject', methods=['POST'])
def inject_anomaly():
    """Inject an anomaly pattern (affects all sources)."""
    p = get_multi_producer()
    
    if not p.running:
        return jsonify({
            "status": "error",
            "message": "Generator is not running. Start it first."
        }), 400
    
    data = request.get_json() or {}
    anomaly_type = data.get('anomaly_type', 'tachycardia_at_rest')
    duration = data.get('duration_seconds', 30)
    
    # Validate anomaly type
    from schemas import ANOMALY_PATTERNS
    if anomaly_type not in ANOMALY_PATTERNS:
        return jsonify({
            "status": "error",
            "message": f"Invalid anomaly type. Valid types: {list(ANOMALY_PATTERNS.keys())}"
        }), 400
    
    # Inject anomaly (affects all sources)
    p.inject_anomaly(anomaly_type, duration)
    
    return jsonify({
        "status": "injected",
        "anomaly_type": anomaly_type,
        "duration_seconds": duration,
        "message": f"Anomaly '{anomaly_type}' injected for {duration} seconds (affects all sources)"
    })


@app.route('/anomalies', methods=['GET'])
def list_anomalies():
    """List available anomaly types."""
    from schemas import ANOMALY_PATTERNS
    return jsonify({
        "anomaly_types": list(ANOMALY_PATTERNS.keys()),
        "patterns": ANOMALY_PATTERNS
    })


@app.route('/generate/historical', methods=['POST'])
def generate_historical():
    """
    Generate historical biometric data for AI insights.
    
    Request body:
    {
        "days": 7,                    # Number of days of history (1-30)
        "events_per_hour": 60,        # Events per hour (10-120)
        "include_anomalies": true,    # Include random anomalies
        "anomaly_probability": 0.05,  # Probability per event (0.0-0.2)
        "pattern": "normal"           # normal|improving|declining|variable
    }
    
    Returns the generated events for the API to insert into the database.
    """
    data = request.get_json() or {}
    
    # Extract and validate parameters
    days = min(max(int(data.get('days', 7)), 1), 30)
    events_per_hour = min(max(int(data.get('events_per_hour', 60)), 10), 120)
    include_anomalies = bool(data.get('include_anomalies', True))
    anomaly_probability = min(max(float(data.get('anomaly_probability', 0.05)), 0.0), 0.2)
    pattern = data.get('pattern', 'normal')
    
    if pattern not in ['normal', 'improving', 'declining', 'variable']:
        pattern = 'normal'
    
    user_id = os.environ.get("USER_ID", "user_001")
    
    try:
        # Generate historical data
        events = generate_historical_data(
            user_id=user_id,
            days=days,
            events_per_hour=events_per_hour,
            include_anomalies=include_anomalies,
            anomaly_probability=anomaly_probability,
            pattern=pattern
        )
        
        return jsonify({
            "status": "generated",
            "events_count": len(events),
            "days": days,
            "pattern": pattern,
            "events": events
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


def run_multi_producer_loop():
    """Run the multi-source producer main loop in a thread."""
    p = get_multi_producer()
    interval_sec = p.base_interval_ms / 1000.0
    last_print_time = 0
    
    while p.running:
        try:
            p.generate_and_publish()
            
            # Print status every 5 seconds
            current_time = time.time()
            if current_time - last_print_time >= 5:
                p.print_status()
                last_print_time = current_time
            
            time.sleep(interval_sec)
        except Exception as e:
            print(f"Error in producer loop: {e}")
            time.sleep(1)


def run_control_server(host='0.0.0.0', port=8001):
    """Run the control server."""
    print(f"Starting control server on {host}:{port}")
    app.run(host=host, port=port, threaded=True)


if __name__ == '__main__':
    run_control_server()
