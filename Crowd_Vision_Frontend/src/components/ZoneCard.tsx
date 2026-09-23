// import React from 'react';
// import { Users, Activity, Gauge } from 'lucide-react';
// import { cn } from '@/lib/utils';
// import type { ZoneData } from '@/types/analysis';

// interface ZoneCardProps {
//   zone: ZoneData;
//   index: number;
// }

// const riskColors = {
//   LOW: 'risk-low',
//   MEDIUM: 'risk-medium',
//   HIGH: 'risk-high',
//   CRITICAL: 'risk-critical',
// };

// const riskBgColors = {
//   LOW: 'bg-risk-low/10 border-risk-low/20',
//   MEDIUM: 'bg-risk-medium/10 border-risk-medium/20',
//   HIGH: 'bg-risk-high/10 border-risk-high/20',
//   CRITICAL: 'bg-risk-critical/10 border-risk-critical/20',
// };

// export const ZoneCard: React.FC<ZoneCardProps> = ({ zone, index }) => {
//   return (
//     <div
//       className={cn(
//         'glass-panel p-5 animate-fade-in-up border',
//         riskBgColors[zone.riskLevel]
//       )}
//       style={{ animationDelay: `${index * 100}ms` }}
//     >
//       <div className="flex items-start justify-between mb-4">
//         <div>
//           <h4 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
//             {zone.name}
//           </h4>
//           <p className="text-xs text-muted-foreground/70 font-mono mt-1">
//             {zone.method}
//           </p>
//         </div>
//         <span className={cn('risk-badge', riskColors[zone.riskLevel])}>
//           {zone.riskLevel}
//         </span>
//       </div>

//       <div className="grid grid-cols-2 gap-4">

//         <div className="space-y-1">
//           <div className="flex items-center gap-1.5 text-muted-foreground">
//             <Activity className="w-3.5 h-3.5" />
//             <span className="metric-label">Density</span>
//           </div>
//           <p className="metric-value text-foreground">
//             {zone.density.toFixed(2)}
//           </p>
//         </div>

//         <div className="space-y-1">
//           <div className="flex items-center gap-1.5 text-muted-foreground">
//             <Gauge className="w-3.5 h-3.5" />
//             <span className="metric-label">Risk</span>
//           </div>
//           <p className={cn('metric-value', `text-${riskColors[zone.riskLevel]}`)}>
//             {zone.riskScore.toFixed(1)}%
//           </p>
//         </div>
//       </div>

//       {/* Risk bar visualization */}
//       <div className="mt-4 space-y-1.5">
//         <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
//           <div
//             className={cn(
//               'h-full rounded-full transition-all duration-500',
//               zone.riskLevel === 'LOW' && 'bg-risk-low',
//               zone.riskLevel === 'MEDIUM' && 'bg-risk-medium',
//               zone.riskLevel === 'HIGH' && 'bg-risk-high',
//               zone.riskLevel === 'CRITICAL' && 'bg-risk-critical'
//             )}
//             style={{ width: `${Math.min(zone.riskScore, 100)}%` }}
//           />
//         </div>
//       </div>
//     </div>
//   );
// };

import React from "react";
import { Users, Activity, Gauge, Wind, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ZoneData, RiskLevel } from "@/types/analysis";
import {
  getPeopleCountLabel,
  getDensityLabel,
  getMotionLabel,
  formatDensity,
  formatMotion,
  formatRiskScore,
  formatRiskFactor,
  getRiskColor,
} from "@/lib/metrics";

interface ZoneCardProps {
  zone: ZoneData;
  index: number;
}

const riskBgColors: Record<RiskLevel | string, string> = {
  LOW: "bg-risk-low/10 border-risk-low/20",
  MEDIUM: "bg-risk-medium/10 border-risk-medium/20",
  HIGH: "bg-risk-high/10 border-risk-high/20",
  CRITICAL: "bg-risk-critical/10 border-risk-critical/20",
};

