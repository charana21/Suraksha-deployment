const RAW_API_BASE_URL = (import.meta.env.VITE_API_URL as string) || "";
const API_BASE_URL = RAW_API_BASE_URL.replace(/\/+$/, "");
const API_ROOT = API_BASE_URL.endsWith("/api")
  ? API_BASE_URL
  : `${API_BASE_URL}/api`;

export interface RolePermission {
  moduleID: string;
  add: number;
  edit: number;
  view: number;
  delete: number;
}

export interface RoleItem {
  _id: string;
  name: string;
  description: string;
  level?: number;
  isSuperUser?: boolean;
  permissions: RolePermission[];
  active: number;
  createAt?: string;
  updateAt?: string;
  createBy?: string | null;
  updateBy?: string | null;
}

export interface RolePayload {
  name: string;
  description: string;
  level: number;
  isSuperUser: boolean;
  permissions: RolePermission[];
  active: number;
}

export interface RoleMutationResponse {
  responseMsg: string;
  responseCode: number;
  role: RoleItem;
}

export type RolePermissionsPayload = RolePermission[];

export interface RolesResponse {
  status: string;
  count: number;
  roles: RoleItem[];
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

const getAuthHeaders = (token?: string) => {
  const resolvedToken = token || getStoredToken();

  return {
    "Content-Type": "application/json",
    ...(resolvedToken ? { Authorization: `Bearer ${resolvedToken}` } : {}),
  };
};

class RolesApiService {
  private baseUrl: string;

  constructor(baseUrl: string = API_ROOT) {
    this.baseUrl = baseUrl;
  }

  async getRoles(token?: string): Promise<RolesResponse> {
    const resolvedToken = token || getStoredToken();

    const response = await fetch(`${this.baseUrl}/master/roles`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        ...(resolvedToken ? { Authorization: `Bearer ${resolvedToken}` } : {}),
      },
    });

    return parseResponse<RolesResponse>(response);
  }

  async createRole(
    payload: RolePayload,
    token?: string,
  ): Promise<RoleMutationResponse> {
    const response = await fetch(`${this.baseUrl}/master/roles`, {
      method: "POST",
      headers: getAuthHeaders(token),
      body: JSON.stringify(payload),
    });

    return parseResponse<RoleMutationResponse>(response);
  }

  async updateRole(
    id: string,
    payload: RolePayload,
    token?: string,
  ): Promise<RoleMutationResponse> {
    const response = await fetch(`${this.baseUrl}/master/roles/${id}`, {
      method: "PUT",
      headers: getAuthHeaders(token),
      body: JSON.stringify(payload),
    });

    return parseResponse<RoleMutationResponse>(response);
  }

  async updateRolePermissions(
    id: string,
    payload: RolePermissionsPayload,
    token?: string,
  ): Promise<RoleMutationResponse> {
    const response = await fetch(`${this.baseUrl}/master/roles/permissions/${id}`, {
      method: "PUT",
      headers: getAuthHeaders(token),
      body: JSON.stringify(payload),
    });

    return parseResponse<RoleMutationResponse>(response);
  }
}

export const rolesApi = new RolesApiService();
