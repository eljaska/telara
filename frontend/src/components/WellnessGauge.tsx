/**
 * Wellness Score Gauge Component
 * Circular gauge showing overall wellness score 0-100
 */

import { useEffect, useState } from 'react';
import { TrendingUp, TrendingDown, Minus, Info } from 'lucide-react';

interface WellnessBreakdown {
  heart_health: { score: number; status: string };
  recovery: { score: number; status: string };
  activity: { score: number; status: string };
  stability: { score: number; status: string };
  alert_status: { score: number; status: string };
}

interface WellnessData {
  score: number;
  breakdown: WellnessBreakdown;
  recommendations: string[];
  calculated_at: string;
}

interface WellnessGaugeProps {
  apiUrl: string;
}

export function WellnessGauge({ apiUrl }: WellnessGaugeProps) {
  const [data, setData] = useState<WellnessData | null>(null);
  const [loading, setLoading] = useState(true);
  const [previousScore, setPreviousScore] = useState<number | null>(null);
  const [showBreakdown, setShowBreakdown] = useState(false);

  useEffect(() => {
    const fetchWellness = async () => {
      try {
        const response = await fetch(`${apiUrl}/wellness/score`);
        const result = await response.json();
        
        if (data) {
          setPreviousScore(data.score);
        }
        setData(result);
      } catch (error) {
        console.error('Failed to fetch wellness score:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchWellness();
    const interval = setInterval(fetchWellness, 30000); // Update every 30s
    
    return () => clearInterval(interval);
  }, [apiUrl]);

  const getScoreColor = (score: number) => {
    if (score >= 80) return '#3fb950';
    if (score >= 60) return '#39c5cf';
    if (score >= 40) return '#d29922';
    return '#f85149';
  };

  const getTrend = () => {
    if (previousScore === null || !data) return null;
    const diff = data.score - previousScore;
    if (diff > 2) return 'up';
    if (diff < -2) return 'down';
    return 'stable';
  };

  const getStatusLabel = (score: number) => {
    if (score >= 85) return 'Excellent';
    if (score >= 70) return 'Good';
    if (score >= 55) return 'Fair';
    if (score >= 40) return 'Needs Attention';
    return 'Critical';
  };

  const score = data?.score ?? 0;
  const color = getScoreColor(score);
  const trend = getTrend();

  // SVG arc calculations
  const radius = 80;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (score / 100) * circumference;

  return (
    <div className="bg-soc-panel border border-soc-border rounded-lg p-4 relative">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium text-soc-muted uppercase tracking-wider">
          Wellness Score
        </h3>
        <button
          onClick={() => setShowBreakdown(!showBreakdown)}
          className="p-1 hover:bg-soc-border rounded transition-colors"
          title="Show breakdown"
        >
          <Info size={16} className="text-soc-muted" />
        </button>
      </div>

      {/* Gauge */}
      <div className="flex flex-col items-center">
        <div className="relative w-48 h-48">
          <svg className="w-full h-full transform -rotate-90" viewBox="0 0 200 200">
            {/* Background circle */}
            <circle
              cx="100"
              cy="100"
              r={radius}
              fill="none"
              stroke="#1c2128"
              strokeWidth="12"
            />
            {/* Progress arc */}
            <circle
              cx="100"
              cy="100"
              r={radius}
              fill="none"
              stroke={color}
              strokeWidth="12"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              className="transition-all duration-1000 ease-out"
              style={{
                filter: `drop-shadow(0 0 8px ${color}40)`,
              }}
            />
          </svg>

          {/* Center content */}
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <div className="flex items-center gap-1">
              <span 
                className="text-5xl font-bold font-mono transition-colors duration-500"
                style={{ color }}
              >
                {loading ? '--' : score}
              </span>
              {trend && !loading && (
                <span className="ml-1">
                  {trend === 'up' && <TrendingUp size={20} className="text-vital-normal" />}
                  {trend === 'down' && <TrendingDown size={20} className="text-vital-critical" />}
                  {trend === 'stable' && <Minus size={20} className="text-soc-muted" />}
                </span>
              )}
            </div>
            <span className="text-sm text-soc-muted mt-1">
              {loading ? 'Loading...' : getStatusLabel(score)}
            </span>
          </div>
        </div>

        {/* Breakdown tooltip */}
        {showBreakdown && data?.breakdown && (
          <div className="mt-4 w-full space-y-2 text-xs">
            {Object.entries(data.breakdown).map(([key, value]) => {
              if (typeof value !== 'object' || !value.score) return null;
              const label = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
              return (
                <div key={key} className="flex items-center justify-between">
                  <span className="text-soc-muted">{label}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-24 h-1.5 bg-soc-border rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{
                          width: `${value.score}%`,
                          backgroundColor: getScoreColor(value.score),
                        }}
                      />
                    </div>
                    <span className="font-mono w-8 text-right">{value.score}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Recommendations */}
        {data?.recommendations && data.recommendations.length > 0 && (
          <div className="mt-4 w-full">
            <div className="text-xs text-accent-cyan bg-accent-cyan/10 rounded p-2">
              {data.recommendations[0]}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

