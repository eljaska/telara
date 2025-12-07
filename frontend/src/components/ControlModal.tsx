/**
 * Control Modal Component
 * Modal overlay for data generator controls and historical data generation
 */

import { useState, useEffect } from 'react';
import { 
  X,
  Play, 
  Pause, 
  Zap, 
  Heart, 
  Thermometer, 
  Wind,
  AlertTriangle,
  Droplets,
  RefreshCw,
  History,
  Calendar,
  TrendingUp,
  TrendingDown,
  Minus,
  Loader2,
  Database,
  CheckCircle2
} from 'lucide-react';

interface GeneratorStatus {
  running: boolean;
  events_generated: number;
  anomaly_active: string | null;
  anomaly_end_time: number | null;
}

interface ControlModalProps {
  apiUrl: string;
  isOpen: boolean;
  onClose: () => void;
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

const PATTERN_OPTIONS = [
  { id: 'normal', label: 'Normal', icon: Minus, description: 'Stable baseline metrics' },
  { id: 'improving', label: 'Improving', icon: TrendingUp, description: 'Gradual improvement over time' },
  { id: 'declining', label: 'Declining', icon: TrendingDown, description: 'Gradual decline over time' },
  { id: 'variable', label: 'Variable', icon: Zap, description: 'Random day-to-day variation' },
];

export function ControlModal({ apiUrl, isOpen, onClose }: ControlModalProps) {
  const [status, setStatus] = useState<GeneratorStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [duration, setDuration] = useState(30);
  const [activeInjection, setActiveInjection] = useState<string | null>(null);
  
  // Historical data state
  const [historicalDays, setHistoricalDays] = useState(7);
  const [historicalPattern, setHistoricalPattern] = useState('normal');
  const [generatingHistorical, setGeneratingHistorical] = useState(false);
  const [historicalResult, setHistoricalResult] = useState<{
    success: boolean;
    message: string;
    inserted?: number;
  } | null>(null);

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
    if (isOpen) {
      fetchStatus();
      const interval = setInterval(fetchStatus, 2000);
      return () => clearInterval(interval);
    }
  }, [isOpen, apiUrl]);

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

  const handleGenerateHistorical = async () => {
    setGeneratingHistorical(true);
    setHistoricalResult(null);
    
    try {
      const response = await fetch(`${apiUrl}/generator/historical`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          days: historicalDays,
          events_per_hour: 60, // Reduced for faster generation
          include_anomalies: true,
          anomaly_probability: 0.05,
          pattern: historicalPattern
        })
      });
      
      const data = await response.json();
      
      if (response.ok) {
        setHistoricalResult({
          success: true,
          message: data.message,
          inserted: data.inserted
        });
      } else {
        setHistoricalResult({
          success: false,
          message: data.detail || 'Generation failed'
        });
      }
    } catch (error) {
      setHistoricalResult({
        success: false,
        message: error instanceof Error ? error.message : 'Unknown error'
      });
    } finally {
      setGeneratingHistorical(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div 
      className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-soc-panel border border-soc-border rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto animate-slide-in">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-soc-border bg-gradient-to-r from-vital-warning/10 to-accent-cyan/10">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-vital-warning/20 rounded-lg">
              <Zap size={20} className="text-vital-warning" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-soc-text">Generator Control</h2>
              <p className="text-xs text-soc-muted">Manage data generation & historical data</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-soc-border rounded-lg transition-colors"
          >
            <X size={20} className="text-soc-muted" />
          </button>
        </div>

        <div className="p-4 space-y-6">
          {/* Generator Status & Toggle */}
          <div className="bg-soc-bg rounded-lg p-4 border border-soc-border">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-medium text-soc-muted uppercase tracking-wider">
                Real-Time Generator
              </h3>
              <button
                onClick={fetchStatus}
                className="p-1 hover:bg-soc-border rounded transition-colors"
                title="Refresh status"
              >
                <RefreshCw size={14} className="text-soc-muted" />
              </button>
            </div>
            
            <div className="flex items-center justify-between">
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
                    {status?.events_generated?.toLocaleString() ?? 0} events generated
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
          </div>

          {/* Active Anomaly Indicator */}
          {activeInjection && (
            <div className="p-3 bg-vital-warning/10 border border-vital-warning/30 rounded-lg">
              <div className="flex items-center gap-2 text-vital-warning text-sm">
                <Zap size={16} className="animate-pulse" />
                <span>Anomaly Active: <strong>{activeInjection.replace(/_/g, ' ')}</strong></span>
              </div>
            </div>
          )}

          {/* Anomaly Injection */}
          <div className="bg-soc-bg rounded-lg p-4 border border-soc-border">
            <h3 className="text-sm font-medium text-soc-muted uppercase tracking-wider mb-4">
              Inject Anomaly Pattern
            </h3>
            
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

            {/* Anomaly Buttons */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {ANOMALY_TYPES.map((anomaly) => {
                const Icon = anomaly.icon;
                const isActive = activeInjection === anomaly.id;
                
                return (
                  <button
                    key={anomaly.id}
                    onClick={() => handleInject(anomaly.id)}
                    disabled={loading || !status?.running || isActive}
                    className={`flex items-center gap-2 p-3 rounded-lg text-left transition-all border ${
                      isActive
                        ? 'border-vital-warning bg-vital-warning/10'
                        : 'border-soc-border hover:border-soc-muted bg-soc-panel'
                    } disabled:opacity-50 disabled:cursor-not-allowed`}
                    title={anomaly.description}
                  >
                    <Icon 
                      size={18} 
                      style={{ color: isActive ? '#d29922' : anomaly.color }} 
                    />
                    <div>
                      <div className="text-sm font-medium">{anomaly.label}</div>
                      <div className="text-[10px] text-soc-muted">{anomaly.description}</div>
                    </div>
                  </button>
                );
              })}
            </div>

            {!status?.running && (
              <div className="mt-4 text-xs text-soc-muted text-center">
                Start the generator to inject anomalies
              </div>
            )}
          </div>

          {/* Historical Data Generation */}
          <div className="bg-soc-bg rounded-lg p-4 border border-soc-border">
            <div className="flex items-center gap-2 mb-4">
              <History size={18} className="text-accent-purple" />
              <h3 className="text-sm font-medium text-soc-muted uppercase tracking-wider">
                Generate Historical Data
              </h3>
            </div>
            
            <p className="text-xs text-soc-muted mb-4">
              Generate backdated biometric data to enable AI insights like Daily Digest and Weekly Comparison.
            </p>
            
            {/* Days Selection */}
            <div className="mb-4">
              <label className="block text-xs text-soc-muted mb-2">Days of History</label>
              <div className="flex gap-2">
                {[7, 14, 30].map((days) => (
                  <button
                    key={days}
                    onClick={() => setHistoricalDays(days)}
                    className={`flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-sm transition-colors ${
                      historicalDays === days
                        ? 'bg-accent-purple/20 text-accent-purple border border-accent-purple/30'
                        : 'bg-soc-panel border border-soc-border text-soc-muted hover:text-soc-text'
                    }`}
                  >
                    <Calendar size={14} />
                    {days} days
                  </button>
                ))}
              </div>
            </div>
            
            {/* Pattern Selection */}
            <div className="mb-4">
              <label className="block text-xs text-soc-muted mb-2">Data Pattern</label>
              <div className="grid grid-cols-2 gap-2">
                {PATTERN_OPTIONS.map((pattern) => {
                  const Icon = pattern.icon;
                  return (
                    <button
                      key={pattern.id}
                      onClick={() => setHistoricalPattern(pattern.id)}
                      className={`flex items-center gap-2 p-2 rounded-lg text-left text-sm transition-colors ${
                        historicalPattern === pattern.id
                          ? 'bg-accent-cyan/20 text-accent-cyan border border-accent-cyan/30'
                          : 'bg-soc-panel border border-soc-border text-soc-muted hover:text-soc-text'
                      }`}
                    >
                      <Icon size={14} />
                      <div>
                        <div className="font-medium">{pattern.label}</div>
                        <div className="text-[10px] opacity-70">{pattern.description}</div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
            
            {/* Generate Button */}
            <button
              onClick={handleGenerateHistorical}
              disabled={generatingHistorical}
              className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-accent-purple/20 hover:bg-accent-purple/30 text-accent-purple rounded-lg font-medium transition-colors disabled:opacity-50"
            >
              {generatingHistorical ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  Generating ~{(historicalDays * 24 * 60).toLocaleString()} events...
                </>
              ) : (
                <>
                  <Database size={18} />
                  Generate {historicalDays} Days (~{(historicalDays * 24 * 60).toLocaleString()} records)
                </>
              )}
            </button>
            
            {/* Result Message */}
            {historicalResult && (
              <div className={`mt-3 p-3 rounded-lg flex items-start gap-2 ${
                historicalResult.success
                  ? 'bg-vital-normal/10 border border-vital-normal/30'
                  : 'bg-vital-critical/10 border border-vital-critical/30'
              }`}>
                {historicalResult.success ? (
                  <CheckCircle2 size={16} className="text-vital-normal mt-0.5" />
                ) : (
                  <AlertTriangle size={16} className="text-vital-critical mt-0.5" />
                )}
                <div className={`text-sm ${historicalResult.success ? 'text-vital-normal' : 'text-vital-critical'}`}>
                  {historicalResult.message}
                  {historicalResult.inserted && (
                    <div className="text-xs mt-1 opacity-80">
                      {historicalResult.inserted.toLocaleString()} records inserted
                    </div>
                  )}
                </div>
              </div>
            )}
            
            {/* Info note */}
            <div className="mt-3 text-xs text-soc-muted text-center">
              Data includes circadian patterns (lower HR at night) and random anomalies
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

