import React from 'react';
import { AlertTriangle, AlertCircle, Info, X, Siren } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { Alert } from '@/types/analysis';

interface AlertBannerProps {
  alerts: Alert[];
  onDismiss: (id: string) => void;
}

const alertIcons = {
  LOW: Info,
  MEDIUM: AlertCircle,
  HIGH: AlertTriangle,
  CRITICAL: Siren,
};

const alertStyles = {
  LOW: 'bg-risk-low/10 border-risk-low/30 text-risk-low',
  MEDIUM: 'bg-risk-medium/10 border-risk-medium/30 text-risk-medium',
  HIGH: 'bg-risk-high/10 border-risk-high/30 text-risk-high',
  CRITICAL: 'bg-risk-critical/10 border-risk-critical/30 text-risk-critical animate-pulse',
};

export const AlertBanner: React.FC<AlertBannerProps> = ({ alerts, onDismiss }) => {
  if (alerts.length === 0) return null;

  return (
    <div className="space-y-3 animate-fade-in-up">
      {alerts.map((alert, index) => {
        const Icon = alertIcons[alert.severity];
        return (
          <div
            key={alert.id}
            className={cn(
              'flex items-center gap-4 px-4 py-3 rounded-lg border',
              alertStyles[alert.severity]
            )}
            style={{ animationDelay: `${index * 50}ms` }}
          >
            <Icon className="w-5 h-5 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium">{alert.message}</p>
              {alert.zone && (
                <p className="text-xs opacity-70 font-mono mt-0.5">
                  Zone: {alert.zone}
                </p>
              )}
            </div>
            <span className="text-xs font-mono opacity-70 flex-shrink-0">
              {new Date(alert.timestamp).toLocaleTimeString()}
            </span>
            <button
              onClick={() => onDismiss(alert.id)}
              className="p-1 rounded hover:bg-background/20 transition-colors flex-shrink-0"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
};
