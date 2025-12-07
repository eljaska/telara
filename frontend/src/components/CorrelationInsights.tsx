/**
 * Correlation Insights Component
 * Displays discovered correlations between health metrics
 */

import { useEffect, useState } from 'react';
import { 
  TrendingUp, 
  TrendingDown, 
  Minus, 
  RefreshCw,
  Zap,
  Clock,
  Brain
} from 'lucide-react';

interface Correlation {
  metric1: string;
  metric2: string;
  correlation: number;
  strength: string;
  direction: string;
  data_points: number;
  insight: string;
  lagged: boolean;
  lag_hours: number | null;
}

interface CorrelationData {
  correlations: Correlation[];
  summary: {
    total_analyzed: number;
    strong_count: number;
    moderate_count: number;
    top_insights: string[];
  };
  analysis_period_hours: number;
  calculated_at: string;
}

interface CorrelationInsightsProps {
  apiUrl: string;
}

const METRIC_LABELS: Record<string, string> = {
  heart_rate: 'Heart Rate',
  hrv_ms: 'HRV',
  spo2_percent: 'SpO2',
  skin_temp_c: 'Temperature',
  activity_level: 'Activity',
  sleep_hours: 'Sleep',
  respiratory_rate: 'Resp. Rate',
};

function CorrelationBar({ correlation, strength }: { correlation: number; strength: string }) {
  const absCorr = Math.abs(correlation);
  const isPositive = correlation > 0;
  
  const getColor = () => {
    if (strength === 'strong') return isPositive ? '#3fb950' : '#f85149';
    if (strength === 'moderate') return isPositive ? '#39c5cf' : '#d29922';
    return '#6e7681';
  };
  
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-2 bg-soc-border rounded-full overflow-hidden">
        <div 
          className="h-full rounded-full transition-all duration-500"
          style={{ 
            width: `${absCorr * 100}%`,
            backgroundColor: getColor()
          }}
        />
      </div>
      <span className="text-xs font-mono text-soc-muted w-12">
        {(correlation > 0 ? '+' : '') + correlation.toFixed(2)}
      </span>
    </div>
  );
}

function CorrelationCard({ corr }: { corr: Correlation }) {
  const getStrengthBadge = () => {
    if (corr.strength === 'strong') {
      return (
        <span className="px-2 py-0.5 rounded text-xs bg-vital-normal/20 text-vital-normal">
          Strong
        </span>
      );
    }
    if (corr.strength === 'moderate') {
      return (
        <span className="px-2 py-0.5 rounded text-xs bg-accent-cyan/20 text-accent-cyan">
          Moderate
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 rounded text-xs bg-soc-border text-soc-muted">
        Weak
      </span>
    );
  };

  return (
    <div className="bg-soc-bg/50 rounded-lg p-3 border border-soc-border/50">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">
            {METRIC_LABELS[corr.metric1] || corr.metric1}
          </span>
          {corr.correlation > 0 ? (
            <TrendingUp size={14} className="text-vital-normal" />
          ) : (
            <TrendingDown size={14} className="text-vital-critical" />
          )}
          <span className="text-sm font-medium">
            {METRIC_LABELS[corr.metric2] || corr.metric2}
          </span>
        </div>
        {getStrengthBadge()}
      </div>
      
      {/* Correlation bar */}
      <CorrelationBar correlation={corr.correlation} strength={corr.strength} />
      
      {/* Lagged indicator */}
      {corr.lagged && corr.lag_hours && (
        <div className="flex items-center gap-1 mt-2 text-xs text-accent-purple">
          <Clock size={12} />
          <span>{corr.lag_hours}h lag</span>
        </div>
      )}
      
      {/* Insight */}
      <p className="text-xs text-soc-muted mt-2 leading-relaxed">
        {corr.insight}
      </p>
      
      {/* Data points */}
      <div className="flex items-center gap-1 mt-2 text-xs text-soc-muted">
        <Zap size={10} />
        <span>{corr.data_points} data points</span>
      </div>
    </div>
  );
}

export function CorrelationInsights({ apiUrl }: CorrelationInsightsProps) {
  const [data, setData] = useState<CorrelationData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  const fetchCorrelations = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiUrl}/correlations?hours=24`);
      if (!response.ok) throw new Error('Failed to fetch correlations');
      const result = await response.json();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCorrelations();
    const interval = setInterval(fetchCorrelations, 60000); // Update every minute
    return () => clearInterval(interval);
  }, [apiUrl]);

  const significantCorrelations = data?.correlations.filter(
    c => c.strength === 'strong' || c.strength === 'moderate'
  ) || [];

  const displayCorrelations = expanded 
    ? significantCorrelations 
    : significantCorrelations.slice(0, 3);

  return (
    <div className="bg-soc-panel border border-soc-border rounded-lg p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Brain size={18} className="text-accent-purple" />
          <h3 className="text-sm font-medium text-soc-muted uppercase tracking-wider">
            Correlation Insights
          </h3>
        </div>
        <button
          onClick={fetchCorrelations}
          className="p-1.5 hover:bg-soc-border rounded transition-colors"
          title="Refresh"
          disabled={loading}
        >
          <RefreshCw 
            size={14} 
            className={`text-soc-muted ${loading ? 'animate-spin' : ''}`} 
          />
        </button>
      </div>

      {/* Content */}
      {loading && !data ? (
        <div className="flex items-center justify-center h-32">
          <RefreshCw size={20} className="text-soc-muted animate-spin" />
        </div>
      ) : error ? (
        <div className="text-xs text-vital-critical bg-vital-critical/10 rounded p-3">
          {error}
        </div>
      ) : data ? (
        <>
          {/* Summary */}
          {data.summary.top_insights.length > 0 && (
            <div className="mb-4 p-3 bg-accent-purple/10 border border-accent-purple/30 rounded-lg">
              <div className="text-xs text-accent-purple mb-1 uppercase tracking-wider">
                Top Discovery
              </div>
              <p className="text-sm text-soc-text">
                {data.summary.top_insights[0]}
              </p>
            </div>
          )}

          {/* Stats bar */}
          <div className="flex items-center gap-4 mb-4 text-xs text-soc-muted">
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-vital-normal" />
              <span>{data.summary.strong_count} strong</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-accent-cyan" />
              <span>{data.summary.moderate_count} moderate</span>
            </div>
            <div className="flex items-center gap-1">
              <Clock size={12} />
              <span>{data.analysis_period_hours}h period</span>
            </div>
          </div>

          {/* Correlation cards */}
          {significantCorrelations.length > 0 ? (
            <div className="space-y-3">
              {displayCorrelations.map((corr, i) => (
                <CorrelationCard key={`${corr.metric1}-${corr.metric2}-${i}`} corr={corr} />
              ))}
              
              {significantCorrelations.length > 3 && (
                <button
                  onClick={() => setExpanded(!expanded)}
                  className="w-full text-xs text-accent-cyan hover:text-accent-cyan/80 transition-colors py-2"
                >
                  {expanded 
                    ? 'Show less' 
                    : `Show ${significantCorrelations.length - 3} more correlations`
                  }
                </button>
              )}
            </div>
          ) : (
            <div className="text-center py-6 text-soc-muted text-sm">
              <Minus size={24} className="mx-auto mb-2 opacity-50" />
              <p>No significant correlations detected yet.</p>
              <p className="text-xs mt-1">More data needed for analysis.</p>
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}

