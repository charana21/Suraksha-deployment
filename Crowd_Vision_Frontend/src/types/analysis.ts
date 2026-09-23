// export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

// export interface ZoneData {
//   id: string;
//   name: string;
//   people: number;
//   yoloCount: number;
//   neuralCount: number;
//   method: string;
//   density: number;
//   riskScore: number;
//   riskLevel: RiskLevel;
// }

// export interface AnalysisResult {
//   processedVideoUrl: string;
//   zones: ZoneData[];
//   totalPeople: number;
//   averageRiskScore: number;
//   maxRiskLevel: RiskLevel;
//   alerts: Alert[];
//   processingTime: number;
//   frameCount: number;
//   fps: number;
// }

// export interface Alert {
//   id: string;
//   type: 'density' | 'flow' | 'risk';
//   severity: RiskLevel;
//   message: string;
//   zone?: string;
//   timestamp: Date;
// }

// export type UploadStatus = 'idle' | 'uploading' | 'processing' | 'complete' | 'error';

// export interface UploadState {
//   status: UploadStatus;
//   progress: number;
//   fileName?: string;
//   error?: string;
// }

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type DensityLevel = "LOW" | "MODERATE" | "HIGH" | "VERY HIGH";

export interface ZoneData {
  id: string;
  name: string;
  coords?: [number, number, number, number];
  people_count: number;
  head_detections: number;
  density_estimate: number;
  density_level: DensityLevel;
  avg_motion: number;
  flow_pressure: number;
  risk_score: number;
  risk_level: RiskLevel;
  risk_factors: string[];
  // Legacy fields for backwards compatibility
  people?: number;
  yoloCount?: number;
  neuralCount?: number;
  method?: string;
  density?: number;
  riskScore?: number;
  riskLevel?: RiskLevel;
}

export interface FrameData {
  frameNumber: number;
  timestamp: number;
  peopleCount: number;
  headDetections: number;
  densityAvg: number;
  densityMax: number;
  motionIntensity: number;
  motionDirection: string | null;
  stampedeProbability: number;
  stampedeWarning: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  zones: ZoneData[];
  heatmapUrl?: string;
}

export interface FrameAnalytics {
  metadata: {
    jobId: string;
    totalFrames: number;
    fps: number;
    duration: number;
    width: number;
    height: number;
  };
  frames: FrameData[];
}

export interface AnalysisResult {
  processedVideoUrl: string;
  zones: ZoneData[];
  totalPeople: number;
  averageRiskScore: number;
  maxRiskLevel: RiskLevel;
  alerts: Alert[];
  processingTime: number;
  frameCount: number;
  fps: number;
  analyticsUrl?: string;
  jobId?: string;
}

export interface Alert {
  id: string;
  type: "density" | "flow" | "risk" | "stampede";
  severity: RiskLevel;
  message: string;
  zone?: string;
  timestamp: Date;
}

export type UploadStatus =
  | "idle"
  | "uploading"
  | "processing"
  | "complete"
  | "error";

export interface UploadState {
  status: UploadStatus;
  progress: number;
  fileName?: string;
  error?: string;
}
