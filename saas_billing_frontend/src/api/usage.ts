import apiClient from "./client";

export interface UsageSummary {
  resource: string;
  used: number;
  limit: number;
  remaining: number;
  plan: string;
  period_start: string | null;
  period_end: string | null;
  overage_enabled: boolean;
  overage_requests: number;
  overage_price_per_1000: string;
  max_overage_requests: number | null;
  estimated_overage_amount: string;
  // "custom" when the organization has its own usage deal.
  limit_source?: "plan" | "custom";
  plan_limit?: number | null;
}

export interface RecordUsageResponse {
  id: string;
  organization: string;
  resource: string;
  quantity: number;
  recorded_at: string;
}

export interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  is_active: boolean;
  created_by_email: string | null;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
  requests_this_period: number;
}

// Only returned once, right after creation.
export interface CreatedApiKey extends ApiKey {
  key: string;
}

export interface OverageCharge {
  id: string;
  period_start: string;
  period_end: string;
  included_requests: number;
  used_requests: number;
  overage_requests: number;
  price_per_1000: string;
  amount: string;
  currency: string;
  status: "BILLED" | "PENDING_NEXT_INVOICE";
  stripe_invoice_id: string;
  created_at: string;
}

export const getUsageSummary = async (
  organizationId: string,
): Promise<UsageSummary> => {
  const response = await apiClient.get<UsageSummary>(
    `/usage/organizations/${organizationId}/`,
  );

  return response.data;
};

export const recordUsage = async (
  organizationId: string,
  quantity: number,
): Promise<RecordUsageResponse> => {
  const response = await apiClient.post<RecordUsageResponse>(
    `/usage/organizations/${organizationId}/record/`,
    {
      quantity,
    },
  );

  return response.data;
};

export const listApiKeys = async (
  organizationId: string,
): Promise<ApiKey[]> => {
  const response = await apiClient.get<ApiKey[]>(
    `/usage/organizations/${organizationId}/api-keys/`,
  );

  return response.data;
};

export const createApiKey = async (
  organizationId: string,
  name: string,
): Promise<CreatedApiKey> => {
  const response = await apiClient.post<CreatedApiKey>(
    `/usage/organizations/${organizationId}/api-keys/`,
    { name },
  );

  return response.data;
};

export const revokeApiKey = async (
  organizationId: string,
  keyId: string,
): Promise<ApiKey> => {
  const response = await apiClient.delete<ApiKey>(
    `/usage/organizations/${organizationId}/api-keys/${keyId}/`,
  );

  return response.data;
};

export const listOverageCharges = async (
  organizationId: string,
): Promise<OverageCharge[]> => {
  const response = await apiClient.get<OverageCharge[]>(
    `/usage/organizations/${organizationId}/overage-charges/`,
  );

  return response.data;
};

// Base URL of the product API (/api/v1), derived from the dashboard API
// base URL, for the "quick start" snippet.
export const PRODUCT_API_BASE_URL =
  new URL(
    (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "") + "/v1",
    window.location.origin,
  ).href.replace(/\/$/, "");
