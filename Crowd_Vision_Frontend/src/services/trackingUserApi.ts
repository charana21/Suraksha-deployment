/**
 * Tracking User API Service
 * Handles communication with the backend live user-tracking endpoint
 */

const API_BASE_URL = import.meta.env.VITE_API_URL?.replace(/\/+$/, '') || 'https://crowdanalytics-api.tride.live/api';

export interface TrackingUserCoordinates {
  longitude: number;
  latitude: number;
}

export interface TrackingUserRecord {
  phoneNumber: string;
  name?: string;
  coordinates: TrackingUserCoordinates;
  timestamp?: string;
}

interface TrackingUserApiResponse {
  count?: number;
  tracking?: Array<{
    phoneNumber?: string;
    name?: string | null;
    coordinates?: {
      longitude?: number;
      latitude?: number;
    };
    timestamp?: string;
  }>;
}

class TrackingUserApiService {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  /**
   * Fetch live tracking records, deduped to the latest entry per phone number.
   */
  async getTrackingUsers(): Promise<TrackingUserRecord[]> {
    const response = await fetch(`${this.baseUrl}/tracking-user`, {
      cache: 'no-store',
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch tracking data: ${response.statusText}`);
    }

    const payload = (await response.json()) as TrackingUserApiResponse | null;
    const latestByPhone = new Map<string, TrackingUserRecord>();

    for (const record of Array.isArray(payload?.tracking) ? payload.tracking : []) {
      const phoneNumber = typeof record.phoneNumber === 'string' ? record.phoneNumber.trim() : '';
      const latitude = Number(record.coordinates?.latitude);
      const longitude = Number(record.coordinates?.longitude);

      if (!phoneNumber || !Number.isFinite(latitude) || !Number.isFinite(longitude)) {
        continue;
      }

      const nextRecord: TrackingUserRecord = {
        phoneNumber,
        name: typeof record.name === 'string' && record.name.trim() ? record.name.trim() : undefined,
        coordinates: { latitude, longitude },
        timestamp: record.timestamp,
      };

      const prev = latestByPhone.get(phoneNumber);
      const nextTime = Date.parse(nextRecord.timestamp || '');
      const prevTime = prev ? Date.parse(prev.timestamp || '') : -Infinity;
      if (!prev || nextTime >= prevTime) {
        latestByPhone.set(phoneNumber, nextRecord);
      }
    }

    return Array.from(latestByPhone.values());
  }
}

export const trackingUserApi = new TrackingUserApiService();
