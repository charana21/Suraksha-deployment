export interface Camera {
  id: string; // camera_id (Immutable ID)
  name: string; // Editable Name
  rtspUrl: string; // Editable Stream URL
  fobType?: 'HYD' | 'KZJ' | string | null; // HYD, KZJ, or null for platform/booking
  zoneId: string; // Linked Zone ID
  status: 'active' | 'inactive' | 'error'; // Backend config status
  isActive: boolean; // Boolean flag

  // Frontend/Runtime specific (populated from status/runtime check)
  runtimeStatus?: 'running' | 'connecting' | 'reconnecting' | 'error' | 'stopped' | 'inactive' | 'unknown';
  shardId?: number;
  isLocalWorker?: boolean;
  liveFrameAgeMs?: number | null;
  location?: string; // Kept for backward compat if needed, or mapped from fobType
  createdAt?: Date; // Kept for backward compat
}

export interface CameraStats {
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

export interface ZoneStats {
  id: string;
  name: string;
  peopleCount: number;
  density: number;
  densityLevel: 'LOW' | 'MODERATE' | 'HIGH' | 'VERY HIGH';
  motionIntensity: number;
  riskLevel: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  riskScore: number;
}

export interface Alert {
  id: string;
  cameraId: string;
  cameraName: string;
  zoneId?: string;
  zoneType?: 'FOB' | 'PLATFORM' | 'BOOKING';
  zoneName?: string;
  type: 'density' | 'motion' | 'stampede' | 'surge' | 'Risk Alert';
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  message: string;
  triggerReason: string;
  timestamp: Date;
  acknowledged: boolean;
  peopleCount?: number;
  fobId?: string;
  imageId?: string;
}

export interface HeatmapData {
  type: 'density' | 'motion' | 'risk';
  data: number[][];
  maxValue: number;
  zones: { id: string; name: string; x: number; y: number; width: number; height: number; value: number }[];
}
