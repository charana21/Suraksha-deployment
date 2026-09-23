import { TrainUploadResponse } from '@/types/trains';
const API_BASE_URL = (import.meta.env.VITE_API_URL as string) || "";

class CalendarApiService {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
  }

  private buildUrl(path: string, query?: string) {
    const trimmedPath = path.startsWith('/') ? path : `/${path}`;
    return `${this.baseUrl}${trimmedPath}${query ? `?${query}` : ''}`;
  }

  /**
   * Upload calendar Excel file
   * Parameters expected in Excel: _id, schedule_date, train_number, boarding_count, deboarding_count, total_passengers
   */
  async uploadCalendarData(file: File): Promise<TrainUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch(this.buildUrl('/trains/upload-calendar'), {
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
   * Upload special trains Excel file
   * Parameters expected in Excel: train_number, schedule_date, total_passengers
   */
  async uploadSpecialTrainsData(file: File): Promise<TrainUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch(this.buildUrl('/special-trains/upload'), {
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
   * Upload UTS and PRS booking Excel file
   * Parameters expected: DATE, UTS INWARD, UTS OUTWARD, UTS TOTAL, PRS INWARD, PRS OUTWARD, PRS TOTAL, OVERALL TOTAL
   */
  async uploadUtsData(file: File): Promise<TrainUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch(this.buildUrl('/uts-data/upload'), {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || errorData.message || `Upload failed: ${response.statusText}`);
    }

    return response.json();
  }
}

export const calendarApi = new CalendarApiService();
