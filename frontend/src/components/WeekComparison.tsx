/**
 * Week Comparison Component
 * Shows this week vs last week with side-by-side analysis
 */

import { useEffect, useState } from 'react';
import {
  TrendingUp,
  TrendingDown,
  Minus,
  RefreshCw,
  Calendar,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  CheckCircle2,
  BarChart3
} from 'lucide-react';

interface MetricData {
  avg: number | null;
  min?: number | null;
  max?: number | null;
}

interface Comparison {
  metric: string;
  label: string;
  unit: string;
  current: MetricData;
  previous: MetricData;
  difference: number;
  percent_change: number;
  direction: 'up' | 'down' | 'stable';
  improved: boolean;
  trend_direction: string;
}

interface PeriodData {
  label: string;
  period: {
    start: string;
    end: string;
  };
  stats: {
    data_available: boolean;
    data_points: number;
  };
  alerts: {
    total: number;
    by_severity: Record<string, number>;
  };
}

interface Summary {
  improvements_count: number;
  regressions_count: number;
  stable_count: number;
  most_improved: string | null;
  needs_attention: string | null;
  insights: string[];
}

interface ComparisonData {
  data_available: boolean;
  current_week: PeriodData;
  previous_week: PeriodData;
  comparisons: Comparison[];
  summary: Summary;
  generated_at: string;
}

interface WeekComparisonProps {
  apiUrl: string;
}

function ComparisonBar({ comparison }: { comparison: Comparison }) {
  const getBarColor = () => {
    if (comparison.improved) return 'bg-vital-normal';
    if (Math.abs(comparison.percent_change) < 5) return 'bg-soc-muted';
    return 'bg-vital-warning';
  };

  const getTextColor = () => {
    if (comparison.improved) return 'text-vital-normal';
    if (Math.abs(comparison.percent_change) < 5) return 'text-soc-muted';
    return 'text-vital-warning';
  };

  // Calculate relative widths for visual comparison
  const maxVal = Math.max(
    comparison.current.avg || 0,
    comparison.previous.avg || 0
  );
  const currentWidth = maxVal > 0 ? ((comparison.current.avg || 0) / maxVal) * 100 : 0;
  const previousWidth = maxVal > 0 ? ((comparison.previous.avg || 0) / maxVal) * 100 : 0;

  return (
    <div className="bg-soc-bg/50 rounded-lg p-3 border border-soc-border/30">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-soc-text">{comparison.label}</span>
          <span className="text-xs text-soc-muted">({comparison.unit})</span>
        </div>
        <div className={`flex items-center gap-1 text-sm ${getTextColor()}`}>
          {comparison.direction === 'up' ? (
            <TrendingUp size={14} />
          ) : comparison.direction === 'down' ? (
            <TrendingDown size={14} />
          ) : (
            <Minus size={14} />
          )}
          <span>
            {comparison.percent_change > 0 ? '+' : ''}{comparison.percent_change}%
          </span>
          {comparison.improved && (
            <CheckCircle2 size={12} className="ml-1" />
          )}
        </div>
      </div>

      {/* Side-by-side bars */}
      <div className="space-y-1.5">
        {/* This week */}
        <div className="flex items-center gap-2">
          <div className="w-16 text-xs text-soc-muted">This wk</div>
          <div className="flex-1 h-3 bg-soc-border rounded-full overflow-hidden">
            <div 
              className={`h-full rounded-full ${getBarColor()}`}
              style={{ width: `${currentWidth}%` }}
            />
          </div>
          <div className="w-12 text-xs font-mono text-right">
            {comparison.current.avg?.toFixed(comparison.unit === '°C' ? 1 : 0) || '--'}
          </div>
        </div>
        
        {/* Last week */}
        <div className="flex items-center gap-2">
          <div className="w-16 text-xs text-soc-muted">Last wk</div>
          <div className="flex-1 h-3 bg-soc-border rounded-full overflow-hidden">
            <div 
              className="h-full rounded-full bg-soc-muted/50"
              style={{ width: `${previousWidth}%` }}
            />
          </div>
          <div className="w-12 text-xs font-mono text-right text-soc-muted">
            {comparison.previous.avg?.toFixed(comparison.unit === '°C' ? 1 : 0) || '--'}
          </div>
        </div>
      </div>

      {/* Difference */}
      <div className="mt-2 text-xs text-soc-muted">
        Δ {comparison.difference > 0 ? '+' : ''}{comparison.difference.toFixed(comparison.unit === '°C' ? 2 : 1)} {comparison.unit}
      </div>
    </div>
  );
}

