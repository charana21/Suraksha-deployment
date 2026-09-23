import { useState, useMemo, useEffect } from "react";
import { PageLayout } from "@/components/layout/PageLayout";
import { FOBMapViewer } from "@/components/fob-map/FOBMapViewer";
import { FOBPeopleCountChart } from "@/components/dashboard/FOBPeopleCountChart";
import { StatsOverview, RiskCounts } from "@/components/dashboard/StatsOverview";
import { ActiveRiskPanel } from "@/components/dashboard/ActiveRiskPanel";
import { useZoneAnalytics } from "@/hooks/useZoneAnalytics";
import { useAlerts } from "@/hooks/useAlerts";
import { useCameras } from "@/hooks/useCameras";
import {
  WifiOff,
  RefreshCw,
  Building2,
  ChevronDown,
  Settings2,
} from "lucide-react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogTrigger,
} from "@/components/ui/dialog";
import { UpcomingTrains } from "@/components/dashboard/UpcomingTrains";
import { TrainUpload } from "@/components/admin/TrainUpload";
import { getMotionLevel, getRiskLevel } from "@/lib/metrics";
import { cn } from "@/lib/utils";

const LiveClock = () => {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => {
      setTime(new Date());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <span className="text-xs font-mono font-medium text-foreground">
      {time.toLocaleTimeString("en-IN", {
        timeZone: "Asia/Kolkata",
        hour12: true,
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
      })}
    </span>
  );
};

const FOB_OPTIONS = [
  { id: "HYB", name: "Hyderabad FOB", shortName: "HYD" },
  { id: "KZJ", name: "Kazipet FOB", shortName: "KZJ" },
];

