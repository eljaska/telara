"""
Telara Data Generator Entrypoint
Runs both the control server and the data producer.
"""

import os
import sys
import threading
import signal

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from producer import BiometricProducer, setup_anomaly_trigger
from control_server import app as control_app, get_producer


def run_control_server():
    """Run the Flask control server."""
    host = os.environ.get("CONTROL_HOST", "0.0.0.0")
    port = int(os.environ.get("CONTROL_PORT", "8001"))
    
    # Disable Flask's reloader and debug mode
    control_app.run(
        host=host,
        port=port,
        threaded=True,
        use_reloader=False,
        debug=False
    )


def main():
    """Main entrypoint."""
    # Configuration
    auto_start = os.environ.get("AUTO_START", "true").lower() == "true"
    auto_anomaly = os.environ.get("AUTO_ANOMALY", "false").lower() == "true"
    
    print("=" * 60)
    print("TELARA DATA GENERATOR")
    print(f"  Auto-start: {auto_start}")
    print(f"  Auto-anomaly: {auto_anomaly}")
    print(f"  Control API: http://0.0.0.0:8001")
    print("=" * 60)
    
    # Start control server in background thread
    control_thread = threading.Thread(target=run_control_server, daemon=True)
    control_thread.start()
    print("✓ Control server started on port 8001")
    
    # Get or create producer
    producer = get_producer()
    
    # Handle shutdown signals
    def signal_handler(signum, frame):
        print("\nReceived shutdown signal...")
        producer.running = False
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if auto_start:
        print("Auto-starting data generation...")
        
        # Connect to Kafka
        if not producer.connect():
            print("Failed to connect to Kafka. Control server still running.")
            # Keep control server running
            control_thread.join()
            return
        
        # Set up auto-anomaly if enabled
        if auto_anomaly:
            print("Auto-anomaly injection enabled. First anomaly in 60 seconds.")
            setup_anomaly_trigger(producer)
        
        # Run producer main loop
        producer.running = True
        interval_sec = producer.interval_ms / 1000.0
        
        import time
        while producer.running:
            try:
                event = producer.generate_event()
                producer.publish_event(event)
                producer.print_status(event)
                time.sleep(interval_sec)
            except Exception as e:
                print(f"Error in producer loop: {e}")
                time.sleep(1)
        
        producer.shutdown()
    else:
        print("Waiting for start command via control API...")
        # Keep the main thread alive
        control_thread.join()


if __name__ == "__main__":
    main()

