import { Alert } from "@/types/camera";
import { cn } from "@/lib/utils";
import { AlertTriangle, Clock, MapPin, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { formatDistanceToNow } from "date-fns";

function parseBackendTimestamp(ts?: unknown): Date | null {
  if (!ts) return null;

  // Already a Date
  if (ts instanceof Date) {
    return isNaN(ts.getTime()) ? null : ts;
  }

  // Unix timestamp (number)
  if (typeof ts === "number") {
    const d = new Date(ts);
    return isNaN(d.getTime()) ? null : d;
  }

  // ISO string (most common)
  if (typeof ts === "string") {
    // Trim microseconds → milliseconds
    const fixed = ts.replace(/\.(\d{3})\d+/, ".$1");
    const d = new Date(fixed);
    return isNaN(d.getTime()) ? null : d;
  }

  // Anything else → invalid
  return null;
}

interface RecentAlertsProps {
  alerts: Alert[];
  onAcknowledge: (id: string) => void;
  limit?: number;
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

export function RecentAlerts({
  alerts,
  onAcknowledge,
  limit = 5,
}: RecentAlertsProps) {
  const displayAlerts = alerts.slice(0, limit);

  if (displayAlerts.length === 0) {
    return (
      <div className="glass-panel p-6 text-center">
        <AlertTriangle className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
        <p className="text-sm text-muted-foreground">No recent alerts</p>
      </div>
    );
  }

  return (
    <div className="glass-panel p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-foreground">Recent Alerts</h3>
        <span className="text-xs text-muted-foreground">
          {alerts.length} total
        </span>
      </div>

      <div className="space-y-2">
        {displayAlerts.map((alert) => (
          <div
            key={alert.id}
            className={cn(
              "p-3 rounded-lg bg-card border-l-4 transition-opacity",
              severityColors[alert.severity],
              alert.acknowledged && "opacity-60"
            )}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span
                    className={cn(
                      "risk-badge",
                      severityBadgeColors[alert.severity]
                    )}
                  >
                    {alert.severity}
                  </span>
                  <span className="text-xs text-muted-foreground capitalize">
                    {alert.type}
                  </span>
                </div>
                <p className="text-sm font-medium text-foreground truncate">
                  {alert.message}
                </p>
                <div className="flex items-center gap-3 mt-1.5 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <MapPin className="w-3 h-3" />
                    {alert.cameraName}
                    {alert.zoneName && ` • ${alert.zoneName}`}
                  </span>
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {(() => {
                      const date = parseBackendTimestamp(alert.timestamp);
                      return date
                        ? date.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', dateStyle: 'medium', timeStyle: 'medium' })
                        : "Unknown";
                    })()}
                  </span>
                </div>
              </div>

              {!alert.acknowledged && (
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 px-2"
                  onClick={() => onAcknowledge(alert.id)}
                >
                  <Check className="w-3.5 h-3.5" />
                </Button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
