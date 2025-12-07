/**
 * Integration Demo Component
 * Mock OAuth flows and data normalization pipeline for health data sources
 */

import { useState } from 'react';
import {
  Link2,
  CheckCircle2,
  Circle,
  ArrowRight,
  RefreshCw,
  Database,
  Zap,
  Shield,
  Clock,
  Heart,
  Activity,
  Moon,
  Watch,
  Smartphone,
  X
} from 'lucide-react';

interface DataSource {
  id: string;
  name: string;
  icon: string;
  color: string;
  connected: boolean;
  lastSync: string | null;
  dataTypes: string[];
  sampleFields: Record<string, string>;
}

interface IntegrationDemoProps {
  onClose?: () => void;
}

const DATA_SOURCES: DataSource[] = [
  {
    id: 'apple_health',
    name: 'Apple HealthKit',
    icon: '🍎',
    color: '#FF3B30',
    connected: false,
    lastSync: null,
    dataTypes: ['Heart Rate', 'HRV', 'Sleep', 'Steps', 'Workouts'],
    sampleFields: {
      'HKQuantityTypeIdentifierHeartRate': 'heart_rate',
      'HKQuantityTypeIdentifierHeartRateVariabilitySDNN': 'hrv_ms',
      'HKCategoryTypeIdentifierSleepAnalysis': 'sleep_hours',
      'HKQuantityTypeIdentifierStepCount': 'steps_per_minute',
    }
  },
  {
    id: 'google_fit',
    name: 'Google Fit',
    icon: '🏃',
    color: '#4285F4',
    connected: false,
    lastSync: null,
    dataTypes: ['Heart Rate', 'Steps', 'Calories', 'Activity'],
    sampleFields: {
      'com.google.heart_rate.bpm': 'heart_rate',
      'com.google.step_count.delta': 'steps_per_minute',
      'com.google.calories.expended': 'calories_per_minute',
      'com.google.activity.segment': 'activity_level',
    }
  },
  {
    id: 'oura',
    name: 'Oura Ring',
    icon: '💍',
    color: '#8B5CF6',
    connected: false,
    lastSync: null,
    dataTypes: ['HRV', 'Sleep', 'Readiness', 'Temperature'],
    sampleFields: {
      'rmssd': 'hrv_ms',
      'sleep.total': 'sleep_hours',
      'readiness.score': 'wellness_score',
      'temperature_delta': 'skin_temp_c',
    }
  },
];

