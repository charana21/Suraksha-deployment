/* -------------------------------------------------------------------------- */
/*  Crowd Control API                                                         */
/*  Suggested location: src/api/crowdControl.ts                               */
/* -------------------------------------------------------------------------- */

export type CrowdGroup = {
  name?: string | null;
  people_count?: number | null;
  capacity?: number | null;
  level?: string | null;
  camera_ids?: string[];
};

export type BookingOfficeCamera = {
  name?: string | null;
  camera_id?: string;
  people_count?: number | null;
  capacity?: number | null;
  level?: string | null;
};

export type CrowdControlResponse = {
  platforms?: { group_level_count?: CrowdGroup[] };
  fobs?: { group_level_count?: CrowdGroup[] };
  holding_areas?: { group_level_count?: CrowdGroup[] };
  booking_office?: { cameras?: BookingOfficeCamera[] };
};

const API_BASE_URL = ((import.meta.env.VITE_API_URL as string) || "").replace(/\/+$/, "");
const API_ROOT = API_BASE_URL.endsWith("/api") ? API_BASE_URL : `${API_BASE_URL}/api`;

export const LIVE_SUMMARY_ENDPOINT = `${API_ROOT}/crowd_control/live-summary`;

export async function fetchCrowdSummary(signal?: AbortSignal): Promise<CrowdControlResponse> {
  const response = await fetch(LIVE_SUMMARY_ENDPOINT, { signal });
  if (!response.ok) {
    throw new Error(`Failed to fetch crowd summary: HTTP ${response.status}`);
  }
  return (await response.json()) as CrowdControlResponse;
}