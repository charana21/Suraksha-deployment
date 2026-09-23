/**
 * RTSP Stream API Service
 * Handles communication with backend RTSP streaming endpoints
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://crowdvision-api.tride.live/api';

export interface StartStreamRequest {
  rtsp_url: string;
  stream_id?: string;
  target_fps?: number;
  name?: string;
}

export interface StreamResponse {
  stream_id: string;
  rtsp_url: string;
  status: string;
  message: string;
}

export interface StreamState {
  stream_id: string;
  camera_id?: string; // Camera ID for WebSocket subscriptions (e.g., "camera_entry_stair")
  name: string;
  rtsp_url: string;
  status: 'connecting' | 'running' | 'error' | 'stopped';
  is_running: boolean;
  fps: number;
  frame_count: number;
  error_count: number;
  last_error?: string;
  started_at?: string;
  last_analysis?: {
    frame_number: number;
    people_count: number;
    head_detections: number;
    density_avg: number;
    density_max: number;
    motion_intensity: number;
    zones?: {
      [key: string]: {
        id: string;
        name: string;
        coords: number[];
        people_count: number;
        head_detections: number;
        density_estimate: number;
        density_level: string;
        avg_motion: number;
        risk_score: number;
        risk_level: string;
        risk_factors: string[];
      };
    };
  };
}

export interface StreamListResponse {
  summary: {
    total: number;
    running: number;
    stopped: number;
    error: number;
  };
  streams: StreamState[];
}

export interface BackendCamera {
  camera_id: string;
  name: string;
  rtsp_url: string;
  fob_type: 'HYD' | 'KZJ';
  zone_id: string;
  status: 'active' | 'inactive' | 'error';
  is_active: boolean;
  runtime_status?: 'running' | 'connecting' | 'error' | 'stopped'; // From status endpoint
}

export interface CameraListResponse {
  status: string;
  cameras: BackendCamera[];
}

export interface CameraStatusResponse {
  camera_id: string;
  runtime_status: 'running' | 'connecting' | 'error' | 'stopped';
  fps?: number;
  message?: string;
}

export interface MultipleStreamResult {
  total: number;
  started: number;
  failed: number;
  results: StreamResponse[];
}

class RTSPApiService {
  private baseUrl: string;

  constructor() {
    this.baseUrl = API_BASE_URL;
  }

  /**
   * Start a new RTSP stream
   */
  async startStream(request: StartStreamRequest): Promise<StreamResponse> {
    const response = await fetch(`${this.baseUrl}/rtsp/start`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ detail: "Failed to start stream" }));
      throw new Error(error.detail || "Failed to start stream");
    }

    return response.json();
  }

  /**
   * Start multiple RTSP streams
   */
  async startMultipleStreams(
    streams: StartStreamRequest[]
  ): Promise<MultipleStreamResult> {
    const response = await fetch(`${this.baseUrl}/rtsp/start-multiple`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ streams }),
    });

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ detail: "Failed to start streams" }));
      throw new Error(error.detail || "Failed to start streams");
    }

    return response.json();
  }

  /**
   * Stop a specific RTSP stream
   */
  async stopStream(
    streamId: string
  ): Promise<{ stream_id: string; status: string; message: string }> {
    const response = await fetch(`${this.baseUrl}/rtsp/stop/${streamId}`, {
      method: "POST",
    });

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ detail: "Failed to stop stream" }));
      throw new Error(error.detail || "Failed to stop stream");
    }

    return response.json();
  }

  /**
   * Stop all RTSP streams
   */
  async stopAllStreams(): Promise<{
    status: string;
    message: string;
    streams_stopped: number;
  }> {
    const response = await fetch(`${this.baseUrl}/rtsp/stop-all`, {
      method: "POST",
    });

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ detail: "Failed to stop streams" }));
      throw new Error(error.detail || "Failed to stop streams");
    }

    return response.json();
  }

  /**
   * Get status of a specific stream
   */
  async getStreamStatus(streamId: string): Promise<StreamState> {
    const response = await fetch(`${this.baseUrl}/rtsp/status/${streamId}`);

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ detail: "Stream not found" }));
      throw new Error(error.detail || "Stream not found");
    }

    return response.json();
  }

  /**
   * List all RTSP streams
   */
  async listStreams(): Promise<StreamListResponse> {
    const response = await fetch(`${this.baseUrl}/rtsp/list`);

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ detail: "Failed to list streams" }));
      throw new Error(error.detail || "Failed to list streams");
    }

    return response.json();
  }

  /**
   * Get frame URL for a stream (for img src)
   */
  getFrameUrl(
    streamId: string,
    options?: { heatmap?: boolean; t?: number }
  ): string {
    const params = new URLSearchParams();

    if (options?.heatmap) params.set("heatmap", "true");
    if (options?.t !== undefined) params.set("t", String(options.t));

    const query = params.toString();
    return `${this.baseUrl}/rtsp/frame/${streamId}${query ? `?${query}` : ""}`;
  }

  /**
   * Health check for RTSP system
   */
  async healthCheck(): Promise<{
    status: string;
    service: string;
    streams: { total: number; running: number };
  }> {
    const response = await fetch(`${this.baseUrl}/rtsp/health`);

    if (!response.ok) {
      throw new Error("RTSP service unavailable");
    }

    return response.json();
  }

  /**
   * Cleanup stopped streams
   */
  async cleanupStoppedStreams(): Promise<{
    status: string;
    message: string;
    streams_cleaned: number;
  }> {
    const response = await fetch(`${this.baseUrl}/rtsp/cleanup`, {
      method: "POST",
    });

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ detail: "Failed to cleanup" }));
      throw new Error(error.detail || "Failed to cleanup");
    }

    return response.json();
  }


  // --- NEW CAMERA MANAGEMENT API ---

  async listCameras(fobType?: string): Promise<CameraListResponse> {
    const params = new URLSearchParams();
    if (fobType) params.append('fob_type', fobType);
    
    const queryString = fobType ? `?${params.toString()}` : '';
    const response = await fetch(`${this.baseUrl}/cameras${queryString}`);

    if (!response.ok) {
      throw new Error("Failed to fetch cameras");
    }
    return response.json();
  }

  async getCamera(id: string): Promise<BackendCamera> {
    const response = await fetch(`${this.baseUrl}/cameras/${id}`);
    if (!response.ok) throw new Error("Failed to get camera details");
    return response.json();
  }

  async updateCamera(id: string, data: { name?: string; rtsp_url?: string }): Promise<BackendCamera> {
    const response = await fetch(`${this.baseUrl}/cameras/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error("Failed to update camera");
    return response.json();
  }

  async startCamera(id: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/cameras/${id}/start`, { method: "POST" });
    if (!response.ok) {
       const err = await response.json().catch(() => ({ detail: "Failed to start" }));
       throw new Error(err.detail || "Failed to start camera");
    }
  }

  async stopCamera(id: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/cameras/${id}/stop`, { method: "POST" });
     if (!response.ok) {
       const err = await response.json().catch(() => ({ detail: "Failed to stop" }));
       throw new Error(err.detail || "Failed to stop camera");
    }
  }

  async getCameraRuntimeStatus(id: string): Promise<CameraStatusResponse> {
    const response = await fetch(`${this.baseUrl}/cameras/${id}/status`);
    if (!response.ok) throw new Error("Failed to get camera status");
    return response.json();
  }

  /**
   * URL for the raw MJPEG live stream (multipart/x-mixed-replace) of a
   * camera. Meant to be used directly as an <img src="..."> - browsers
   * render MJPEG multipart streams natively, no manual decoding needed.
   */
  getLiveStreamUrl(id: string): string {
    return `${this.baseUrl}/cameras/${id}/live`;
  }
}

export const rtspApi = new RTSPApiService();
