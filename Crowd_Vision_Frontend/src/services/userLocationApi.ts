const API_BASE_URL = import.meta.env.VITE_API_URL?.replace(/\/+$/, '') || 'https://crowdvision-api.tride.live/api';

export interface UserLocationLocation {
  latitude: number;
  longitude: number;
  timestamp?: string;
}

export interface UserLocationRecord {
  _id?: string;
  phoneNumber: string;
  platform?: string;
  location: UserLocationLocation;
  timestamp?: string;
}

class UserLocationApi {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private normalizePhone(payload: Record<string, unknown>): string {
    const phone = payload.phoneNumber ?? payload.phone ?? payload.number;
    if (typeof phone === 'string' && phone.trim().length > 0) {
      return phone.trim();
    }
    return "Unknown";
  }

  private toFiniteNumber(value: unknown): number | null {
    if (typeof value === "string") {
      const trimmed = value.trim();
      if (!trimmed) return null;
      const parsed = Number(trimmed);
      return Number.isFinite(parsed) ? parsed : null;
    }
    if (typeof value === "number" && Number.isFinite(value)) {
      return value;
    }
    return null;
  }

  private buildLocation(raw: Record<string, unknown>): UserLocationLocation {
    const timestamp = typeof raw.timestamp === 'string' ? raw.timestamp : undefined;
    const coordsArray = Array.isArray(raw.coordinates) ? raw.coordinates : [];
    const coordsObject = !Array.isArray(raw.coordinates) && raw.coordinates && typeof raw.coordinates === 'object'
      ? (raw.coordinates as Record<string, unknown>)
      : null;

    const latitude =
      this.toFiniteNumber(raw.latitude ?? raw.lat) ??
      this.toFiniteNumber(coordsObject?.latitude ?? coordsObject?.lat) ??
      this.toFiniteNumber(coordsArray[1]);

    const longitude =
      this.toFiniteNumber(raw.longitude ?? raw.lon ?? raw.lng) ??
      this.toFiniteNumber(coordsObject?.longitude ?? coordsObject?.lon ?? coordsObject?.lng) ??
      this.toFiniteNumber(coordsArray[0]);

    return {
      latitude: latitude ?? NaN,
      longitude: longitude ?? NaN,
      timestamp,
    };
  }

  private stringifyId(value: unknown): string {
    if (typeof value === 'string') return value;
    if (typeof value === 'number') return value.toString();
    if (value && typeof value === 'object' && '_id' in value) {
      return String((value as Record<string, unknown>)._id);
    }
    return "unknown";
  }

  private timestampFor(payload: Record<string, unknown>, rawLocation: Record<string, unknown>): string | undefined {
    if (typeof payload.timestamp === 'string') return payload.timestamp;
    if (typeof rawLocation.timestamp === 'string') return rawLocation.timestamp;
    return undefined;
  }

  private normalizePayload(payload: Record<string, unknown>): UserLocationRecord | null {
    const rawLocation = (payload.location as Record<string, unknown>) || {};
    if (!rawLocation || Object.keys(rawLocation).length === 0) return null;

    const record: UserLocationRecord = {
      _id: this.stringifyId(payload._id ?? payload.recordId ?? payload.phoneNumber),
      phoneNumber: this.normalizePhone(payload),
      platform: typeof payload.platform === "string"
        ? payload.platform
        : (typeof payload.paltform === "string" ? payload.paltform : undefined),
      location: this.buildLocation(rawLocation),
      timestamp: this.timestampFor(payload, rawLocation),
    };
    return record;
  }

  async getLatestUserLocation(): Promise<UserLocationRecord | null> {
    const response = await fetch(`${this.baseUrl}/location/all`, {
      cache: 'no-store',
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch user locations: ${response.statusText}`);
    }

    const payload = (await response.json()) as { locations?: Record<string, unknown>[] } | null;
    const locations = Array.isArray(payload?.locations) ? payload.locations : [];

    if (!locations.length) {
      return null;
    }

    const records = locations
      .map((loc) => this.normalizePayload(loc))
      .filter((rec): rec is UserLocationRecord => rec !== null);

    if (!records.length) {
      return null;
    }

    const latest = records.reduce((prev, current) => {
      const prevTime = prev.timestamp ? Date.parse(prev.timestamp) : 0;
      const currTime = current.timestamp ? Date.parse(current.timestamp) : 0;
      return currTime >= prevTime ? current : prev;
    });

    return latest;
  }

  async getAllUserLocations(): Promise<UserLocationRecord[]> {
    const response = await fetch(`${this.baseUrl}/location/all`, {
      cache: 'no-store',
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch user locations: ${response.statusText}`);
    }

    const payload = (await response.json()) as { locations?: Record<string, unknown>[] } | null;
    const locations = Array.isArray(payload?.locations) ? payload.locations : [];

    if (!locations.length) {
      return [];
    }

    const records = locations
      .map((loc) => this.normalizePayload(loc))
      .filter((rec): rec is UserLocationRecord => rec !== null);

    // Sort by timestamp descending (most recent first)
    return records.sort((a, b) => {
      const timeA = a.timestamp ? Date.parse(a.timestamp) : 0;
      const timeB = b.timestamp ? Date.parse(b.timestamp) : 0;
      return timeB - timeA;
    });
  }

  async saveUserLocation(params: {
    latitude: number;
    longitude: number;
    phoneNumber?: string;
    username?: string;
    timestamp?: string;
  }): Promise<void> {
    const { latitude, longitude, phoneNumber, username, timestamp } = params;

    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
      return;
    }

    const identity = (phoneNumber || username || "Unknown").trim() || "Unknown";
    const isoTimestamp = timestamp || new Date().toISOString();

    const payload = {
      phoneNumber: identity,
      username: username || identity,
      location: {
        latitude,
        longitude,
        timestamp: isoTimestamp,
      },
      timestamp: isoTimestamp,
    };

    const candidatePaths = [
      "/location",
      "/location/update",
      "/location/add",
      "/location/create",
    ];

    for (const path of candidatePaths) {
      try {
        const response = await fetch(`${this.baseUrl}${path}`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        });

        if (response.ok) {
          return;
        }
      } catch {
        // Keep trying candidate endpoints.
      }
    }
  }
}

export const userLocationApi = new UserLocationApi();
