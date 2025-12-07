/**
 * Daily Health Digest Component
 * Shows "Your Day at a Glance" with key metrics, observations, and recommendations
 */

import { useEffect, useState } from 'react';
import {
  TrendingUp,
  TrendingDown,
  Minus,
  RefreshCw,
  Sparkles,
  Lightbulb,
  Calendar,
  Heart,
  Activity,
  Thermometer,
  Wind,
  Droplets,
  AlertTriangle
} from 'lucide-react';

interface MetricStats {
  avg: number;
  min?: number;
  max?: number;
  readings: number;
}

interface MetricComparison {
  today: number;
  yesterday: number;
  difference: number;
  percent_change: number;
  direction: 'up' | 'down' | 'stable';
  improved: boolean;
}

interface DigestData {
  title: string;
  generated_at: string;
  period: {
    start: string;
    end: string;
    hours: number;
  };
  summary: {
    data_points: number;
    alerts_count: number;
    critical_alerts: number;
  };
  metrics: {
    data_available: boolean;
    heart_rate?: MetricStats;
    hrv?: MetricStats;
    spo2?: MetricStats;
    temperature?: MetricStats;
    activity?: MetricStats;
  };
  comparisons: Record<string, MetricComparison>;
  observations: string[];
  recommendation: string;
  yesterday_available: boolean;
}

interface DailyDigestProps {
  apiUrl: string;
}

const METRIC_CONFIG: Record<string, { label: string; icon: React.ElementType; unit: string; color: string }> = {
  heart_rate: { label: 'Heart Rate', icon: Heart, unit: 'bpm', color: '#f85149' },
  hrv: { label: 'HRV', icon: TrendingUp, unit: 'ms', color: '#a371f7' },
  spo2: { label: 'SpO2', icon: Droplets, unit: '%', color: '#58a6ff' },
  temperature: { label: 'Temp', icon: Thermometer, unit: '°C', color: '#d29922' },
  activity: { label: 'Activity', icon: Activity, unit: 'lvl', color: '#3fb950' },
};

function MetricCard({
  metricKey,
  stats,
  comparison
}: {
  metricKey: string;
  stats?: MetricStats;
  comparison?: MetricComparison;
}) {
  const config = METRIC_CONFIG[metricKey];
  if (!config || !stats) return null;

  const Icon = config.icon;
  
  const getDeltaColor = () => {
    if (!comparison) return 'text-soc-muted';
    if (comparison.improved) return 'text-vital-normal';
    if (Math.abs(comparison.percent_change) < 5) return 'text-soc-muted';
    return 'text-vital-warning';
  };

  return (
    <div className="bg-soc-bg/50 rounded-lg p-3 border border-soc-border/50">
      <div className="flex items-center gap-2 mb-2">
        <Icon size={16} style={{ color: config.color }} />
        <span className="text-xs text-soc-muted uppercase tracking-wider">
          {config.label}
        </span>
      </div>
      
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-bold font-mono" style={{ color: config.color }}>
          {metricKey === 'temperature' ? stats.avg.toFixed(1) : Math.round(stats.avg)}
        </span>
        <span className="text-sm text-soc-muted">{config.unit}</span>
      </div>
      
      {comparison && (
        <div className={`flex items-center gap-1 mt-1 text-xs ${getDeltaColor()}`}>
          {comparison.direction === 'up' ? (
            <TrendingUp size={12} />
          ) : comparison.direction === 'down' ? (
            <TrendingDown size={12} />
          ) : (
            <Minus size={12} />
          )}
          <span>
            {comparison.percent_change > 0 ? '+' : ''}{comparison.percent_change.toFixed(1)}% vs yesterday
          </span>
        </div>
      )}
      
      {stats.min !== undefined && stats.max !== undefined && (
        <div className="text-xs text-soc-muted mt-1">
          Range: {metricKey === 'temperature' 
            ? `${stats.min.toFixed(1)} - ${stats.max.toFixed(1)}`
            : `${stats.min} - ${stats.max}`
          }
        </div>
      )}
    </div>
  );
}