export const ZoneCard: React.FC<ZoneCardProps> = ({ zone, index }) => {
  // Handle both new and legacy field names
  const peopleCount = zone.people_count ?? zone.people ?? 0;
  const headDetections = zone.head_detections ?? zone.yoloCount ?? 0;
  const density = zone.density_estimate ?? zone.density ?? 0;
  const densityLevel = zone.density_level ?? "LOW";
  const motion = zone.avg_motion ?? 0;
  const flowPressure = zone.flow_pressure ?? 0;
  const riskScore = zone.risk_score ?? zone.riskScore ?? 0;
  const riskLevel = zone.risk_level ?? zone.riskLevel ?? "LOW";
  const riskFactors = zone.risk_factors ?? [];
  const method = zone.method ?? "Hybrid";

  return (
    <div
      className={cn(
        "glass-panel p-5 animate-fade-in-up border",
        riskBgColors[riskLevel]
      )}
      style={{ animationDelay: `${index * 100}ms` }}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <h4 className="text-sm font-medium text-foreground">
            {zone.name || zone.id}
          </h4>
          <p className="text-xs text-muted-foreground/70 font-mono mt-1">
            {method}
          </p>
        </div>
        <span className={cn("risk-badge", getRiskColor(riskLevel as RiskLevel).replace('text-', ''))}>
          {riskLevel}
        </span>
      </div>

      {/* Main Metrics Grid */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        {/* People Count */}
        <div className="space-y-1">
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <Users className="w-3.5 h-3.5" />
            <span className="metric-label">Count</span>
          </div>
          <p className="metric-value text-foreground text-lg">{peopleCount}</p>
          <p className="text-xs text-muted-foreground">
            {getPeopleCountLabel(peopleCount)}
          </p>
        </div>

        {/* Density */}
        <div className="space-y-1">
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <Activity className="w-3.5 h-3.5" />
            <span className="metric-label">Density</span>
          </div>
          <p className="metric-value text-foreground">
            {formatDensity(density)}
          </p>
          <p className="text-xs text-muted-foreground">{getDensityLabel(density)}</p>
        </div>

        {/* Motion */}
        <div className="space-y-1">
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <Wind className="w-3.5 h-3.5" />
            <span className="metric-label">Motion</span>
          </div>
          <p className="metric-value text-foreground">{formatMotion(motion)} px/f</p>
          <p className="text-xs text-muted-foreground">
            {getMotionLabel(motion)}
          </p>
        </div>

        {/* Risk Score */}
        <div className="space-y-1">
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <Gauge className="w-3.5 h-3.5" />
            <span className="metric-label">Risk</span>
          </div>
          <p className={cn("metric-value", getRiskColor(riskLevel as RiskLevel))}>
            {formatRiskScore(riskScore)}
          </p>
        </div>
      </div>

      {/* Risk bar visualization */}
      <div className="space-y-1.5">
        <div className="h-2 bg-secondary rounded-full overflow-hidden">
          <div
            className={cn(
              "h-full rounded-full transition-all duration-500",
              riskLevel === "LOW" && "bg-risk-low",
              riskLevel === "MEDIUM" && "bg-risk-medium",
              riskLevel === "HIGH" && "bg-risk-high",
              riskLevel === "CRITICAL" && "bg-risk-critical"
            )}
            style={{ width: `${Math.min(riskScore, 100)}%` }}
          />
        </div>
      </div>

      {/* Risk Factors */}
      {riskFactors.length > 0 && (
        <div className="mt-4 pt-3 border-t border-border/50">
          <div className="flex items-center gap-1.5 mb-2 text-muted-foreground">
            <AlertTriangle className="w-3 h-3" />
            <span className="text-xs font-medium">Risk Factors</span>
          </div>
          <div className="space-y-1">
            {riskFactors.slice(0, 3).map((factor, i) => {
              const formatted = formatRiskFactor(factor);
              return (
                <p
                  key={i}
                  className={cn(
                    "text-xs",
                    formatted.severity === "critical" && "text-risk-critical font-bold",
                    formatted.severity === "danger" && "text-risk-high font-medium",
                    formatted.severity === "warning" && "text-risk-medium",
                    formatted.severity === "info" && "text-muted-foreground"
                  )}
                >
                  {formatted.label}
                </p>
              );
            })}
            {riskFactors.length > 3 && (
              <p className="text-xs text-muted-foreground">
                +{riskFactors.length - 3} more...
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
