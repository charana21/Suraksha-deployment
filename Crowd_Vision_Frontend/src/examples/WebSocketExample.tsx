/**
 * WebSocket Example Component
 *
 * This is a standalone example showing how to use WebSocket analytics.
 * Use this for testing or as a reference for integration.
 */

import { useWebSocketAnalytics } from '@/hooks/useWebSocketAnalytics';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useState } from 'react';

export function WebSocketExample() {
  const [cameraId, setCameraId] = useState<string | null>('camera_entry_stair');
  const [enabled, setEnabled] = useState(true);

  const { stats, isConnected, connectionState, lastUpdate, allStats } = useWebSocketAnalytics({
    cameraId,
    enabled,
    onAnalytics: (id, data) => {
    },
    onAlert: (id, alert) => {
    },
  });

  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold">WebSocket Example</h1>
        <p className="text-muted-foreground">
          Real-time analytics via WebSocket (no polling)
        </p>
      </div>

      {/* Controls */}
      <Card>
        <CardHeader>
          <CardTitle>Connection Controls</CardTitle>
          <CardDescription>
            Test WebSocket connection and reconnection
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">Status:</span>
              <Badge
                variant={
                  connectionState === 'connected'
                    ? 'success'
                    : connectionState === 'connecting'
                    ? 'warning'
                    : 'destructive'
                }
              >
                {connectionState}
              </Badge>
            </div>

            {lastUpdate && (
              <div className="text-sm text-muted-foreground">
                Last update: {lastUpdate.toLocaleTimeString()}
              </div>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Button
              onClick={() => setEnabled(!enabled)}
              variant={enabled ? 'destructive' : 'default'}
            >
              {enabled ? 'Disconnect' : 'Connect'}
            </Button>

            <Button
              onClick={() => setCameraId(cameraId ? null : 'camera_entry_stair')}
              variant="outline"
            >
              {cameraId ? 'Subscribe to All' : 'Subscribe to Single'}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Single Camera Stats */}
      {cameraId && stats && (
        <Card>
          <CardHeader>
            <CardTitle>Camera: {cameraId}</CardTitle>
            <CardDescription>Real-time analytics data</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-sm text-muted-foreground">People Count</div>
                <div className="text-2xl font-bold">{stats.peopleCount}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">Density</div>
                <div className="text-2xl font-bold">
                  {stats.density.toFixed(2)}
                </div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">Risk Score</div>
                <div className="text-2xl font-bold">{stats.riskScore.toFixed(0)}</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground">Risk Level</div>
                <Badge
                  variant={
                    stats.riskLevel === 'CRITICAL' || stats.riskLevel === 'HIGH'
                      ? 'destructive'
                      : stats.riskLevel === 'MEDIUM'
                      ? 'warning'
                      : 'success'
                  }
                >
                  {stats.riskLevel}
                </Badge>
              </div>
            </div>

            {stats.zones.length > 0 && (
              <div className="mt-4">
                <div className="text-sm font-medium mb-2">Zones</div>
                <div className="space-y-2">
                  {stats.zones.map((zone) => (
                    <div
                      key={zone.id}
                      className="flex items-center justify-between p-2 bg-muted rounded"
                    >
                      <span className="text-sm">{zone.name}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-muted-foreground">
                          {zone.peopleCount} people
                        </span>
                        <Badge variant="outline">{zone.riskLevel}</Badge>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Multi-Camera Stats */}
      {!cameraId && allStats.size > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>All Cameras ({allStats.size})</CardTitle>
            <CardDescription>Multi-camera subscription</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4">
              {Array.from(allStats.entries()).map(([id, cameraStats]) => (
                <div
                  key={id}
                  className="flex items-center justify-between p-3 bg-muted rounded"
                >
                  <div>
                    <div className="font-medium">{id}</div>
                    <div className="text-sm text-muted-foreground">
                      {cameraStats.peopleCount} people, Risk: {cameraStats.riskLevel}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-lg font-bold">
                      {cameraStats.riskScore.toFixed(0)}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {cameraStats.timestamp.toLocaleTimeString()}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Instructions */}
      <Card>
        <CardHeader>
          <CardTitle>Testing Instructions</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <ol className="list-decimal list-inside space-y-2">
            <li>Open browser DevTools → Network tab → Filter by WS</li>
            <li>
              You should see a WebSocket connection to{' '}
              <code className="bg-muted px-1 py-0.5 rounded">
                ws://localhost:8000/api/ws/analytics
              </code>
            </li>
            <li>Click the connection to see real-time messages</li>
            <li>Try disconnecting/reconnecting using the button above</li>
            <li>Stop the backend to test automatic reconnection</li>
          </ol>

          <div className="mt-4 p-3 bg-muted rounded">
            <div className="font-medium mb-1">Console Logs</div>
            <div className="text-muted-foreground">
              Check browser console for [Analytics] and [Alert] logs from the
              onAnalytics and onAlert callbacks.
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default WebSocketExample;
