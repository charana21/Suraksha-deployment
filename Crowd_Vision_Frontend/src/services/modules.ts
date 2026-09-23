const RAW_API_BASE_URL = (import.meta.env.VITE_API_URL as string) || "";
const API_BASE_URL = RAW_API_BASE_URL.replace(/\/+$/, '');
const API_ROOT = API_BASE_URL.endsWith('/api')
  ? API_BASE_URL
  : `${API_BASE_URL}/api`;

export interface ModuleItem {
  _id: string;
  name: string;
  description: string;
  urlName: string;
  master: boolean;
  active: number;
  createAt?: string;
  updateAt?: string;
  createBy?: string;
  updateBy?: string;
}

export interface ModulePayload {
  name: string;
  description: string;
  urlName: string;
  master: boolean;
  active: number;
}

export interface ModuleMutationResponse {
  responseMsg: string;
  responseCode: number;
  module: ModuleItem;
}

export interface ModulesResponse {
  status: string;
  count: number;
  modules: ModuleItem[];
}

const getStoredToken = () =>
  localStorage.getItem('access_token') ||
  localStorage.getItem('auth_token');

const parseResponse = async <T>(response: Response): Promise<T> => {
  const text = await response.text();
  let data: unknown = {};

  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { message: text };
  }

  const payload = data as {
    responseMsg?: string;
    detail?: string;
    message?: string;
  };

  if (!response.ok) {
    throw new Error(
      payload.responseMsg ||
        payload.detail ||
        payload.message ||
        response.statusText ||
        'Request failed',
    );
  }

  return data as T;
};

const getAuthHeaders = (token?: string) => {
  const resolvedToken = token || getStoredToken();

  return {
    'Content-Type': 'application/json',
    ...(resolvedToken ? { Authorization: `Bearer ${resolvedToken}` } : {}),
  };
};

class ModulesApiService {
  private baseUrl: string;

  constructor(baseUrl: string = API_ROOT) {
    this.baseUrl = baseUrl;
  }

  async getModules(token?: string): Promise<ModulesResponse> {
    const response = await fetch(`${this.baseUrl}/master/modules`, {
      method: 'GET',
      headers: getAuthHeaders(token),
    });

    return parseResponse<ModulesResponse>(response);
  }

  async createModule(
    payload: ModulePayload,
    token?: string,
  ): Promise<ModuleMutationResponse> {
    const response = await fetch(`${this.baseUrl}/master/modules`, {
      method: 'POST',
      headers: getAuthHeaders(token),
      body: JSON.stringify(payload),
    });

    return parseResponse<ModuleMutationResponse>(response);
  }

  async updateModule(
    id: string,
    payload: ModulePayload,
    token?: string,
  ): Promise<ModuleMutationResponse> {
    const response = await fetch(`${this.baseUrl}/master/modules/${id}`, {
      method: 'PUT',
      headers: getAuthHeaders(token),
      body: JSON.stringify(payload),
    });

    return parseResponse<ModuleMutationResponse>(response);
  }
}

export const modulesApi = new ModulesApiService();
