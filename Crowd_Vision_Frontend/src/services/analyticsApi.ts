const API_BASE_URL = import.meta.env.VITE_API_URL;

export interface AnalyticsHistoryParams {
    fob_id: string;
    start: string; // ISO string
    end: string;   // ISO string
    interval?: string; // '1h', '1d', etc.
}

export interface ZoneHistoryParams {
    zone_id: string;
    start: string;
    end: string;
    interval?: string;
}

export interface CameraHistoryParams {
    camera_id: string;
    start: string;
    end: string;
    interval?: string;
}

export interface StationHistoryParams {
    station_id?: string; // defaults to 'HYB'
    start: string;
    end: string;
    interval?: string;
}

export interface AnalyticsHistoryPoint {
    timestamp: string;
    count: number;
}

export interface AnalyticsHistoryResponse {
    data: AnalyticsHistoryPoint[];
    overall_peak: number;
}

const mapHistoryJson = (json: any): AnalyticsHistoryResponse => {
    const items = Array.isArray(json) ? json : (json.data || []);
    const overallPeak = json.overall_peak || 0;
    const mappedData = items.map((item: any) => ({
        timestamp: item.timestamp,
        count: item.peak_count ?? item.total_count ?? item.count ?? 0,
    }));
    return { data: mappedData, overall_peak: overallPeak };
};

const fetchJson = async (url: string): Promise<any> => {
    const response = await fetch(url, { method: 'GET', headers: { 'Content-Type': 'application/json' } });
    if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    return response.json();
};

export const analyticsApi = {
    getFobHistory: async (params: AnalyticsHistoryParams): Promise<AnalyticsHistoryResponse> => {
        const query = new URLSearchParams({
            fob_id: params.fob_id,
            start: params.start,
            end: params.end,
            interval: params.interval || '1h',
        });
        try {
            const json = await fetchJson(`${API_BASE_URL}/analytics/fob/history?${query}`);
            return mapHistoryJson(json);
        } catch (error) {
            return { data: [], overall_peak: 0 };
        }
    },

    /** Generic zone history — works for FOB, PLATFORM, BOOKING zones */
    getZoneHistory: async (params: ZoneHistoryParams): Promise<AnalyticsHistoryResponse> => {
        const query = new URLSearchParams({
            zone_id: params.zone_id,
            start: params.start,
            end: params.end,
            interval: params.interval || '5m',
        });
        try {
            const json = await fetchJson(`${API_BASE_URL}/analytics/zone/history?${query}`);
            return mapHistoryJson(json);
        } catch (error) {
            return { data: [], overall_peak: 0 };
        }
    },

    /** Camera-wise footfall history */
    getCameraHistory: async (params: CameraHistoryParams): Promise<AnalyticsHistoryResponse> => {
        const query = new URLSearchParams({
            camera_id: params.camera_id,
            start: params.start,
            end: params.end,
            interval: params.interval || '5m',
        });
        try {
            const json = await fetchJson(`${API_BASE_URL}/analytics/camera/history?${query}`);
            return mapHistoryJson(json);
        } catch (error) {
            return { data: [], overall_peak: 0 };
        }
    },

    /** Station-wide aggregated footfall history */
    getStationHistory: async (params: StationHistoryParams): Promise<AnalyticsHistoryResponse> => {
        const query = new URLSearchParams({
            station_id: params.station_id || 'HYB',
            start: params.start,
            end: params.end,
            interval: params.interval || '5m',
        });
        try {
            const json = await fetchJson(`${API_BASE_URL}/analytics/station/history?${query}`);
            return mapHistoryJson(json);
        } catch (error) {
            return { data: [], overall_peak: 0 };
        }
    },
};
