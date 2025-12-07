/**
 * Main Dashboard Component
 * Integrates all health monitoring components
 */

import { useState } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import { VitalChart } from './VitalChart';
import { ThreatLog } from './ThreatLog';
import { WellnessGauge } from './WellnessGauge';
import { HealthChat } from './HealthChat';
import { Timeline } from './Timeline';
import { ControlPanel } from './ControlPanel';
import { 
  Activity, 
  Wifi, 
  WifiOff, 
  Heart, 
  Thermometer, 
  Wind,
  Droplets,
  Zap,
  Clock,
  TrendingUp,
  MessageSquare,
  Settings,
  LayoutGrid
} from 'lucide-react';

// API URLs from environment or defaults
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/vitals';
const CHAT_WS_URL = import.meta.env.VITE_CHAT_WS_URL || 'ws://localhost:8000/ws/chat';

function ConnectionStatus({ 
  status, 
  eventsPerSecond 
}: { 
  status: string; 
  eventsPerSecond: number;
}) {
  const isConnected = status === 'connected';
  
  return (
    <div className="flex items-center gap-4">
      <div className="flex items-center gap-2">
        {isConnected ? (
          <>
            <div className="relative">
              <Wifi size={18} className="text-vital-normal" />
              <div className="absolute -top-1 -right-1 w-2 h-2 bg-vital-normal rounded-full live-indicator" />
            </div>
            <span className="text-sm text-vital-normal font-medium">LIVE</span>
          </>
        ) : (
          <>
            <WifiOff size={18} className="text-vital-critical" />
            <span className="text-sm text-vital-critical font-medium">
              {status.toUpperCase()}
            </span>
          </>
        )}
      </div>
      {isConnected && (
        <div className="flex items-center gap-1 text-sm text-soc-muted">
          <Zap size={14} className="text-accent-cyan" />
          <span className="font-mono">{eventsPerSecond}</span>
          <span>evt/s</span>
        </div>
      )}
    </div>
  );
}

function VitalIndicator({ 
  icon: Icon, 
  label, 
  value, 
  unit,
  color = 'text-accent-cyan'
}: {
  icon: React.ElementType;
  label: string;
  value: string | number | null;
  unit: string;
  color?: string;
}) {
  return (
    <div className="flex items-center gap-3 bg-soc-panel/50 rounded-lg px-4 py-3 border border-soc-border/50">
      <Icon size={20} className={color} />
      <div>
        <div className="text-xs text-soc-muted uppercase tracking-wider">{label}</div>
        <div className="text-lg font-bold font-mono">
          {value ?? '--'} <span className="text-sm text-soc-muted font-normal">{unit}</span>
        </div>
      </div>
    </div>
  );
}

type ViewMode = 'dashboard' | 'chat' | 'control';

