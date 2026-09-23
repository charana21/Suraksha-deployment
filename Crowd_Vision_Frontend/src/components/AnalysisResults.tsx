// // import React, { useState } from 'react';
// // import { VideoPlayer } from './VideoPlayer';
// // import { ZoneCard } from './ZoneCard';
// // import { AlertBanner } from './AlertBanner';
// // import { MetricsPanel } from './MetricsPanel';
// // import { Button } from '@/components/ui/button';
// // import { RefreshCw, Download, FileVideo } from 'lucide-react';
// // import type { AnalysisResult, Alert } from '@/types/analysis';

// // interface AnalysisResultsProps {
// //   result: AnalysisResult;
// //   onNewAnalysis: () => void;
// // }

// // export const AnalysisResults: React.FC<AnalysisResultsProps> = ({
// //   result,
// //   onNewAnalysis,
// // }) => {
// //   const [alerts, setAlerts] = useState<Alert[]>(result.alerts);

// //   const handleDismissAlert = (id: string) => {
// //     setAlerts((prev) => prev.filter((a) => a.id !== id));
// //   };

// //   const handleDownload = () => {
// //     // In a real implementation, this would download the processed video
// //     const link = document.createElement('a');
// //     link.href = result.processedVideoUrl;
// //     link.download = 'processed_analysis.mp4';
// //     link.click();
// //   };

// //   return (
// //     <div className="space-y-8">
// //       {/* Alert Banner */}
// //       <AlertBanner alerts={alerts} onDismiss={handleDismissAlert} />

// //       {/* Actions */}
// //       <div className="flex flex-wrap gap-4 justify-between items-center">
// //         <div>
// //           <h2 className="text-2xl font-bold text-foreground">Analysis Complete</h2>
// //           <p className="text-sm text-muted-foreground">
// //             Video processed successfully with {result.frameCount.toLocaleString()} frames analyzed
// //           </p>
// //         </div>
// //         <div className="flex gap-3">
// //           <Button variant="outline" onClick={handleDownload}>
// //             <Download className="w-4 h-4 mr-2" />
// //             Download Result
// //           </Button>
// //           <Button variant="glow" onClick={onNewAnalysis}>
// //             <RefreshCw className="w-4 h-4 mr-2" />
// //             New Analysis
// //           </Button>
// //         </div>
// //       </div>

// //       {/* Metrics Overview */}
// //       <MetricsPanel result={result} />

// //       {/* Main Content Grid */}
// //       <div className="grid lg:grid-cols-2 gap-8">
// //         {/* Video Player */}
// //         <div className="space-y-4">
// //           <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
// //             <FileVideo className="w-4 h-4" />
// //             <span>Processed Output</span>
// //           </div>
// //           <VideoPlayer src={result.processedVideoUrl} title="Analyzed Video with Heatmap Overlay" />
// //         </div>

// //         {/* Zone Analysis */}
// //         <div className="space-y-4">
// //           <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
// //             <span>Zone Analysis</span>
// //           </div>
// //           <div className="grid grid-cols-2 gap-4">
// //             {result.zones.map((zone, index) => (
// //               <ZoneCard key={zone.id} zone={zone} index={index} />
// //             ))}
// //           </div>
// //         </div>
// //       </div>
// //     </div>
// //   );
// // };

// import React, { useState, useRef, useCallback } from "react";
// import { VideoPlayer, VideoPlayerRef } from "./VideoPlayer";
// import { ZoneCard } from "./ZoneCard";
// import { AlertBanner } from "./AlertBanner";
// import { MetricsPanel } from "./MetricsPanel";
// import { DynamicStatsPanel } from "./DynamicStatsPanel";
// import { Button } from "@/components/ui/button";
// import { RefreshCw, Download, FileVideo, BarChart3 } from "lucide-react";
// import { useFrameAnalytics } from "@/hooks/useFrameAnalytics";
// import type { AnalysisResult, Alert, ZoneData } from "@/types/analysis";

// interface AnalysisResultsProps {
//   result: AnalysisResult;
//   onNewAnalysis: () => void;
// }

// export const AnalysisResults: React.FC<AnalysisResultsProps> = ({
//   result,
//   onNewAnalysis,
// }) => {
//   const [alerts, setAlerts] = useState<Alert[]>(result.alerts);
//   const videoPlayerRef = useRef<VideoPlayerRef>(null);

//   // Extract jobId from video URL
//   const jobId =
//     result.jobId ||
//     result.processedVideoUrl.split("/").pop()?.replace("_analyzed.mp4", "");

//   // Fetch frame analytics
//   const {
//     analytics,
//     currentFrame,
//     updateFrameByTime,
//     isLoading: analyticsLoading,
//   } = useFrameAnalytics({
//     jobId,
//     fps: result.fps || 25,
//   });

//   const handleDismissAlert = (id: string) => {
//     setAlerts((prev) => prev.filter((a) => a.id !== id));
//   };

//   const handleDownload = () => {
//     const link = document.createElement("a");
//     link.href = result.processedVideoUrl;
//     link.download = "processed_analysis.mp4";
//     link.click();
//   };

//   const handleTimeUpdate = useCallback(
//     (currentTime: number) => {
//       updateFrameByTime(currentTime);
//     },
//     [updateFrameByTime]
//   );

//   // Get current zones from frame data if available, otherwise use result zones
//   const currentZones: ZoneData[] = currentFrame?.zones || result.zones;

//   return (
//     <div className="space-y-8">
//       {/* Alert Banner */}
//       <AlertBanner alerts={alerts} onDismiss={handleDismissAlert} />

