/**
 * Integration Demo Component
 * Real integration with multi-source Kafka topics for health data sources
 */

import { useState, useEffect, useCallback } from 'react';
import {
  Link2,
  CheckCircle2,
  ArrowRight,
  RefreshCw,
  Database,
  Shield,
  Clock,
  Heart,
  Activity,
  Moon,
  Watch,
  Smartphone,
  X,
  AlertCircle,
  Loader2
} from 'lucide-react';

// API URL from environment
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface DataSource {
  id: string;
  name: string;
  icon: string;
  color: string;
  connected: boolean;
  enabled: boolean;
  lastSync: string | null;
  eventsReceived: number;
  dataTypes: string[];
  sampleFields: Record<string, string>;
  loading?: boolean;
}

interface IntegrationDemoProps {
  onClose?: () => void;
}

// Map API source IDs to our display format
const SOURCE_ID_MAP: Record<string, string> = {
  'apple': 'apple_health',
  'google': 'google_fit',
  'oura': 'oura',
};

const REVERSE_SOURCE_ID_MAP: Record<string, string> = {
  'apple_health': 'apple',
  'google_fit': 'google',
  'oura': 'oura',
};

// Initial source configurations (will be updated from API)
const INITIAL_SOURCES: DataSource[] = [
  {
    id: 'apple_health',
    name: 'Apple HealthKit',
    icon: '🍎',
    color: '#FF3B30',
    connected: true, // Default to connected
    enabled: true,
    lastSync: null,
    eventsReceived: 0,
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
    connected: true,
    enabled: true,
    lastSync: null,
    eventsReceived: 0,
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
    connected: true,
    enabled: true,
    lastSync: null,
    eventsReceived: 0,
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
  const [error, setError] = useState<string | null>(null);

  const handleConnect = async () => {
    setConnecting(true);
    setError(null);
    
    try {
      // Call the actual API to connect the source
      const apiSourceId = REVERSE_SOURCE_ID_MAP[source.id] || source.id;
      const response = await fetch(`${API_URL}/sources/${apiSourceId}/connect`, {
        method: 'POST',
      });
      
      if (!response.ok) {
        throw new Error('Failed to connect source');
      }
      
      onConnect();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Connection failed');
      setConnecting(false);
    }
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
            Enable real-time health data streaming via Kafka
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
            <span className="text-accent-cyan font-medium">Multi-Source Integration</span>
            <p className="mt-1">
              Each source has its own Kafka topic for isolated, reliable data streaming.
            </p>
          </div>
        </div>

        {/* Error message */}
        {error && (
          <div className="flex items-center gap-2 p-3 bg-vital-critical/10 border border-vital-critical/30 rounded-lg mb-4 text-xs text-vital-critical">
            <AlertCircle size={16} />
            {error}
          </div>
        )}

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
    return (
      <div className="mt-6 p-4 bg-soc-bg/50 rounded-lg border border-soc-border/50 text-center">
        <p className="text-sm text-soc-muted">
          Connect at least one source to see the data normalization pipeline.
        </p>
      </div>
    );
  }

  return (
    <div className="mt-6 p-4 bg-soc-bg/50 rounded-lg border border-soc-border/50">
      <div className="flex items-center gap-2 mb-4">
        <Database size={16} className="text-accent-purple" />
        <span className="text-sm font-medium text-soc-text">
          Multi-Source Data Pipeline
        </span>
        <span className="text-xs text-vital-normal ml-auto">
          {connectedSources.reduce((sum, s) => sum + s.eventsReceived, 0)} events processed
        </span>
      </div>

      {/* Pipeline visualization */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2">
        {/* Source nodes with Kafka topics */}
        <div className="flex flex-col gap-1 flex-shrink-0">
          {connectedSources.map((source) => (
            <div 
              key={source.id}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs"
              style={{ backgroundColor: `${source.color}20`, color: source.color }}
            >
              <span>{source.icon}</span>
              <span className="font-medium">{source.name}</span>
              <span className="text-[10px] opacity-70">
                ({source.eventsReceived})
              </span>
            </div>
          ))}
        </div>

        {/* Arrow with Kafka label */}
        <div className="flex-shrink-0 flex flex-col items-center">
          <div className="text-[9px] text-soc-muted mb-1">Kafka</div>
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
            <div>• Source attribution</div>
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
            className="w-10 h-10 rounded-lg flex items-center justify-center text-xl relative"
            style={{ backgroundColor: `${source.color}20` }}
          >
            {source.icon}
            {source.connected && (
              <div className="absolute -bottom-1 -right-1 w-3 h-3 bg-vital-normal rounded-full border-2 border-soc-panel" />
            )}
          </div>
          <div>
            <div className="font-medium text-soc-text">{source.name}</div>
            <div className="text-xs text-soc-muted">
              {source.dataTypes.slice(0, 3).join(', ')}
            </div>
          </div>
        </div>
        
        {source.loading ? (
          <div className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-soc-muted">
            <Loader2 size={14} className="animate-spin" />
            Processing...
          </div>
        ) : source.connected ? (
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

      {source.connected && (
        <div className="flex items-center justify-between text-xs text-soc-muted">
          <div className="flex items-center gap-1.5">
            <Clock size={12} />
            {source.lastSync ? `Last: ${source.lastSync}` : 'Streaming...'}
          </div>
          <div className="flex items-center gap-1.5">
            <Activity size={12} className="text-vital-normal" />
            {source.eventsReceived.toLocaleString()} events
          </div>
        </div>
      )}
    </div>
  );
}

export function IntegrationDemo({ onClose }: IntegrationDemoProps) {
  const [sources, setSources] = useState<DataSource[]>(INITIAL_SOURCES);
  const [connectingSource, setConnectingSource] = useState<DataSource | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch initial source status from API
  const fetchSourceStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/sources`);
      if (!response.ok) throw new Error('Failed to fetch sources');
      
      const data = await response.json();
      
      setSources(prev => prev.map(source => {
        const apiSourceId = REVERSE_SOURCE_ID_MAP[source.id] || source.id;
        const apiSource = data.sources?.find((s: any) => s.id === apiSourceId);
        
        if (apiSource) {
          return {
            ...source,
            connected: apiSource.connected ?? apiSource.enabled ?? true,
            enabled: apiSource.enabled ?? true,
            eventsReceived: apiSource.events_received ?? 0,
            lastSync: apiSource.last_event_time 
              ? new Date(apiSource.last_event_time).toLocaleTimeString()
              : null,
          };
        }
        return source;
      }));
      
      setError(null);
    } catch (err) {
      console.error('Error fetching sources:', err);
      // Don't show error on initial load - sources default to connected
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial fetch and periodic refresh
  useEffect(() => {
    fetchSourceStatus();
    
    // Refresh every 5 seconds
    const interval = setInterval(fetchSourceStatus, 5000);
    return () => clearInterval(interval);
  }, [fetchSourceStatus]);

  const handleConnect = async (sourceId: string) => {
    setSources(prev => prev.map(s => 
      s.id === sourceId 
        ? { ...s, connected: true, lastSync: 'Just now' }
        : s
    ));
    setConnectingSource(null);
  };

  const handleDisconnect = async (sourceId: string) => {
    // Set loading state
    setSources(prev => prev.map(s =>
      s.id === sourceId ? { ...s, loading: true } : s
    ));
    
    try {
      const apiSourceId = REVERSE_SOURCE_ID_MAP[sourceId] || sourceId;
      const response = await fetch(`${API_URL}/sources/${apiSourceId}/disconnect`, {
        method: 'POST',
      });
      
      if (!response.ok) throw new Error('Failed to disconnect');
      
      setSources(prev => prev.map(s =>
        s.id === sourceId
          ? { ...s, connected: false, lastSync: null, loading: false }
          : s
      ));
    } catch (err) {
      console.error('Error disconnecting source:', err);
      setSources(prev => prev.map(s =>
        s.id === sourceId ? { ...s, loading: false } : s
      ));
    }
  };

  const connectedCount = sources.filter(s => s.connected).length;
  const totalEvents = sources.reduce((sum, s) => sum + s.eventsReceived, 0);

  return (
    <div className="bg-soc-panel border border-soc-border rounded-lg overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-soc-border bg-gradient-to-r from-accent-purple/10 to-accent-cyan/10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Link2 size={18} className="text-accent-purple" />
            <h3 className="text-sm font-medium text-soc-text">
              Multi-Source Integrations
            </h3>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-soc-muted">
              {connectedCount} of {sources.length} connected
            </span>
            {totalEvents > 0 && (
              <span className="text-xs text-vital-normal">
                {totalEvents.toLocaleString()} events
              </span>
            )}
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
            <span className="text-accent-cyan font-medium">Multi-Source Kafka Architecture</span>
            <p className="text-soc-muted mt-1">
              Each health data source streams to its own Kafka topic for isolated, 
              reliable data ingestion. Data is normalized into a unified schema for AI analysis.
            </p>
          </div>
        </div>

        {/* Loading state */}
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 size={24} className="animate-spin text-accent-cyan" />
          </div>
        ) : (
          <>
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
          </>
        )}

        {/* Architecture note */}
        <div className="mt-4 p-3 bg-soc-bg/30 rounded-lg border border-soc-border/30">
          <div className="flex items-center gap-2 text-xs text-soc-muted">
            <Watch size={14} className="text-accent-purple" />
            <span>
              <strong>Kafka Topics:</strong> biometrics-apple, biometrics-google, biometrics-oura
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
