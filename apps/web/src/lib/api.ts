/**
 * Typed API client for the FastAPI backend.
 */
import axios, { AxiosInstance, AxiosRequestConfig } from "axios";
import Cookies from "js-cookie";

const BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL ??
  (process.env.NODE_ENV === "production" ? "/api/v1" : "http://localhost:8000/api/v1")
).replace(/\/$/, "");

export const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Attach access token to every request
apiClient.interceptors.request.use((config) => {
  const token = Cookies.get("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Refresh token on 401
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean };

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      const refreshToken = Cookies.get("refresh_token");
      if (!refreshToken) {
        Cookies.remove("access_token");
        Cookies.remove("refresh_token");
        window.location.href = "/ar/login";
        return Promise.reject(error);
      }

      try {
        const { data } = await axios.post(`${BASE_URL}/auth/refresh`, {
          refresh_token: refreshToken,
        });
        Cookies.set("access_token", data.access_token, { expires: 1 / 48 }); // 30 min
        apiClient.defaults.headers.common.Authorization = `Bearer ${data.access_token}`;
        return apiClient(originalRequest);
      } catch {
        Cookies.remove("access_token");
        Cookies.remove("refresh_token");
        window.location.href = "/ar/login";
        return Promise.reject(error);
      }
    }

    return Promise.reject(error);
  }
);

// ── Typed API functions ───────────────────────────────────────────────────────

export const authApi = {
  login: (email: string, password: string) =>
    apiClient.post("/auth/login", { email, password }),
  register: (data: Record<string, unknown>) =>
    apiClient.post("/auth/register", data),
  refresh: (refresh_token: string) =>
    apiClient.post("/auth/refresh", { refresh_token }),
  logout: () => apiClient.post("/auth/logout"),
  forgotPassword: (email: string) =>
    apiClient.post("/auth/forgot-password", { email }),
  resetPassword: (token: string, new_password: string) =>
    apiClient.post("/auth/reset-password", { token, new_password }),
  me: () => apiClient.get("/auth/me"),
};

export const inventoryApi = {
  listBatches: (params?: Record<string, unknown>) =>
    apiClient.get("/inventory/batches", { params }),
  createBatch: (data: Record<string, unknown>) =>
    apiClient.post("/inventory/batches", data),
  getBatch: (id: string) => apiClient.get(`/inventory/batches/${id}`),
  updateBatch: (id: string, data: Record<string, unknown>) =>
    apiClient.patch(`/inventory/batches/${id}`, data),
  fefoRecommendation: (id: string) =>
    apiClient.get(`/inventory/batches/${id}/fefo`),
  listNearExpiry: (days?: number) =>
    apiClient.get("/inventory/near-expiry", { params: { days } }),
  getRules: () => apiClient.get("/inventory/rules"),
  upsertRules: (data: Record<string, unknown>) =>
    apiClient.put("/inventory/rules", data),
};

export const listingsApi = {
  list: (params?: Record<string, unknown>) =>
    apiClient.get("/listings", { params }),
  listMine: (params?: Record<string, unknown>) =>
    apiClient.get("/listings/mine", { params }),
  create: (data: Record<string, unknown>) =>
    apiClient.post("/listings", data),
  get: (id: string) => apiClient.get(`/listings/${id}`),
  update: (id: string, data: Record<string, unknown>) =>
    apiClient.patch(`/listings/${id}`, data),
  cancel: (id: string) => apiClient.delete(`/listings/${id}`),
  checkEligibility: (batchId: string) =>
    apiClient.get("/listings/eligibility-check", { params: { batch_id: batchId } }),
};

export const offersApi = {
  list: (params?: Record<string, unknown>) =>
    apiClient.get("/offers", { params }),
  listMine: (params?: Record<string, unknown>) =>
    apiClient.get("/offers", { params }),
  listIncoming: (params?: Record<string, unknown>) =>
    apiClient.get("/offers/incoming", { params }),
  incoming: (params?: Record<string, unknown>) =>
    apiClient.get("/offers/incoming", { params }),
  submit: (data: Record<string, unknown>) =>
    apiClient.post("/offers", data),
  accept: (id: string) => apiClient.post(`/offers/${id}/accept`),
  reject: (id: string, seller_note?: string) =>
    apiClient.post(`/offers/${id}/reject`, undefined, { params: { seller_note } }),
  cancel: (id: string) => apiClient.post(`/offers/${id}/cancel`),
};

export const reservationsApi = {
  list: (params?: Record<string, unknown>) =>
    apiClient.get("/reservations", { params }),
  get: (id: string) => apiClient.get(`/reservations/${id}`),
  cancel: (id: string) => apiClient.post(`/reservations/${id}/cancel`),
};

