const RAW_API_BASE_URL = (import.meta.env.VITE_API_URL as string) || "";
const API_BASE_URL = RAW_API_BASE_URL.replace(/\/+$/, '');
const API_ROOT = API_BASE_URL.endsWith('/api')
  ? API_BASE_URL
  : `${API_BASE_URL}/api`;

export const API_ENDPOINTS = {
  LOGIN: `${API_ROOT}/master/login`,
};

export interface User {
  email: string;
  userID?: string;
  role?: 'admin' | 'operator' | 'viewer' | string;
  full_name?: string | null;
  designation?: string | null;
  phone?: string | null;
  is_active?: boolean;
  created_at?: string;
  last_login?: string | null;
}

export interface LoginResponse {
  responseMsg: string;
  responseCode: number;
  token: string;
  userID: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

const getStoredToken = () =>
  localStorage.getItem('access_token') ||
  localStorage.getItem('auth_token');

const decodeBase64Url = (value: string) => {
  const normalized = value.replace(/-/g, '+').replace(/_/g, '/');
  const padded = normalized.padEnd(
    normalized.length + ((4 - (normalized.length % 4)) % 4),
    '=',
  );
  return atob(padded);
};

const decodeJwtPayload = (token: string): Record<string, unknown> | null => {
  const parts = token.split('.');
  if (parts.length < 2) {
    return null;
  }

  try {
    return JSON.parse(decodeBase64Url(parts[1]));
  } catch {
    return null;
  }
};

const isTokenExpired = (payload: Record<string, unknown>) => {
  const exp = payload.exp;
  return typeof exp === 'number' && Date.now() >= exp * 1000;
};

const mapTokenToUser = (token: string, userID?: string): User => {
  const payload = decodeJwtPayload(token) ?? {};
  if (isTokenExpired(payload)) {
    throw new Error('Session expired');
  }

  const email = typeof payload.email === 'string' ? payload.email : '';
  const fullName =
    typeof payload.name === 'string' ? payload.name : null;

  return {
    email,
    userID:
      userID ||
      (typeof payload.uID === 'string' ? payload.uID : undefined),
    full_name: fullName,
  };
};

export const authApi = {
  login: async (email: string, password: string): Promise<LoginResponse> => {
    const response = await fetch(API_ENDPOINTS.LOGIN, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    const text = await response.text();
    let data: any = {};
    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      data = { message: text };
    }

    if (!response.ok) {
      throw new Error(data?.detail || data?.message || 'Login failed');
    }

    return data as LoginResponse;
  },

  logout: async (): Promise<void> => {
    // Backend does not provide a logout endpoint; clear tokens on client.
    return;
  },

  getCurrentUser: async (token?: string): Promise<User> => {
    const resolvedToken = token || getStoredToken();
    if (!resolvedToken) {
      throw new Error('Missing token');
    }

    return mapTokenToUser(resolvedToken);
  },

  getUserFromToken: (token: string, userID?: string): User => {
    return mapTokenToUser(token, userID);
  }
};

