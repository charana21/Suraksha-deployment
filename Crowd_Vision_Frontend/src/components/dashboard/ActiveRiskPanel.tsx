import { ZoneAnalytics } from "@/types/zone";
import { Alert, Camera } from "@/types/camera";
import { cn } from "@/lib/utils";
import { AlertTriangle, MapPin, Clock, Check, ShieldAlert, Activity } from "lucide-react";
import { Button } from "@/components/ui/button";
import { formatDistanceToNow } from "date-fns";

// Helper to safely parse localized or irregular timestamps from backend
function parseBackendTimestamp(ts?: unknown): Date | null {
  if (!ts) return null;
  if (ts instanceof Date) {
    return isNaN(ts.getTime()) ? null : ts;
  }
  if (typeof ts === "number") {
    const d = new Date(ts);
    return isNaN(d.getTime()) ? null : d;
  }
  if (typeof ts === "string") {
    // Attempt standard parsing
    let d = new Date(ts);
    if (!isNaN(d.getTime())) return d;

    // Fix common backend formatting issues like "2023-01-01 10:00:00" (replace space with T)
    const isoFixed = ts.replace(" ", "T");
    d = new Date(isoFixed);
    if (!isNaN(d.getTime())) return d;

    return null;
  }
  return null;
}

interface ActiveRiskPanelProps {
  highRiskZones: ZoneAnalytics[];
  alerts: Alert[];
  cameras?: Camera[];
  onAcknowledge: (id: string) => void;
  alertLimit?: number;
}

const severityColors = {
  LOW: "border-l-risk-low",
  MEDIUM: "border-l-risk-medium",
  HIGH: "border-l-risk-high",
  CRITICAL: "border-l-risk-critical",
};

const severityBadgeColors = {
  LOW: "risk-low",
  MEDIUM: "risk-medium",
  HIGH: "risk-high",
  CRITICAL: "risk-critical",
};

const riskBgColors: Record<string, string> = {
  LOW: "bg-risk-low/10",
  MEDIUM: "bg-risk-medium/10",
  HIGH: "bg-risk-high/10",
  CRITICAL: "bg-risk-critical/15",
};

export function ActiveRiskPanel({
  highRiskZones,
  alerts,
  cameras = [],
  onAcknowledge,
  alertLimit = 3,
}: ActiveRiskPanelProps) {
  const displayAlerts = alerts.slice(0, alertLimit);

  return (
    <div className="glass-panel p-4 h-full flex flex-col">
      {/* Active Risk Zones Section */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-risk-high" />
            <h3 className="text-sm font-medium text-foreground">Active Risk Zones</h3>
          </div>
          <span className="text-xs text-muted-foreground bg-card px-2 py-0.5 rounded-full">
            {highRiskZones.length}
          </span>
        </div>

        {highRiskZones.length > 0 ? (
          <div className="grid grid-cols-1 gap-2">
            {highRiskZones.map((zone) => (
              <div
                key={zone.zone_id}
                className={cn(
                  "p-2.5 rounded-lg border transition-all",
                  riskBgColors[zone.risk_level],
                  zone.risk_level === "CRITICAL" && "border-risk-critical/40",
                  zone.risk_level === "HIGH" && "border-risk-high/30",
                  zone.risk_level === "CRITICAL" && "animate-pulse"
                )}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className={cn("risk-badge text-[9px] sm:text-[10px] shrink-0", severityBadgeColors[zone.risk_level])}>
                      {zone.risk_level}
                    </span>
                    <span className="text-xs sm:text-sm font-medium text-foreground truncate">{zone.zone_name}</span>
                  </div>
                  <div className="flex items-center gap-2 text-[10px] sm:text-xs text-muted-foreground shrink-0">
                    <span className="flex items-center gap-0.5">
                      <Activity className="w-2.5 h-2.5 sm:w-3 sm:h-3" />
                      {Math.round(zone.risk_score)}
                    </span>
                    <span className="hidden w-[1px] h-3 bg-border sm:block"></span>
                    <span className="hidden sm:inline">{zone.people_count} people</span>
                    <span className="sm:hidden">{zone.people_count}ppl</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-4 text-muted-foreground">
            <ShieldAlert className="w-6 h-6 mx-auto mb-2 opacity-50" />
            <p className="text-xs">All zones normal</p>
          </div>
        )
        }
      </div>

      {/* Divider */}
      <div className="border-t border-border/50 my-2" />

      {/* Recent Alerts Section */}
      <div className="flex-1 min-h-0">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-muted-foreground" />
            <h3 className="text-sm font-medium text-foreground">Recent Alerts</h3>
          </div>
          <span className="text-xs text-muted-foreground bg-card px-2 py-0.5 rounded-full">
            {alerts.length}
          </span>
        </div>

        {displayAlerts.length > 0 ? (
          <div className="space-y-2">
            {displayAlerts.map((alert) => (
              <div
                key={alert.id}
                className={cn(
                  "p-2.5 rounded-lg bg-card border-l-4 transition-opacity",
                  severityColors[alert.severity],
                  alert.acknowledged && "opacity-60"
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={cn("risk-badge text-[10px]", severityBadgeColors[alert.severity])}>
                        {alert.severity}
                      </span>
                      <span className="text-[10px] text-muted-foreground capitalize">{alert.type}</span>
                    </div>
                    <p className="text-xs font-medium text-foreground truncate">{alert.message}</p>
                    <div className="flex items-center gap-2 mt-1 text-[10px] text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <MapPin className="w-2.5 h-2.5" />
                        {(() => {
                          const camera = cameras.find(c => c.id === alert.cameraId);
                          const location = camera?.location;
                          return location
                            ? <span><span className="font-semibold">{location}</span> • {alert.cameraName}</span>
                            : <span>{alert.zoneName || alert.cameraName}</span>;
                        })()}
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock className="w-2.5 h-2.5" />
                        {(() => {
                          const date = parseBackendTimestamp(alert.timestamp);
                          return date ? date.toLocaleTimeString("en-IN", {
                            timeZone: "Asia/Kolkata",
                            hour12: true,
                            hour: "2-digit",
                            minute: "2-digit",
                            second: "2-digit"
                          }) : "Just now";
                        })()}
                      </span>
                    </div>
                  </div>
                  {!alert.acknowledged && (
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-6 w-6 p-0"
                      onClick={() => onAcknowledge(alert.id)}
                    >
                      <Check className="w-3 h-3" />
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-4 text-muted-foreground">
            <AlertTriangle className="w-6 h-6 mx-auto mb-2 opacity-50" />
            <p className="text-xs">No recent alerts</p>
          </div>
        )}
      </div>
    </div>
  );
}
