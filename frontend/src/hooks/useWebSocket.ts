/**
 * WebSocket Hook for Real-time Data Streaming
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

interface UseWebSocketReturn {
  vitals: VitalData[];
  alerts: AlertData[];
  latestVital: VitalData | null;
  connectionState: ConnectionState;
  eventsPerSecond: number;
}

export function useWebSocket(maxVitals: number = 100): UseWebSocketReturn {
  const [vitals, setVitals] = useState<VitalData[]>([]);
  const [alerts, setAlerts] = useState<AlertData[]>([]);
  const [latestVital, setLatestVital] = useState<VitalData | null>(null);
  const [connectionState, setConnectionState] = useState<ConnectionState>({
    status: 'connecting',
    lastHeartbeat: null,
    reconnectAttempts: 0,
  });
  const [eventsPerSecond, setEventsPerSecond] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const heartbeatIntervalRef = useRef<number | null>(null);
  const eventCountRef = useRef(0);
  const lastSecondRef = useRef(Date.now());

  // Calculate events per second
  useEffect(() => {
    const interval = setInterval(() => {
      const now = Date.now();
      const elapsed = (now - lastSecondRef.current) / 1000;
      if (elapsed >= 1) {
        setEventsPerSecond(Math.round(eventCountRef.current / elapsed));
        eventCountRef.current = 0;
        lastSecondRef.current = now;
      }
    }, 1000);

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
          const message: WebSocketMessage = JSON.parse(event.data);

          switch (message.type) {
            case 'vital':
              if (message.data) {
                const vital = message.data as VitalData;
                setLatestVital(vital);
                setVitals(prev => {
                  const updated = [...prev, vital];
                  return updated.slice(-maxVitals);
                });
                eventCountRef.current++;
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
    connectionState,
    eventsPerSecond,
  };
}

