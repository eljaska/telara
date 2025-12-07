/**
 * Control Panel Component
 * Controls for data generator: start/stop, anomaly injection
 */

import { useState, useEffect } from 'react';
import { 
  Play, 
  Pause, 
  Zap, 
  Heart, 
  Thermometer, 
  Wind,
  AlertTriangle,
  Droplets,
  RefreshCw
} from 'lucide-react';

interface GeneratorStatus {
  running: boolean;
  events_generated: number;
  anomaly_active: string | null;
  anomaly_end_time: number | null;
}

interface ControlPanelProps {
  apiUrl: string;
}

const ANOMALY_TYPES = [
  { 
    id: 'tachycardia_at_rest', 
    label: 'Tachycardia', 
    icon: Heart, 
    color: '#f85149',
    description: 'High HR while sedentary'
  },
  { 
    id: 'hypoxia', 
    label: 'Low SpO2', 
    icon: Wind, 
    color: '#58a6ff',
    description: 'Blood oxygen drop'
  },
  { 
    id: 'fever_onset', 
    label: 'Fever', 
    icon: Thermometer, 
    color: '#d29922',
    description: 'Elevated temperature'
  },
  { 
    id: 'burnout_stress', 
    label: 'Stress', 
    icon: AlertTriangle, 
    color: '#a371f7',
    description: 'Low HRV pattern'
  },
  { 
    id: 'dehydration', 
    label: 'Dehydration', 
    icon: Droplets, 
    color: '#39c5cf',
    description: 'Elevated HR, low BP'
  },
];

export function ControlPanel({ apiUrl }: ControlPanelProps) {
  const [status, setStatus] = useState<GeneratorStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [duration, setDuration] = useState(30);
  const [activeInjection, setActiveInjection] = useState<string | null>(null);

  const fetchStatus = async () => {
    try {
      const response = await fetch(`${apiUrl}/generator/status`);
      const data = await response.json();
      setStatus(data);
      setActiveInjection(data.anomaly_active);
    } catch (error) {
      console.error('Failed to fetch generator status:', error);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 2000);
    return () => clearInterval(interval);
  }, [apiUrl]);

  const handleToggle = async () => {
    setLoading(true);
    try {
      const endpoint = status?.running ? 'stop' : 'start';
      await fetch(`${apiUrl}/generator/${endpoint}`, { method: 'POST' });
      await fetchStatus();
    } catch (error) {
      console.error('Failed to toggle generator:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleInject = async (anomalyType: string) => {
    setLoading(true);
    try {
      await fetch(`${apiUrl}/generator/inject/${anomalyType}?duration=${duration}`, {
        method: 'POST',
      });
      setActiveInjection(anomalyType);
      await fetchStatus();
    } catch (error) {
      console.error('Failed to inject anomaly:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-soc-panel border border-soc-border rounded-lg p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-soc-muted uppercase tracking-wider">
          Data Generator Control
        </h3>
        <button
          onClick={fetchStatus}
          className="p-1 hover:bg-soc-border rounded transition-colors"
          title="Refresh status"
        >
          <RefreshCw size={14} className="text-soc-muted" />
        </button>
      </div>

      {/* Status & Toggle */}
      <div className="flex items-center justify-between mb-4 p-3 bg-soc-bg rounded-lg">
        <div className="flex items-center gap-3">
          <div 
            className={`w-3 h-3 rounded-full ${
              status?.running ? 'bg-vital-normal live-indicator' : 'bg-soc-muted'
            }`}
          />
          <div>
            <div className="text-sm font-medium">
              {status?.running ? 'Running' : 'Stopped'}
            </div>
            <div className="text-xs text-soc-muted">
              {status?.events_generated?.toLocaleString() ?? 0} events
            </div>
          </div>
        </div>
        <button
          onClick={handleToggle}
          disabled={loading}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-all ${
            status?.running
              ? 'bg-vital-critical/20 text-vital-critical hover:bg-vital-critical/30'
              : 'bg-vital-normal/20 text-vital-normal hover:bg-vital-normal/30'
          } disabled:opacity-50`}
        >
          {status?.running ? (
            <>
              <Pause size={16} />
              Stop
            </>
          ) : (
            <>
              <Play size={16} />
              Start
            </>
          )}
        </button>
      </div>

      {/* Active Anomaly Indicator */}
      {activeInjection && (
        <div className="mb-4 p-3 bg-vital-warning/10 border border-vital-warning/30 rounded-lg">
          <div className="flex items-center gap-2 text-vital-warning text-sm">
            <Zap size={16} className="animate-pulse" />
            <span>Anomaly Active: <strong>{activeInjection.replace(/_/g, ' ')}</strong></span>
          </div>
        </div>
      )}

      {/* Duration Slider */}
      <div className="mb-4">
        <label className="block text-xs text-soc-muted mb-2">
          Injection Duration: <span className="text-soc-text font-mono">{duration}s</span>
        </label>
        <input
          type="range"
          min="15"
          max="120"
          step="15"
          value={duration}
          onChange={(e) => setDuration(parseInt(e.target.value))}
          className="w-full h-2 bg-soc-border rounded-lg appearance-none cursor-pointer accent-accent-cyan"
        />
        <div className="flex justify-between text-xs text-soc-muted mt-1">
          <span>15s</span>
          <span>120s</span>
        </div>
      </div>

      {/* Anomaly Injection Buttons */}
      <div className="space-y-2">
        <label className="block text-xs text-soc-muted mb-2">
          Inject Anomaly Pattern
        </label>
        <div className="grid grid-cols-2 gap-2">
          {ANOMALY_TYPES.map((anomaly) => {
            const Icon = anomaly.icon;
            const isActive = activeInjection === anomaly.id;
            
            return (
              <button
                key={anomaly.id}
                onClick={() => handleInject(anomaly.id)}
                disabled={loading || !status?.running || isActive}
                className={`flex items-center gap-2 p-2 rounded-lg text-left transition-all border ${
                  isActive
                    ? 'border-vital-warning bg-vital-warning/10'
                    : 'border-soc-border hover:border-soc-muted bg-soc-bg'
                } disabled:opacity-50 disabled:cursor-not-allowed`}
                title={anomaly.description}
              >
                <Icon 
                  size={16} 
                  style={{ color: isActive ? '#d29922' : anomaly.color }} 
                />
                <div>
                  <div className="text-xs font-medium">{anomaly.label}</div>
                  <div className="text-[10px] text-soc-muted">{anomaly.description}</div>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Warning */}
      {!status?.running && (
        <div className="mt-4 text-xs text-soc-muted text-center">
          Start the generator to inject anomalies
        </div>
      )}
    </div>
  );
}

