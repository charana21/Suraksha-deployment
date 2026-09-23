/**
 * Alert Management API Service
 * Handles communication with backend Alert endpoints
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://crowdvision-api.tride.live/api';

export type AlertSeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type AlertStatus = 'triggered' | 'acknowledged' | 'resolved';

export interface Alert {
    _id?: string;
    alert_id: string;
    camera_id: string;
    camera_name?: string;
    zone_id?: string;
    zone_type?: 'FOB' | 'PLATFORM' | 'BOOKING';
    fob_id?: string;
    severity: AlertSeverity;
    status: AlertStatus;
    trigger_reason?: string;
    risk_score?: number;
    people_count?: number;
    timestamp: string; // ISO String
}

export interface ListAlertsParams {
    camera_id?: string;
    camera_name?: string;
    severity?: AlertSeverity;
    status?: AlertStatus;
    zone_type?: 'FOB' | 'PLATFORM' | 'BOOKING';
    zone_id?: string;
    hours?: number;
    limit?: number;
    page?: number;
    pagesize?: number;
}

export interface ListAlertsResponse {
    status: string;
    count: number;
    alerts: Alert[];
    total?: number;
    page?: number;
    pagesize?: number;
    total_pages?: number;
}

export interface AlertDetailResponse {
    status: string;
    alert: Alert;
}

export interface AlertActionResponse {
    status: string;
    message: string;
    alert_id: string;
}

// Stats Interfaces
export interface AlertStatsSummary {
    total_alerts: number;
    critical_incidents: number;
    avg_alerts_per_day: number;
    peak_hour: string;
}

export interface DailyTrend {
    date: string;
    total: number;
    critical: number;
}

export interface SeverityDistribution {
    LOW?: number;
    MEDIUM?: number;
    HIGH?: number;
    CRITICAL?: number;
}

export interface TopCamera {
    camera_id: string;
    count: number;
}

export interface HourlyDistribution {
    hour: string;
    count: number;
}

export interface ZoneTypeDistribution {
    FOB?: number;
    PLATFORM?: number;
    BOOKING?: number;
}

export interface AlertStatsResponse {
    status: string;
    range: string;
    summary: AlertStatsSummary;
    daily_trend: DailyTrend[];
    severity_distribution: SeverityDistribution;
    zone_type_distribution?: ZoneTypeDistribution;
    top_cameras: TopCamera[];
    hourly_distribution: HourlyDistribution[];
}

export interface CameraSummaryResponse {
    status: string;
    camera_id: string;
    time_range_hours: number;
    total_alerts: number;
    by_severity: Record<AlertSeverity, number>;
    by_status: Record<AlertStatus, number>;
}



export interface IslandTrain {
    train_number: string;
    train_name: string;
    arrival_time: string | null;
    departure_time: string | null;
    passengers: number;
    platform: string;
    stability_percent?: number;
    certainty?: string;
    explanation?: string;
}

export interface IslandAlert {
    alert_id: string;
    alert_type: string;
    island_id: string;
    island_name: string;
    window_start: string;
    window_end: string;
    total_footfall: number;
    threshold: number;
    exceeds_by: number;
    exceeds_by_percent: number;
    risk_level: string;
    certainty_breakdown?: {
        high_certainty_trains: number;
        medium_certainty_trains: number;
        low_certainty_trains: number;
        total_trains: number;
    };
    contributing_trains: IslandTrain[];
    status: string;
    advisory_message: string;
}

export interface IslandAlertResponse {
    status: string;
    current_time: string;
    window_end: string;
    count: number;
    alerts: IslandAlert[];
}

class AlertApiService {
    private baseUrl: string;

    constructor() {
        this.baseUrl = API_BASE_URL;
    }

    /**
     * List historical alerts with filtering
     */
    async listAlerts(params: ListAlertsParams = {}): Promise<ListAlertsResponse> {
        const query = new URLSearchParams();
        if (params.camera_id) query.append('camera_id', params.camera_id);
        if (params.camera_name) query.append('camera_name', params.camera_name);
        if (params.severity) query.append('severity', params.severity);
        if (params.status) query.append('status', params.status);
        if (params.zone_type) query.append('zone_type', params.zone_type);
        if (params.zone_id) query.append('zone_id', params.zone_id);
        if (params.hours) query.append('hours', params.hours.toString());
        if (params.limit) query.append('limit', params.limit.toString());
        if (params.page) query.append('page', params.page.toString());
        if (params.pagesize) query.append('pagesize', params.pagesize.toString());

        const response = await fetch(`${this.baseUrl}/alerts?${query.toString()}`);
        if (!response.ok) throw new Error('Failed to fetch alerts');
        return response.json();
    }

    /**
     * Get all currently unresolved alerts (status="triggered")
     */
    async getActiveAlerts(): Promise<ListAlertsResponse> {
        const response = await fetch(`${this.baseUrl}/alerts/active`);
        if (!response.ok) throw new Error('Failed to fetch active alerts');
        return response.json();
    }

    /**
     * Get specific alert by ID
     */
    async getAlertDetails(alertId: string): Promise<AlertDetailResponse> {
        const response = await fetch(`${this.baseUrl}/alerts/${alertId}`);
        if (!response.ok) throw new Error('Failed to fetch alert details');
        return response.json();
    }

    /**
     * Acknowledge an alert
     */
    async acknowledgeAlert(alertId: string): Promise<AlertActionResponse> {
        const response = await fetch(`${this.baseUrl}/alerts/${alertId}/acknowledge`, {
            method: 'POST',
        });
        if (!response.ok) throw new Error('Failed to acknowledge alert');
        return response.json();
    }

    /**
     * Resolve an alert
     */
    async resolveAlert(alertId: string): Promise<AlertActionResponse> {
        const response = await fetch(`${this.baseUrl}/alerts/${alertId}/resolve`, {
            method: 'POST',
        });
        if (!response.ok) throw new Error('Failed to resolve alert');
        return response.json();
    }

    /**
     * Get Global Alert Stats (Dashboard)
     * Supported ranges: 24h, 7d, 30d
     */
    async getAlertStats(range: '24h' | '7d' | '30d' = '7d'): Promise<AlertStatsResponse> {
        const query = new URLSearchParams({ range });
        const response = await fetch(`${this.baseUrl}/alerts/report/stats?${query.toString()}`);
        if (!response.ok) throw new Error('Failed to fetch alert stats');
        return response.json();
    }

    /**
     * Get quick stats for a specific camera
     */
    async getCameraSummary(cameraId: string, hours: number = 24): Promise<CameraSummaryResponse> {
        const query = new URLSearchParams({ hours: hours.toString() });
        const response = await fetch(`${this.baseUrl}/alerts/camera/${cameraId}/summary?${query.toString()}`);
        if (!response.ok) throw new Error('Failed to fetch camera summary');
        return response.json();
    }

    /**
     * Get live island platform alerts
     * Polls every 30 seconds (managed by caller)
     */
    async getLiveIslandAlerts(hours_ahead: number = 2): Promise<IslandAlertResponse> {
        const query = new URLSearchParams({ hours_ahead: hours_ahead.toString() });
        const response = await fetch(`${this.baseUrl}/island-alerts/live?${query.toString()}`);
        if (!response.ok) throw new Error('Failed to fetch island alerts');
        return response.json();
    }
}

export const alertApi = new AlertApiService();
