"""
Telara PyFlink Stream Processor
Detects health anomalies using MATCH_RECOGNIZE pattern matching.
"""

import os
from pyflink.table import EnvironmentSettings, TableEnvironment
from pyflink.table.expressions import col


def create_kafka_source_ddl() -> str:
    """Create DDL for the biometrics-raw Kafka source table."""
    return """
    CREATE TABLE biometrics_raw (
        event_id STRING,
        `timestamp` STRING,
        user_id STRING,
        heart_rate INT,
        hrv_ms INT,
        activity_level INT,
        steps_per_minute INT,
        skin_temp_c DOUBLE,
        spo2_percent INT,
        respiratory_rate INT,
        ts AS TO_TIMESTAMP(`timestamp`),
        WATERMARK FOR ts AS ts - INTERVAL '5' SECOND
    ) WITH (
        'connector' = 'kafka',
        'topic' = 'biometrics-raw',
        'properties.bootstrap.servers' = 'kafka:29092',
        'properties.group.id' = 'flink-telara-processor',
        'format' = 'json',
        'json.ignore-parse-errors' = 'true',
        'scan.startup.mode' = 'latest-offset'
    )
    """


def create_kafka_sink_ddl() -> str:
    """Create DDL for the biometrics-alerts Kafka sink table."""
    return """
    CREATE TABLE biometrics_alerts (
        alert_id STRING,
        alert_type STRING,
        user_id STRING,
        severity STRING,
        start_time TIMESTAMP(3),
        end_time TIMESTAMP(3),
        avg_heart_rate DOUBLE,
        event_count BIGINT,
        description STRING
    ) WITH (
        'connector' = 'kafka',
        'topic' = 'biometrics-alerts',
        'properties.bootstrap.servers' = 'kafka:29092',
        'format' = 'json'
    )
    """


def create_tachycardia_detection_query() -> str:
    """
    MATCH_RECOGNIZE query to detect Tachycardia at Rest.
    
    Pattern: 5+ consecutive events where:
    - heart_rate > 100 bpm
    - activity_level < 10 (sedentary)
    - steps_per_minute < 5 (at rest)
    
    Note: Pattern uses reluctant quantifier A{5,}? and ends with B to avoid
    the "greedy quantifier as last element" limitation in Flink.
    """
    return """
    INSERT INTO biometrics_alerts
    SELECT 
        CAST(UUID() AS STRING) as alert_id,
        'TACHYCARDIA_AT_REST' as alert_type,
        user_id,
        CASE 
            WHEN avg_hr > 130 THEN 'CRITICAL'
            WHEN avg_hr > 115 THEN 'HIGH'
            ELSE 'MEDIUM'
        END as severity,
        start_ts as start_time,
        end_ts as end_time,
        avg_hr as avg_heart_rate,
        match_count as event_count,
        CONCAT('Sustained elevated HR (', CAST(CAST(avg_hr AS INT) AS STRING), ' bpm avg) detected while at rest for ', CAST(match_count AS STRING), ' consecutive readings') as description
    FROM biometrics_raw
    MATCH_RECOGNIZE (
        PARTITION BY user_id
        ORDER BY ts
        MEASURES
            FIRST(A.ts) AS start_ts,
            LAST(A.ts) AS end_ts,
            AVG(CAST(A.heart_rate AS DOUBLE)) AS avg_hr,
            COUNT(A.event_id) AS match_count
        ONE ROW PER MATCH
        AFTER MATCH SKIP PAST LAST ROW
        PATTERN (A{5,}? B)
        DEFINE
            A AS A.heart_rate > 100 AND A.activity_level < 10 AND A.steps_per_minute < 5,
            B AS B.heart_rate <= 100 OR B.activity_level >= 10 OR B.steps_per_minute >= 5
    ) AS T
    """


