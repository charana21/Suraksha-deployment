// import { useState, useCallback, useRef } from "react";
// import type {
//   AnalysisResult,
//   UploadState,
//   Alert,
//   RiskLevel,
//   ZoneData,
// } from "@/types/analysis";

// // Configure your Python backend URL here
// // For local development: http://localhost:8000
// // For production: Your deployed backend URL (e.g., https://your-app.railway.app)
// const API_BASE_URL =
//   import.meta.env.VITE_API_URL || "https://crowdvision-api.tride.live";

// interface ApiStatusResponse {
//   jobId: string;
//   status: "queued" | "processing" | "complete" | "error";
//   progress: number;
//   fileName?: string;
//   processedVideoUrl?: string;
//   zones?: ZoneData[];
//   totalPeople?: number;
//   averageRiskScore?: number;
//   maxRiskLevel?: RiskLevel;
//   alerts?: Alert[];
//   processingTime?: number;
//   frameCount?: number;
//   fps?: number;
//   error?: string;
// }

// export const useVideoAnalysis = () => {
//   const [uploadState, setUploadState] = useState<UploadState>({
//     status: "idle",
//     progress: 0,
//   });
//   const [result, setResult] = useState<AnalysisResult | null>(null);
//   const abortControllerRef = useRef<AbortController | null>(null);
//   const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

//   const pollJobStatus = useCallback(async (jobId: string) => {
//     try {
//       console.log(`[Poll] Checking status for job: ${jobId}`);
//       const response = await fetch(`${API_BASE_URL}/api/status/${jobId}`);

//       if (!response.ok) {
//         throw new Error("Failed to get job status");
//       }

//       const data: ApiStatusResponse = await response.json();
//       console.log(`[Poll] Status: ${data.status}, Progress: ${data.progress}%`);

//       if (data.status === "processing" || data.status === "queued") {
//         setUploadState((prev) => ({
//           ...prev,
//           status: "processing",
//           progress: data.progress,
//         }));
//       } else if (data.status === "complete") {
//         // Stop polling
//         if (pollingIntervalRef.current) {
//           clearInterval(pollingIntervalRef.current);
//           pollingIntervalRef.current = null;
//         }

//         // Construct full video URL
//         const videoUrl = data.processedVideoUrl?.startsWith("http")
//           ? data.processedVideoUrl
//           : `${API_BASE_URL}${data.processedVideoUrl}`;

//         console.log("[Complete] Video URL:", videoUrl);
//         console.log("[Complete] Zones:", data.zones);

//         // Transform alerts to have proper Date objects
//         const alerts: Alert[] = (data.alerts || []).map((alert: any) => ({
//           ...alert,
//           timestamp: new Date(alert.timestamp * 1000),
//         }));

//         const analysisResult: AnalysisResult = {
//           processedVideoUrl: videoUrl,
//           zones: data.zones || [],
//           totalPeople: data.totalPeople || 0,
//           averageRiskScore: data.averageRiskScore || 0,
//           maxRiskLevel: data.maxRiskLevel || "LOW",
//           alerts,
//           processingTime: data.processingTime || 0,
//           frameCount: data.frameCount || 0,
//           fps: data.fps || 0,
//         };

//         setResult(analysisResult);
//         setUploadState({
//           status: "complete",
//           progress: 100,
//           fileName: data.fileName,
//         });
//       } else if (data.status === "error") {
//         // Stop polling
//         if (pollingIntervalRef.current) {
//           clearInterval(pollingIntervalRef.current);
//           pollingIntervalRef.current = null;
//         }

//         console.error("[Error] Analysis failed:", data.error);
//         setUploadState({
//           status: "error",
//           progress: 0,
//           error: data.error || "Analysis failed",
//         });
//       }
//     } catch (error) {
//       console.error("Polling error:", error);
//       // Don't stop polling on network errors, it might be temporary
//     }
//   }, []);

//   const uploadVideo = useCallback(
//     async (file: File) => {
//       // Cancel any existing upload
//       if (abortControllerRef.current) {
//         abortControllerRef.current.abort();
//       }
//       if (pollingIntervalRef.current) {
//         clearInterval(pollingIntervalRef.current);
//       }

//       abortControllerRef.current = new AbortController();

//       setUploadState({
//         status: "uploading",
//         progress: 0,
//         fileName: file.name,
//       });

//       try {
//         console.log("[Upload] Starting upload for:", file.name);
//         const formData = new FormData();
//         formData.append("video", file);

//         // Upload the video
//         const response = await fetch(`${API_BASE_URL}/api/analyze`, {
//           method: "POST",
//           body: formData,
//           signal: abortControllerRef.current.signal,
//         });

//         if (!response.ok) {
//           const errorData = await response.json().catch(() => ({}));
//           throw new Error(errorData.detail || "Upload failed");
//         }

//         const { jobId } = await response.json();
//         console.log("[Upload] Job created:", jobId);

//         // Switch to processing state
//         setUploadState((prev) => ({
//           ...prev,
//           status: "processing",
//           progress: 0,
//         }));

//         // Start polling for status
//         pollingIntervalRef.current = setInterval(() => {
//           pollJobStatus(jobId);
//         }, 1000);

//         // Initial poll
//         pollJobStatus(jobId);
//       } catch (error: any) {
//         if (error.name === "AbortError") {
//           setUploadState({
//             status: "idle",
//             progress: 0,
//           });
//           return;
//         }

