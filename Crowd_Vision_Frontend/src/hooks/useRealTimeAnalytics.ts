import { useState, useEffect, useCallback } from 'react';
import { CameraStats, ZoneStats } from '@/types/camera';
import { rtspApi } from '@/services/rtspApi';
import { getDensityLevel, getRiskLevel } from '@/lib/metrics';
import type { DensityLevel, RiskLevel } from '@/lib/metrics';
import { useWebSocketAnalytics } from './useWebSocketAnalytics';

const POLL_INTERVAL = 2000; // Poll every 2 seconds for real-time updates (fallback mode)

function mapDensityLevel(level: string): DensityLevel {
  const upperLevel = level.toUpperCase();
  if (upperLevel === 'LOW') return 'LOW';
  if (upperLevel === 'MODERATE') return 'MODERATE';
  if (upperLevel === 'HIGH') return 'HIGH';
  return 'VERY HIGH';
}

function mapRiskLevel(level: string): RiskLevel {
  const upperLevel = level.toUpperCase();
  if (upperLevel === 'LOW') return 'LOW';
  if (upperLevel === 'MEDIUM') return 'MEDIUM';
  if (upperLevel === 'HIGH') return 'HIGH';
  return 'CRITICAL';
}

export interface RealTimeAnalyticsOptions {
  /** Enable WebSocket (default: true). Set to false to use polling */
  useWebSocket?: boolean;
}

export function useRealTimeAnalytics(
  streamId: string | null,
  options: RealTimeAnalyticsOptions = {}
) {
  const { useWebSocket = true } = options;

  const [stats, setStats] = useState<CameraStats | null>(null);
  const [isLive, setIsLive] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // WebSocket-based analytics (default)
  const wsAnalytics = useWebSocketAnalytics({
    cameraId: streamId,
    enabled: useWebSocket && isLive,
  });

  const fetchStreamAnalytics = useCallback(async () => {
    if (!streamId || !isLive) return;

    try {
      const streamState = await rtspApi.getStreamStatus(streamId);

      if (!streamState.last_analysis) {
        // No analysis data yet
        setStats(null);
        return;
      }

      const analysis = streamState.last_analysis;

      // Map zones from backend to frontend format
      // Backend returns zones as an object with zone IDs as keys
      const zones: ZoneStats[] = analysis.zones
        ? Object.values(analysis.zones).map((zone: any) => ({
            id: zone.id,
            name: zone.name,
            peopleCount: zone.people_count || zone.head_detections || 0,
            density: zone.density_estimate || 0,
            densityLevel: mapDensityLevel(zone.density_level),
            motionIntensity: zone.avg_motion || 0,
            riskLevel: mapRiskLevel(zone.risk_level),
            riskScore: zone.risk_score || 0,
          }))
        : [];

      // Create stats object from backend data
      const newStats: CameraStats = {
        cameraId: streamId,
        timestamp: new Date(),
        peopleCount: analysis.people_count || 0,
        density: analysis.density_avg || 0,
        densityLevel: 'LOW', // Backend doesn't provide overall density level, derive from zones
        motionIntensity: analysis.motion_intensity || 0,
        riskLevel: 'LOW', // Backend doesn't provide overall risk level, derive from zones
        riskScore: zones.length > 0 ? Math.max(...zones.map(z => z.riskScore)) : 0,
        fps: streamState.fps || 0,
        frameCount: streamState.frame_count || 0,
        zones,
      };

      // Derive overall density level from average density using production ranges
      newStats.densityLevel = getDensityLevel(newStats.density);

      // Derive overall risk level from zone risk scores using production ranges
      newStats.riskLevel = getRiskLevel(newStats.riskScore);

      setStats(newStats);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch analytics');
    }
  }, [streamId, isLive]);

  // Use WebSocket data when available
  useEffect(() => {
    if (useWebSocket && wsAnalytics.stats) {
      setStats(wsAnalytics.stats);
      setError(wsAnalytics.error);
    }
  }, [useWebSocket, wsAnalytics.stats, wsAnalytics.error]);

  // Fallback to polling when WebSocket is disabled
  useEffect(() => {
    if (useWebSocket || !streamId || !isLive) {
      if (!useWebSocket) {
        setStats(null);
      }
      return;
    }

    // Polling mode (fallback)
    fetchStreamAnalytics();
    const interval = setInterval(fetchStreamAnalytics, POLL_INTERVAL);

    return () => clearInterval(interval);
  }, [useWebSocket, streamId, isLive, fetchStreamAnalytics]);

  return {
    stats: useWebSocket ? wsAnalytics.stats : stats,
    isLive,
    setIsLive,
    error: useWebSocket ? wsAnalytics.error : error,
    refresh: fetchStreamAnalytics,
    isConnected: useWebSocket ? wsAnalytics.isConnected : undefined,
    connectionState: useWebSocket ? wsAnalytics.connectionState : undefined,
    lastUpdate: useWebSocket ? wsAnalytics.lastUpdate : undefined,
  };
}
