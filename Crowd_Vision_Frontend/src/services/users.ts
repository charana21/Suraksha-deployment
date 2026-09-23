const RAW_API_BASE_URL = (import.meta.env.VITE_API_URL as string) || "";
const API_BASE_URL = RAW_API_BASE_URL.replace(/\/+$/, "");
const API_ROOT = API_BASE_URL.endsWith("/api")
  ? API_BASE_URL
  : `${API_BASE_URL}/api`;

export interface UserItem {
  _id: string;
  name: string;
  email: string;
  phone: string;
  roleID: string;
  active: number;
  password?: string;
  services: string[];
  createAt?: string;
  updateAt?: string;
  createBy?: string;
  updateBy?: string;
}

export interface UserPayload {
  name: string;
  email: string;
  phone: string;
  roleID: string;
  active: number;
  password?: string;
  services: string[];
}

export interface UsersResponse {
  status: string;
  count: number;
  users: UserItem[];
}

export interface UserMutationResponse {
  responseMsg: string;
  responseCode: number;
  user: UserItem;
}

const getStoredToken = () =>
  localStorage.getItem("access_token") ||
  localStorage.getItem("auth_token");

const parseResponse = async <T>(response: Response): Promise<T> => {
  const text = await response.text();
  let data: any = {};

  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { message: text };
  }

  if (!response.ok) {
    throw new Error(
      data?.responseMsg ||
        data?.detail ||
        data?.message ||
        response.statusText ||
        "Request failed",
    );
  }

  return data as T;
};

class UsersApiService {
  private baseUrl: string;

  constructor(baseUrl: string = API_ROOT) {
    this.baseUrl = baseUrl;
  }

  async getUsers(token?: string): Promise<UsersResponse> {
    const resolvedToken = token || getStoredToken();

    const response = await fetch(`${this.baseUrl}/master/users`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        ...(resolvedToken ? { Authorization: `Bearer ${resolvedToken}` } : {}),
      },
    });

    return parseResponse<UsersResponse>(response);
  }

  async createUser(
    payload: UserPayload,
    token?: string,
  ): Promise<UserMutationResponse> {
    const resolvedToken = token || getStoredToken();

    const response = await fetch(`${this.baseUrl}/master/users`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(resolvedToken ? { Authorization: `Bearer ${resolvedToken}` } : {}),
      },
      body: JSON.stringify(payload),
    });

    return parseResponse<UserMutationResponse>(response);
  }

  async updateUser(
    id: string,
    payload: UserPayload,
    token?: string,
  ): Promise<UserMutationResponse> {
    const resolvedToken = token || getStoredToken();

    const response = await fetch(`${this.baseUrl}/master/users/${id}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        ...(resolvedToken ? { Authorization: `Bearer ${resolvedToken}` } : {}),
      },
      body: JSON.stringify(payload),
    });

    return parseResponse<UserMutationResponse>(response);
  }
}

export const usersApi = new UsersApiService();