export function Dashboard() {
  const { vitals, alerts, latestVital, connectionState, eventsPerSecond } = useWebSocket(100);
  const [viewMode, setViewMode] = useState<ViewMode>('dashboard');
  const [showChat, setShowChat] = useState(true);
  
  const formatTime = () => {
    return new Date().toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  return (
    <div className="min-h-screen bg-soc-bg grid-bg">
      {/* Header */}
      <header className="border-b border-soc-border bg-soc-panel/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            {/* Logo & Title */}
            <div className="flex items-center gap-4">
              <div className="relative">
                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-accent-cyan to-accent-purple flex items-center justify-center glow-border">
                  <Activity size={24} className="text-white" />
                </div>
              </div>
              <div>
                <h1 className="text-2xl font-display font-bold tracking-widest text-accent-cyan">
                  TELARA
                </h1>
                <p className="text-xs text-soc-muted tracking-wider">
                  HEALTH SECURITY OPERATIONS CENTER
                </p>
              </div>
            </div>
            
            {/* View Mode Toggles */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => setViewMode('dashboard')}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
                  viewMode === 'dashboard'
                    ? 'bg-accent-cyan/20 text-accent-cyan'
                    : 'text-soc-muted hover:text-soc-text'
                }`}
              >
                <LayoutGrid size={16} />
                Dashboard
              </button>
              <button
                onClick={() => setShowChat(!showChat)}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
                  showChat
                    ? 'bg-accent-purple/20 text-accent-purple'
                    : 'text-soc-muted hover:text-soc-text'
                }`}
              >
                <MessageSquare size={16} />
                AI Coach
              </button>
              <button
                onClick={() => setViewMode(viewMode === 'control' ? 'dashboard' : 'control')}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
                  viewMode === 'control'
                    ? 'bg-vital-warning/20 text-vital-warning'
                    : 'text-soc-muted hover:text-soc-text'
                }`}
              >
                <Settings size={16} />
                Control
              </button>
            </div>
            
            {/* Connection Status & Time */}
            <div className="flex items-center gap-6">
              <ConnectionStatus 
                status={connectionState.status} 
                eventsPerSecond={eventsPerSecond}
              />
              <div className="flex items-center gap-2 text-soc-muted">
                <Clock size={16} />
                <span className="font-mono text-sm">{formatTime()}</span>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-6 py-6">
        {/* Quick Stats Bar */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-6">
          <VitalIndicator 
            icon={Heart} 
            label="Heart Rate" 
            value={latestVital?.heart_rate}
            unit="bpm"
            color="text-vital-critical"
          />
          <VitalIndicator 
            icon={TrendingUp} 
            label="HRV" 
            value={latestVital?.hrv_ms}
            unit="ms"
            color="text-accent-purple"
          />
          <VitalIndicator 
            icon={Droplets} 
            label="SpO2" 
            value={latestVital?.spo2_percent}
            unit="%"
            color="text-vital-info"
          />
          <VitalIndicator 
            icon={Thermometer} 
            label="Temperature" 
            value={latestVital?.skin_temp_c?.toFixed(1)}
            unit="°C"
            color="text-vital-warning"
          />
          <VitalIndicator 
            icon={Wind} 
            label="Resp. Rate" 
            value={latestVital?.respiratory_rate}
            unit="/min"
            color="text-accent-cyan"
          />
          <VitalIndicator 
            icon={Activity} 
            label="Activity" 
            value={latestVital?.activity_level}
            unit="lvl"
            color="text-vital-normal"
          />
        </div>

        {/* Main Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Left Column - Wellness Score & Control */}
          <div className="lg:col-span-1 space-y-4">
            <WellnessGauge apiUrl={API_URL} />
            
            {viewMode === 'control' && (
              <ControlPanel apiUrl={API_URL} />
            )}
            
            <Timeline 
              vitals={vitals}
              alerts={alerts}
              selectedMetric="heart_rate"
            />
          </div>

          {/* Center Column - Charts */}
          <div className="lg:col-span-2 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <VitalChart
                data={vitals}
                metric="heart_rate"
                title="Heart Rate"
                unit="bpm"
                color="#f85149"
                warningThreshold={100}
                criticalThreshold={120}
                normalRange={[60, 100]}
              />
              <VitalChart
                data={vitals}
                metric="hrv_ms"
                title="Heart Rate Variability"
                unit="ms"
                color="#a371f7"
                normalRange={[40, 70]}
              />
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <VitalChart
                data={vitals}
                metric="spo2_percent"
                title="Blood Oxygen (SpO2)"
                unit="%"
                color="#58a6ff"
                normalRange={[95, 100]}
              />
              <VitalChart
                data={vitals}
                metric="skin_temp_c"
                title="Body Temperature"
                unit="°C"
                color="#d29922"
                warningThreshold={37.5}
                criticalThreshold={38.5}
                normalRange={[36.0, 37.2]}
              />
            </div>

            {/* System Status Bar */}
            <div className="bg-soc-panel border border-soc-border rounded-lg p-4">
              <div className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-6">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-vital-normal live-indicator" />
                    <span className="text-soc-muted">Kafka</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-vital-normal live-indicator" />
                    <span className="text-soc-muted">Flink CEP</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-vital-normal live-indicator" />
                    <span className="text-soc-muted">Claude AI</span>
                  </div>
                </div>
                <div className="text-soc-muted font-mono">
                  Buffered: {vitals.length} vitals | {alerts.length} alerts
                </div>
              </div>
            </div>
          </div>

          {/* Right Column - Threat Log & Chat */}
          <div className="lg:col-span-1 space-y-4">
            {showChat ? (
              <div className="h-[400px]">
                <HealthChat 
                  wsUrl={CHAT_WS_URL}
                  apiUrl={API_URL}
                />
              </div>
            ) : null}
            
            <div className={showChat ? 'h-[300px]' : 'h-[600px]'}>
              <ThreatLog alerts={alerts} />
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-soc-border bg-soc-panel/50 mt-8">
        <div className="container mx-auto px-6 py-3">
          <div className="flex items-center justify-between text-xs text-soc-muted">
            <span>TELARA v2.0 | Palo Alto Networks Hackathon 2025</span>
            <span>Powered by Kafka + Flink + Claude AI + React</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