export default function Dashboard() {
  const [selectedZoneId, setSelectedZoneId] = useState<string | null>(null);
  const [fobId, setFobId] = useState<string>("HYB");

  const { zones: rawZones, isLoading, isConnected, refresh, lastUpdate, dataTimestamp } = useZoneAnalytics({
    stationId: fobId,
    enableWebSocket: true,
  });

  const { alerts, acknowledgeAlert, checkForAlerts } = useAlerts();
  const { cameras } = useCameras();

  const selectedFOB = FOB_OPTIONS.find((f) => f.id === fobId) || FOB_OPTIONS[0];

  // Recalculate risk levels based on scores to ensure frontend settings match
  const zones = useMemo(() => {
    return rawZones.map(z => ({
      ...z,
      risk_level: getRiskLevel(z.risk_score || 0)
    }));
  }, [rawZones]);

  // -----------------------------
  // GLOBAL RISK
  // -----------------------------
  const globalRisk = useMemo(() => {
    if (!zones.length) return "LOW";
    if (zones.some((z) => z.risk_level === "CRITICAL")) return "CRITICAL";
    if (zones.some((z) => z.risk_level === "HIGH")) return "HIGH";
    if (zones.some((z) => z.risk_level === "MEDIUM")) return "MEDIUM";
    return "LOW";
  }, [zones]);

  const highRiskZones = zones.filter(
    (z) => z.risk_level === "HIGH" || z.risk_level === "CRITICAL"
  );

  const highRiskZone = highRiskZones[0];

  const riskCounts: RiskCounts = useMemo(() => ({
    LOW: zones.filter((z) => z.risk_level === "LOW").length,
    MEDIUM: zones.filter((z) => z.risk_level === "MEDIUM").length,
    HIGH: zones.filter((z) => z.risk_level === "HIGH").length,
    CRITICAL: zones.filter((z) => z.risk_level === "CRITICAL").length,
  }), [zones]);

  // -----------------------------
  // AGGREGATES
  // -----------------------------
  const totalPeople = zones.reduce((acc, z) => acc + (z.people_count || 0), 0);

  const avgDensity =
    zones.length > 0
      ? zones.reduce((a, z) => a + (z.density_avg || 0), 0) / zones.length
      : 0;

  const dashboardStats = useMemo(() => {
    // If no zones, return 0/default stats
    const count = zones.length || 1;
    const avgMotionIntensity = zones.length > 0
      ? zones.reduce((a, z) => a + (z.motion_intensity || 0), 0) / zones.length
      : 0;

    const avgRiskScore = zones.length > 0
      ? zones.reduce((a, z) => a + (z.risk_score || 0), 0) / zones.length
      : 0;

    return {
      peopleCount: totalPeople,
      density: avgDensity,
      motionIntensity: avgMotionIntensity,
      motionLevel: getMotionLevel(avgMotionIntensity),
      riskLevel: globalRisk,
      riskScore: avgRiskScore,
      densityLevel: globalRisk,
    };
  }, [zones, totalPeople, avgDensity, globalRisk]);

  // Generate alerts from zone data
  useEffect(() => {
    if (zones.length > 0) {
      const stats = {
        cameraId: fobId,
        riskLevel: dashboardStats.riskLevel,
        riskScore: dashboardStats.riskScore,
        density: dashboardStats.density,
        motionIntensity: dashboardStats.motionIntensity,
        zones: zones.map(z => ({
          id: z.zone_id,
          name: z.zone_name,
          riskLevel: z.risk_level,
          peopleCount: z.people_count,
          density: z.density_avg,
          motionIntensity: z.motion_intensity
        }))
      };
      checkForAlerts(stats as any, `${selectedFOB.name} System`);
    }
  }, [zones, dashboardStats, checkForAlerts, fobId, selectedFOB.name]);

  // Compute effective live status (WebSocket connected OR polling successfully)
  const isLive = useMemo(() => {
    if (isConnected) return true;
    if (lastUpdate && !isLoading) {
      // If we have a recent update (within 10s), consider it live
      const diff = new Date().getTime() - lastUpdate.getTime();
      return diff < 10000;
    }
    return false;
  }, [isConnected, lastUpdate, isLoading]);

  return (
    <PageLayout>
      <div className="space-y-5 lg:space-y-6 animate-fade-in max-w-[1600px] 2xl:max-w-[2400px] min-[2560px]:max-w-[98%] mx-auto min-[2560px]:gap-10">
        {/* ================= HEADER ================= */}
        <header className="grid grid-cols-1 lg:grid-cols-[1fr_auto_1fr] items-center gap-4 lg:gap-6 pb-3 lg:pb-4">
          {/* Left: Title */}
          <div className="text-center lg:text-left">
            <h1 className="text-2xl lg:text-3xl font-bold text-foreground tracking-tight" style={{ fontFamily: "'Outfit', sans-serif" }}>
              Dashboard
            </h1>
            <p className="text-xs lg:text-sm text-muted-foreground mt-0.5" style={{ fontFamily: "'Outfit', sans-serif" }}>
              Real-time crowd monitoring & analytics
            </p>
          </div>

          {/* Center: FOB SELECTOR */}
          <div className="flex justify-center">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="fob-selector group px-6 py-3 text-base lg:text-lg">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-primary/20">
                      <Building2 className="h-5 w-5 text-primary" />
                    </div>
                    <div className="text-left">
                      <div className="text-[10px] uppercase text-muted-foreground leading-none mb-1">
                        Active FOB
                      </div>
                      <div className="text-base lg:text-lg font-bold leading-none">{selectedFOB.name}</div>
                    </div>
                  </div>
                  <ChevronDown className="ml-4 h-5 w-5" />
                </button>
              </DropdownMenuTrigger>

              <DropdownMenuContent align="center" className="w-[240px]">
                {FOB_OPTIONS.map((fob) => (
                  <DropdownMenuItem
                    key={fob.id}
                    onClick={() => setFobId(fob.id)}
                    className={fobId === fob.id ? "bg-primary/10" : ""}
                  >
                    <Building2 className="h-4 w-4 mr-2" />
                    {fob.name}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>

          {/* Right: STATUS & ACTIONS */}
          <div className="flex justify-center lg:justify-end items-center gap-3">
            {/* ADMIN UPLOADS */}
            <Dialog>
              <DialogTrigger asChild>
                <button
                  className="px-3 py-2 rounded-lg border border-border hover:bg-muted transition-colors flex items-center gap-2 text-sm font-medium"
                  title="Upload Train Schedule"
                >
                  <Settings2 className="h-4 w-4 text-muted-foreground" />
                  <span className="hidden sm:inline">Upload Schedule</span>
                </button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-[600px] p-0 overflow-hidden bg-card">
                <TrainUpload />
              </DialogContent>
            </Dialog>

            {/* STATUS & LATENCY */}
            <div className="flex items-center gap-3 pl-3 border-l border-border">
              {/* Latency Indicator */}
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-card border border-border/50 shadow-sm">
                <div className="w-2 h-2 rounded-full animate-pulse bg-primary/50" />
                <LiveClock />
              </div>
              <div
                className={`status-indicator ${isLive ? "live" : "offline"}`}
              >
                {isLive ? "LIVE" : <WifiOff size={14} />}
              </div>

              <button
                onClick={refresh}
                className="p-2 rounded-lg border border-border hover:bg-muted transition-colors"
                title="Refresh"
              >
                <RefreshCw
                  className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`}
                />
              </button>
            </div>
          </div>
        </header>

        {/* ================= STATS ================= */}
        <div className="w-full">
          <StatsOverview stats={dashboardStats} riskCounts={riskCounts} />
        </div>

        {/* ================= MAP WITH TRAINS OVERLAY ================= */}
        <div className="w-full relative">
          {isLoading && zones.length === 0 ? (
            <div className="glass-panel p-6 h-[400px] lg:h-[600px] xl:h-[650px] 2xl:h-[750px] min-[2560px]:h-[950px] flex items-center justify-center rounded-2xl">
              <div className="loader" />
            </div>
          ) : (
            <div className="relative w-full">
              {/* Map Container - Constrained width on large screens to avoid overlay */}
              <div className="relative w-full h-[400px] lg:h-[600px] xl:h-[650px] 2xl:h-[750px] min-[2560px]:h-[950px] bg-card/30 rounded-2xl border border-border/50">
                <FOBMapViewer
                  zones={zones}
                  selectedZoneId={selectedZoneId}
                  onZoneSelect={setSelectedZoneId}
                  title={`${selectedFOB.name.toUpperCase()} VIEW`}
                  className="absolute inset-0 w-full h-full xl:w-[calc(100%-300px)]"
                  variant="dashboard"
                />
              </div>

              {/* TRAIN SCHEDULE - Overlay on Desktop (XL+) */}
              <div className="hidden xl:block absolute top-4 right-4 w-72 z-30">
                <UpcomingTrains variant="overlay" />
              </div>

              {/* TRAIN SCHEDULE - Below map on Mobile/Tablet/Laptop (LG) */}
              <div className="xl:hidden mt-5">
                <div className="mb-3 font-bold text-muted-foreground text-xs uppercase tracking-widest text-center">
                  Train Schedule
                </div>
                <div className="bg-card/90 backdrop-blur-md rounded-xl border border-border/50 p-1">
                  <UpcomingTrains variant="overlay" />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* ================= CHART + ACTIVE RISK PANEL ================= */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 lg:gap-6">
          <div className="w-full">
            <FOBPeopleCountChart
              currentCount={totalPeople}
              currentDensity={avgDensity}
              title={`${selectedFOB.id} FOB Total Footfall`}
              fobId={selectedFOB.id}
              minimalHeader={true}
            />
          </div>

          <div className="w-full">
            <ActiveRiskPanel
              highRiskZones={highRiskZones}
              alerts={alerts}
              cameras={cameras}
              onAcknowledge={acknowledgeAlert}
              alertLimit={4}
            />
          </div>
        </div>
      </div>
    </PageLayout>
  );
}
