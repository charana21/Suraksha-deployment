import React from "react";
import {
  Users,
  Activity,
  Wind,
  AlertTriangle,
  Compass,
  Gauge,
  TrendingUp,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { FrameData, RiskLevel } from "@/types/analysis";
import {
  getPeopleCountLabel,
  getDensityLabel,
  formatDensity,
  formatRiskScore,
  getRiskColor,
  getRiskBgColor,
} from "@/lib/metrics";

interface DynamicStatsPanelProps {
  frame: FrameData | null;
  isLive?: boolean;
}

const riskBgColors: Record<RiskLevel | string, string> = {
  LOW: "bg-risk-low/20 border-risk-low/40",
  MEDIUM: "bg-risk-medium/20 border-risk-medium/40",
  HIGH: "bg-risk-high/20 border-risk-high/40",
  CRITICAL: "bg-risk-critical/20 border-risk-critical/40 animate-pulse",
};

const motionDirectionIcons: Record<string, string> = {
  up: "↑",
  down: "↓",
  left: "←",
  right: "→",
  "up-left": "↖",
  "up-right": "↗",
  "down-left": "↙",
  "down-right": "↘",
  static: "●",
};

export const DynamicStatsPanel: React.FC<DynamicStatsPanelProps> = ({
  frame,
  isLive = false,
}) => {
  if (!frame) {
    return (
      <div className="glass-panel p-4 animate-pulse">
        <div className="text-center text-muted-foreground text-sm">
          Loading frame data...
        </div>
      </div>
    );
  }

  const stampedeLevel = frame.stampedeWarning || "LOW";

  return (
    <div className="space-y-4">
      {/* Live Indicator */}
      {isLive && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="w-2 h-2 rounded-full bg-risk-high animate-pulse" />
          <span>Live Stats • Frame {frame.frameNumber}</span>
        </div>
      )}

      {/* Stampede Warning Banner */}
      {stampedeLevel !== "LOW" && (
        <div
          className={cn(
            "glass-panel p-4 border-2 rounded-lg",
            riskBgColors[stampedeLevel]
          )}
        >
          <div className="flex items-center gap-3">
            <AlertTriangle
              className={cn("w-6 h-6", getRiskColor(stampedeLevel as RiskLevel))}
            />
            <div>
              <p className={cn("font-bold text-sm", getRiskColor(stampedeLevel as RiskLevel))}>
                STAMPEDE RISK: {stampedeLevel}
              </p>
              <p className="text-xs text-muted-foreground">
                Probability: {formatRiskScore(frame.stampedeProbability)}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {/* People Count */}
        <div className="glass-panel p-3 space-y-1">
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <Users className="w-3.5 h-3.5" />
            <span className="text-xs">People</span>
          </div>
          <p className="text-xl font-bold text-foreground">
            {frame.peopleCount}
          </p>
          <p className="text-xs text-muted-foreground">
            {getPeopleCountLabel(frame.peopleCount)}
          </p>
        </div>

        {/* Density */}
        <div className="glass-panel p-3 space-y-1">
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <Activity className="w-3.5 h-3.5" />
            <span className="text-xs">Density</span>
          </div>
          <p className="text-xl font-bold text-foreground">
            {formatDensity(frame.densityAvg)}
          </p>
          <p className="text-xs text-muted-foreground">
            {getDensityLabel(frame.densityAvg)}
          </p>
        </div>

        {/* Motion */}
        <div className="glass-panel p-3 space-y-1">
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <Wind className="w-3.5 h-3.5" />
            <span className="text-xs">Motion</span>
          </div>
          <div className="flex items-center gap-2">
            <p className="text-xl font-bold text-foreground">
              {frame.motionIntensity.toFixed(1)}
            </p>
            {frame.motionDirection && (
              <span className="text-lg">
                {motionDirectionIcons[frame.motionDirection] || "●"}
              </span>
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            {frame.motionDirection || "static"}
          </p>
        </div>

        {/* Stampede Probability */}
        <div
          className={cn(
            "glass-panel p-3 space-y-1 border",
            stampedeLevel === "LOW"
              ? "border-transparent"
              : riskBgColors[stampedeLevel]
          )}
        >
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span className="text-xs">Stampede</span>
          </div>
          <p className={cn("text-xl font-bold", getRiskColor(stampedeLevel as RiskLevel))}>
            {formatRiskScore(frame.stampedeProbability)}
          </p>
          <p className={cn("text-xs", getRiskColor(stampedeLevel as RiskLevel))}>
            {stampedeLevel}
          </p>
        </div>
      </div>

      {/* Zone Quick View */}
      {frame.zones && frame.zones.length > 0 && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
          {frame.zones.map((zone) => {
            const riskLevel = zone.risk_level || zone.riskLevel || "LOW";
            return (
              <div
                key={zone.id}
                className={cn(
                  "glass-panel p-2 border",
                  riskBgColors[riskLevel]
                )}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-medium text-muted-foreground truncate">
                    {zone.name || zone.id}
                  </span>
                  <span
                    className={cn("text-xs font-bold", getRiskColor(riskLevel as RiskLevel))}
                  >
                    {riskLevel}
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-foreground font-mono">
                    {zone.people_count ?? zone.people ?? 0} ppl
                  </span>
                  <span className={cn("font-mono", getRiskColor(riskLevel as RiskLevel))}>
                    {Math.round(zone.risk_score ?? zone.riskScore ?? 0)}/100
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
