/**
 * WebSocket Service for Real-Time Analytics
 * Replaces polling with push-based updates from backend
 *
 * SINGLETON PATTERN: Only one WebSocket connection is shared across the app
 */

const WS_BASE_URL =
  import.meta.env.VITE_WS_URL ||
  (import.meta.env.VITE_API_URL || 'https://crowdvision-api.tride.live/api')
    .replace(/^http/, 'ws')
    .replace(/\/api$/, '');

import { TrainSchedule } from '@/types/trains';

export interface AnalyticsMessage {
  type: 'analytics';
  camera_id: string;
  timestamp: string;
  data: {
    frame_number: number;
    people_count: number;
    head_detections: number;
    density_avg: number;
    density_max: number;
    motion_intensity: number;
    risk_score: number;
    risk_level: string;
    risk_factors: string[];
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

export interface AlertMessage {
  type: 'alert';
  camera_id: string;
  timestamp: string;
  data: {
    alert_id: string;
    severity: string;
    trigger_reason: string;
    risk_score: number;
    status: string;
    has_image: boolean;
  };
}

export interface TrainScheduleMessage {
  type: 'train_schedule';
  event: 'upcoming_update';
  timestamp: string;
  data: {
    trains: any[];
    total_count: number;
  };
}

export type WebSocketMessage = AnalyticsMessage | AlertMessage | TrainScheduleMessage;

export type MessageHandler = (message: WebSocketMessage) => void;
export type ConnectionHandler = (connected: boolean) => void;

/**
 * Singleton WebSocket Manager for Real-Time Analytics
 *
 * Features:
 * - Single shared connection across all components
 * - Automatic reconnection with exponential backoff
 * - Reference counting for cleanup
 */
class WebSocketManager {
  private static instance: WebSocketManager | null = null;

  private ws: WebSocket | null = null;
  private messageHandlers: Set<MessageHandler> = new Set();
  private connectionHandlers: Set<ConnectionHandler> = new Set();
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectInterval = 3000;
  private isConnecting = false;
  private refCount = 0;

  private constructor() {}

  static getInstance(): WebSocketManager {
    if (!WebSocketManager.instance) {
      WebSocketManager.instance = new WebSocketManager();
    }
    return WebSocketManager.instance;
  }

  /**
   * Subscribe to WebSocket messages
   * Returns cleanup function
   */
  subscribe(
    onMessage: MessageHandler,
    onConnection?: ConnectionHandler
  ): () => void {
    this.messageHandlers.add(onMessage);
    if (onConnection) {
      this.connectionHandlers.add(onConnection);
      // Immediately notify of current state
      onConnection(this.isConnected);
    }

    this.refCount++;

    // Connect if this is the first subscriber
    if (this.refCount === 1) {
      this.connect();
    }

    // Return cleanup function
    return () => {
      this.messageHandlers.delete(onMessage);
      if (onConnection) {
        this.connectionHandlers.delete(onConnection);
      }
      this.refCount--;

      // Disconnect if no more subscribers
      if (this.refCount <= 0) {
        this.disconnect();
      }
    };
  }

  private connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN || this.isConnecting) {
      return;
    }

    this.isConnecting = true;
    const token =
      localStorage.getItem('access_token') ||
      localStorage.getItem('auth_token');
    const url = token
      ? `${WS_BASE_URL}/api/ws/analytics?token=${encodeURIComponent(token)}`
      : `${WS_BASE_URL}/api/ws/analytics`;

    try {
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        this.isConnecting = false;
        this.reconnectAttempts = 0;
        this.notifyConnection(true);
      };

      this.ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          this.messageHandlers.forEach(handler => {
            try {
              handler(message);
            } catch (e) {
            }
          });
        } catch (error) {
        }
      };

      this.ws.onerror = (error) => {
        this.isConnecting = false;
      };

      this.ws.onclose = (event) => {
        this.isConnecting = false;
        this.notifyConnection(false);

        // Reconnect if we still have subscribers
        if (this.refCount > 0) {
          this.attemptReconnect();
        }
      };
    } catch (error) {
      this.isConnecting = false;
      this.attemptReconnect();
    }
  }

  private disconnect(): void {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.refCount = 0;
    this.reconnectAttempts = 0;
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      return;
    }

    if (this.reconnectTimeout) {
      return; // Already scheduled
    }

    this.reconnectAttempts++;
    const delay = Math.min(
      this.reconnectInterval * Math.pow(2, this.reconnectAttempts - 1),
      30000
    );

    this.reconnectTimeout = setTimeout(() => {
      this.reconnectTimeout = null;
      this.connect();
    }, delay);
  }

  private notifyConnection(connected: boolean): void {
    this.connectionHandlers.forEach(handler => {
      try {
        handler(connected);
      } catch (e) {
      }
    });
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  get connectionState(): string {
    if (!this.ws) return 'disconnected';
    switch (this.ws.readyState) {
      case WebSocket.CONNECTING: return 'connecting';
      case WebSocket.OPEN: return 'connected';
      case WebSocket.CLOSING: return 'closing';
      case WebSocket.CLOSED: return 'disconnected';
      default: return 'unknown';
    }
  }
}

// Export singleton instance
export const websocketManager = WebSocketManager.getInstance();

// Legacy exports for compatibility (deprecated)
export class WebSocketService {
  private cleanup: (() => void) | null = null;

  constructor(_endpoint: string, options: { onMessage?: MessageHandler; onOpen?: () => void; onClose?: () => void } = {}) {
    // Use singleton instead
    this.cleanup = websocketManager.subscribe(
      options.onMessage || (() => {}),
      (connected) => {
        if (connected) {
          options.onOpen?.();
        } else {
          options.onClose?.();
        }
      }
    );
  }

  connect(): void {
    // Already connected via singleton
  }

  disconnect(): void {
    this.cleanup?.();
  }

  get isConnected(): boolean {
    return websocketManager.isConnected;
  }

  get connectionState(): string {
    return websocketManager.connectionState;
  }
}

export function createAnalyticsWebSocket(options: { onMessage?: MessageHandler; onOpen?: () => void; onClose?: () => void; onError?: () => void } = {}): WebSocketService {
  return new WebSocketService('/api/ws/analytics', options);
}

export function createCameraWebSocket(cameraId: string, options: { onMessage?: MessageHandler; onOpen?: () => void; onClose?: () => void; onError?: () => void } = {}): WebSocketService {
  // Always use the all-cameras endpoint via singleton
  return new WebSocketService('/api/ws/analytics', options);
}