//         console.error("Upload error:", error);
//         setUploadState({
//           status: "error",
//           progress: 0,
//           error:
//             error.message ||
//             "Failed to upload video. Make sure the backend is running.",
//         });
//       }
//     },
//     [pollJobStatus]
//   );

//   const cancelUpload = useCallback(() => {
//     if (abortControllerRef.current) {
//       abortControllerRef.current.abort();
//     }
//     if (pollingIntervalRef.current) {
//       clearInterval(pollingIntervalRef.current);
//       pollingIntervalRef.current = null;
//     }
//     setUploadState({
//       status: "idle",
//       progress: 0,
//     });
//   }, []);

//   const resetAnalysis = useCallback(() => {
//     if (pollingIntervalRef.current) {
//       clearInterval(pollingIntervalRef.current);
//       pollingIntervalRef.current = null;
//     }
//     setResult(null);
//     setUploadState({
//       status: "idle",
//       progress: 0,
//     });
//   }, []);

//   return {
//     uploadState,
//     result,
//     uploadVideo,
//     cancelUpload,
//     resetAnalysis,
//   };
// };

import { useState, useCallback, useRef } from "react";
import type {
  AnalysisResult,
  UploadState,
  Alert,
  RiskLevel,
  ZoneData,
} from "@/types/analysis";

// Configure your Python backend URL here
// For local development: http://localhost:8000
// For production: Your deployed backend URL (e.g., https://your-app.railway.app)
const API_BASE_URL = import.meta.env.VITE_API_URL || "https://crowdvision-api.tride.live";

interface ApiStatusResponse {
  jobId: string;
  status: "queued" | "processing" | "complete" | "error";
  progress: number;
  fileName?: string;
  processedVideoUrl?: string;
  zones?: ZoneData[];
  totalPeople?: number;
  averageRiskScore?: number;
  maxRiskLevel?: RiskLevel;
  alerts?: Alert[];
  processingTime?: number;
  frameCount?: number;
  fps?: number;
  error?: string;
  analyticsUrl?: string;
}

export const useVideoAnalysis = () => {
  const [uploadState, setUploadState] = useState<UploadState>({
    status: "idle",
    progress: 0,
  });
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const pollJobStatus = useCallback(async (jobId: string): Promise<void> => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/status/${jobId}`);

      if (!response.ok) {
        throw new Error("Failed to get job status");
      }

      const data: ApiStatusResponse = await response.json();

      if (data.status === "processing" || data.status === "queued") {
        setUploadState((prev) => ({
          ...prev,
          status: "processing",
          progress: data.progress,
        }));
      } else if (data.status === "complete") {
        // Stop polling
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
          pollingIntervalRef.current = null;
        }

        // Construct full video URL
        const videoUrl = data.processedVideoUrl?.startsWith("http")
          ? data.processedVideoUrl
          : `${API_BASE_URL}${data.processedVideoUrl}`;

        // Transform alerts to have proper Date objects
        const alerts: Alert[] = (data.alerts || []).map((alert: any) => ({
          ...alert,
          timestamp: new Date(alert.timestamp * 1000),
        }));

        const analysisResult: AnalysisResult = {
          processedVideoUrl: videoUrl,
          zones: data.zones || [],
          totalPeople: data.totalPeople || 0,
          averageRiskScore: data.averageRiskScore || 0,
          maxRiskLevel: data.maxRiskLevel || "LOW",
          alerts,
          processingTime: data.processingTime || 0,
          frameCount: data.frameCount || 0,
          fps: data.fps || 0,
          jobId: jobId,
          analyticsUrl: data.analyticsUrl,
        };

        setResult(analysisResult);
        setUploadState({
          status: "complete",
          progress: 100,
          fileName: data.fileName,
        });
      } else if (data.status === "error") {
        // Stop polling
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
          pollingIntervalRef.current = null;
        }

        setUploadState({
          status: "error",
          progress: 0,
          error: data.error || "Analysis failed",
        });
      }
    } catch (error) {
      // Don't stop polling on network errors, it might be temporary
    }
  }, []);

  const uploadVideo = useCallback(
    async (file: File) => {
      // Cancel any existing upload
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }

      abortControllerRef.current = new AbortController();

      setUploadState({
        status: "uploading",
        progress: 0,
        fileName: file.name,
      });

      try {
        const formData = new FormData();
        formData.append("video", file);

        // Upload the video
        const response = await fetch(`${API_BASE_URL}/api/analyze`, {
          method: "POST",
          body: formData,
          signal: abortControllerRef.current.signal,
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.detail || "Upload failed");
        }

        const { jobId } = await response.json();

        // Switch to processing state
        setUploadState((prev) => ({
          ...prev,
          status: "processing",
          progress: 0,
        }));

        // Start polling for status
        pollingIntervalRef.current = setInterval(() => {
          pollJobStatus(jobId);
        }, 1000);

        // Initial poll
        pollJobStatus(jobId);
      } catch (error: any) {
        if (error.name === "AbortError") {
          setUploadState({
            status: "idle",
            progress: 0,
          });
          return;
        }

        setUploadState({
          status: "error",
          progress: 0,
          error:
            error.message ||
            "Failed to upload video. Make sure the backend is running.",
        });
      }
    },
    [pollJobStatus]
  );

  const cancelUpload = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
    setUploadState({
      status: "idle",
      progress: 0,
    });
  }, []);

  const resetAnalysis = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
    setResult(null);
    setUploadState({
      status: "idle",
      progress: 0,
    });
  }, []);

  return {
    uploadState,
    result,
    uploadVideo,
    cancelUpload,
    resetAnalysis,
  };
};