function OAuthModal({
  source,
  onConnect,
  onCancel
}: {
  source: DataSource;
  onConnect: () => void;
  onCancel: () => void;
}) {
  const [connecting, setConnecting] = useState(false);

  const handleConnect = async () => {
    setConnecting(true);
    // Simulate OAuth flow
    await new Promise(resolve => setTimeout(resolve, 1500));
    onConnect();
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-soc-panel border border-soc-border rounded-xl max-w-md w-full p-6 animate-slide-in">
        {/* Header */}
        <div className="text-center mb-6">
          <div 
            className="w-16 h-16 rounded-2xl flex items-center justify-center text-3xl mx-auto mb-4"
            style={{ backgroundColor: `${source.color}20` }}
          >
            {source.icon}
          </div>
          <h3 className="text-xl font-bold text-soc-text">
            Connect {source.name}
          </h3>
          <p className="text-sm text-soc-muted mt-2">
            Authorize Telara to access your health data
          </p>
        </div>

        {/* Permissions */}
        <div className="space-y-3 mb-6">
          <div className="text-xs text-soc-muted uppercase tracking-wider">
            Telara will access:
          </div>
          {source.dataTypes.map((type) => (
            <div key={type} className="flex items-center gap-3 text-sm">
              <CheckCircle2 size={16} className="text-vital-normal" />
              <span className="text-soc-text">{type}</span>
            </div>
          ))}
        </div>

        {/* Security note */}
        <div className="flex items-start gap-3 p-3 bg-accent-cyan/10 rounded-lg mb-6">
          <Shield size={18} className="text-accent-cyan mt-0.5" />
          <div className="text-xs text-soc-muted">
            <span className="text-accent-cyan font-medium">Secure Connection</span>
            <p className="mt-1">
              Your data is encrypted and you can revoke access at any time.
            </p>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <button
            onClick={onCancel}
            className="flex-1 px-4 py-2 border border-soc-border rounded-lg text-soc-muted hover:bg-soc-border transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleConnect}
            disabled={connecting}
            className="flex-1 px-4 py-2 rounded-lg text-white font-medium transition-colors flex items-center justify-center gap-2"
            style={{ backgroundColor: source.color }}
          >
            {connecting ? (
              <>
                <RefreshCw size={16} className="animate-spin" />
                Connecting...
              </>
            ) : (
              <>
                <Link2 size={16} />
                Connect
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

function DataNormalizationView({ sources }: { sources: DataSource[] }) {
  const connectedSources = sources.filter(s => s.connected);

  if (connectedSources.length === 0) {
    return null;
  }

  return (
    <div className="mt-6 p-4 bg-soc-bg/50 rounded-lg border border-soc-border/50">
      <div className="flex items-center gap-2 mb-4">
        <Database size={16} className="text-accent-purple" />
        <span className="text-sm font-medium text-soc-text">
          Data Normalization Pipeline
        </span>
      </div>

      {/* Pipeline visualization */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2">
        {/* Source nodes */}
        <div className="flex flex-col gap-1 flex-shrink-0">
          {connectedSources.map((source) => (
            <div 
              key={source.id}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs"
              style={{ backgroundColor: `${source.color}20`, color: source.color }}
            >
              <span>{source.icon}</span>
              <span className="font-medium">{source.name}</span>
            </div>
          ))}
        </div>

        {/* Arrow */}
        <div className="flex-shrink-0 flex items-center">
          <div className="w-8 h-px bg-soc-border" />
          <ArrowRight size={16} className="text-soc-muted" />
        </div>

        {/* Transform */}
        <div className="flex-shrink-0 px-4 py-3 bg-accent-cyan/10 border border-accent-cyan/30 rounded-lg">
          <div className="text-xs text-accent-cyan font-medium mb-1">
            Normalize & Transform
          </div>
          <div className="text-[10px] text-soc-muted space-y-0.5">
            <div>• Unit conversion</div>
            <div>• Field mapping</div>
            <div>• Deduplication</div>
          </div>
        </div>

        {/* Arrow */}
        <div className="flex-shrink-0 flex items-center">
          <div className="w-8 h-px bg-soc-border" />
          <ArrowRight size={16} className="text-soc-muted" />
        </div>

        {/* Unified schema */}
        <div className="flex-shrink-0 px-4 py-3 bg-vital-normal/10 border border-vital-normal/30 rounded-lg">
          <div className="text-xs text-vital-normal font-medium mb-1">
            Unified Schema
          </div>
          <div className="text-[10px] text-soc-muted space-y-0.5">
            <div className="flex items-center gap-1">
              <Heart size={10} /> heart_rate
            </div>
            <div className="flex items-center gap-1">
              <Activity size={10} /> hrv_ms
            </div>
            <div className="flex items-center gap-1">
              <Moon size={10} /> sleep_hours
            </div>
          </div>
        </div>

        {/* Arrow */}
        <div className="flex-shrink-0 flex items-center">
          <div className="w-8 h-px bg-soc-border" />
          <ArrowRight size={16} className="text-soc-muted" />
        </div>

        {/* Output */}
        <div className="flex-shrink-0 px-4 py-3 bg-accent-purple/10 border border-accent-purple/30 rounded-lg">
          <div className="text-xs text-accent-purple font-medium mb-1">
            AI Analysis
          </div>
          <div className="text-[10px] text-soc-muted space-y-0.5">
            <div>• Correlations</div>
            <div>• Predictions</div>
            <div>• Insights</div>
          </div>
        </div>
      </div>

      {/* Field mapping examples */}
      <div className="mt-4 pt-4 border-t border-soc-border/50">
        <div className="text-xs text-soc-muted mb-2">Sample Field Mappings:</div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {connectedSources.slice(0, 2).map((source) => (
            Object.entries(source.sampleFields).slice(0, 2).map(([from, to]) => (
              <div 
                key={from}
                className="flex items-center gap-2 text-[10px] font-mono bg-soc-bg p-1.5 rounded"
              >
                <span style={{ color: source.color }}>{from}</span>
                <ArrowRight size={10} className="text-soc-muted" />
                <span className="text-vital-normal">{to}</span>
              </div>
            ))
          ))}
        </div>
      </div>
    </div>
  );
}

function SourceCard({
  source,
  onConnect,
  onDisconnect
}: {
  source: DataSource;
  onConnect: () => void;
  onDisconnect: () => void;
}) {
  return (
    <div 
      className={`p-4 rounded-lg border transition-colors ${
        source.connected 
          ? 'bg-soc-bg border-vital-normal/50' 
          : 'bg-soc-bg/50 border-soc-border/50 hover:border-soc-border'
      }`}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div 
            className="w-10 h-10 rounded-lg flex items-center justify-center text-xl"
            style={{ backgroundColor: `${source.color}20` }}
          >
            {source.icon}
          </div>
          <div>
            <div className="font-medium text-soc-text">{source.name}</div>
            <div className="text-xs text-soc-muted">
              {source.dataTypes.slice(0, 3).join(', ')}
            </div>
          </div>
        </div>
        
        {source.connected ? (
          <button
            onClick={onDisconnect}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-vital-normal bg-vital-normal/10 rounded-lg hover:bg-vital-normal/20 transition-colors"
          >
            <CheckCircle2 size={14} />
            Connected
          </button>
        ) : (
          <button
            onClick={onConnect}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-soc-muted bg-soc-border/50 rounded-lg hover:bg-soc-border transition-colors"
          >
            <Link2 size={14} />
            Connect
          </button>
        )}
      </div>

      {source.connected && source.lastSync && (
        <div className="flex items-center gap-1.5 text-xs text-soc-muted">
          <Clock size={12} />
          Last synced: {source.lastSync}
        </div>
      )}
    </div>
  );
}

export function IntegrationDemo({ onClose }: IntegrationDemoProps) {
  const [sources, setSources] = useState<DataSource[]>(DATA_SOURCES);
  const [connectingSource, setConnectingSource] = useState<DataSource | null>(null);

  const handleConnect = (sourceId: string) => {
    setSources(prev => prev.map(s => 
      s.id === sourceId 
        ? { ...s, connected: true, lastSync: 'Just now' }
        : s
    ));
    setConnectingSource(null);
  };

  const handleDisconnect = (sourceId: string) => {
    setSources(prev => prev.map(s =>
      s.id === sourceId
        ? { ...s, connected: false, lastSync: null }
        : s
    ));
  };

  const connectedCount = sources.filter(s => s.connected).length;

  return (
    <div className="bg-soc-panel border border-soc-border rounded-lg overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-soc-border bg-gradient-to-r from-accent-purple/10 to-accent-cyan/10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Link2 size={18} className="text-accent-purple" />
            <h3 className="text-sm font-medium text-soc-text">
              Data Source Integrations
            </h3>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-soc-muted">
              {connectedCount} of {sources.length} connected
            </span>
            {onClose && (
              <button
                onClick={onClose}
                className="p-1 hover:bg-soc-border rounded transition-colors"
              >
                <X size={16} className="text-soc-muted" />
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="p-4">
        {/* Info banner */}
        <div className="flex items-start gap-3 p-3 bg-accent-cyan/10 border border-accent-cyan/30 rounded-lg mb-4">
          <Smartphone size={18} className="text-accent-cyan mt-0.5" />
          <div className="text-xs">
            <span className="text-accent-cyan font-medium">Multi-Source Health Data</span>
            <p className="text-soc-muted mt-1">
              Connect your health devices and apps to unify all your biometric data in one place.
              Telara normalizes data from different sources into a unified schema for AI analysis.
            </p>
          </div>
        </div>

        {/* Source cards */}
        <div className="space-y-3">
          {sources.map((source) => (
            <SourceCard
              key={source.id}
              source={source}
              onConnect={() => setConnectingSource(source)}
              onDisconnect={() => handleDisconnect(source.id)}
            />
          ))}
        </div>

        {/* Normalization pipeline */}
        <DataNormalizationView sources={sources} />

        {/* Architecture note */}
        <div className="mt-4 p-3 bg-soc-bg/30 rounded-lg border border-soc-border/30">
          <div className="flex items-center gap-2 text-xs text-soc-muted">
            <Watch size={14} className="text-accent-purple" />
            <span>
              Demo mode: In production, this would integrate with real OAuth2 flows 
              and streaming data pipelines.
            </span>
          </div>
        </div>
      </div>

      {/* OAuth Modal */}
      {connectingSource && (
        <OAuthModal
          source={connectingSource}
          onConnect={() => handleConnect(connectingSource.id)}
          onCancel={() => setConnectingSource(null)}
        />
      )}
    </div>
  );
}

