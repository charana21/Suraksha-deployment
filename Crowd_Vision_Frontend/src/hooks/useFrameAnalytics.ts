import { useState, useEffect, useCallback, useRef } from "react";
import type { FrameAnalytics, FrameData } from "@/types/analysis";

const API_BASE_URL = import.meta.env.VITE_API_URL || "https://crowdvision-api.tride.live";

interface UseFrameAnalyticsOptions {
  jobId: string | undefined;
  fps: number;
}

export const useFrameAnalytics = ({ jobId, fps }: UseFrameAnalyticsOptions) => {
  const [analytics, setAnalytics] = useState<FrameAnalytics | null>(null);
  const [currentFrame, setCurrentFrame] = useState<FrameData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const frameMapRef = useRef<Map<number, FrameData>>(new Map());

  // Fetch full analytics on mount
  useEffect(() => {
    if (!jobId) return;

    const fetchAnalytics = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await fetch(`${API_BASE_URL}/api/analytics/${jobId}`);

        if (!response.ok) {
          // Analytics might not exist for older jobs
          return;
        }

        const data: FrameAnalytics = await response.json();
        setAnalytics(data);

        // Build frame map for fast lookup
        const map = new Map<number, FrameData>();
        data.frames.forEach((frame) => {
          map.set(frame.frameNumber, frame);
        });
        frameMapRef.current = map;

        // Set initial frame
        if (data.frames.length > 0) {
          setCurrentFrame(data.frames[0]);
        }
      } catch (err) {
        setError("Failed to load frame analytics");
      } finally {
        setIsLoading(false);
      }
    };

    fetchAnalytics();
  }, [jobId]);

  // Update current frame based on video time
  const updateFrameByTime = useCallback(
    (currentTime: number) => {
      if (!analytics || analytics.frames.length === 0) return;

      // Calculate frame number from time
      const frameNumber = Math.floor(currentTime * fps) + 1;

      // Find closest frame (we might not have every frame)
      let closest = analytics.frames[0];
      let minDiff = Math.abs(closest.frameNumber - frameNumber);

      for (const frame of analytics.frames) {
        const diff = Math.abs(frame.frameNumber - frameNumber);
        if (diff < minDiff) {
          minDiff = diff;
          closest = frame;
        }
        // Break early if exact match or passed
        if (frame.frameNumber >= frameNumber) break;
      }

      setCurrentFrame(closest);
    },
    [analytics, fps]
  );

  // Get frame by number
  const getFrameByNumber = useCallback(
    (frameNumber: number): FrameData | undefined => {
      return frameMapRef.current.get(frameNumber);
    },
    []
  );

  return {
    analytics,
    currentFrame,
    isLoading,
    error,
    updateFrameByTime,
    getFrameByNumber,
  };
};
