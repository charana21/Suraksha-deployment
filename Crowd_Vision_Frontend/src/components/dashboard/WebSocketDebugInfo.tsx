import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface WebSocketDebugInfoProps {
  selectedCamera: {
    id: string;
    cameraId?: string;
    name: string;
  } | null;
  webSocketCameraId: string | null;
  connectionState?: string;
  isConnected?: boolean;
  stats?: {
    peopleCount: number;
    zones: { id: string; name: string }[];
  } | null;
  lastUpdate?: Date | null;
}

/**
 * Debug component to show WebSocket connection details
 * Remove this once WebSocket is working correctly
 */
export function WebSocketDebugInfo({
  selectedCamera,
  webSocketCameraId,
  connectionState,
  isConnected,
  stats,
  lastUpdate,
}: WebSocketDebugInfoProps) {
  if (!selectedCamera) return null;

  return (
    <Card className="border-blue-200 bg-blue-50/50">
      <CardHeader>
        <CardTitle className="text-sm">WebSocket Debug Info</CardTitle>
        <CardDescription className="text-xs">
          Remove this component once working
        </CardDescription>
      </CardHeader>
      <CardContent className="text-xs space-y-2">
        <div className="grid grid-cols-2 gap-2">
          <div>
            <span className="font-medium">Stream ID:</span>
            <code className="ml-1 bg-card px-1 py-0.5 rounded">
              {selectedCamera.id}
            </code>
          </div>
          <div>
            <span className="font-medium">Camera ID:</span>
            <code className="ml-1 bg-card px-1 py-0.5 rounded">
              {selectedCamera.cameraId || 'NOT SET'}
            </code>
          </div>
        </div>

        <div>
          <span className="font-medium">WebSocket Subscribing To:</span>
          <code className="ml-1 bg-card px-1 py-0.5 rounded">
            {webSocketCameraId || 'null'}
          </code>
        </div>

        <div className="flex items-center gap-2">
          <span className="font-medium">Connection:</span>
          <Badge
            variant={
              isConnected ? 'success' : connectionState === 'connecting' ? 'warning' : 'destructive'
            }
          >
            {connectionState || 'unknown'}
          </Badge>
        </div>

        <div className="pt-2 border-t border-blue-200 space-y-1">
          <div>
            <span className="font-medium">Data Received:</span>
            {stats ? (
              <span className="ml-1 text-green-600">
                ✓ People: {stats.peopleCount}, Zones: {stats.zones.length}
              </span>
            ) : (
              <span className="ml-1 text-yellow-600">
                ⏳ Waiting for data...
              </span>
            )}
          </div>
          {lastUpdate && (
            <div>
              <span className="font-medium">Last Update:</span>
              <span className="ml-1">{lastUpdate.toLocaleTimeString()}</span>
            </div>
          )}
          <p className="text-xs text-muted-foreground pt-1">
            {selectedCamera.cameraId ? (
              <span className="text-green-600">
                ✓ Camera ID is set. WebSocket should work.
              </span>
            ) : (
              <span className="text-red-600">
                ✗ Camera ID is missing! Backend needs to return camera_id in stream response.
              </span>
            )}
          </p>
          <p className="text-xs text-muted-foreground">
            Check browser console for [WebSocket] logs
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
