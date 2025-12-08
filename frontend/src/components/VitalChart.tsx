/**
 * Real-time Vital Signs Chart Component
 */

import { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import type { VitalData } from '../types';

interface VitalChartProps {
  data: VitalData[];
  metric: 'heart_rate' | 'hrv_ms' | 'spo2_percent' | 'skin_temp_c';
  title: string;
  unit: string;
  color: string;
  warningThreshold?: number;
  criticalThreshold?: number;
  normalRange?: [number, number];
}

export function VitalChart({
  data,
  metric,
  title,
  unit,
  color,
  warningThreshold,
  criticalThreshold,
  normalRange,
}: VitalChartProps) {
  const chartData = useMemo(() => {
    // Filter out null/undefined values to create continuous lines
    return data
      .filter(d => d[metric] != null)
      .slice(-60)
      .map((d, i) => ({
        index: i,
        time: new Date(d.timestamp).toLocaleTimeString('en-US', {
          hour12: false,
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        }),
        value: d[metric],
        timestamp: d.timestamp,
      }));
  }, [data, metric]);

  // Get latest value from filtered data (not raw data which may have nulls for this metric)
  const latestValue = chartData.length > 0 ? chartData[chartData.length - 1].value : null;
  
  const getValueColor = (value: number | null) => {
    if (value === null) return '#6e7681';
    if (criticalThreshold && value >= criticalThreshold) return '#f85149';
    if (warningThreshold && value >= warningThreshold) return '#d29922';
    if (normalRange && (value < normalRange[0] || value > normalRange[1])) return '#d29922';
    return color;
  };

  const valueColor = getValueColor(latestValue as number);

  const domain = useMemo(() => {
    if (metric === 'heart_rate') return [40, 160];
    if (metric === 'hrv_ms') return [10, 100];
    if (metric === 'spo2_percent') return [85, 100];
    if (metric === 'skin_temp_c') return [35, 40];
    return ['auto', 'auto'];
  }, [metric]);

  return (
    <div className="bg-soc-panel border border-soc-border rounded-lg p-4 h-full">
      {/* Header */}
      <div className="flex justify-between items-center mb-3">
        <h3 className="text-sm font-medium text-soc-muted uppercase tracking-wider">
          {title}
        </h3>
        <div className="flex items-center gap-2">
          <span 
            className="text-2xl font-bold font-mono transition-colors duration-300"
            style={{ color: valueColor }}
          >
            {latestValue !== null ? (
              typeof latestValue === 'number' ? latestValue.toFixed(metric === 'skin_temp_c' ? 1 : 0) : latestValue
            ) : '--'}
          </span>
          <span className="text-sm text-soc-muted">{unit}</span>
        </div>
      </div>

      {/* Chart */}
      <div className="h-32">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: -20 }}>
            <CartesianGrid 
              strokeDasharray="3 3" 
              stroke="rgba(57, 197, 207, 0.1)" 
              vertical={false}
            />
            <XAxis 
              dataKey="time" 
              tick={{ fontSize: 10, fill: '#6e7681' }}
              axisLine={{ stroke: '#1c2128' }}
              tickLine={{ stroke: '#1c2128' }}
              interval="preserveStartEnd"
            />
            <YAxis 
              domain={domain}
              tick={{ fontSize: 10, fill: '#6e7681' }}
              axisLine={{ stroke: '#1c2128' }}
              tickLine={{ stroke: '#1c2128' }}
              width={35}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#0d1117',
                border: '1px solid #1c2128',
                borderRadius: '6px',
                fontSize: '12px',
              }}
              labelStyle={{ color: '#6e7681' }}
              formatter={(value: number) => [
                `${value.toFixed(metric === 'skin_temp_c' ? 1 : 0)} ${unit}`,
                title,
              ]}
            />
            
            {/* Reference lines for thresholds */}
            {warningThreshold && (
              <ReferenceLine 
                y={warningThreshold} 
                stroke="#d29922" 
                strokeDasharray="5 5"
                strokeOpacity={0.5}
              />
            )}
            {criticalThreshold && (
              <ReferenceLine 
                y={criticalThreshold} 
                stroke="#f85149" 
                strokeDasharray="5 5"
                strokeOpacity={0.5}
              />
            )}
            
            {/* Main data line */}
            <Line
              type="monotone"
              dataKey="value"
              stroke={color}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: color }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Normal range indicator */}
      {normalRange && (
        <div className="mt-2 text-xs text-soc-muted text-center">
          Normal: {normalRange[0]}-{normalRange[1]} {unit}
        </div>
      )}
    </div>
  );
}

