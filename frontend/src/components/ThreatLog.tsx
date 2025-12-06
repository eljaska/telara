/**
 * Threat Log Component - Displays real-time alerts
 */

import { AlertTriangle, AlertCircle, Info, Clock, Activity } from 'lucide-react';
import type { AlertData, AlertSeverity } from '../types';
import { SEVERITY_COLORS, ALERT_TYPE_LABELS } from '../types';

interface ThreatLogProps {
  alerts: AlertData[];
}

function getSeverityIcon(severity: AlertSeverity) {
  const iconProps = { size: 18, className: 'flex-shrink-0' };
  
  switch (severity) {
    case 'CRITICAL':
      return <AlertTriangle {...iconProps} style={{ color: SEVERITY_COLORS.CRITICAL }} />;
    case 'HIGH':
      return <AlertCircle {...iconProps} style={{ color: SEVERITY_COLORS.HIGH }} />;
    case 'MEDIUM':
      return <Info {...iconProps} style={{ color: SEVERITY_COLORS.MEDIUM }} />;
    default:
      return <Info {...iconProps} style={{ color: SEVERITY_COLORS.LOW }} />;
  }
}

function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function formatDuration(start: string, end: string): string {
  const startDate = new Date(start);
  const endDate = new Date(end);
  const diffMs = endDate.getTime() - startDate.getTime();
  const diffSeconds = Math.round(diffMs / 1000);
  
  if (diffSeconds < 60) {
    return `${diffSeconds}s`;
  }
  const minutes = Math.floor(diffSeconds / 60);
  const seconds = diffSeconds % 60;
  return `${minutes}m ${seconds}s`;
}

function AlertCard({ alert }: { alert: AlertData }) {
  const severityClass = `severity-${alert.severity.toLowerCase()}`;
  
  return (
    <div 
      className={`${severityClass} rounded-md p-3 mb-2 animate-slide-in`}
    >
      {/* Header */}
      <div className="flex items-start gap-2 mb-2">
        {getSeverityIcon(alert.severity)}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <span 
              className="text-sm font-semibold truncate"
              style={{ color: SEVERITY_COLORS[alert.severity] }}
            >
              {ALERT_TYPE_LABELS[alert.alert_type] || alert.alert_type}
            </span>
            <span 
              className="text-xs font-bold px-2 py-0.5 rounded"
              style={{ 
                backgroundColor: `${SEVERITY_COLORS[alert.severity]}20`,
                color: SEVERITY_COLORS[alert.severity],
              }}
            >
              {alert.severity}
            </span>
          </div>
          <div className="text-xs text-soc-muted mt-1">
            User: {alert.user_id}
          </div>
        </div>
      </div>
      
      {/* Description */}
      <p className="text-sm text-soc-text mb-2 leading-relaxed">
        {alert.description}
      </p>
      
      {/* Metadata */}
      <div className="flex flex-wrap gap-3 text-xs text-soc-muted">
        <div className="flex items-center gap-1">
          <Clock size={12} />
          <span>{formatTimestamp(alert.start_time)}</span>
        </div>
        <div className="flex items-center gap-1">
          <Activity size={12} />
          <span>Duration: {formatDuration(alert.start_time, alert.end_time)}</span>
        </div>
        <div className="flex items-center gap-1">
          <span>Events: {alert.event_count}</span>
        </div>
      </div>
    </div>
  );
}

export function ThreatLog({ alerts }: ThreatLogProps) {
  const criticalCount = alerts.filter(a => a.severity === 'CRITICAL').length;
  const highCount = alerts.filter(a => a.severity === 'HIGH').length;
  
  return (
    <div className="bg-soc-panel border border-soc-border rounded-lg h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-soc-border">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-lg font-display font-bold text-accent-cyan tracking-wider">
            THREAT LOG
          </h2>
          <div className="flex items-center gap-2">
            {criticalCount > 0 && (
              <span className="text-xs font-bold px-2 py-1 rounded bg-vital-critical/20 text-vital-critical">
                {criticalCount} CRITICAL
              </span>
            )}
            {highCount > 0 && (
              <span className="text-xs font-bold px-2 py-1 rounded bg-vital-warning/20 text-vital-warning">
                {highCount} HIGH
              </span>
            )}
          </div>
        </div>
        <p className="text-xs text-soc-muted">
          Real-time anomaly detection alerts from Flink CEP
        </p>
      </div>
      
      {/* Alert List */}
      <div className="flex-1 overflow-y-auto p-4">
        {alerts.length === 0 ? (
          <div className="text-center py-8">
            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-vital-normal/10 flex items-center justify-center">
              <Activity size={32} className="text-vital-normal" />
            </div>
            <p className="text-soc-muted text-sm">No active threats detected</p>
            <p className="text-soc-muted text-xs mt-1">System is monitoring...</p>
          </div>
        ) : (
          <div>
            {alerts.map((alert) => (
              <AlertCard key={alert.alert_id} alert={alert} />
            ))}
          </div>
        )}
      </div>
      
      {/* Footer Stats */}
      <div className="p-3 border-t border-soc-border bg-soc-bg/50 text-xs text-soc-muted">
        <div className="flex justify-between">
          <span>Total Alerts: {alerts.length}</span>
          <span>Patterns: 3 active</span>
        </div>
      </div>
    </div>
  );
}