export const transactionsApi = {
  list: (params?: Record<string, unknown>) =>
    apiClient.get("/transactions", { params }),
  get: (id: string) => apiClient.get(`/transactions/${id}`),
  createFromReservation: (reservationId: string) =>
    apiClient.post(`/transactions/from-reservation/${reservationId}`),
  dispatch: (id: string, data?: Record<string, unknown>) =>
    apiClient.post(`/transactions/${id}/dispatch`, data ?? {}),
  confirmReceipt: (id: string, data?: Record<string, unknown>) =>
    apiClient.post(`/transactions/${id}/confirm-receipt`, data ?? {}),
};

export const organizationsApi = {
  list: (params?: Record<string, unknown>) =>
    apiClient.get("/organizations", { params }),
  get: (id: string) => apiClient.get(`/organizations/${id}`),
  getMyOrg: () => apiClient.get("/organizations/me"),
  updateMyOrg: (data: Record<string, unknown>) =>
    apiClient.patch("/organizations/me", data),
  update: (id: string, data: Record<string, unknown>) =>
    apiClient.patch(`/organizations/${id}`, data),
  approve: (id: string, notes?: string) =>
    apiClient.post(`/organizations/${id}/approve`, { notes }),
  reject: (id: string, reason: string) =>
    apiClient.post(`/organizations/${id}/reject`, { reason }),
  suspend: (id: string, reason: string) =>
    apiClient.post(`/organizations/${id}/suspend`, { reason }),
};

export const branchesApi = {
  list: (params?: Record<string, unknown>) =>
    apiClient.get("/branches", { params }),
  create: (data: Record<string, unknown>) =>
    apiClient.post("/branches", data),
  get: (id: string) => apiClient.get(`/branches/${id}`),
  update: (id: string, data: Record<string, unknown>) =>
    apiClient.patch(`/branches/${id}`, data),
  delete: (id: string) => apiClient.delete(`/branches/${id}`),
};

export const productsApi = {
  listCategories: () => apiClient.get("/products/categories"),
  updateCategory: (id: string, data: Record<string, unknown>) =>
    apiClient.patch(`/products/categories/${id}`, data),
  list: (params?: Record<string, unknown>) =>
    apiClient.get("/products", { params }),
  get: (id: string) => apiClient.get(`/products/${id}`),
};

export const notificationsApi = {
  list: (params?: Record<string, unknown>) =>
    apiClient.get("/notifications", { params }),
  unreadCount: () => apiClient.get("/notifications/unread-count"),
  markRead: (id: string) => apiClient.post(`/notifications/${id}/read`),
  markAllRead: () => apiClient.post("/notifications/read-all"),
  getPreferences: () => apiClient.get("/notifications/preferences"),
  updatePreference: (id: string, is_enabled: boolean) =>
    apiClient.patch(`/notifications/preferences/${id}`, { is_enabled }),
};

export const reportsApi = {
  nearExpiry: (params?: Record<string, unknown>) =>
    apiClient.get("/reports/near-expiry", { params }),
  expiredLoss: (params?: Record<string, unknown>) =>
    apiClient.get("/reports/expired-loss", { params }),
  recoverableValue: () => apiClient.get("/reports/recoverable-value"),
  topProducts: (params?: Record<string, unknown>) =>
    apiClient.get("/reports/top-products", { params }),
  branchComparison: () => apiClient.get("/reports/branch-comparison"),
};

export const adminApi = {
  // Approvals
  approvals: (params?: Record<string, unknown>) =>
    apiClient.get("/admin/approvals", { params }),
  getApprovals: (params?: Record<string, unknown>) =>
    apiClient.get("/admin/approvals", { params }),
  approveOrg: (id: string, notes?: string) =>
    apiClient.post(`/organizations/${id}/approve`, { notes }),
  rejectOrg: (id: string, reason: string) =>
    apiClient.post(`/organizations/${id}/reject`, { reason }),
  suspendOrg: (id: string, reason: string) =>
    apiClient.post(`/organizations/${id}/suspend`, { reason }),
  // Compliance
  compliance: (params?: Record<string, unknown>) =>
    apiClient.get("/admin/compliance", { params }),
  getCompliance: (params?: Record<string, unknown>) =>
    apiClient.get("/admin/compliance", { params }),
  updateBranchCompliance: (branchId: string, status: string) =>
    apiClient.patch(`/branches/${branchId}/compliance`, { storage_condition_status: status }),
  // Audit logs
  auditLogs: (params?: Record<string, unknown>) =>
    apiClient.get("/admin/audit-logs", { params }),
  getAuditLogs: (params?: Record<string, unknown>) =>
    apiClient.get("/admin/audit-logs", { params }),
  // Moderation
  moderation: (params?: Record<string, unknown>) =>
    apiClient.get("/admin/moderation", { params }),
  getModeration: (params?: Record<string, unknown>) =>
    apiClient.get("/admin/moderation", { params }),
  removeListing: (id: string, reason: string) =>
    apiClient.post(`/admin/moderation/${id}/remove`, { reason }),
  // Settings
  settings: () => apiClient.get("/admin/settings"),
  getSettings: () => apiClient.get("/admin/settings"),
  updateSetting: (key: string, value: unknown) =>
    apiClient.put(`/admin/settings/${key}`, { value }),
};
