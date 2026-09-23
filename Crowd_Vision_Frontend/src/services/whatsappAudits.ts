const RAW_API_BASE_URL = (import.meta.env.VITE_API_URL as string) || "";
const API_BASE_URL = RAW_API_BASE_URL.replace(/\/+$/, "");
const API_ROOT = API_BASE_URL.endsWith("/api")
  ? API_BASE_URL
  : `${API_BASE_URL}/api`;

export interface WhatsAppAuditLocation {
  type?: string;
  coordinates: [number, number];
}

export interface WhatsAppAuditRecord {
  _id: string;
  loginDate: string;
  phoneNumber: string;
  platform: string;
  timestamp: string;
  location?: WhatsAppAuditLocation;
}

export interface WhatsAppAuditsResponse {
  count: number;
  locations: WhatsAppAuditRecord[];
}

const getStoredToken = () =>
  localStorage.getItem("access_token") ||
  localStorage.getItem("auth_token");

const parseResponse = async <T>(response: Response): Promise<T> => {
  const text = await response.text();
  let data: any = {};

  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { message: text };
  }

  if (!response.ok) {
    throw new Error(
      data?.responseMsg ||
        data?.detail ||
        data?.message ||
        response.statusText ||
        "Request failed",
    );
  }

  return data as T;
};

const toNumber = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

const normalizeLocation = (value: unknown): WhatsAppAuditLocation | undefined => {
  if (!value || typeof value !== "object") return undefined;

  const raw = value as Record<string, unknown>;
  const coords = Array.isArray(raw.coordinates) ? raw.coordinates : [];
  const longitude = toNumber(coords[0]);
  const latitude = toNumber(coords[1]);

  if (longitude === null || latitude === null) return undefined;

  return {
    type: typeof raw.type === "string" ? raw.type : "Point",
    coordinates: [longitude, latitude],
  };
};

const normalizeRecord = (value: Record<string, unknown>): WhatsAppAuditRecord | null => {
  const id =
    typeof value._id === "string"
      ? value._id
      : typeof value._id === "number"
        ? String(value._id)
        : "";

  const loginDate = typeof value.loginDate === "string" ? value.loginDate : "";
  const phoneNumber =
    typeof value.phoneNumber === "string"
      ? value.phoneNumber
      : typeof value.phone === "string"
        ? value.phone
        : "";
  const platform =
    typeof value.platform === "string"
      ? value.platform
      : typeof value.paltform === "string"
        ? value.paltform
        : "";
  const timestamp = typeof value.timestamp === "string" ? value.timestamp : "";
  const location = normalizeLocation(value.location);

  if (!id && !phoneNumber && !timestamp) {
    return null;
  }

  return {
    _id: id || `${phoneNumber}-${timestamp || loginDate}`,
    loginDate,
    phoneNumber,
    platform,
    timestamp,
    location,
  };
};

class WhatsAppAuditsApiService {
  private baseUrl: string;

  constructor(baseUrl: string = API_ROOT) {
    this.baseUrl = baseUrl;
  }

  async getAudits(token?: string): Promise<WhatsAppAuditsResponse> {
    const resolvedToken = token || getStoredToken();

    const response = await fetch(`${this.baseUrl}/location/all`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        ...(resolvedToken ? { Authorization: `Bearer ${resolvedToken}` } : {}),
      },
      cache: "no-store",
    });

    const data = await parseResponse<{ count?: number; locations?: Record<string, unknown>[] }>(response);
    const locations = Array.isArray(data.locations) ? data.locations : [];

    return {
      count: typeof data.count === "number" ? data.count : locations.length,
      locations: locations
        .map((item) => normalizeRecord(item))
        .filter((item): item is WhatsAppAuditRecord => item !== null)
        .sort((a, b) => {
          const timeA = a.timestamp ? Date.parse(a.timestamp) : 0;
          const timeB = b.timestamp ? Date.parse(b.timestamp) : 0;
          return timeB - timeA;
        }),
    };
  }
}

export const whatsappAuditsApi = new WhatsAppAuditsApiService();