function ObservationCard({ observation, index }: { observation: string; index: number }) {
  return (
    <div className="flex gap-3 p-3 bg-soc-bg/30 rounded-lg border border-soc-border/30">
      <div className="flex-shrink-0 w-6 h-6 rounded-full bg-accent-purple/20 flex items-center justify-center">
        <Sparkles size={12} className="text-accent-purple" />
      </div>
      <p className="text-sm text-soc-text leading-relaxed">
        {observation}
      </p>
    </div>
  );
}

export function DailyDigest({ apiUrl }: DailyDigestProps) {
  const [digest, setDigest] = useState<DigestData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDigest = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiUrl}/digest/daily`);
      if (!response.ok) throw new Error('Failed to fetch digest');
      const data = await response.json();
      setDigest(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDigest();
    // Refresh every 5 minutes
    const interval = setInterval(fetchDigest, 300000);
    return () => clearInterval(interval);
  }, [apiUrl]);

  if (loading && !digest) {
    return (
      <div className="bg-soc-panel border border-soc-border rounded-lg p-6">
        <div className="flex items-center justify-center h-40">
          <RefreshCw size={24} className="text-soc-muted animate-spin" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-soc-panel border border-soc-border rounded-lg p-6">
        <div className="text-center text-vital-critical">
          <AlertTriangle size={24} className="mx-auto mb-2" />
          <p className="text-sm">{error}</p>
        </div>
      </div>
    );
  }

  if (!digest || !digest.metrics.data_available) {
    return (
      <div className="bg-soc-panel border border-soc-border rounded-lg p-6">
        <div className="text-center text-soc-muted">
          <Calendar size={24} className="mx-auto mb-2 opacity-50" />
          <p className="text-sm">No data available for digest</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-soc-panel border border-soc-border rounded-lg overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-soc-border bg-gradient-to-r from-accent-purple/10 to-accent-cyan/10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Calendar size={18} className="text-accent-cyan" />
            <h3 className="text-sm font-medium text-soc-text">
              {digest.title}
            </h3>
          </div>
          <button
            onClick={fetchDigest}
            className="p-1.5 hover:bg-soc-border/50 rounded transition-colors"
            title="Refresh"
            disabled={loading}
          >
            <RefreshCw size={14} className={`text-soc-muted ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
        
        {/* Summary stats */}
        <div className="flex items-center gap-4 mt-2 text-xs text-soc-muted">
          <span>{digest.summary.data_points} readings</span>
          <span>•</span>
          <span>{digest.period.hours}h period</span>
          {digest.summary.alerts_count > 0 && (
            <>
              <span>•</span>
              <span className={digest.summary.critical_alerts > 0 ? 'text-vital-critical' : 'text-vital-warning'}>
                {digest.summary.alerts_count} alert{digest.summary.alerts_count !== 1 ? 's' : ''}
              </span>
            </>
          )}
        </div>
      </div>

      <div className="p-4 space-y-4">
        {/* Metrics Grid */}
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
          {Object.entries(METRIC_CONFIG).map(([key]) => (
            <MetricCard
              key={key}
              metricKey={key}
              stats={(digest.metrics as any)[key]}
              comparison={digest.comparisons[key]}
            />
          ))}
        </div>

        {/* AI Observations */}
        {digest.observations.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-xs text-soc-muted uppercase tracking-wider">
              <Sparkles size={12} className="text-accent-purple" />
              <span>AI Observations</span>
            </div>
            <div className="space-y-2">
              {digest.observations.map((obs, i) => (
                <ObservationCard key={i} observation={obs} index={i} />
              ))}
            </div>
          </div>
        )}

        {/* Primary Recommendation */}
        <div className="p-3 bg-accent-cyan/10 border border-accent-cyan/30 rounded-lg">
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-accent-cyan/20 flex items-center justify-center">
              <Lightbulb size={16} className="text-accent-cyan" />
            </div>
            <div>
              <div className="text-xs text-accent-cyan uppercase tracking-wider mb-1">
                Today's Recommendation
              </div>
              <p className="text-sm text-soc-text leading-relaxed">
                {digest.recommendation}
              </p>
            </div>
          </div>
        </div>

        {/* Yesterday comparison note */}
        {!digest.yesterday_available && (
          <div className="text-xs text-soc-muted text-center">
            Comparisons will be available after more data is collected
          </div>
        )}
      </div>
    </div>
  );
}

