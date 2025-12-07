/**
 * Main Dashboard Component
 * Integrates all health monitoring components including Tier 2 & 3 features
 * 
 * All tab data is preloaded on mount to avoid loading delays when switching tabs.
 * Components are rendered but hidden using CSS instead of conditional rendering.
 */

import { useState, useEffect } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import { VitalChart } from './VitalChart';
import { ThreatLog } from './ThreatLog';
import { WellnessGauge } from './WellnessGauge';
import { HealthChat } from './HealthChat';
import { Timeline } from './Timeline';
import { ControlModal } from './ControlModal';
import { CorrelationInsights } from './CorrelationInsights';
import { DailyDigest } from './DailyDigest';
import { PredictiveInsights } from './PredictiveInsights';
import { IntegrationDemo } from './IntegrationDemo';
import { WeekComparison } from './WeekComparison';
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
  Settings,
  LayoutGrid,
  Brain,
  Link2
} from 'lucide-react';

// API URLs from environment or defaults
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/vitals';
const CHAT_WS_URL = import.meta.env.VITE_CHAT_WS_URL || 'ws://localhost:8000/ws/chat';

// Preload AI insights data on app startup
const preloadData = async () => {
  const endpoints = [
    '/wellness/score',
    '/correlations?hours=24',
    '/predictions?max_hours=6',
    '/digest/daily',
    '/comparison/weekly'
  ];
  
  // Fire all requests in parallel, don't wait for them
  endpoints.forEach(endpoint => {
    fetch(`${API_URL}${endpoint}`).catch(() => {});
  });
};

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
  color = 'text-accent-cyan',
  sourceIcons = [],
  isFresh = true,
}: {
  icon: React.ElementType;
  label: string;
  value: string | number | null;
  unit: string;
  color?: string;
  sourceIcons?: string[];
  isFresh?: boolean;
}) {
  return (
    <div className={`flex items-center gap-3 bg-soc-panel/50 rounded-lg px-4 py-3 border border-soc-border/50 ${!isFresh ? 'opacity-60' : ''}`}>
      <Icon size={20} className={color} />
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className="text-xs text-soc-muted uppercase tracking-wider">{label}</span>
          {sourceIcons.length > 0 && (
            <span className="text-xs" title={`Sources: ${sourceIcons.join(', ')}`}>
              {sourceIcons.slice(0, 3).join('')}
            </span>
          )}
        </div>
        <div className="text-lg font-bold font-mono">
          {value ?? '--'} <span className="text-sm text-soc-muted font-normal">{unit}</span>
        </div>
      </div>
    </div>
  );
}

type ViewMode = 'dashboard' | 'insights' | 'integrations';