//       {/* Actions */}
//       <div className="flex flex-wrap gap-4 justify-between items-center">
//         <div>
//           <h2 className="text-2xl font-bold text-foreground">
//             Analysis Complete
//           </h2>
//           <p className="text-sm text-muted-foreground">
//             Video processed with {result.frameCount.toLocaleString()} frames
//             {analytics && ` • ${analytics.frames.length} frames analyzed`}
//           </p>
//         </div>
//         <div className="flex gap-3">
//           <Button variant="outline" onClick={handleDownload}>
//             <Download className="w-4 h-4 mr-2" />
//             Download Result
//           </Button>
//           <Button variant="glow" onClick={onNewAnalysis}>
//             <RefreshCw className="w-4 h-4 mr-2" />
//             New Analysis
//           </Button>
//         </div>
//       </div>

//       {/* Static Metrics Overview */}
//       <MetricsPanel result={result} />

//       {/* Main Content - Video + Dynamic Stats */}
//       <div className="grid lg:grid-cols-5 gap-6">
//         {/* Video Player - Takes 3 columns */}
//         <div className="lg:col-span-3 space-y-4">
//           <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
//             <FileVideo className="w-4 h-4" />
//             <span>Processed Output</span>
//           </div>
//           <VideoPlayer
//             ref={videoPlayerRef}
//             src={result.processedVideoUrl}
//             title="Analyzed Video with Heatmap Overlay"
//             onTimeUpdate={handleTimeUpdate}
//           />
//         </div>

//         {/* Dynamic Stats Panel - Takes 2 columns */}
//         <div className="lg:col-span-2 space-y-4">
//           <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
//             <BarChart3 className="w-4 h-4" />
//             <span>Live Statistics</span>
//             {currentFrame && (
//               <span className="text-xs bg-primary/20 px-2 py-0.5 rounded">
//                 Frame {currentFrame.frameNumber}
//               </span>
//             )}
//           </div>
//           <DynamicStatsPanel
//             frame={currentFrame}
//             isLive={videoPlayerRef.current?.isVideoPlaying()}
//           />
//         </div>
//       </div>

//       {/* Zone Analysis Grid */}
//       <div className="space-y-4">
//         <div className="flex items-center justify-between">
//           <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
//             <span>Zone Analysis</span>
//             {currentFrame && (
//               <span className="text-xs text-primary">
//                 (Live @ {currentFrame.timestamp.toFixed(1)}s)
//               </span>
//             )}
//           </div>
//         </div>
//         <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
//           {currentZones.map((zone, index) => (
//             <ZoneCard key={zone.id} zone={zone} index={index} />
//           ))}
//         </div>
//       </div>
//     </div>
//   );
// };



import React, { useState, useRef, useCallback } from "react";
import { VideoPlayer, VideoPlayerRef } from "./VideoPlayer";
import { ZoneCard } from "./ZoneCard";
import { AlertBanner } from "./AlertBanner";
import { MetricsPanel } from "./MetricsPanel";
import { Button } from "@/components/ui/button";
import { RefreshCw, Download, FileVideo } from "lucide-react";
import { useFrameAnalytics } from "@/hooks/useFrameAnalytics";
import type { AnalysisResult, Alert, ZoneData } from "@/types/analysis";

interface AnalysisResultsProps {
  result: AnalysisResult;
  onNewAnalysis: () => void;
}

export const AnalysisResults: React.FC<AnalysisResultsProps> = ({
  result,
  onNewAnalysis,
}) => {
  const [alerts, setAlerts] = useState<Alert[]>(result.alerts);
  const videoPlayerRef = useRef<VideoPlayerRef>(null);

  const jobId =
    result.jobId ||
    result.processedVideoUrl.split("/").pop()?.replace("_analyzed.mp4", "");

  const { analytics, currentFrame, updateFrameByTime } = useFrameAnalytics({
    jobId,
    fps: result.fps || 25,
  });

  const handleDismissAlert = (id: string) => {
    setAlerts((prev) => prev.filter((a) => a.id !== id));
  };

  const handleDownload = () => {
    const link = document.createElement("a");
    link.href = result.processedVideoUrl;
    link.download = "processed_analysis.mp4";
    link.click();
  };

  const handleTimeUpdate = useCallback(
    (currentTime: number) => {
      updateFrameByTime(currentTime);
    },
    [updateFrameByTime]
  );

  const currentZones: ZoneData[] = currentFrame?.zones || result.zones;

  return (
    <div className="space-y-8">
      <AlertBanner alerts={alerts} onDismiss={handleDismissAlert} />

      <div className="flex flex-wrap gap-4 justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-foreground">
            Analysis Complete
          </h2>
          <p className="text-sm text-muted-foreground">
            Video processed with {result.frameCount.toLocaleString()} frames
            {analytics && ` • ${analytics.frames.length} frames analyzed`}
          </p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" onClick={handleDownload}>
            <Download className="w-4 h-4 mr-2" />
            Download Result
          </Button>
          <Button variant="glow" onClick={onNewAnalysis}>
            <RefreshCw className="w-4 h-4 mr-2" />
            New Analysis
          </Button>
        </div>
      </div>

      <MetricsPanel result={result} />

      <div className="grid lg:grid-cols-2 gap-8">
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <FileVideo className="w-4 h-4" />
            <span>Processed Output</span>
          </div>
          <VideoPlayer
            ref={videoPlayerRef}
            src={result.processedVideoUrl}
            title="Analyzed Video with Heatmap Overlay"
            onTimeUpdate={handleTimeUpdate}
          />
        </div>

        <div className="space-y-4">
          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <span>Zone Analysis</span>
            {currentFrame && (
              <span className="text-xs text-primary">
                (Live @ {currentFrame.timestamp.toFixed(1)}s)
              </span>
            )}
          </div>
          <div className="grid grid-cols-2 gap-4">
            {currentZones.map((zone, index) => (
              <ZoneCard key={zone.id} zone={zone} index={index} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
