# WebSocket API Reference

Complete API documentation for WebSocket services and hooks.

---

## Table of Contents

1. [WebSocket Service](#websocket-service)
2. [useWebSocketAnalytics Hook](#usewebsocketanalytics-hook)
3. [useRealTimeAnalytics Hook](#userealtimeanalytics-hook)
4. [useAlerts Hook](#usealerts-hook)
5. [Message Types](#message-types)
6. [Type Definitions](#type-definitions)

---

## WebSocket Service

Low-level WebSocket connection manager.

### Import

```tsx
import {
  WebSocketService,
  createAnalyticsWebSocket,
  createCameraWebSocket,
} from '@/services/websocketService';
```

### Factory Functions

#### `createAnalyticsWebSocket(options?)`

Create WebSocket for all cameras.

```tsx
const ws = createAnalyticsWebSocket({
  onMessage: (message) => console.log(message),
  onError: (error) => console.error(error),
  onOpen: () => console.log('Connected'),
  onClose: () => console.log('Disconnected'),
  reconnectInterval: 3000,      // Initial delay (default: 3000)
  maxReconnectAttempts: 10,     // Max attempts (default: 10)
});

ws.connect();
```

#### `createCameraWebSocket(cameraId, options?)`

Create WebSocket for specific camera.

```tsx
const ws = createCameraWebSocket('camera_entry_stair', {
  onMessage: (message) => console.log(message),
});

ws.connect();
```

### WebSocketService Class

#### Properties

```tsx
ws.isConnected: boolean           // Connection state
ws.connectionState: string        // State: connecting|connected|closing|disconnected
```

#### Methods

```tsx
ws.connect(): void                // Connect to WebSocket
ws.disconnect(): void             // Disconnect (stops reconnection)
ws.onMessage(handler): () => void // Add message handler, returns cleanup fn
ws.onError(handler): () => void   // Add error handler
ws.onOpen(handler): () => void    // Add open handler
ws.onClose(handler): () => void   // Add close handler
```

#### Example: Manual Connection Management

```tsx
const ws = createAnalyticsWebSocket();

// Add handlers
const removeMessage = ws.onMessage((msg) => {
  console.log('Message:', msg);
});

const removeError = ws.onError((error) => {
  console.error('Error:', error);
});

// Connect
ws.connect();

// Later: cleanup
removeMessage();
removeError();
ws.disconnect();
```

---

## useWebSocketAnalytics Hook

React hook for WebSocket-based analytics.

### Import

```tsx
import { useWebSocketAnalytics } from '@/hooks/useWebSocketAnalytics';
```

### Signature

```tsx
function useWebSocketAnalytics(options?: {
  cameraId?: string | null;
  enabled?: boolean;
  onAnalytics?: (cameraId: string, stats: CameraStats) => void;
  onAlert?: (cameraId: string, alert: AlertMessage['data']) => void;
}): {
  stats: CameraStats | null;
  allStats: Map<string, CameraStats>;
  isConnected: boolean;
  error: string | null;
  lastUpdate: Date | null;
  connectionState: string;
}
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cameraId` | `string \| null` | `undefined` | Camera ID to subscribe to. `null` = all cameras |
| `enabled` | `boolean` | `true` | Enable/disable WebSocket connection |
| `onAnalytics` | `function` | `undefined` | Callback for analytics updates |
| `onAlert` | `function` | `undefined` | Callback for alert messages |

### Return Values

| Property | Type | Description |
|----------|------|-------------|
| `stats` | `CameraStats \| null` | Current stats (single camera mode) |
| `allStats` | `Map<string, CameraStats>` | All stats (multi-camera mode) |
| `isConnected` | `boolean` | WebSocket connection status |
| `error` | `string \| null` | Error message if any |
| `lastUpdate` | `Date \| null` | Last update timestamp |
| `connectionState` | `string` | Connection state string |

### Examples

#### Single Camera

```tsx
function CameraView() {
  const { stats, isConnected, lastUpdate } = useWebSocketAnalytics({
    cameraId: 'camera_entry_stair',
  });

  if (!isConnected) return <div>Connecting...</div>;
  if (!stats) return <div>Waiting for data...</div>;

  return (
    <div>
      <p>People: {stats.peopleCount}</p>
      <p>Updated: {lastUpdate?.toLocaleTimeString()}</p>
    </div>
  );
}
```

#### Multi-Camera

```tsx
function MultiCameraView() {
  const { allStats, isConnected } = useWebSocketAnalytics({
    cameraId: null, // Subscribe to ALL cameras
  });

  return (
    <div>
      {Array.from(allStats.entries()).map(([id, stats]) => (
        <div key={id}>
          <h3>{id}</h3>
          <p>People: {stats.peopleCount}</p>
        </div>
      ))}
    </div>
  );
}
```

#### With Callbacks

```tsx
function AlertingView() {
  const { stats } = useWebSocketAnalytics({
    cameraId: 'camera_entry_stair',
    onAnalytics: (id, data) => {
      console.log(`Analytics from ${id}:`, data);
    },
    onAlert: (id, alert) => {
      // Show toast notification
      toast.error(`Alert: ${alert.trigger_reason}`);
    },
  });

  return <div>{/* ... */}</div>;
}
```

---

## useRealTimeAnalytics Hook

High-level hook with WebSocket and polling fallback.

### Import

```tsx
import { useRealTimeAnalytics } from '@/hooks/useRealTimeAnalytics';
```

### Signature

```tsx
function useRealTimeAnalytics(
  streamId: string | null,
  options?: {
    useWebSocket?: boolean;
  }
): {
  stats: CameraStats | null;
  isLive: boolean;
  setIsLive: (live: boolean) => void;
  error: string | null;
  refresh: () => Promise<void>;
  isConnected?: boolean;
  connectionState?: string;
  lastUpdate?: Date | null;
}
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `streamId` | `string \| null` | required | Camera stream ID |
| `options.useWebSocket` | `boolean` | `true` | Use WebSocket (true) or polling (false) |

### Return Values

| Property | Type | Description |
|----------|------|-------------|
| `stats` | `CameraStats \| null` | Current analytics stats |
| `isLive` | `boolean` | Live updates enabled |
| `setIsLive` | `function` | Enable/disable live updates |
| `error` | `string \| null` | Error message |
| `refresh` | `function` | Manual refresh (polling mode) |
| `isConnected` | `boolean \| undefined` | WebSocket connected (WS mode only) |
| `connectionState` | `string \| undefined` | Connection state (WS mode only) |
| `lastUpdate` | `Date \| null \| undefined` | Last update time (WS mode only) |

### Examples

#### Default (WebSocket)

```tsx
function Dashboard() {
  const { stats, isConnected } = useRealTimeAnalytics('camera-1');

  return (
    <div>
      {isConnected ? '🟢 Live' : '🔴 Offline'}
      <p>People: {stats?.peopleCount}</p>
    </div>
  );
}
```

#### Polling Mode

```tsx
function Dashboard() {
  const { stats, refresh } = useRealTimeAnalytics('camera-1', {
    useWebSocket: false, // Use polling instead
  });

  return (
    <div>
      <button onClick={refresh}>Refresh</button>
      <p>People: {stats?.peopleCount}</p>
    </div>
  );
}
```

---

## useAlerts Hook

Hook for managing alerts with WebSocket support.

### Import

```tsx
import { useAlerts } from '@/hooks/useAlerts';
```

### Signature

```tsx
function useAlerts(options?: {
  useWebSocket?: boolean;
}): {
  alerts: Alert[];
  addAlert: (alert: Omit<Alert, 'id' | 'timestamp' | 'acknowledged'>) => Alert;
  acknowledgeAlert: (id: string) => void;
  clearAlerts: () => void;
  checkForAlerts: (stats: CameraStats, cameraName: string) => void;
  getAlertsByCamera: (cameraId: string) => Alert[];
  getAlertsBySeverity: (severity: Alert['severity']) => Alert[];
  getUnacknowledgedAlerts: () => Alert[];
  isLoading: boolean;
}
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `options.useWebSocket` | `boolean` | `true` | Enable WebSocket alerts |

### Examples

#### Default (WebSocket)

```tsx
function AlertsPanel() {
  const { alerts, acknowledgeAlert } = useAlerts();

  return (
    <div>
      {alerts.map((alert) => (
        <div key={alert.id}>
          <p>{alert.message}</p>
          {!alert.acknowledged && (
            <button onClick={() => acknowledgeAlert(alert.id)}>
              Acknowledge
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
```

---

## Message Types

### Analytics Message

Sent by backend when analytics are computed.

```typescript
interface AnalyticsMessage {
  type: 'analytics';
  camera_id: string;
  timestamp: string; // ISO 8601
  data: {
    frame_number: number;
    people_count: number;
    head_detections: number;
    density_avg: number;
    density_max: number;
    motion_intensity: number;
    risk_score: number;
    risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
    risk_factors: string[];
    zones?: {
      [key: string]: {
        id: string;
        name: string;
        coords: number[];
        people_count: number;
        head_detections: number;
        density_estimate: number;
        density_level: string;
        avg_motion: number;
        risk_score: number;
        risk_level: string;
        risk_factors: string[];
      };
    };
  };
}
```

### Alert Message

Sent by backend when alert is triggered.

```typescript
interface AlertMessage {
  type: 'alert';
  camera_id: string;
  timestamp: string; // ISO 8601
  data: {
    alert_id: string;
    severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
    trigger_reason: string;
    risk_score: number;
    status: 'triggered' | 'acknowledged' | 'resolved';
    has_image: boolean;
  };
}
```

### Union Type

```typescript
type WebSocketMessage = AnalyticsMessage | AlertMessage;
```

---

## Type Definitions

### CameraStats

```typescript
interface CameraStats {
  cameraId: string;
  timestamp: Date;
  peopleCount: number;
  density: number;
  densityLevel: 'LOW' | 'MODERATE' | 'HIGH' | 'VERY HIGH';
  motionIntensity: number;
  riskLevel: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  riskScore: number;
  fps: number;
  frameCount: number;
  zones: ZoneStats[];
}
```

### ZoneStats

```typescript
interface ZoneStats {
  id: string;
  name: string;
  peopleCount: number;
  density: number;
  densityLevel: 'LOW' | 'MODERATE' | 'HIGH' | 'VERY HIGH';
  motionIntensity: number;
  riskLevel: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  riskScore: number;
}
```

### Alert

```typescript
interface Alert {
  id: string;
  cameraId: string;
  cameraName: string;
  zoneId?: string;
  zoneName?: string;
  type: 'density' | 'surge' | 'stampede';
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  message: string;
  triggerReason: string;
  timestamp: Date;
  acknowledged: boolean;
}
```

---

## Connection States

| State | Description |
|-------|-------------|
| `connecting` | WebSocket connection is being established |
| `connected` | WebSocket is open and receiving data |
| `closing` | WebSocket is gracefully closing |
| `disconnected` | WebSocket is closed (will auto-reconnect) |

---

## Error Handling

### Connection Errors

```tsx
const { error, connectionState } = useWebSocketAnalytics({
  cameraId: 'camera-1',
});

if (error) {
  return <div>Error: {error}</div>;
}

if (connectionState === 'disconnected') {
  return <div>Reconnecting...</div>;
}
```

### Manual Error Handling

```tsx
const ws = createAnalyticsWebSocket({
  onError: (error) => {
    console.error('WebSocket error:', error);
    // Show toast notification
    toast.error('Connection lost. Reconnecting...');
  },
});
```

---

## Best Practices

### 1. Use High-Level Hooks

Prefer `useRealTimeAnalytics` over `useWebSocketAnalytics` unless you need advanced features.

```tsx
// Good
const { stats } = useRealTimeAnalytics('camera-1');

// Advanced use case
const { stats, allStats } = useWebSocketAnalytics({
  cameraId: null,
  onAlert: handleAlert,
});
```

### 2. Cleanup

Hooks automatically cleanup on unmount. Manual connections need cleanup:

```tsx
useEffect(() => {
  const ws = createAnalyticsWebSocket();
  ws.connect();

  return () => {
    ws.disconnect(); // Important!
  };
}, []);
```

### 3. Error Boundaries

Wrap components using WebSocket in error boundaries:

```tsx
<ErrorBoundary>
  <Dashboard />
</ErrorBoundary>
```

### 4. Loading States

Always handle loading/connecting states:

```tsx
const { stats, isConnected } = useWebSocketAnalytics({ cameraId });

if (!isConnected) {
  return <Skeleton />;
}

if (!stats) {
  return <div>Waiting for data...</div>;
}

return <div>{stats.peopleCount}</div>;
```

---

## Migration from Polling

### Before

```tsx
const { stats } = useRealTimeAnalytics(cameraId);
// Uses polling internally
```

### After

```tsx
const { stats } = useRealTimeAnalytics(cameraId);
// Uses WebSocket by default, same API!
```

No code changes required! WebSocket is now the default.

---

## Performance Tips

1. **Use single camera subscription** when possible (less memory)
2. **Disable when not visible** (e.g., inactive tabs)
3. **Debounce UI updates** for high-frequency data
4. **Use callbacks** for side effects instead of useEffect

```tsx
// Good: Callback-based
const { stats } = useWebSocketAnalytics({
  cameraId: 'camera-1',
  onAnalytics: (id, data) => {
    updateChart(data); // Direct side effect
  },
});

// Less efficient: useEffect-based
const { stats } = useWebSocketAnalytics({ cameraId: 'camera-1' });
useEffect(() => {
  if (stats) updateChart(stats);
}, [stats]);
```

---

## Complete Example

```tsx
import { useWebSocketAnalytics } from '@/hooks/useWebSocketAnalytics';
import { ConnectionIndicator } from '@/components/dashboard/ConnectionIndicator';

function CameraMonitor({ cameraId }: { cameraId: string }) {
  const {
    stats,
    isConnected,
    connectionState,
    lastUpdate,
    error,
  } = useWebSocketAnalytics({
    cameraId,
    enabled: true,
    onAnalytics: (id, data) => {
      console.log(`Analytics from ${id}:`, data);
    },
    onAlert: (id, alert) => {
      toast.error(`Alert: ${alert.trigger_reason}`);
    },
  });

  if (error) {
    return <div className="error">{error}</div>;
  }

  return (
    <div>
      <ConnectionIndicator
        connectionState={connectionState}
        lastUpdate={lastUpdate}
      />

      {stats && (
        <div>
          <h2>{cameraId}</h2>
          <p>People: {stats.peopleCount}</p>
          <p>Risk: {stats.riskLevel}</p>
          <p>Density: {stats.density.toFixed(2)}</p>
        </div>
      )}
    </div>
  );
}
```

---

## Summary

- **WebSocketService**: Low-level connection management
- **useWebSocketAnalytics**: Direct WebSocket hook
- **useRealTimeAnalytics**: High-level hook with fallback
- **useAlerts**: Alert management with WebSocket

All hooks provide automatic cleanup, reconnection, and error handling.
