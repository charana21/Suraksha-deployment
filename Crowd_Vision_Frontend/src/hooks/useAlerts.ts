import { useState, useEffect, useCallback } from 'react';
import { Alert, CameraStats } from '@/types/camera';
import { formatDensity, formatMotion } from '@/lib/metrics';
import { useWebSocketAnalytics } from './useWebSocketAnalytics';
import { alertApi } from '@/services/alertApi';

const MAX_ALERTS = 100;
const ALERTS_CACHE_KEY = 'crowd_vision_alerts_cache';
const serializeAlert = (alert: Alert) => ({
  ...alert,
  timestamp: alert.timestamp.toISOString(),
});
const deserializeAlert = (alert: any): Alert => ({
  ...alert,
  timestamp: new Date(alert.timestamp),
});
let alertCache: Alert[] = [];

// Utility function to remove hex color codes from strings
const stripHexColors = (text: string): string => {
  if (!text) return text;
  // Remove hex color codes (e.g., #820bad, #845ee1) - matches # followed by 3 or 6 hex digits
  return text.replace(/#[0-9A-Fa-f]{3,6}\s*/g, '').trim();
};

export interface UseAlertsOptions {
  /** Enable WebSocket alerts (default: true) */
  useWebSocket?: boolean;
}

export function useAlerts(options: UseAlertsOptions = {}) {
  const { useWebSocket = true } = options;

  const getCachedAlerts = useCallback(() => {
    if (alertCache.length > 0) return alertCache;
    try {
      if (typeof sessionStorage === 'undefined') return [];
      const stored = sessionStorage.getItem(ALERTS_CACHE_KEY);
      if (!stored) return [];
      const parsed = JSON.parse(stored);
      if (!Array.isArray(parsed)) return [];
      alertCache = parsed.map(deserializeAlert);
      return alertCache;
    } catch (err) {
      return [];
    }
  }, []);

  const [alerts, setAlerts] = useState<Alert[]>(getCachedAlerts);
  const [isLoading, setIsLoading] = useState(alerts.length === 0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [totalCount, setTotalCount] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [cameraNameQuery, setCameraNameQueryState] = useState('');

  const setCameraNameQuery = useCallback((value: string) => {
    setCameraNameQueryState(value);
    setPage(1);
  }, []);

  const cacheAlerts = useCallback((items: Alert[]) => {
    alertCache = items;
    try {
      if (typeof sessionStorage === 'undefined') return;
      sessionStorage.setItem(ALERTS_CACHE_KEY, JSON.stringify(items.map(serializeAlert)));
    } catch (err) {
      // ignore storage errors
    }
  }, []);

  // Load active alerts (API + Local Storage fallback)
  const fetchActiveAlerts = useCallback(async () => {
    try {
      setIsLoading(true);

      const localAckStorage = localStorage.getItem('crowd_vision_acked_ids');
      const localAckSet = new Set(localAckStorage ? JSON.parse(localAckStorage) : []);

      let mappedAlerts: Alert[] = [];

      try {
        // Attempt backend fetch
        const data = await alertApi.listAlerts({
          hours: 24,
          page,
          pagesize: pageSize,
          camera_name: cameraNameQuery.trim() || undefined,
        });
        if (data && data.alerts) {
          const total = data.total ?? data.count ?? data.alerts.length;
          setTotalCount(total);
          setTotalPages(data.total_pages ?? Math.max(1, Math.ceil(total / pageSize)));
          mappedAlerts = data.alerts.map((apiAlert: any) => ({
            id: apiAlert.alert_id,
            cameraId: apiAlert.camera_id,
            cameraName: stripHexColors(apiAlert.camera_name || apiAlert.camera_id),
            type: (apiAlert.severity === 'CRITICAL' || apiAlert.severity === 'critical') ? 'stampede' : 'density',
            severity: apiAlert.severity.toUpperCase() as Alert['severity'], // Normalize case
            message: stripHexColors(apiAlert.trigger_reason || 'Alert triggered'),
            triggerReason: stripHexColors(apiAlert.trigger_reason || `Risk Score: ${apiAlert.risk_score}`),
            timestamp: new Date(apiAlert.timestamp.endsWith('Z') ? apiAlert.timestamp : apiAlert.timestamp + 'Z'),
            acknowledged: apiAlert.status === 'acknowledged' || localAckSet.has(apiAlert.alert_id),
            peopleCount: apiAlert.people_count,
            fobId: apiAlert.fob_id,
            zoneId: apiAlert.zone_id,
            zoneType: apiAlert.zone_type,
            imageId: apiAlert.image_id,
          }));
        }
      } catch (apiError) {
      }

      // 3. API Only (No Local Storage)
      const unique = Array.from(new Map(mappedAlerts.map(item => [item.id, item])).values());

      // Sort by timestamp desc
      unique.sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());

      const sliced = unique.slice(0, MAX_ALERTS);
      setAlerts(sliced);
      cacheAlerts(sliced);
    } catch (error) {
    } finally {
      setIsLoading(false);
    }
  }, [cacheAlerts, page, pageSize, cameraNameQuery]);

  useEffect(() => {
    fetchActiveAlerts();
  }, [fetchActiveAlerts]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const handler = () => {
      fetchActiveAlerts();
    };
    window.addEventListener("crowdvision:reports-exit", handler);
    return () => {
      window.removeEventListener("crowdvision:reports-exit", handler);
    };
  }, [fetchActiveAlerts]);

  // Setup WebSocket to receive alerts
  useWebSocketAnalytics({
    cameraId: null, // Subscribe to all cameras
    enabled: useWebSocket,
    onAlert: useCallback((cameraId: string, alertData) => {
      const newAlert: Alert = {
        id: alertData.alert_id,
        cameraId,
        cameraName: stripHexColors(cameraId),
        type: (alertData.severity === 'CRITICAL' || alertData.severity === 'critical') ? 'stampede' : 'density',
        severity: alertData.severity.toUpperCase() as Alert['severity'],
        message: stripHexColors(alertData.trigger_reason),
        triggerReason: stripHexColors(`Risk score: ${Math.round(alertData.risk_score)}/100`),
        timestamp: new Date(),
        acknowledged: alertData.status === 'acknowledged',
        peopleCount: (alertData as any).people_count,
      };

      setAlerts((prev) => {
        const exists = prev.some((a) => a.id === newAlert.id);
        if (exists) return prev;
        const updated = [newAlert, ...prev].slice(0, MAX_ALERTS);
        cacheAlerts(updated);
        return updated;
      });
      // Optionally save WS alerts to local storage? simpler to not, or treat them as API-like
    }, []),
  });

  const saveLocalAlerts = (alertsToSave: Alert[]) => {
    // Filter only local ones to save
    const localOnly = alertsToSave.filter(a => a.id.startsWith('local-'));
    localStorage.setItem('crowd_vision_local_alerts', JSON.stringify(localOnly));
  };

  const addAlert = useCallback((alert: Omit<Alert, 'id' | 'timestamp' | 'acknowledged'>) => {
    // Local transient alert
    const newAlert: Alert = {
      ...alert,
      id: `local-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date(),
      acknowledged: false,
    };

    setAlerts((prev) => {
      const updated = [newAlert, ...prev].slice(0, MAX_ALERTS);
      cacheAlerts(updated);
      saveLocalAlerts(updated);
      return updated;
    });
    return newAlert;
  }, []);

  const acknowledgeAlert = useCallback(async (id: string) => {
    // 1. Update Local State & Storage
    setAlerts((prev) => {
      const updated = prev.map((a) => (a.id === id ? { ...a, acknowledged: true } : a));
      cacheAlerts(updated);
      // Save the ack state for local alerts
      saveLocalAlerts(updated);
      return updated;
    });

    try {
      if (!id.startsWith('local-')) {
        await alertApi.acknowledgeAlert(id);
      } else {
        // For local alerts, we just saved the accepted state above via saveLocalAlerts logic?
        // Wait, saveLocalAlerts saves the object. If object has ack=true, it's saved.
      }

      // Persist global ACK ID
      const localAckStorage = localStorage.getItem('crowd_vision_acked_ids');
      const localAckSet = new Set(localAckStorage ? JSON.parse(localAckStorage) : []);
      localAckSet.add(id);
      localStorage.setItem('crowd_vision_acked_ids', JSON.stringify([...localAckSet]));

    } catch (error) {
    }
  }, []);

  const clearAlerts = useCallback(() => {
    const cleared: Alert[] = [];
    setAlerts(cleared);
    cacheAlerts(cleared);
    localStorage.removeItem('crowd_vision_local_alerts');
  }, []);

  // Check stats and generate alerts if thresholds exceeded (Client-side fallback)
  const checkForAlerts = useCallback(
    (stats: CameraStats, cameraName: string) => {
      const newAlerts: Omit<Alert, 'id' | 'timestamp' | 'acknowledged'>[] = [];

      // Check per-zone
      stats.zones.forEach((zone) => {
        if (zone.riskLevel === 'CRITICAL' || zone.riskLevel === 'HIGH') {
          newAlerts.push({
            cameraId: stats.cameraId,
            cameraName,
            zoneId: zone.id,
            zoneName: zone.name,
            type: 'Risk Alert',
            severity: zone.riskLevel,
            message: zone.riskLevel === 'CRITICAL' ? 'Critical safety threshold exceeded' : 'Crowd density threshold exceeded',
            triggerReason: `People: ${zone.peopleCount}, Density: ${formatDensity(zone.density)}`,
          });
        }
      });

      // Only add if we don't have a similar recent alert (within 10 seconds)
      const now = Date.now();
      newAlerts.forEach((alert) => {
        // We need to access current 'alerts' state here. 
        // CAUTION: 'alerts' in dependency array causes frequent recreation.
        // We will trust the function is called with fresh state or use ref if needed.
        // With current design, checkForAlerts deps on [alerts], so it sees fresh alerts.
        const hasRecent = alerts.some(
          (a) =>
            a.cameraId === alert.cameraId &&
            a.type === alert.type &&
            a.zoneId === alert.zoneId &&
            now - a.timestamp.getTime() < 10000
        );
        if (!hasRecent) {
          // addAlert(alert); // Disabled: User requested API-only alerts
        }
      });
    },
    [alerts, addAlert]
  );

  const getAlertsByCamera = useCallback(
    (cameraId: string) => alerts.filter((a) => a.cameraId === cameraId),
    [alerts]
  );

  const getAlertsBySeverity = useCallback(
    (severity: Alert['severity']) => alerts.filter((a) => a.severity === severity),
    [alerts]
  );

  const getUnacknowledgedAlerts = useCallback(
    () => alerts.filter((a) => !a.acknowledged),
    [alerts]
  );

  return {
    alerts,
    addAlert,
    acknowledgeAlert,
    clearAlerts,
    checkForAlerts,
    getAlertsByCamera,
    getAlertsBySeverity,
    getUnacknowledgedAlerts,
    isLoading,
    refresh: fetchActiveAlerts,
    page,
    setPage,
    pageSize,
    setPageSize,
    totalCount,
    totalPages,
    cameraNameQuery,
    setCameraNameQuery,
  };
}