export function WeekComparison({ apiUrl }: WeekComparisonProps) {
  const [data, setData] = useState<ComparisonData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  const fetchComparison = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiUrl}/comparison/weekly`);
      if (!response.ok) throw new Error('Failed to fetch comparison');
      const result = await response.json();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchComparison();
    const interval = setInterval(fetchComparison, 300000); // 5 min
    return () => clearInterval(interval);
  }, [apiUrl]);

  if (loading && !data) {
    return (
      <div className="bg-soc-panel border border-soc-border rounded-lg p-6">
        <div className="flex items-center justify-center h-32">
          <RefreshCw size={24} className="text-soc-muted animate-spin" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-soc-panel border border-soc-border rounded-lg p-4">
        <div className="text-xs text-vital-critical bg-vital-critical/10 rounded p-3">
          {error}
        </div>
      </div>
    );
  }

  if (!data?.data_available) {
    return (
      <div className="bg-soc-panel border border-soc-border rounded-lg p-6">
        <div className="text-center text-soc-muted">
          <Calendar size={32} className="mx-auto mb-2 opacity-50" />
          <p className="text-sm">Not enough data for weekly comparison</p>
          <p className="text-xs mt-1">Needs at least 2 weeks of history</p>
        </div>
      </div>
    );
  }

  const displayComparisons = expanded 
    ? data.comparisons 
    : data.comparisons.slice(0, 3);

  return (
    <div className="bg-soc-panel border border-soc-border rounded-lg overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-soc-border bg-gradient-to-r from-accent-cyan/10 to-vital-normal/10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BarChart3 size={18} className="text-accent-cyan" />
            <h3 className="text-sm font-medium text-soc-text">
              This Week vs Last Week
            </h3>
          </div>
          <button
            onClick={fetchComparison}
            className="p-1.5 hover:bg-soc-border/50 rounded transition-colors"
            disabled={loading}
          >
            <RefreshCw size={14} className={`text-soc-muted ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      <div className="p-4 space-y-4">
        {/* Summary stats */}
        <div className="grid grid-cols-3 gap-3">
          <div className="text-center p-2 bg-vital-normal/10 rounded-lg">
            <div className="text-xl font-bold text-vital-normal">
              {data.summary.improvements_count}
            </div>
            <div className="text-xs text-soc-muted">Improved</div>
          </div>
          <div className="text-center p-2 bg-soc-border/30 rounded-lg">
            <div className="text-xl font-bold text-soc-muted">
              {data.summary.stable_count}
            </div>
            <div className="text-xs text-soc-muted">Stable</div>
          </div>
          <div className="text-center p-2 bg-vital-warning/10 rounded-lg">
            <div className="text-xl font-bold text-vital-warning">
              {data.summary.regressions_count}
            </div>
            <div className="text-xs text-soc-muted">Declined</div>
          </div>
        </div>

        {/* Alerts comparison */}
        <div className="flex items-center justify-between p-3 bg-soc-bg/50 rounded-lg">
          <div className="flex items-center gap-2">
            <AlertTriangle size={14} className="text-vital-warning" />
            <span className="text-sm text-soc-muted">Health Alerts</span>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="text-soc-text">
              This wk: <span className="font-mono">{data.current_week.alerts.total}</span>
            </span>
            <span className="text-soc-muted">
              Last wk: <span className="font-mono">{data.previous_week.alerts.total}</span>
            </span>
            {data.current_week.alerts.total < data.previous_week.alerts.total ? (
              <TrendingDown size={14} className="text-vital-normal" />
            ) : data.current_week.alerts.total > data.previous_week.alerts.total ? (
              <TrendingUp size={14} className="text-vital-warning" />
            ) : (
              <Minus size={14} className="text-soc-muted" />
            )}
          </div>
        </div>

        {/* Metric comparisons */}
        <div className="space-y-2">
          {displayComparisons.map((comp) => (
            <ComparisonBar key={comp.metric} comparison={comp} />
          ))}
        </div>

        {/* Expand/collapse */}
        {data.comparisons.length > 3 && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="w-full flex items-center justify-center gap-2 py-2 text-xs text-accent-cyan hover:text-accent-cyan/80 transition-colors"
          >
            {expanded ? (
              <>
                <ChevronUp size={14} />
                Show less
              </>
            ) : (
              <>
                <ChevronDown size={14} />
                Show {data.comparisons.length - 3} more metrics
              </>
            )}
          </button>
        )}

        {/* Insights */}
        {data.summary.insights.length > 0 && (
          <div className="p-3 bg-accent-purple/10 border border-accent-purple/30 rounded-lg">
            <div className="text-xs text-accent-purple uppercase tracking-wider mb-2">
              Weekly Insights
            </div>
            <ul className="space-y-1.5">
              {data.summary.insights.map((insight, i) => (
                <li key={i} className="text-sm text-soc-text flex items-start gap-2">
                  <span className="text-accent-purple mt-0.5">•</span>
                  {insight}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Data points info */}
        <div className="text-xs text-soc-muted text-center">
          Based on {data.current_week.stats.data_points} readings this week
        </div>
      </div>
    </div>
  );
}

