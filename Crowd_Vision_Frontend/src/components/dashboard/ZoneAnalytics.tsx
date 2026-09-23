import { ZoneStats } from '@/types/camera';
import { cn } from '@/lib/utils';
import { Users, Gauge, Activity, AlertTriangle } from 'lucide-react';
import {
  getDensityLabel,
  getMotionLabel,
  formatDensity,
  formatMotion,
  getRiskColor,
} from '@/lib/metrics';

interface ZoneAnalyticsProps {
  zones: ZoneStats[];
}

const riskColors = {
  LOW: 'border-risk-low/30 bg-risk-low/5',
  MEDIUM: 'border-risk-medium/30 bg-risk-medium/5',
  HIGH: 'border-risk-high/30 bg-risk-high/5',
  CRITICAL: 'border-risk-critical/30 bg-risk-critical/5',
};

export function ZoneAnalytics({ zones }: ZoneAnalyticsProps) {
  if (!zones || zones.length === 0) {
    return (
      <div className="glass-panel p-6 text-center text-muted-foreground">
        No zone data available
      </div>
    );
  }

  return (
    <div className="glass-panel p-4">
      <h3 className="text-sm font-medium text-foreground mb-4">Zone Analytics</h3>
      <div className="grid gap-3">
        {zones.map((zone) => (
          <div
            key={zone.id}
            className={cn(
              'p-4 rounded-lg border transition-colors',
              riskColors[zone.riskLevel]
            )}
          >
            <div className="flex items-center justify-between mb-3">
              <h4 className="font-medium text-foreground">{zone.name}</h4>
              <span className={cn('risk-badge', `risk-${zone.riskLevel.toLowerCase()}`)}>
                {zone.riskLevel}
              </span>
            </div>
            
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="flex items-center gap-2">
                <Users className="w-3.5 h-3.5 text-muted-foreground" />
                <span className="text-muted-foreground">People:</span>
                <span className="font-medium text-foreground">{zone.peopleCount}</span>
              </div>

              <div className="flex items-center gap-2">
                <Gauge className="w-3.5 h-3.5 text-muted-foreground" />
                <span className="text-muted-foreground">Density:</span>
                <span className="font-medium text-foreground">{formatDensity(zone.density)}</span>
              </div>

              <div className="flex items-center gap-2">
                <Activity className="w-3.5 h-3.5 text-muted-foreground" />
                <span className="text-muted-foreground">Motion:</span>
                <span className="font-medium text-foreground">{formatMotion(zone.motionIntensity)}</span>
              </div>

              <div className="flex items-center gap-2">
                <AlertTriangle className={cn('w-3.5 h-3.5', getRiskColor(zone.riskLevel))} />
                <span className="text-muted-foreground">Risk:</span>
                <span className={cn('font-medium', getRiskColor(zone.riskLevel))}>
                  {Math.round(zone.riskScore)}/100
                </span>
              </div>
            </div>

            {/* Additional context labels */}
            <div className="mt-2 pt-2 border-t border-border/50 text-xs text-muted-foreground">
              {getDensityLabel(zone.density)} • {getMotionLabel(zone.motionIntensity)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
