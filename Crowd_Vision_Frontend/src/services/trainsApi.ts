import { UpcomingTrainsResponse, TrainUploadResponse, TrainLiveToggleResponse, ArrivalHistoryResponse } from '@/types/trains';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://crowdvision-api.tride.live/api';

class TrainsApiService {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
  }

  private getAuthHeaders() {
    if (typeof window === 'undefined') {
      return {};
    }
    const token = localStorage.getItem('auth_token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  private buildUrl(path: string, query?: string) {
    const trimmedPath = path.startsWith('/') ? path : `/${path}`;
    return `${this.baseUrl}${trimmedPath}${query ? `?${query}` : ''}`;
  }

  private async handleResponse<T>(response: Response, context: string): Promise<T> {
    const defaultMessage = `${context} failed: ${response.status} ${response.statusText}`;
    if (!response.ok) {
      let message = defaultMessage;
      try {
        const payload = await response.json();
        if (payload?.detail) {
          message = payload.detail;
        } else if (payload?.message) {
          message = payload.message;
        }
      } catch {
        // ignore parsing errors
      }
      throw new Error(message);
    }
    return response.json();
  }

  /**
   * Upload train schedule Excel file
   */
  async uploadTrainSchedule(file: File, replaceDates: boolean = false): Promise<TrainUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    if (replaceDates) {
      formData.append('replace_dates', 'true');
    }

    const response = await fetch(this.buildUrl('/trains/upload'), {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || errorData.message || `Upload failed: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get upcoming trains
   */
  async getUpcomingTrains(): Promise<UpcomingTrainsResponse> {
    const params = new URLSearchParams({
      window_hours: '1',
      include_live: 'true',
    });
    const response = await fetch(this.buildUrl('/trains/upcoming', params.toString()), {
      headers: this.getAuthHeaders(),
    });

    return this.handleResponse<UpcomingTrainsResponse>(response, 'Fetching upcoming trains');
  }

  async getLiveToggle(): Promise<TrainLiveToggleResponse> {
    const response = await fetch(this.buildUrl('/trains/live-toggle'), {
      headers: this.getAuthHeaders(),
    });
    return this.handleResponse<TrainLiveToggleResponse>(response, 'Fetching live toggle');
  }

  async setLiveToggle(enabled: boolean): Promise<TrainLiveToggleResponse> {
    const response = await fetch(this.buildUrl('/trains/live-toggle'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
      },
      body: JSON.stringify({ enabled }),
    });

    const result = await this.handleResponse<TrainLiveToggleResponse>(response, 'Updating live toggle');

    return result;
  }

  /**
   * Get arrival/departure history for a train within a date range
   */
  async getArrivalHistory(params: { trainNumber: string; startDate: string; endDate: string }): Promise<ArrivalHistoryResponse> {
    const query = new URLSearchParams({
      start_date: params.startDate,
      end_date: params.endDate,
      train_number: params.trainNumber,
    });
    const response = await fetch(this.buildUrl('/trains/live-status/history', query.toString()), {
      headers: this.getAuthHeaders(),
    });

    return this.handleResponse<ArrivalHistoryResponse>(response, 'Fetching arrival history');
  }

  /**
   * Download arrival/departure history (PDF/Excel) for a train within a date range
   */
  async downloadArrivalHistory(params: { trainNumber: string; startDate: string; endDate: string }): Promise<void> {
    const query = new URLSearchParams({
      start_date: params.startDate,
      end_date: params.endDate,
      train_number: params.trainNumber,
      download: 'true',
    });
    const response = await fetch(this.buildUrl('/trains/live-status/history', query.toString()), {
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      throw new Error(`Downloading arrival history failed: ${response.status} ${response.statusText}`);
    }

    const blob = await response.blob();
    const disposition = response.headers.get('Content-Disposition') || '';
    const filenameMatch = disposition.match(/filename="?([^"]+)"?/i);
    const filename = filenameMatch?.[1] || `arrival-history-${params.trainNumber}-${params.startDate}_to_${params.endDate}.xlsx`;

    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  }
}

export const trainsApi = new TrainsApiService();