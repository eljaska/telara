"""
Telara Data Generator Control Server
HTTP API for controlling the biometric data generator.
"""

import os
import threading
from flask import Flask, jsonify, request
from producer import BiometricProducer

app = Flask(__name__)

# Global producer instance
producer: BiometricProducer = None
producer_thread: threading.Thread = None
producer_lock = threading.Lock()


def get_producer() -> BiometricProducer:
    """Get or create the producer instance."""
    global producer
    if producer is None:
        bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
        topic = os.environ.get("KAFKA_TOPIC", "biometrics-raw")
        interval_ms = int(os.environ.get("EVENT_INTERVAL_MS", "500"))
        user_id = os.environ.get("USER_ID", "user_001")
        
        producer = BiometricProducer(
            bootstrap_servers=bootstrap_servers,
            topic=topic,
            user_id=user_id,
            interval_ms=interval_ms,
        )
    return producer


@app.route('/status', methods=['GET'])
def get_status():
    """Get current generator status."""
    p = get_producer()
    return jsonify({
        "running": p.running,
        "events_generated": p.events_generated,
        "anomaly_active": p.anomaly_active,
        "anomaly_end_time": p.anomaly_end_time,
        "user_id": p.user_id,
        "topic": p.topic,
        "interval_ms": p.interval_ms,
    })


@app.route('/start', methods=['POST'])
def start_generator():
    """Start the data generator."""
    global producer_thread
    
    with producer_lock:
        p = get_producer()
        
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
        producer_thread = threading.Thread(target=run_producer_loop, daemon=True)
        producer_thread.start()
        
        return jsonify({
            "status": "started",
            "message": "Generator started successfully"
        })


@app.route('/stop', methods=['POST'])
def stop_generator():
    """Stop the data generator."""
    with producer_lock:
        p = get_producer()
        
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
    """Inject an anomaly pattern."""
    p = get_producer()
    
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
    
    # Inject anomaly
    p.inject_anomaly(anomaly_type, duration)
    
    return jsonify({
        "status": "injected",
        "anomaly_type": anomaly_type,
        "duration_seconds": duration,
        "message": f"Anomaly '{anomaly_type}' injected for {duration} seconds"
    })


@app.route('/anomalies', methods=['GET'])
def list_anomalies():
    """List available anomaly types."""
    from schemas import ANOMALY_PATTERNS
    return jsonify({
        "anomaly_types": list(ANOMALY_PATTERNS.keys()),
        "patterns": ANOMALY_PATTERNS
    })


def run_producer_loop():
    """Run the producer main loop in a thread."""
    import time
    p = get_producer()
    interval_sec = p.interval_ms / 1000.0
    
    while p.running:
        try:
            event = p.generate_event()
            p.publish_event(event)
            p.print_status(event)
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