def create_hypoxia_detection_query() -> str:
    """
    Additional pattern: Low SpO2 detection (potential hypoxia).
    
    Pattern: 3+ consecutive events where SpO2 < 94%
    """
    return """
    INSERT INTO biometrics_alerts
    SELECT 
        CAST(UUID() AS STRING) as alert_id,
        'LOW_SPO2_HYPOXIA' as alert_type,
        user_id,
        CASE 
            WHEN avg_spo2 < 90 THEN 'CRITICAL'
            WHEN avg_spo2 < 92 THEN 'HIGH'
            ELSE 'MEDIUM'
        END as severity,
        start_ts as start_time,
        end_ts as end_time,
        avg_spo2 as avg_heart_rate,
        match_count as event_count,
        CONCAT('Low blood oxygen (', CAST(CAST(avg_spo2 AS INT) AS STRING), '% avg SpO2) detected for ', CAST(match_count AS STRING), ' consecutive readings') as description
    FROM biometrics_raw
    MATCH_RECOGNIZE (
        PARTITION BY user_id
        ORDER BY ts
        MEASURES
            FIRST(A.ts) AS start_ts,
            LAST(A.ts) AS end_ts,
            AVG(CAST(A.spo2_percent AS DOUBLE)) AS avg_spo2,
            COUNT(A.event_id) AS match_count
        ONE ROW PER MATCH
        AFTER MATCH SKIP PAST LAST ROW
        PATTERN (A{3,}? B)
        DEFINE
            A AS A.spo2_percent < 94,
            B AS B.spo2_percent >= 94
    ) AS T
    """


def create_fever_detection_query() -> str:
    """
    Additional pattern: Elevated temperature detection (fever onset).
    
    Pattern: 3+ consecutive events where skin_temp_c > 37.5
    """
    return """
    INSERT INTO biometrics_alerts
    SELECT 
        CAST(UUID() AS STRING) as alert_id,
        'ELEVATED_TEMPERATURE' as alert_type,
        user_id,
        CASE 
            WHEN avg_temp > 38.5 THEN 'CRITICAL'
            WHEN avg_temp > 38.0 THEN 'HIGH'
            ELSE 'MEDIUM'
        END as severity,
        start_ts as start_time,
        end_ts as end_time,
        avg_temp as avg_heart_rate,
        match_count as event_count,
        CONCAT('Elevated body temperature (', CAST(ROUND(avg_temp, 1) AS STRING), '°C avg) detected for ', CAST(match_count AS STRING), ' consecutive readings') as description
    FROM biometrics_raw
    MATCH_RECOGNIZE (
        PARTITION BY user_id
        ORDER BY ts
        MEASURES
            FIRST(A.ts) AS start_ts,
            LAST(A.ts) AS end_ts,
            AVG(A.skin_temp_c) AS avg_temp,
            COUNT(A.event_id) AS match_count
        ONE ROW PER MATCH
        AFTER MATCH SKIP PAST LAST ROW
        PATTERN (A{3,}? B)
        DEFINE
            A AS A.skin_temp_c > 37.5,
            B AS B.skin_temp_c <= 37.5
    ) AS T
    """


def main():
    """Main entry point for the Flink job."""
    print("=" * 60)
    print("TELARA FLINK STREAM PROCESSOR")
    print("Starting health anomaly detection pipeline...")
    print("=" * 60)
    
    # Create streaming table environment
    env_settings = EnvironmentSettings.in_streaming_mode()
    table_env = TableEnvironment.create(env_settings)
    
    # Configure Flink
    table_env.get_config().set("pipeline.jars", "file:///opt/flink/lib/flink-sql-connector-kafka-3.0.2-1.18.jar")
    table_env.get_config().set("table.exec.source.idle-timeout", "10000")
    
    # Create source table
    print("\n[1/5] Creating Kafka source table (biometrics-raw)...")
    table_env.execute_sql(create_kafka_source_ddl())
    print("      Source table created successfully.")
    
    # Create sink table
    print("\n[2/5] Creating Kafka sink table (biometrics-alerts)...")
    table_env.execute_sql(create_kafka_sink_ddl())
    print("      Sink table created successfully.")
    
    # Submit detection queries
    print("\n[3/5] Submitting Tachycardia at Rest detection query...")
    table_env.execute_sql(create_tachycardia_detection_query())
    print("      Tachycardia detection query submitted.")
    
    print("\n[4/5] Submitting Low SpO2 (Hypoxia) detection query...")
    table_env.execute_sql(create_hypoxia_detection_query())
    print("      Hypoxia detection query submitted.")
    
    print("\n[5/5] Submitting Elevated Temperature detection query...")
    table_env.execute_sql(create_fever_detection_query())
    print("      Temperature detection query submitted.")
    
    print("\n" + "=" * 60)
    print("ALL DETECTION QUERIES RUNNING")
    print("Monitoring patterns: TACHYCARDIA_AT_REST, LOW_SPO2_HYPOXIA, ELEVATED_TEMPERATURE")
    print("=" * 60)
    
    # Keep the job running
    import time
    while True:
        time.sleep(60)
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Flink job running...")


if __name__ == "__main__":
    main()
