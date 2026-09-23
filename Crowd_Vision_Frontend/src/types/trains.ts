export interface TrainSchedule {
  train_number: string;
  train_name: string;
  
  // API Fields
  arrival_scheduled: string | null;
  departure_scheduled: string | null;
  arrival_actual: string | null;
  departure_actual: string | null;
  
  platform: string | null;
  delay_status: string;
  
  is_current: boolean;
  code?: string;
  name?: string;
  distance?: number | null;
  sequence?: number | null;
  total_passengers?: number | null;

  // Legacy/Computed fields (optional)
  train_type?: string;
  source?: string;
  destination?: string;
  train_event?: 'THROUGH' | 'ORIGINATING' | 'TERMINATING';
  
  status?: string;
}

export interface UpcomingTrainsResponse {
  status: string;
  timestamp: string;
  window_hours: number;
  trains: TrainSchedule[];
  total_count: number;
}

export interface TrainUploadResponse {
  status: string;
  message: string;
  records_processed: number;
  records_inserted?: number;
  records_updated?: number;
  records_skipped?: number;
  // Some endpoints (e.g. /trains/upload-calendar) return these unprefixed instead
  inserted?: number;
  updated?: number;
  skipped?: number;
  dates_found?: string[];
  errors: string[];
}

export interface TrainLiveToggleResponse {
  status: string;
  live_refresh_enabled: boolean;
  last_updated_at: string | null;
  last_updated_by?: string | null;
  last_fetch_cycle?: string | null;
  message?: string;
}

export interface ArrivalHistoryRawApiResponse {
  sequence?: number;
  code?: string;
  name?: string;
  distance?: number;
  platform?: string;
  arrival_scheduled?: string;
  arrival_actual?: string;
  departure_scheduled?: string;
  departure_actual?: string;
  delay_status?: string;
  is_current?: boolean;
}

export interface ArrivalHistoryRecord {
  _id: string;
  schedule_date: string;
  station_code: string;
  train_number: string;
  actual_arrival: string | null;
  actual_departure: string | null;
  api_response_raw: ArrivalHistoryRawApiResponse;
  current_status: string;
  delay_minutes: number;
  delay_status: string;
  fetch_cycle: string;
  is_terminal_status: boolean;
  last_fetched_at: string;
  platform_number: string | null;
}

export interface ArrivalHistoryResponse {
  status: string;
  start_date: string;
  end_date: string;
  count: number;
  trains: ArrivalHistoryRecord[];
}
