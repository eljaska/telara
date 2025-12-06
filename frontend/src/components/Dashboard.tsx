/**
 * Main Dashboard Component
 */

import { useWebSocket } from '../hooks/useWebSocket';
import { VitalChart } from './VitalChart';
import { ThreatLog } from './ThreatLog';
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
  TrendingUp
} from 'lucide-react';

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

export function Dashboard() {
  const { vitals, alerts, latestVital, connectionState, eventsPerSecond } = useWebSocket(100);
  
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
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Charts Panel - 2 columns */}
          <div className="lg:col-span-2 space-y-4">
            {/* Primary Charts Row */}
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
            
            {/* Secondary Charts Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <VitalChart
                data={vitals}
                metric="spo2_percent"
                title="Blood Oxygen (SpO2)"
                unit="%"
                color="#58a6ff"
                warningThreshold={undefined}
                criticalThreshold={undefined}
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
                    <span className="text-soc-muted">WebSocket</span>
                  </div>
                </div>
                <div className="text-soc-muted font-mono">
                  Events buffered: {vitals.length} | Active patterns: 3
                </div>
              </div>
            </div>
          </div>

          {/* Threat Log Panel - 1 column */}
          <div className="lg:col-span-1 h-[600px]">
            <ThreatLog alerts={alerts} />
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-soc-border bg-soc-panel/50 mt-8">
        <div className="container mx-auto px-6 py-3">
          <div className="flex items-center justify-between text-xs text-soc-muted">
            <span>TELARA v1.0 | Palo Alto Networks Hackathon 2025</span>
            <span>Powered by Apache Kafka + Flink + FastAPI + React</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

