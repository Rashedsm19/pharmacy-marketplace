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
  // Without this a request to a sleeping instance hangs forever and the screen
  // sits on a spinner with nothing to tell the person. Sixty seconds is chosen
  // to clear a cold start on the free tier and still fail while someone is
  // still watching.
  timeout: 60_000,
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
function signOut(): void {
  Cookies.remove("access_token");
  Cookies.remove("refresh_token");
  if (typeof window !== "undefined") {
    const locale = window.location.pathname.split("/")[1] || "ar";
    window.location.href = `/${locale}/login`;
  }
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean };

    // A session is only over when the server says so. A request that never got
    // an answer means the network or the service is having a moment, and
    // throwing the person back to the login screen for that is how a correct
    // password ends up looking wrong.
    if (!error.response) return Promise.reject(error);

    // Never refresh while support is inside a customer's account: a refresh
    // would mint the administrator's own token and replay the customer's
    // request as the platform.
    const impersonating =
      typeof window !== "undefined" &&
      Boolean(window.sessionStorage.getItem("support.session"));

    if (error.response.status === 401 && !originalRequest._retry && !impersonating) {
      originalRequest._retry = true;
      const refreshToken = Cookies.get("refresh_token");
      if (!refreshToken) {
        signOut();
        return Promise.reject(error);
      }

      try {
        const { data } = await axios.post(
          `${BASE_URL}/auth/refresh`,
          { refresh_token: refreshToken },
          { timeout: 60_000 }
        );
        Cookies.set("access_token", data.access_token, {
          expires: 1 / 48, // 30 min
          sameSite: "strict",
        });
        apiClient.defaults.headers.common.Authorization = `Bearer ${data.access_token}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        // Same rule again: only a refusal ends the session, not a failed trip.
        if ((refreshError as { response?: unknown })?.response) signOut();
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
  // There is no /listings/mine on the API — that request fell through to
  // /listings/{listing_id} and returned 422, so a pharmacy with live listings
  // was told it had none on the screen for managing them.
  listMine: (params?: Record<string, unknown>) =>
    apiClient.get("/listings", { params: { ...params, my_listings: true } }),
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

  // Compliance documents
  uploadDocument: (docType: "cr" | "license", file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient.post(`/organizations/me/documents/${docType}`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  deleteDocument: (docType: "cr" | "license") =>
    apiClient.delete(`/organizations/me/documents/${docType}`),
  downloadDocument: (orgId: string, docType: "cr" | "license") =>
    apiClient.get(`/organizations/${orgId}/documents/${docType}`, {
      responseType: "blob",
    }),
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
  // Cross-pharmacy visibility — super admin only
  allInventory: (params?: Record<string, unknown>) =>
    apiClient.get("/admin/inventory", { params }),
  draftProducts: (params?: Record<string, unknown>) =>
    apiClient.get("/admin/products/drafts", { params }),
  promoteDraft: (
    id: string,
    data?: { name?: string; name_ar?: string; sku?: string; barcode?: string }
  ) => apiClient.post(`/admin/products/drafts/${id}/promote`, data ?? {}),
  allImports: (params?: Record<string, unknown>) =>
    apiClient.get("/admin/imports", { params }),

  // ── Support console ─────────────────────────────────────────────────────
  customers: (params?: Record<string, unknown>) =>
    apiClient.get("/admin/customers", { params }),
  customer: (orgId: string) => apiClient.get(`/admin/customers/${orgId}`),
  users: (params?: Record<string, unknown>) =>
    apiClient.get("/admin/users", { params }),
  user: (id: string) => apiClient.get(`/admin/users/${id}`),
  resetLink: (id: string, reason: string) =>
    apiClient.post(`/admin/users/${id}/reset-link`, { reason }),
  deactivateUser: (id: string, reason: string) =>
    apiClient.post(`/admin/users/${id}/deactivate`, { reason }),
  activateUser: (id: string, reason: string) =>
    apiClient.post(`/admin/users/${id}/activate`, { reason }),
  deleteUser: (id: string, reason: string, force = false) =>
    apiClient.delete(`/admin/users/${id}`, { params: { reason, force } }),
  impersonate: (id: string, reason: string, minutes = 30) =>
    apiClient.post(`/admin/users/${id}/impersonate`, { reason, minutes }),
  endImpersonation: (sessionId: string) =>
    apiClient.post(`/admin/impersonation/${sessionId}/end`),
  impersonationSessions: (params?: Record<string, unknown>) =>
    apiClient.get("/admin/impersonation/sessions", { params }),
  reactivateOrg: (orgId: string, reason: string) =>
    apiClient.post(`/admin/organizations/${orgId}/reactivate`, { reason }),
  purgeOrg: (orgId: string, confirmName: string, reason: string) =>
    apiClient.delete(`/admin/organizations/${orgId}`, {
      data: { confirm_name: confirmName, reason },
    }),
  importForCustomer: (orgId: string, file: File, reason: string) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient.post(`/admin/organizations/${orgId}/imports`, form, {
      params: { reason },
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  deleteBatch: (batchId: string, reason: string) =>
    apiClient.delete(`/admin/inventory/batches/${batchId}`, { params: { reason } }),
};

export const disputesApi = {
  open: (data: {
    transaction_id: string;
    reason: string;
    description: string;
    disputed_quantity?: number;
  }) => apiClient.post("/disputes", data),
  list: (params?: Record<string, unknown>) => apiClient.get("/disputes", { params }),
  get: (id: string) => apiClient.get(`/disputes/${id}`),
  respond: (id: string, response: string) =>
    apiClient.post(`/disputes/${id}/respond`, { response }),
  resolve: (id: string, outcome: string, notes: string) =>
    apiClient.post(`/disputes/${id}/resolve`, { outcome, notes }),
  queue: (params?: Record<string, unknown>) =>
    apiClient.get("/disputes/queue", { params }),
  uploadEvidence: (id: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient.post(`/disputes/${id}/evidence`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
};

export const importsApi = {
  downloadTemplate: () =>
    apiClient.get("/inventory/import/template", { responseType: "blob" }),
  capacity: () => apiClient.get("/inventory/import/capacity"),
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient.post("/inventory/import", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  list: (params?: Record<string, unknown>) =>
    apiClient.get("/inventory/import", { params }),
  get: (id: string) => apiClient.get(`/inventory/import/${id}`),
  downloadErrors: (id: string) =>
    apiClient.get(`/inventory/import/${id}/errors`, { responseType: "blob" }),
};

export const apiKeysApi = {
  scopes: () => apiClient.get("/api-keys/scopes"),
  list: () => apiClient.get("/api-keys"),
  create: (data: { name: string; scopes: string[]; expires_at?: string | null }) =>
    apiClient.post("/api-keys", data),
  revoke: (id: string) => apiClient.delete(`/api-keys/${id}`),
};
