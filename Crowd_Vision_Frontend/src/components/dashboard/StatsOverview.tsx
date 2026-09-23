import { Users, Activity, AlertTriangle, TrendingUp } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  getPeopleCountLabel,
  getMotionDescription,
  MotionLevel,
} from '@/lib/metrics';

export interface RiskCounts {
  LOW: number;
  MEDIUM: number;
  HIGH: number;
  CRITICAL: number;
}

export interface DashboardStats {
  peopleCount: number;
  density: number;
  motionIntensity: number;
  motionLevel: string;
  riskLevel: string;
  riskScore: number;
  densityLevel: string;
}

interface StatsOverviewProps {
  stats: DashboardStats | null;
  riskCounts?: RiskCounts;
}

const riskBackgroundColors: Record<string, string> = {
  LOW: 'bg-[#22c55e]',
  MEDIUM: 'bg-[#f59e0b]',
  HIGH: 'bg-[#ea580c]',
  CRITICAL: 'bg-[#dc2626]',
};

function formatRiskCountsDisplay(riskCounts?: RiskCounts): string {
  if (!riskCounts) return '';

  const parts: string[] = [];
  if (riskCounts.CRITICAL > 0) parts.push(`${riskCounts.CRITICAL} CRITICAL`);
  if (riskCounts.HIGH > 0) parts.push(`${riskCounts.HIGH} HIGH`);
  if (riskCounts.MEDIUM > 0) parts.push(`${riskCounts.MEDIUM} MEDIUM`);

  if (parts.length === 0) {
    return 'All zones normal';
  }

  return parts.join(', ');
}

export function StatsOverview({ stats, riskCounts }: StatsOverviewProps) {
  if (!stats) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 lg:gap-4">
        {[1, 2].map((i) => (
          <div key={i} className="stat-card animate-pulse h-32 lg:h-36 bg-[#121620] rounded-xl border border-border/30" />
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 lg:gap-4">
      {/* FOB Crowd Count */}
      <div className={cn(
        "stat-card group hover:shadow-xl transition-all duration-300 p-4 lg:p-5 rounded-xl relative overflow-hidden",
        stats.peopleCount > 150 ? "bg-[#121620] border-2 border-[#dc2626]" : "bg-[#121620] border border-border/30"
      )}>
        <div className="flex items-center justify-between mb-3 lg:mb-4">
          <span className={cn(
            "text-[9px] lg:text-[10px] font-bold uppercase tracking-[0.16em] text-foreground",
            stats.peopleCount > 150 && "drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]"
          )} style={{ fontFamily: "'Outfit', sans-serif" }}>FOB Crowd Count</span>
          {stats.peopleCount > 150 ? (
            <span className="text-[8px] lg:text-[9px] font-bold text-foreground bg-background/20 px-2 py-0.5 rounded-md" style={{ fontFamily: "'Outfit', sans-serif" }}>
              Threshold Exceeded
            </span>
          ) : (
            <div className="p-1.5 lg:p-2 rounded-lg bg-primary/10 text-primary">
              <Users className="w-4 h-4" />
            </div>
          )}
        </div>
        <div className="flex items-baseline gap-2 mb-2">
          <p className="text-3xl lg:text-4xl font-black text-foreground tracking-tighter" style={{ fontFamily: "'Outfit', sans-serif" }}>{stats.peopleCount}</p>
        </div>
        <div className="flex items-center gap-2 text-[9px] lg:text-[10px] font-bold">
          <TrendingUp className={cn("w-3 h-3 lg:w-3.5 lg:h-3.5", stats.peopleCount > 150 ? "text-foreground" : "text-status-active")} />
          <span className={cn("tracking-wider uppercase", stats.peopleCount > 150 ? "text-foreground/85" : "text-status-active")} style={{ fontFamily: "'Outfit', sans-serif" }}>{getPeopleCountLabel(stats.peopleCount)}</span>
        </div>
        <div className="absolute top-0 right-0 w-24 h-24 bg-card/5 blur-[40px] rounded-full -mr-10 -mt-10" />
      </div>

      {/* Estimated Risk */}
      <div className={cn(
        'stat-card group hover:shadow-xl transition-all duration-300 border-0 p-4 lg:p-5 rounded-xl relative overflow-hidden flex flex-col justify-center min-h-[120px] lg:min-h-[132px]',
        riskBackgroundColors[stats.riskLevel] || 'bg-[#1C222D]'
      )}>
        <div className="absolute top-3 lg:top-4 right-3 lg:right-4 p-2 rounded-lg bg-card/20">
          <AlertTriangle className="w-4 h-4 lg:w-5 lg:h-5 text-foreground" />
        </div>

        <span className="text-[9px] lg:text-[10px] font-bold uppercase tracking-[0.16em] text-foreground mb-3" style={{ fontFamily: "'Outfit', sans-serif" }}>Estimated Risk</span>

        <p className="text-3xl lg:text-4xl font-black text-foreground tracking-tighter mb-2" style={{ fontFamily: "'Outfit', sans-serif" }}>
          {stats.riskLevel}
        </p>

        <p className="text-[9px] lg:text-[10px] font-bold text-foreground/75 uppercase tracking-[0.08em]" style={{ fontFamily: "'Outfit', sans-serif" }}>
          {riskCounts ? formatRiskCountsDisplay(riskCounts) : `Score: ${Math.round(stats.riskScore)}`}
        </p>

        {/* Glossy overlay effect */}
        <div className="absolute inset-0 bg-gradient-to-br from-white/10 to-transparent pointer-events-none" />
      </div>
    </div>
  );
}
