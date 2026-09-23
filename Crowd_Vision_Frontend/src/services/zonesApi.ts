import { ZoneAnalyticsResponse, ZonesListResponse } from '@/types/zone';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://crowdvision-api.tride.live/api';

class ZonesApiService {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  /**
   * Get all zones for a station
   */
  async getZones(stationId?: string): Promise<ZonesListResponse> {
    const params = new URLSearchParams();
    if (stationId) {
      params.set('station_id', stationId);
    }

    const query = params.toString();
    const response = await fetch(`${this.baseUrl}/zones${query ? `?${query}` : ''}`);

    if (!response.ok) {
      throw new Error(`Failed to fetch zones: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get zones for a specific station ordered by display_order
   */
  async getZonesByStation(stationId: string): Promise<ZonesListResponse> {
    const response = await fetch(`${this.baseUrl}/zones/station/${stationId}`);

    if (!response.ok) {
      throw new Error(`Failed to fetch zones for station ${stationId}: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get aggregated analytics for all zones (for SVG rendering)
   */
  async getZoneAnalytics(stationId?: string): Promise<ZoneAnalyticsResponse> {
    const params = new URLSearchParams();
    if (stationId) {
      params.set('station_id', stationId);
    }

    const query = params.toString();
    const response = await fetch(`${this.baseUrl}/zones/analytics${query ? `?${query}` : ''}`);

    if (!response.ok) {
      throw new Error(`Failed to fetch zone analytics: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get analytics for a single zone
   */
  async getSingleZoneAnalytics(zoneId: string): Promise<{ status: string; timestamp: string; zone: import('@/types/zone').ZoneAnalytics }> {
    const response = await fetch(`${this.baseUrl}/zones/${zoneId}/analytics`);

    if (!response.ok) {
      throw new Error(`Failed to fetch zone analytics for ${zoneId}: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Assign a camera to a zone
   */
  async assignCameraToZone(cameraId: string, zoneId: string | null): Promise<{ status: string; message: string }> {
    const response = await fetch(`${this.baseUrl}/cameras/${cameraId}/zone`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ zone_id: zoneId }),
    });

    if (!response.ok) {
      throw new Error(`Failed to assign camera to zone: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get cameras assigned to a zone
   */
  async getCamerasInZone(zoneId: string): Promise<{ status: string; zone_id: string; zone_name: string; count: number; cameras: unknown[] }> {
    const response = await fetch(`${this.baseUrl}/zones/${zoneId}/cameras`);

    if (!response.ok) {
      throw new Error(`Failed to fetch cameras for zone ${zoneId}: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get WebSocket URL for zone analytics
   */
  getZoneWebSocketUrl(stationId?: string): string {
    const wsBase = this.baseUrl.replace(/^http/, 'ws').replace('/api', '');
    if (stationId) {
      return `${wsBase}/api/ws/zones/analytics/${stationId}`;
    }
    return `${wsBase}/api/ws/zones/analytics`;
  }
}

export const zonesApi = new ZonesApiService();
