import { useEffect } from "react";
import { PageLayout } from "@/components/layout/PageLayout";
import { CameraSelector } from "@/components/dashboard/CameraSelector";
import { StatsOverview } from "@/components/dashboard/StatsOverview";
import { ZoneAnalytics } from "@/components/dashboard/ZoneAnalytics";
import { HeatmapViewer } from "@/components/dashboard/HeatmapViewer";
import { RecentAlerts } from "@/components/dashboard/RecentAlerts";
import { ConnectionIndicator } from "@/components/dashboard/ConnectionIndicator";
import { WebSocketDebugInfo } from "@/components/dashboard/WebSocketDebugInfo";
import { useCameras } from "@/hooks/useCameras";
import { useRealTimeAnalytics } from "@/hooks/useRealTimeAnalytics";
import { useAlerts } from "@/hooks/useAlerts";
import { Circle } from "lucide-react";

export default function Heatmaps() {
  const {
    cameras,
    selectedCamera,
    selectedCameraId,
    setSelectedCameraId,
    getFrameUrl,
  } = useCameras();

  // Use camera_id for WebSocket (e.g., "camera_entry_stair"), fallback to stream_id if not available
  const webSocketCameraId = selectedCamera?.cameraId || selectedCameraId;

  const { stats, isLive, setIsLive, isConnected, connectionState, lastUpdate } =
    useRealTimeAnalytics(webSocketCameraId);
  const { alerts, acknowledgeAlert, checkForAlerts, getUnacknowledgedAlerts } =
    useAlerts();

  // Check for alerts when stats update
  useEffect(() => {
    if (stats && selectedCamera) {
      checkForAlerts(stats, selectedCamera.name);
    }
  }, [stats, selectedCamera, checkForAlerts]);

  const unacknowledgedCount = getUnacknowledgedAlerts().length;

  return (
    <PageLayout>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-foreground">
              Dashboard
            </h1>
            <p className="text-sm text-muted-foreground">
              Real-time crowd analytics and monitoring
            </p>
          </div>
          <div className="flex items-center gap-4">
            {unacknowledgedCount > 0 && (
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-risk-critical/10 text-risk-critical text-sm font-medium">
                <Circle className="w-2 h-2 fill-current animate-pulse" />
                {unacknowledgedCount} active alert
                {unacknowledgedCount > 1 ? "s" : ""}
              </div>
            )}
            {/* WebSocket Connection Indicator */}
            {connectionState && (
              <ConnectionIndicator
                connectionState={connectionState}
                lastUpdate={lastUpdate}
              />
            )}
            {/* Live/Paused Toggle Status */}
            <div className="flex items-center gap-2 text-sm">
              <Circle
                className={`w-2 h-2 fill-current ${
                  isLive ? "text-status-active" : "text-status-inactive"
                }`}
              />
              <span className="text-muted-foreground">
                {isLive ? "Updates On" : "Paused"}
              </span>
            </div>
          </div>
        </div>

        {/* Camera Selector - Compact horizontal */}
        <CameraSelector
          cameras={cameras}
          selectedId={selectedCameraId}
          onSelect={setSelectedCameraId}
        />

        {/* Debug Info - Remove once WebSocket is working */}
        {/* <WebSocketDebugInfo
          selectedCamera={selectedCamera}
          webSocketCameraId={webSocketCameraId}
          connectionState={connectionState}
          isConnected={isConnected}
          stats={stats}
          lastUpdate={lastUpdate}
        /> */}

        {/* Stats Overview */}
        <StatsOverview stats={stats} />

        {/* Main Content Grid */}
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Left Column - Live Feed with Heatmap */}
          <div className="lg:col-span-2">
            <HeatmapViewer
              heatmap={null}
              type="density"
              onTypeChange={() => {}}
              streamId={selectedCameraId}
              frameUrl={
                selectedCameraId
                  ? getFrameUrl(selectedCameraId, false)
                  : undefined
              }
            />
          </div>

          {/* Right Column - Zone Analytics + Alerts */}
          <div className="lg:col-span-1 space-y-6">
            {/* <ZoneAnalytics zones={stats?.zones || []} /> */}
            <RecentAlerts
              alerts={alerts}
              onAcknowledge={acknowledgeAlert}
              limit={4}
            />
          </div>
        </div>

        {/* FOB Total Footfall Chart */}
      </div>
    </PageLayout>
  );
}
