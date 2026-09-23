export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type DensityLevel = 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL' | 'VERY_HIGH';
export type ZoneType = 'FOB' | 'PLATFORM' | 'STAIRS' | 'LIFT' | 'ENTRY' | 'EXIT';

export interface Zone {
  zone_id: string;
  zone_name: string;
  svg_region_id: string;
  display_order: number;
  station_id: string;
  zone_type: ZoneType;
  description?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ZoneAnalytics {
  zone_id: string;
  zone_name: string;
  svg_region_id: string;
  display_order: number;
  zone_type: string;
  people_count: number;
  density_avg: number;
  density_level: DensityLevel;
  motion_intensity: number;
  motion_level?: string;
  risk_score: number;
  risk_level: RiskLevel;
  camera_count: number;
  cameras: CameraAnalytics[] | string[];
  timestamp?: string; // Capture timestamp from backend
}

export interface CameraAnalytics {
  camera_id: string;
  svg_region_id: string;
  people_count: number;
  density_avg: number;
  density_level: DensityLevel;
  motion_intensity: number;
  motion_level?: string;
  risk_score: number;
  risk_level: RiskLevel;
  delta_1min?: number;
  delta_5min?: number;
  flow_status?: 'filling' | 'emptying' | 'stable';
}

export interface ZoneAnalyticsResponse {
  status: string;
  station_id: string | null;
  timestamp: string;
  zones: ZoneAnalytics[];
}

export interface ZoneWebSocketMessage {
  type: 'zone_analytics';
  station_id: string;
  timestamp: string;
  zones: ZoneAnalytics[];
}

export interface ZonesListResponse {
  status: string;
  count: number;
  zones: Zone[];
}

export const RISK_COLORS: Record<RiskLevel | 'UNKNOWN', string> = {
  LOW: '#22c55e',      // Green - Safe
  MEDIUM: '#f97316',   // Orange - Caution
  HIGH: '#ef4444',     // Red - Danger
  CRITICAL: '#dc2626', // Dark Red - Emergency
  UNKNOWN: '#6b7280',  // Gray - No data
};

export const RISK_LABELS: Record<RiskLevel, string> = {
  LOW: 'Low Risk',
  MEDIUM: 'Medium Risk',
  HIGH: 'High Risk',
  CRITICAL: 'Critical',
};
