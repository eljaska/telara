"""
Telara Data Generator Entrypoint
Runs both the control server and the multi-source data producer.
"""

import os
import sys
import threading
import signal
import time

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from producer import MultiSourceProducer, setup_anomaly_trigger, set_multi_source_producer
from control_server import app as control_app, get_multi_producer


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
    print("TELARA MULTI-SOURCE DATA GENERATOR")
    print(f"  Auto-start: {auto_start}")
    print(f"  Auto-anomaly: {auto_anomaly}")
    print(f"  Control API: http://0.0.0.0:8001")
    print("  Sources: Apple HealthKit, Google Fit, Oura Ring")
    print("=" * 60)
    
    # Start control server in background thread
    control_thread = threading.Thread(target=run_control_server, daemon=True)
    control_thread.start()
    print("✓ Control server started on port 8001")
    
    # Get or create multi-source producer
    producer = get_multi_producer()
    
    # Handle shutdown signals
    def signal_handler(signum, frame):
        print("\nReceived shutdown signal...")
        producer.running = False
        producer.producer.running = False
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if auto_start:
        print("Auto-starting multi-source data generation...")
        
        # Connect to Kafka
        if not producer.connect():
            print("Failed to connect to Kafka. Control server still running.")
            # Keep control server running
            control_thread.join()
            return
        
        # Set up auto-anomaly if enabled (affects all sources)
        if auto_anomaly:
            print("Auto-anomaly injection enabled. First anomaly in 60 seconds.")
            setup_anomaly_trigger(producer.producer)
        
        # Run multi-source producer main loop
        producer.running = True
        producer.producer.running = True
        interval_sec = producer.base_interval_ms / 1000.0
        last_print_time = 0
        
        print(f"\n{'='*60}")
        print(f"TELARA MULTI-SOURCE DATA GENERATOR STARTED")
        print(f"  User: {producer.user_id}")
        print(f"  Base Interval: {producer.base_interval_ms}ms")
        print(f"  Sources:")
        for source in producer.sources.values():
            status = "✓" if source["enabled"] else "✗"
            print(f"    {status} {source['name']} -> {source['topic']}")
        print(f"{'='*60}\n")
        
        while producer.running:
            try:
                producer.generate_and_publish()
                
                # Print status every 5 seconds
                current_time = time.time()
                if current_time - last_print_time >= 5:
                    producer.print_status()
                    last_print_time = current_time
                
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
