import React, { // FIXED: Added the comma here
  useRef,
  useState,
  useEffect,
  useImperativeHandle,
  forwardRef,
} from "react";
import {
  Play,
  Pause,
  Volume2,
  VolumeX,
  Maximize,
  RotateCcw,
  AlertCircle,
  Loader2,
  Info,
} from "lucide-react";

export interface VideoPlayerRef {
  getCurrentTime: () => number;
  getDuration: () => number;
  isVideoPlaying: () => boolean;
}

interface VideoPlayerProps {
  src: string;
  title?: string;
  onTimeUpdate?: (currentTime: number) => void;
}

export const VideoPlayer = forwardRef<VideoPlayerRef, VideoPlayerProps>(
  ({ src, title, onTimeUpdate }, ref) => {
    const videoRef = useRef<HTMLVideoElement>(null);
    const [isPlaying, setIsPlaying] = useState(false);
    const [isMuted, setIsMuted] = useState(false);
    const [progress, setProgress] = useState(0);
    const [duration, setDuration] = useState(0);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [debugInfo, setDebugInfo] = useState<any>(null);
    const [showDebug, setShowDebug] = useState(false);

    useImperativeHandle(ref, () => ({
      getCurrentTime: () => videoRef.current?.currentTime || 0,
      getDuration: () => videoRef.current?.duration || 0,
      isVideoPlaying: () => isPlaying,
    }));

    useEffect(() => {
      setIsLoading(true);
      setError(null);
      setProgress(0);
      setIsPlaying(false);

      // Fetch debug info
      const jobId = src.split("/").pop();
      if (jobId) {
        const baseUrl = (import.meta.env.VITE_API_URL as string) || "";
        const fetchUrl = baseUrl.endsWith('/api') ? `${baseUrl}/debug/video-info/${jobId}` : `${baseUrl}/api/debug/video-info/${jobId}`;
        fetch(fetchUrl)
          .then((res) => res.json())
          .then((data) => {
            setDebugInfo(data);
          })
          .catch(() => {});
      }
    }, [src]);

    const togglePlay = () => {
      if (videoRef.current) {
        if (isPlaying) {
          videoRef.current.pause();
        } else {
          videoRef.current.play().catch((err) => {
            setError("Failed to play video");
          });
        }
        setIsPlaying(!isPlaying);
      }
    };

    const toggleMute = () => {
      if (videoRef.current) {
        videoRef.current.muted = !isMuted;
        setIsMuted(!isMuted);
      }
    };

    const handleTimeUpdate = () => {
      if (videoRef.current) {
        const currentTime = videoRef.current.currentTime;
        const prog = (currentTime / videoRef.current.duration) * 100;
        setProgress(prog || 0);
        onTimeUpdate?.(currentTime);
      }
    };

    const handleLoadedMetadata = () => {
      if (videoRef.current) {
        setDuration(videoRef.current.duration);
        setIsLoading(false);
        setError(null);
      }
    };

    const handleCanPlay = () => {
      setIsLoading(false);
    };

    const handleError = (e: React.SyntheticEvent<HTMLVideoElement, Event>) => {
      const videoEl = videoRef.current;
      const errorDetails = videoEl?.error;

      let errorMessage = "Failed to load video. ";

      if (errorDetails) {
        switch (errorDetails.code) {
          case 1:
            errorMessage += "Video loading was aborted.";
            break;
          case 2:
            errorMessage += "Network error. Check if backend is running.";
            break;
          case 3:
            errorMessage += "Video file is corrupted or invalid format.";
            break;
          case 4:
            errorMessage += "Video format not supported or file not found.";
            break;
          default:
            errorMessage += "Unknown error occurred.";
        }
      }

      setIsLoading(false);
      setError(errorMessage);
    };

    const handleSeek = (value: number[]) => {
      if (videoRef.current) {
        const time = (value[0] / 100) * videoRef.current.duration;
        videoRef.current.currentTime = time;
        setProgress(value[0]);
        onTimeUpdate?.(time);
      }
    };

    const handleFullscreen = () => {
      if (videoRef.current) {
        if (videoRef.current.requestFullscreen) {
          videoRef.current.requestFullscreen();
        }
      }
    };

    const handleRestart = () => {
      if (videoRef.current) {
        videoRef.current.currentTime = 0;
        setProgress(0);
        onTimeUpdate?.(0);
        if (!isPlaying) {
          videoRef.current.play().catch(() => {});
          setIsPlaying(true);
        }
      }
    };

    const formatTime = (seconds: number) => {
      if (!isFinite(seconds)) return "0:00";
      const mins = Math.floor(seconds / 60);
      const secs = Math.floor(seconds % 60);
      return `${mins}:${secs.toString().padStart(2, "0")}`;
    };

    return (
      <div className="glass-panel glow-border overflow-hidden animate-fade-in-up">
        {title && (
          <div className="px-4 py-3 border-b border-border flex justify-between items-center">
            <h3 className="text-sm font-medium text-foreground">{title}</h3>
            <button
              onClick={() => setShowDebug(!showDebug)}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              <Info className="w-4 h-4" />
            </button>
          </div>
        )}

        {showDebug && debugInfo && (
          <div className="px-4 py-2 bg-muted/50 border-b border-border">
            <div className="text-xs font-mono space-y-1">
              <div>
                Status:{" "}
                <span className="text-primary">{debugInfo.job_status}</span>
              </div>
              <div>
                File exists:{" "}
                <span
                  className={
                    debugInfo.file_exists ? "text-green-500" : "text-red-500"
                  }
                >
                  {debugInfo.file_exists ? "✓" : "✗"}
                </span>
              </div>
              <div>
                File size:{" "}
                <span className="text-primary">
                  {debugInfo.file_size?.toLocaleString()} bytes
                </span>
              </div>
              <div>
                OpenCV can open:{" "}
                <span
                  className={
                    debugInfo.opencv_can_open
                      ? "text-green-500"
                      : "text-red-500"
                  }
                >
                  {debugInfo.opencv_can_open ? "✓" : "✗"}
                </span>
              </div>
              <div className="truncate">Path: {debugInfo.output_path}</div>
            </div>
          </div>
        )}

        <div className="relative bg-background/50">
          {isLoading && (
            <div className="absolute inset-0 flex items-center justify-center bg-background/80 z-10">
              <div className="text-center space-y-3">
                <Loader2 className="w-8 h-8 animate-spin text-primary mx-auto" />
                <p className="text-sm text-muted-foreground">
                  Loading video...
                </p>
                <p className="text-xs text-muted-foreground font-mono">{src}</p>
              </div>
            </div>
          )}

          {error && (
            <div className="absolute inset-0 flex items-center justify-center bg-background/80 z-10">
              <div className="text-center space-y-3 p-6 max-w-md">
                <AlertCircle className="w-12 h-12 text-destructive mx-auto" />
                <p className="text-sm text-foreground font-medium">
                  Video Load Error
                </p>
                <p className="text-xs text-muted-foreground">{error}</p>

                {debugInfo && (
                  <div className="mt-4 p-3 bg-muted rounded text-left">
                    <p className="text-xs font-semibold mb-2">Debug Info:</p>
                    <div className="text-xs font-mono space-y-1">
                      <div>
                        File exists: {debugInfo.file_exists ? "Yes" : "No"}
                      </div>
                      <div>File size: {debugInfo.file_size} bytes</div>
                      <div>Job status: {debugInfo.job_status}</div>
                    </div>
                  </div>
                )}

                <div className="flex gap-2 justify-center">
                  <button
                    onClick={() => {
                      setError(null);
                      setIsLoading(true);
                      if (videoRef.current) {
                        videoRef.current.load();
                      }
                    }}
                    className="text-xs text-primary hover:underline"
                  >
                    Try Again
                  </button>
                  <button
                    onClick={() => setShowDebug(true)}
                    className="text-xs text-muted-foreground hover:text-foreground"
                  >
                    Show Debug
                  </button>
                </div>
              </div>
            </div>
          )}

          <video
            ref={videoRef}
            src={src}
            className="w-full aspect-video object-contain bg-black"
            onTimeUpdate={handleTimeUpdate}
            onLoadedMetadata={handleLoadedMetadata}
            onCanPlay={handleCanPlay}
            onError={handleError}
            onEnded={() => setIsPlaying(false)}
            onPlay={() => setIsPlaying(true)}
            onPause={() => setIsPlaying(false)}
            preload="metadata"
            crossOrigin="anonymous"
          />

          {!error && !isLoading && (
            <div className="absolute inset-0 pointer-events-none overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-b from-transparent via-primary/5 to-transparent animate-scan" />
            </div>
          )}
        </div>

        <div className="p-4 space-y-3 bg-background/50">
          <div className="relative">
            <input
              type="range"
              min="0"
              max="100"
              step="0.1"
              value={progress}
              onChange={(e) => handleSeek([parseFloat(e.target.value)])}
              className="w-full h-1 bg-border rounded-full appearance-none cursor-pointer
                         [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 
                         [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:rounded-full 
                         [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:cursor-pointer
                         [&::-moz-range-thumb]:w-3 [&::-moz-range-thumb]:h-3 
                         [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-primary 
                         [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:cursor-pointer"
              disabled={isLoading || !!error}
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <button
                onClick={togglePlay}
                disabled={isLoading || !!error}
                className="w-9 h-9 rounded-lg bg-primary/10 hover:bg-primary/20 
                           flex items-center justify-center transition-colors
                           disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isPlaying ? (
                  <Pause className="w-5 h-5 text-primary" />
                ) : (
                  <Play className="w-5 h-5 text-primary" />
                )}
              </button>

              <button
                onClick={handleRestart}
                disabled={isLoading || !!error}
                className="w-9 h-9 rounded-lg bg-primary/10 hover:bg-primary/20 
                           flex items-center justify-center transition-colors
                           disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <RotateCcw className="w-4 h-4 text-primary" />
              </button>

              <button
                onClick={toggleMute}
                disabled={isLoading || !!error}
                className="w-9 h-9 rounded-lg bg-primary/10 hover:bg-primary/20 
                           flex items-center justify-center transition-colors
                           disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isMuted ? (
                  <VolumeX className="w-4 h-4 text-primary" />
                ) : (
                  <Volume2 className="w-4 h-4 text-primary" />
                )}
              </button>

              <span className="text-xs font-mono text-muted-foreground ml-2">
                {formatTime((progress / 100) * duration)} /{" "}
                {formatTime(duration)}
              </span>
            </div>

            <button
              onClick={handleFullscreen}
              disabled={isLoading || !!error}
              className="w-9 h-9 rounded-lg bg-primary/10 hover:bg-primary/20 
                         flex items-center justify-center transition-colors
                         disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Maximize className="w-4 h-4 text-primary" />
            </button>
          </div>
        </div>
      </div>
    );
  }
);

VideoPlayer.displayName = "VideoPlayer";
