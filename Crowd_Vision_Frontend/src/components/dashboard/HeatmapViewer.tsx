import { HeatmapData } from '@/types/camera';
import { cn } from '@/lib/utils';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useState, useEffect, useRef } from 'react';
import { rtspApi } from '@/services/rtspApi';

interface HeatmapViewerProps {
  heatmap: HeatmapData | null;
  type: 'density' | 'motion' | 'risk';
  onTypeChange: (type: 'density' | 'motion' | 'risk') => void;
  streamId?: string | null;
  frameUrl?: string;
}

const typeLabels = {
  density: 'Density',
  motion: 'Motion',
  risk: 'Risk',
};

function getHeatColor(value: number, type: 'density' | 'motion' | 'risk'): string {
  // Low to high color gradients
  if (type === 'risk') {
    if (value < 0.25) return 'hsl(142, 76%, 36%)'; // Green
    if (value < 0.5) return 'hsl(38, 92%, 50%)'; // Yellow
    if (value < 0.75) return 'hsl(25, 95%, 53%)'; // Orange
    return 'hsl(0, 84%, 60%)'; // Red
  }
  
  // Blue gradient for density and motion
  const intensity = Math.floor(value * 100);
  return `hsl(215, 90%, ${90 - intensity * 0.6}%)`;
}

export function HeatmapViewer({ heatmap, type, onTypeChange, streamId, frameUrl }: HeatmapViewerProps) {
  const [imageKey, setImageKey] = useState(0);
  const [showHeatmap, setShowHeatmap] = useState(true);
  const [lastValidFrame, setLastValidFrame] = useState<string | null>(null);
  const [isLoadingNewFrame, setIsLoadingNewFrame] = useState(false);
  const [lastFrameNumber, setLastFrameNumber] = useState<number>(0);
  const [streamStatus, setStreamStatus] = useState<string>('unknown');
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  // Poll stream status to know when new frames are available
  useEffect(() => {
    if (!streamId) {
      setLastFrameNumber(0);
      setStreamStatus('unknown');
      return;
    }

    const checkForNewFrame = async () => {
      try {
        const status = await rtspApi.getStreamStatus(streamId);
        setStreamStatus(status.status);

        // Check if a new frame is available
        const currentFrameNumber = status.frame_count || 0;

        if (currentFrameNumber > lastFrameNumber) {
          // New frame available! Trigger fetch
          setLastFrameNumber(currentFrameNumber);
          setImageKey(prev => prev + 1);
          setIsLoadingNewFrame(true);
        }
      } catch (error) {
        setStreamStatus('error');
      }
    };

    // Initial check
    checkForNewFrame();

    // Poll every 1 second to detect new frames quickly
    pollingRef.current = setInterval(checkForNewFrame, 1000);

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, [streamId, lastFrameNumber]);

  // When heatmap toggle changes, trigger immediate refresh if we have a frame
  useEffect(() => {
    if (frameUrl && lastFrameNumber > 0) {
      setImageKey(prev => prev + 1);
      setIsLoadingNewFrame(true);
    }
  }, [showHeatmap]);

  return (
    <div className="glass-panel p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-foreground">Live Feed</h3>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
            <input
              type="checkbox"
              checked={showHeatmap}
              onChange={(e) => setShowHeatmap(e.target.checked)}
              className="w-3 h-3 rounded border-border"
            />
            Show Heatmap
          </label>
        </div>
      </div>

      {streamId && frameUrl ? (
        <div className="relative aspect-video bg-secondary rounded-lg overflow-hidden">
          {/* Persistent layer: Always show last valid frame in background */}
          {lastValidFrame && (
            <img
              key="background"
              src={lastValidFrame}
              alt="Last valid frame"
              className="absolute inset-0 w-full h-full object-contain"
            />
          )}

          {/* Foreground layer: Try to load new frame on top */}
          <img
            key={`current-${imageKey}`}
            src={`${frameUrl}${frameUrl?.includes('?') ? '&' : '?'}heatmap=${showHeatmap}&t=${imageKey}`}
            alt="Live stream frame"
            className={cn(
              "absolute inset-0 w-full h-full object-contain transition-opacity duration-300",
              isLoadingNewFrame ? "opacity-0" : "opacity-100"
            )}
            onLoad={(e) => {
              // Successfully loaded new frame
              const target = e.target as HTMLImageElement;
              setLastValidFrame(target.src);
              setIsLoadingNewFrame(false);
            }}
            onError={() => {
              // Failed to load - keep showing previous frame
              setIsLoadingNewFrame(false);
            }}
          />

          {/* Loading/Status indicator */}
          <div className="absolute top-2 left-2 bg-background/90 rounded px-2 py-1 text-xs font-medium flex items-center gap-2">
            {streamStatus === 'running' && (
              <span className="w-2 h-2 rounded-full bg-green-500" title="Stream active" />
            )}
            {streamStatus === 'connecting' && (
              <span className="w-2 h-2 rounded-full bg-yellow-500 animate-pulse" title="Connecting..." />
            )}
            {streamStatus === 'error' && (
              <span className="w-2 h-2 rounded-full bg-red-500" title="Stream error" />
            )}
            <span>{showHeatmap ? 'Heatmap View' : 'Camera View'}</span>
            {lastFrameNumber > 0 && (
              <span className="text-muted-foreground">• Frame {lastFrameNumber}</span>
            )}
          </div>

          {/* Show message when waiting for first frame */}
          {!lastValidFrame && (
            <div className="absolute inset-0 flex items-center justify-center bg-secondary/50">
              <div className="text-center text-muted-foreground">
                {streamStatus === 'running' ? (
                  <>
                    <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
                    <p className="text-sm font-medium">Processing first frame...</p>
                    <p className="text-xs mt-1">This may take a few seconds</p>
                  </>
                ) : streamStatus === 'connecting' ? (
                  <>
                    <div className="w-8 h-8 border-2 border-yellow-500 border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
                    <p className="text-sm font-medium">Connecting to stream...</p>
                    <p className="text-xs mt-1">Please wait</p>
                  </>
                ) : streamStatus === 'error' ? (
                  <>
                    <div className="w-8 h-8 text-red-500 mx-auto mb-2">⚠</div>
                    <p className="text-sm font-medium">Stream error</p>
                    <p className="text-xs mt-1">Check camera connection</p>
                  </>
                ) : (
                  <>
                    <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
                    <p className="text-sm font-medium">Loading stream...</p>
                    <p className="text-xs mt-1">Waiting for data</p>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="aspect-video bg-secondary rounded-lg flex items-center justify-center text-muted-foreground">
          Select a camera to view live feed
        </div>
      )}
    </div>
  );
}