export function Dashboard() {
  const { vitals, alerts, latestVital, aggregatedState, connectionState, eventsPerSecond } = useWebSocket(100);
  const [viewMode, setViewMode] = useState<ViewMode>('dashboard');
  const [showControlModal, setShowControlModal] = useState(false);
  const [dataPreloaded, setDataPreloaded] = useState(false);
  
  // Helper to get aggregated metric value and source info
  const getAggregatedMetric = (metricName: string) => {
    if (aggregatedState?.vitals?.[metricName]) {
      const metric = aggregatedState.vitals[metricName];
      return {
        value: metric.value,
        sourceIcons: metric.source_icons || [],
        isFresh: metric.freshness_ms < 10000, // 10 second freshness
      };
    }
    return { value: null, sourceIcons: [], isFresh: true };
  };
  
  // Preload all data on mount for faster tab switching
  useEffect(() => {
    if (!dataPreloaded) {
      preloadData();
      setDataPreloaded(true);
    }
  }, [dataPreloaded]);
  
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
                onClick={() => setViewMode('insights')}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
                  viewMode === 'insights'
                    ? 'bg-accent-purple/20 text-accent-purple'
                    : 'text-soc-muted hover:text-soc-text'
                }`}
              >
                <Brain size={16} />
                AI Insights
              </button>
              <button
                onClick={() => setViewMode('integrations')}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
                  viewMode === 'integrations'
                    ? 'bg-vital-normal/20 text-vital-normal'
                    : 'text-soc-muted hover:text-soc-text'
                }`}
              >
                <Link2 size={16} />
                Integrations
              </button>
              <button
                onClick={() => setShowControlModal(true)}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
                  showControlModal
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
        {/* Quick Stats Bar - Multi-Source Aggregated Display */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-6">
          <VitalIndicator 
            icon={Heart} 
            label="Heart Rate" 
            value={getAggregatedMetric('heart_rate').value ?? latestVital?.heart_rate}
            unit="bpm"
            color="text-vital-critical"
            sourceIcons={getAggregatedMetric('heart_rate').sourceIcons}
            isFresh={getAggregatedMetric('heart_rate').isFresh}
          />
          <VitalIndicator 
            icon={TrendingUp} 
            label="HRV" 
            value={getAggregatedMetric('hrv_ms').value ?? latestVital?.hrv_ms}
            unit="ms"
            color="text-accent-purple"
            sourceIcons={getAggregatedMetric('hrv_ms').sourceIcons}
            isFresh={getAggregatedMetric('hrv_ms').isFresh}
          />
          <VitalIndicator 
            icon={Droplets} 
            label="SpO2" 
            value={getAggregatedMetric('spo2_percent').value ?? latestVital?.spo2_percent}
            unit="%"
            color="text-vital-info"
            sourceIcons={getAggregatedMetric('spo2_percent').sourceIcons}
            isFresh={getAggregatedMetric('spo2_percent').isFresh}
          />
          <VitalIndicator 
            icon={Thermometer} 
            label="Temperature" 
            value={getAggregatedMetric('skin_temp_c').value ?? latestVital?.skin_temp_c?.toFixed(1)}
            unit="°C"
            color="text-vital-warning"
            sourceIcons={getAggregatedMetric('skin_temp_c').sourceIcons}
            isFresh={getAggregatedMetric('skin_temp_c').isFresh}
          />
          <VitalIndicator 
            icon={Wind} 
            label="Resp. Rate" 
            value={getAggregatedMetric('respiratory_rate').value ?? latestVital?.respiratory_rate}
            unit="/min"
            color="text-accent-cyan"
            sourceIcons={getAggregatedMetric('respiratory_rate').sourceIcons}
            isFresh={getAggregatedMetric('respiratory_rate').isFresh}
          />
          <VitalIndicator 
            icon={Activity} 
            label="Activity" 
            value={getAggregatedMetric('activity_level').value ?? latestVital?.activity_level}
            unit="lvl"
            color="text-vital-normal"
            sourceIcons={getAggregatedMetric('activity_level').sourceIcons}
            isFresh={getAggregatedMetric('activity_level').isFresh}
          />
        </div>

        {/* AI Insights View - Full AI Features */}
        <div className={viewMode === 'insights' ? '' : 'hidden'}>
          <div className="space-y-6">
            {/* Health Chat - Prominent at top */}
            <div className="h-[400px]">
              <HealthChat 
                wsUrl={CHAT_WS_URL}
                apiUrl={API_URL}
              />
            </div>
            
            {/* AI Insights Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-1">
                <DailyDigest apiUrl={API_URL} />
              </div>
              <div className="lg:col-span-1">
                <PredictiveInsights apiUrl={API_URL} />
              </div>
              <div className="lg:col-span-1">
                <WeekComparison apiUrl={API_URL} />
              </div>
            </div>
            
            {/* Correlation Insights - Full width */}
            <CorrelationInsights apiUrl={API_URL} />
          </div>
        </div>

        {/* Integrations View */}
        <div className={viewMode === 'integrations' ? 'mb-6' : 'hidden'}>
          <IntegrationDemo />
        </div>

        {/* Dashboard View - Clean Data Focus */}
        <div className={viewMode === 'dashboard' ? '' : 'hidden'}>
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* Left Column - Wellness Score & Timeline */}
            <div className="lg:col-span-1 space-y-4">
              <WellnessGauge apiUrl={API_URL} />
              
              {/* Only show correlations on dashboard if not on insights tab */}
              {viewMode === 'dashboard' && <CorrelationInsights apiUrl={API_URL} />}
              
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

            {/* Right Column - Threat Log (Full height) */}
            <div className="lg:col-span-1">
              <div className="h-[700px]">
                <ThreatLog alerts={alerts} />
              </div>
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

      {/* Control Modal */}
      <ControlModal 
        apiUrl={API_URL}
        isOpen={showControlModal}
        onClose={() => setShowControlModal(false)}
      />
    </div>
  );
}
