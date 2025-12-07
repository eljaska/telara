/**
 * Historical Timeline Component
 * Shows 24-hour timeline of vitals with alert markers
 */

import { useMemo } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { AlertTriangle, Clock } from 'lucide-react';
import type { VitalData, AlertData } from '../types';

interface TimelineProps {
  vitals: VitalData[];
  alerts: AlertData[];
  selectedMetric?: 'heart_rate' | 'hrv_ms' | 'spo2_percent' | 'skin_temp_c';
}

export function Timeline({ 
  vitals, 
  alerts, 
  selectedMetric = 'heart_rate' 
}: TimelineProps) {
  const chartData = useMemo(() => {
    // Aggregate vitals into time buckets (1-minute intervals)
    const buckets: Map<string, { sum: number; count: number; alerts: AlertData[] }> = new Map();
    
    vitals.forEach(vital => {
      const date = new Date(vital.timestamp);
      const bucketKey = `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
      
      const existing = buckets.get(bucketKey) || { sum: 0, count: 0, alerts: [] };
      const value = vital[selectedMetric];
      if (typeof value === 'number') {
        existing.sum += value;
        existing.count += 1;
      }
      buckets.set(bucketKey, existing);
    });
    
    // Add alerts to their corresponding time buckets
    alerts.forEach(alert => {
      const date = new Date(alert.start_time);
      const bucketKey = `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
      
      const existing = buckets.get(bucketKey);
      if (existing) {
        existing.alerts.push(alert);
      }
    });
    
    // Convert to array and sort by time
    return Array.from(buckets.entries())
      .map(([time, data]) => ({
        time,
        value: data.count > 0 ? Math.round(data.sum / data.count) : null,
        hasAlert: data.alerts.length > 0,
        alertCount: data.alerts.length,
        alerts: data.alerts,
      }))
      .sort((a, b) => a.time.localeCompare(b.time));
  }, [vitals, alerts, selectedMetric]);

  const getMetricConfig = () => {
    switch (selectedMetric) {
      case 'heart_rate':
        return { label: 'Heart Rate', unit: 'bpm', color: '#f85149', domain: [50, 150] };
      case 'hrv_ms':
        return { label: 'HRV', unit: 'ms', color: '#a371f7', domain: [20, 80] };
      case 'spo2_percent':
        return { label: 'SpO2', unit: '%', color: '#58a6ff', domain: [90, 100] };
      case 'skin_temp_c':
        return { label: 'Temperature', unit: '°C', color: '#d29922', domain: [35, 39] };
      default:
        return { label: 'Value', unit: '', color: '#39c5cf', domain: ['auto', 'auto'] };
    }
  };

  const config = getMetricConfig();

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload || !payload.length) return null;
    
    const data = payload[0].payload;
    
    return (
      <div className="bg-soc-panel border border-soc-border rounded-lg p-3 shadow-lg">
        <div className="flex items-center gap-2 text-sm text-soc-muted mb-1">
          <Clock size={12} />
          {label}
        </div>
        <div className="text-lg font-bold" style={{ color: config.color }}>
          {data.value} {config.unit}
        </div>
        {data.hasAlert && (
          <div className="flex items-center gap-1 mt-2 text-vital-warning text-xs">
            <AlertTriangle size={12} />
            {data.alertCount} alert{data.alertCount > 1 ? 's' : ''}
          </div>
        )}
      </div>
    );
  };

  const recentAlerts = alerts.slice(0, 5);

  return (
    <div className="bg-soc-panel border border-soc-border rounded-lg p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-soc-muted uppercase tracking-wider">
          Timeline
        </h3>
        <div className="flex items-center gap-2">
          <select
            value={selectedMetric}
            onChange={() => {}}
            className="bg-soc-bg border border-soc-border rounded px-2 py-1 text-xs"
          >
            <option value="heart_rate">Heart Rate</option>
            <option value="hrv_ms">HRV</option>
            <option value="spo2_percent">SpO2</option>
            <option value="skin_temp_c">Temperature</option>
          </select>
        </div>
      </div>

      {/* Chart */}
      <div className="h-40">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={config.color} stopOpacity={0.3} />
                <stop offset="95%" stopColor={config.color} stopOpacity={0} />
              </linearGradient>
            </defs>
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
              domain={config.domain}
              tick={{ fontSize: 10, fill: '#6e7681' }}
              axisLine={{ stroke: '#1c2128' }}
              tickLine={{ stroke: '#1c2128' }}
              width={35}
            />
            <Tooltip content={<CustomTooltip />} />
            
            {/* Alert markers as reference lines */}
            {chartData
              .filter(d => d.hasAlert)
              .map((d, i) => (
                <ReferenceLine
                  key={i}
                  x={d.time}
                  stroke="#d29922"
                  strokeWidth={2}
                  strokeDasharray="3 3"
                />
              ))
            }
            
            <Area
              type="monotone"
              dataKey="value"
              stroke={config.color}
              strokeWidth={2}
              fill="url(#colorValue)"
              isAnimationActive={false}
              dot={(props: any) => {
                const { cx, cy, payload } = props;
                if (!payload.hasAlert) return null;
                return (
                  <circle
                    cx={cx}
                    cy={cy}
                    r={5}
                    fill="#d29922"
                    stroke="#0d1117"
                    strokeWidth={2}
                  />
                );
              }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Recent Alerts */}
      {recentAlerts.length > 0 && (
        <div className="mt-4 pt-3 border-t border-soc-border">
          <div className="text-xs text-soc-muted mb-2">Recent Events</div>
          <div className="space-y-1">
            {recentAlerts.map((alert, i) => (
              <div 
                key={alert.alert_id || i}
                className="flex items-center gap-2 text-xs"
              >
                <div 
                  className="w-1.5 h-1.5 rounded-full"
                  style={{ 
                    backgroundColor: alert.severity === 'CRITICAL' ? '#f85149' 
                      : alert.severity === 'HIGH' ? '#d29922' 
                      : '#58a6ff' 
                  }}
                />
                <span className="text-soc-muted">
                  {new Date(alert.start_time).toLocaleTimeString('en-US', { 
                    hour: '2-digit', 
                    minute: '2-digit',
                    hour12: false 
                  })}
                </span>
                <span className="truncate">
                  {alert.alert_type.replace(/_/g, ' ')}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

