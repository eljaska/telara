/**
 * WebSocket Hook for Real-time Data Streaming
 * 
 * Handles multi-source aggregated data from the Speed Layer.
 * Each vital message includes both raw event data and aggregated state.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import type { 
  VitalData, 
  AlertData, 
  WebSocketMessage, 
  ConnectionState,
  InitialState 
} from '../types';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/vitals';
const RECONNECT_DELAY = 3000;
const MAX_RECONNECT_ATTEMPTS = 10;
const HEARTBEAT_INTERVAL = 25000;

// Aggregated metric value with source attribution
interface AggregatedMetric {
  value: number;
  sources: string[];
  source_icons: string[];
  freshness_ms: number;
  reading_count: number;
}

// Aggregated state from multi-source fusion
interface AggregatedState {
  vitals: Record<string, AggregatedMetric>;
  last_update: string;
  source_count: number;
}

interface UseWebSocketReturn {
  vitals: VitalData[];
  alerts: AlertData[];
  latestVital: VitalData | null;
  aggregatedState: AggregatedState | null;  // NEW: Aggregated multi-source data
  connectionState: ConnectionState;
  eventsPerSecond: number;
}

export function useWebSocket(maxVitals: number = 100): UseWebSocketReturn {
  const [vitals, setVitals] = useState<VitalData[]>([]);
  const [alerts, setAlerts] = useState<AlertData[]>([]);
  const [latestVital, setLatestVital] = useState<VitalData | null>(null);
  const [aggregatedState, setAggregatedState] = useState<AggregatedState | null>(null);
  const [connectionState, setConnectionState] = useState<ConnectionState>({
    status: 'connecting',
    lastHeartbeat: null,
    reconnectAttempts: 0,
  });
  const [eventsPerSecond, setEventsPerSecond] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const heartbeatIntervalRef = useRef<number | null>(null);
  
  // Rolling window for smooth evt/s calculation (5-second window)
  const eventTimestampsRef = useRef<number[]>([]);
  const RATE_WINDOW_MS = 5000;

  // Calculate events per second using rolling window
  // This smooths out Kafka batch arrivals for stable display
  useEffect(() => {
    const interval = setInterval(() => {
      const now = Date.now();
      const cutoff = now - RATE_WINDOW_MS;
      
      // Remove timestamps older than the window
      eventTimestampsRef.current = eventTimestampsRef.current.filter(t => t > cutoff);
      
      // Calculate rate: events in window / window size in seconds
      const eventsInWindow = eventTimestampsRef.current.length;
      setEventsPerSecond(Math.round(eventsInWindow / (RATE_WINDOW_MS / 1000)));
    }, 500); // Update every 500ms for responsive UI

    return () => clearInterval(interval);
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    console.log(`[WebSocket] Connecting to ${WS_URL}...`);
    setConnectionState(prev => ({ ...prev, status: 'connecting' }));

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('[WebSocket] Connected');
        setConnectionState({
          status: 'connected',
          lastHeartbeat: new Date(),
          reconnectAttempts: 0,
        });

        // Start heartbeat
        heartbeatIntervalRef.current = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send('ping');
          }
        }, HEARTBEAT_INTERVAL);
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);

          switch (message.type) {
            case 'vital':
              if (message.data) {
                const vital = message.data as VitalData;
                setLatestVital(vital);
                setVitals(prev => {
                  const updated = [...prev, vital];
                  return updated.slice(-maxVitals);
                });
                
                // Update aggregated state if present (multi-source fusion)
                if (message.aggregated) {
                  setAggregatedState(message.aggregated as AggregatedState);
                }
                
                // Track event timestamp for rolling rate calculation
                eventTimestampsRef.current.push(Date.now());
              }
              break;

            case 'alert':
              if (message.data) {
                const alert = message.data as AlertData;
                setAlerts(prev => [alert, ...prev].slice(0, 50));
              }
              break;

            case 'initial_state':
              if (message.data) {
                const initial = message.data as InitialState;
                setVitals(initial.vitals.map(v => v.data).slice(-maxVitals));
                setAlerts(initial.alerts.map(a => a.data));
                if (initial.vitals.length > 0) {
                  setLatestVital(initial.vitals[initial.vitals.length - 1].data);
                }
              }
              break;

            case 'heartbeat':
              setConnectionState(prev => ({
                ...prev,
                lastHeartbeat: new Date(),
              }));
              break;
          }
        } catch (error) {
          console.error('[WebSocket] Parse error:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error);
        setConnectionState(prev => ({ ...prev, status: 'error' }));
      };

      ws.onclose = (event) => {
        console.log(`[WebSocket] Closed: ${event.code} ${event.reason}`);
        setConnectionState(prev => ({
          ...prev,
          status: 'disconnected',
        }));

        // Clear heartbeat
        if (heartbeatIntervalRef.current) {
          clearInterval(heartbeatIntervalRef.current);
        }

        // Attempt reconnect
        setConnectionState(prev => {
          if (prev.reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
            const delay = RECONNECT_DELAY * Math.pow(1.5, prev.reconnectAttempts);
            console.log(`[WebSocket] Reconnecting in ${delay}ms...`);
            
            reconnectTimeoutRef.current = window.setTimeout(() => {
              connect();
            }, delay);

            return {
              ...prev,
              reconnectAttempts: prev.reconnectAttempts + 1,
            };
          }
          return prev;
        });
      };
    } catch (error) {
      console.error('[WebSocket] Connection error:', error);
      setConnectionState(prev => ({ ...prev, status: 'error' }));
    }
  }, [maxVitals]);

  // Initial connection
  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (heartbeatIntervalRef.current) {
        clearInterval(heartbeatIntervalRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  return {
    vitals,
    alerts,
    latestVital,
    aggregatedState,
    connectionState,
    eventsPerSecond,
  };
}

