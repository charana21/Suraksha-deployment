const RAW_API_BASE_URL = (import.meta.env.VITE_API_URL as string) || "";
const API_BASE_URL = RAW_API_BASE_URL.replace(/\/+$/, '');
const API_ROOT = API_BASE_URL.endsWith('/api')
  ? API_BASE_URL
  : `${API_BASE_URL}/api`;

export interface UserModuleActions {
  moduleID: string;
  add: number;
  edit: number;
  view: number;
  delete: number;
}

export interface UserModule {
  moduleID: string;
  moduleName: string;
  urlName: string;
  master: boolean;
  actions: UserModuleActions;
}

export interface UserDetailsResponse {
  userId: string;
  roleID: string;
  userName: string;
  roleName: string;
  email: string;
  modules: UserModule[];
}

const parseResponse = async <T>(response: Response): Promise<T> => {
  const text = await response.text();
  let data: any = {};

  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { message: text };
  }

  if (!response.ok) {
    throw new Error(data?.detail || data?.message || response.statusText || 'Request failed');
  }

  return data as T;
};

class UserApiService {
  private baseUrl: string;

  constructor(baseUrl: string = API_ROOT) {
    this.baseUrl = baseUrl;
  }

  async getUserDetails(token: string): Promise<UserDetailsResponse> {
    const response = await fetch(`${this.baseUrl}/master/userdetail`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
    });

    return parseResponse<UserDetailsResponse>(response);
  }
}

export const userApi = new UserApiService();
