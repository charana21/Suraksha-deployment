import { RISK_COLORS, RISK_LABELS, RiskLevel } from '@/types/zone';
import { cn } from '@/lib/utils';

interface ZoneLegendProps {
  className?: string;
}

export function ZoneLegend({ className }: ZoneLegendProps) {
  const riskLevels: RiskLevel[] = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];

  return (
    <div className={cn('flex items-center gap-4', className)}>
      <span className="text-xs text-muted-foreground font-medium">Risk Level:</span>
      <div className="flex items-center gap-3">
        {riskLevels.map((level) => (
          <div key={level} className="flex items-center gap-1.5">
            <div
              className="w-3 h-3 rounded-sm"
              style={{ backgroundColor: RISK_COLORS[level] }}
            />
            <span className="text-xs text-muted-foreground">{RISK_LABELS[level]}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
