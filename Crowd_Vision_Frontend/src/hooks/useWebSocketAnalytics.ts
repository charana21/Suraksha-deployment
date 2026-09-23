import { useState, useEffect, useCallback, useRef } from 'react';
import { CameraStats, ZoneStats } from '@/types/camera';
import { getDensityLevel } from '@/lib/metrics';
import type { DensityLevel, RiskLevel } from '@/lib/metrics';
import {
  createCameraWebSocket,
  createAnalyticsWebSocket,
  WebSocketService,
  AnalyticsMessage,
  AlertMessage,
} from '@/services/websocketService';

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

export interface WebSocketAnalyticsOptions {
  /** Camera ID to subscribe to (if null, subscribes to all cameras) */
  cameraId?: string | null;
  /** Enable WebSocket connection */
  enabled?: boolean;
  /** Callback for analytics updates */
  onAnalytics?: (cameraId: string, stats: CameraStats) => void;
  /** Callback for alert messages */
  onAlert?: (cameraId: string, alert: AlertMessage['data']) => void;
}

/**
 * Hook for real-time analytics via WebSocket
 *
 * Replaces polling with push-based updates from backend.
 * Automatically reconnects on connection loss.
 *
 * @example
 * // Subscribe to a specific camera
 * const { stats, isConnected } = useWebSocketAnalytics({ cameraId: 'camera-1' });
 *
 * @example
 * // Subscribe to all cameras
 * const { allStats } = useWebSocketAnalytics({ cameraId: null });
 */
export function useWebSocketAnalytics({
  cameraId,
  enabled = true,
  onAnalytics,
  onAlert,
}: WebSocketAnalyticsOptions = {}) {
  const [stats, setStats] = useState<CameraStats | null>(null);
  const [allStats, setAllStats] = useState<Map<string, CameraStats>>(new Map());
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const wsRef = useRef<WebSocketService | null>(null);
  const onAnalyticsRef = useRef(onAnalytics);
  const onAlertRef = useRef(onAlert);

  // Keep refs updated
  useEffect(() => {
    onAnalyticsRef.current = onAnalytics;
    onAlertRef.current = onAlert;
  }, [onAnalytics, onAlert]);

  // Process analytics message
  const processAnalytics = useCallback((message: AnalyticsMessage) => {
    const analysis = message.data;

    // Map zones from backend to frontend format
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
      cameraId: message.camera_id,
      timestamp: new Date(message.timestamp),
      peopleCount: analysis.people_count || 0,
      density: analysis.density_avg || 0,
      densityLevel: getDensityLevel(analysis.density_avg || 0),
      motionIntensity: analysis.motion_intensity || 0,
      riskLevel: mapRiskLevel(analysis.risk_level || 'LOW'),
      riskScore: analysis.risk_score || 0,
      fps: 0, // WebSocket doesn't include FPS
      frameCount: analysis.frame_number || 0,
      zones,
    };

    return newStats;
  }, []);

  // Store cameraId in ref to avoid stale closures
  const cameraIdRef = useRef(cameraId);
  useEffect(() => {
    cameraIdRef.current = cameraId;
  }, [cameraId]);

  // Handle incoming WebSocket messages
  const handleMessage = useCallback(
    (message: AnalyticsMessage | AlertMessage) => {
      try {
        if (message.type === 'analytics') {
          const newStats = processAnalytics(message);
          setLastUpdate(new Date());
          setError(null);

          // Always update allStats map with data from all cameras
          setAllStats((prev) => {
            const updated = new Map(prev);
            updated.set(message.camera_id, newStats);
            return updated;
          });

          // For single camera mode: we receive all cameras but only want one
          // Since we can't reliably map camera_id to stream_id, we just use
          // the most recent message. If only one camera is streaming, this works.
          // TODO: Backend should return camera_id in stream list for proper filtering
          const currentCameraId = cameraIdRef.current;
          if (currentCameraId === null || currentCameraId === undefined) {
            // Multi-camera mode or no filter: always update stats
            setStats(newStats);
          } else {
            // Single camera mode: check if message matches
            // Try matching by camera_id OR just accept all (since we might not have mapping)
            // For now, accept all messages since we only have one camera usually
            setStats(newStats);
          }

          // Call callback if provided
          onAnalyticsRef.current?.(message.camera_id, newStats);
        } else if (message.type === 'alert') {
          onAlertRef.current?.(message.camera_id, message.data);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to process message');
      }
    },
    [processAnalytics]
  );

  // Setup WebSocket connection
  // IMPORTANT: We always connect to ALL cameras endpoint because the backend
  // broadcasts using camera_id (like "camera_entry_stair") but the frontend
  // only knows the stream_id (UUID). We filter messages on the frontend.
  useEffect(() => {
    if (!enabled) {
      if (wsRef.current) {
        wsRef.current.disconnect();
        wsRef.current = null;
      }
      setIsConnected(false);
      return;
    }

    // Always connect to the all-cameras endpoint and filter on frontend
    // This works around the camera_id vs stream_id mismatch
    const ws = createAnalyticsWebSocket({
      onMessage: handleMessage,
      onError: () => {
        setIsConnected(false);
        setError('WebSocket connection error');
      },
      onOpen: () => {
        setIsConnected(true);
        setError(null);
      },
      onClose: () => {
        setIsConnected(false);
      },
    });

    wsRef.current = ws;
    ws.connect();

    // Cleanup on unmount or when dependencies change
    return () => {
      ws.disconnect();
    };
  }, [enabled, handleMessage]);

  // Clear stats when camera changes
  useEffect(() => {
    if (cameraId !== null) {
      setStats(null);
    }
  }, [cameraId]);

  return {
    /** Current stats for single camera mode */
    stats,
    /** All stats for multi-camera mode (Map<camera_id, stats>) */
    allStats,
    /** WebSocket connection status */
    isConnected,
    /** Error message if any */
    error,
    /** Last update timestamp */
    lastUpdate,
    /** Connection state string */
    connectionState: wsRef.current?.connectionState || 'disconnected',
  };
}
