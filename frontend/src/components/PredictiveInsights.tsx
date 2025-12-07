/**
 * Predictive Insights Component
 * Shows predicted health states and threshold crossings
 */

import { useEffect, useState } from 'react';
import {
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Clock,
  RefreshCw,
  Zap,
  Brain,
  Heart,
  Activity,
  Battery,
  Thermometer
} from 'lucide-react';

interface Prediction {
  metric: string;
  label: string;
  prediction_type: string;
  severity: string;
  predicted_time: string;
  hours_until: number;
  current_value: number;
  predicted_value: number;
  threshold: number | null;
  confidence: number;
  message: string;
  recommendation: string;
}

interface PredictionData {
  predictions: Prediction[];
  data_available: boolean;
  data_points_analyzed: number;
  prediction_horizon_hours: number;
  generated_at: string;
}

interface PredictiveInsightsProps {
  apiUrl: string;
}

const PREDICTION_ICONS: Record<string, React.ElementType> = {
  heart_rate: Heart,
  hrv_ms: TrendingUp,
  spo2_percent: Activity,
  skin_temp_c: Thermometer,
  fatigue: Battery,
  stress: Zap,
};

function PredictionCard({ prediction }: { prediction: Prediction }) {
  const Icon = PREDICTION_ICONS[prediction.metric] || AlertTriangle;
  
  const getSeverityColor = () => {
    switch (prediction.severity) {
      case 'high': return 'border-vital-critical bg-vital-critical/10';
      case 'moderate': return 'border-vital-warning bg-vital-warning/10';
      default: return 'border-accent-cyan bg-accent-cyan/10';
    }
  };

  const getSeverityTextColor = () => {
    switch (prediction.severity) {
      case 'high': return 'text-vital-critical';
      case 'moderate': return 'text-vital-warning';
      default: return 'text-accent-cyan';
    }
  };

  const formatTimeUntil = (hours: number) => {
    if (hours < 1) {
      return `${Math.round(hours * 60)} min`;
    }
    return `${hours.toFixed(1)} hrs`;
  };

  const formatPredictedTime = (isoString: string) => {
    const date = new Date(isoString);
    return date.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    });
  };

  return (
    <div className={`rounded-lg border p-4 ${getSeverityColor()}`}>
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className={`p-2 rounded-lg ${getSeverityColor().replace('bg-', 'bg-').replace('/10', '/20')}`}>
            <Icon size={18} className={getSeverityTextColor()} />
          </div>
          <div>
            <div className="font-medium text-soc-text">{prediction.label}</div>
            <div className="text-xs text-soc-muted capitalize">{prediction.prediction_type.replace('_', ' ')}</div>
          </div>
        </div>
        <div className="text-right">
          <div className={`text-sm font-medium ${getSeverityTextColor()}`}>
            ~{formatTimeUntil(prediction.hours_until)}
          </div>
          <div className="text-xs text-soc-muted">
            @ {formatPredictedTime(prediction.predicted_time)}
          </div>
        </div>
      </div>

      {/* Message */}
      <p className="text-sm text-soc-text mb-3 leading-relaxed">
        {prediction.message}
      </p>

      {/* Current vs Predicted */}
      {prediction.threshold !== null && (
        <div className="flex items-center gap-4 mb-3 text-sm">
          <div className="flex items-center gap-2">
            <span className="text-soc-muted">Current:</span>
            <span className="font-mono font-medium">{Math.round(prediction.current_value)}</span>
          </div>
          <TrendingUp size={14} className={getSeverityTextColor()} />
          <div className="flex items-center gap-2">
            <span className="text-soc-muted">Threshold:</span>
            <span className={`font-mono font-medium ${getSeverityTextColor()}`}>
              {Math.round(prediction.threshold)}
            </span>
          </div>
        </div>
      )}

      {/* Progress bar showing trajectory */}
      {prediction.threshold !== null && (
        <div className="mb-3">
          <div className="h-2 bg-soc-bg rounded-full overflow-hidden">
            <div 
              className={`h-full rounded-full transition-all duration-500 ${
                prediction.severity === 'high' ? 'bg-vital-critical' : 
                prediction.severity === 'moderate' ? 'bg-vital-warning' : 'bg-accent-cyan'
              }`}
              style={{ 
                width: `${Math.min(100, (prediction.current_value / prediction.threshold) * 100)}%` 
              }}
            />
          </div>
          <div className="flex justify-between text-xs text-soc-muted mt-1">
            <span>Current</span>
            <span>Threshold</span>
          </div>
        </div>
      )}

      {/* Recommendation */}
      <div className="bg-soc-bg/50 rounded p-2 text-xs text-soc-muted">
        <span className="text-accent-cyan font-medium">Tip: </span>
        {prediction.recommendation}
      </div>

      {/* Confidence indicator */}
      <div className="flex items-center justify-end gap-2 mt-2 text-xs text-soc-muted">
        <Brain size={12} />
        <span>{Math.round(prediction.confidence * 100)}% confidence</span>
      </div>
    </div>
  );
}

export function PredictiveInsights({ apiUrl }: PredictiveInsightsProps) {
  const [data, setData] = useState<PredictionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchPredictions = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiUrl}/predictions?max_hours=6`);
      if (!response.ok) throw new Error('Failed to fetch predictions');
      const result = await response.json();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPredictions();
    const interval = setInterval(fetchPredictions, 60000); // Update every minute
    return () => clearInterval(interval);
  }, [apiUrl]);

  return (
    <div className="bg-soc-panel border border-soc-border rounded-lg p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Zap size={18} className="text-vital-warning" />
          <h3 className="text-sm font-medium text-soc-muted uppercase tracking-wider">
            Predictive Alerts
          </h3>
        </div>
        <div className="flex items-center gap-2">
          {data?.data_available && (
            <span className="text-xs text-soc-muted">
              {data.prediction_horizon_hours}h horizon
            </span>
          )}
          <button
            onClick={fetchPredictions}
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
      ) : !data?.data_available ? (
        <div className="text-center py-8 text-soc-muted">
          <Clock size={32} className="mx-auto mb-2 opacity-50" />
          <p className="text-sm">Not enough data for predictions</p>
          <p className="text-xs mt-1">More historical data needed</p>
        </div>
      ) : data.predictions.length === 0 ? (
        <div className="text-center py-8">
          <div className="w-12 h-12 rounded-full bg-vital-normal/20 flex items-center justify-center mx-auto mb-3">
            <TrendingUp size={24} className="text-vital-normal" />
          </div>
          <p className="text-sm text-vital-normal font-medium">All Clear</p>
          <p className="text-xs text-soc-muted mt-1">
            No concerning trends detected
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {data.predictions.map((pred, i) => (
            <PredictionCard key={`${pred.metric}-${i}`} prediction={pred} />
          ))}
          
          {/* Data info */}
          <div className="text-xs text-soc-muted text-center pt-2">
            Based on {data.data_points_analyzed} data points
          </div>
        </div>
      )}
    </div>
  );
}

