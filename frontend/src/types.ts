/**
 * Telara Type Definitions
 */

export interface VitalData {
  event_id: string;
  timestamp: string;
  user_id: string;
  heart_rate: number;
  hrv_ms: number;
  spo2_percent: number;
  skin_temp_c: number;
  respiratory_rate: number;
  blood_pressure_systolic: number | null;
  blood_pressure_diastolic: number | null;
  steps_per_minute: number;
  activity_level: number;
  calories_per_minute: number;
  posture: string;
  sleep_stage: string | null;
  hours_last_night: number;
  room_temp_c: number;
  humidity_percent: number;
  device_sources: string[];
}

export interface AlertData {
  alert_id: string;
  alert_type: string;
  user_id: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  start_time: string;
  end_time: string;
  avg_heart_rate: number;
  event_count: number;
  description: string;
}

export interface WebSocketMessage {
  type: 'vital' | 'alert' | 'initial_state' | 'heartbeat';
  data?: VitalData | AlertData | InitialState;
  timestamp?: string;
}

export interface InitialState {
  vitals: Array<{ type: 'vital'; data: VitalData }>;
  alerts: Array<{ type: 'alert'; data: AlertData }>;
}

export interface ConnectionState {
  status: 'connecting' | 'connected' | 'disconnected' | 'error';
  lastHeartbeat: Date | null;
  reconnectAttempts: number;
}

export interface ChartDataPoint {
  timestamp: string;
  time: string;
  heart_rate: number;
  hrv_ms: number;
  spo2_percent: number;
  skin_temp_c: number;
  activity_level: number;
}

export interface DashboardStats {
  eventsPerSecond: number;
  totalEvents: number;
  totalAlerts: number;
  criticalAlerts: number;
  uptime: number;
}

export type AlertSeverity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';

export const SEVERITY_COLORS: Record<AlertSeverity, string> = {
  CRITICAL: '#f85149',
  HIGH: '#d29922',
  MEDIUM: '#58a6ff',
  LOW: '#3fb950',
};

export const ALERT_TYPE_LABELS: Record<string, string> = {
  TACHYCARDIA_AT_REST: 'Tachycardia at Rest',
  LOW_SPO2_HYPOXIA: 'Low SpO2 / Hypoxia',
  ELEVATED_TEMPERATURE: 'Elevated Temperature',
  BURNOUT_STRESS: 'Burnout / Stress',
  DEHYDRATION: 'Dehydration Risk',
};

