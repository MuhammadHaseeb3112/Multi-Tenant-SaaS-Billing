import apiClient from "./client";

export interface BillingPlan {
  code: string;
  name: string;
  description: string;
  monthly_price: string;
  annual_price: string;
  api_request_limit: number;
  is_active: boolean;
}

export interface Subscription {
  id: string;
  organization_id: string;
  organization_name: string;
  plan: BillingPlan;
  status: string;
  interval: string;
  current_period_start: string | null;
  current_period_end: string | null;
  trial_start: string | null;
  trial_end: string | null;
  cancel_at_period_end: boolean;
  canceled_at: string | null;
  payment_failed_at?: string | null;
  grace_period_end?: string | null;
  stripe_customer_id: string | null;
  stripe_subscription_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface CheckoutResponse {
  checkout_url: string;
  session_id: string;
}

export interface SubscriptionActionResponse {
  detail: string;
  subscription_id?: string;
  cancel_at_period_end?: boolean;
}

export const getPlans = async (): Promise<BillingPlan[]> => {
  const response = await apiClient.get<BillingPlan[]>(
    "/billing/plans/",
  );

  return response.data;
};

export const getSubscription = async (
  organizationId: string,
): Promise<Subscription> => {
  const response = await apiClient.get<Subscription>(
    `/billing/organizations/${organizationId}/subscription/`,
  );

  return response.data;
};

export const createCheckout = async (
  organizationId: string,
  planCode: string,
  interval: "MONTHLY" | "ANNUAL",
): Promise<CheckoutResponse> => {
  const response = await apiClient.post<CheckoutResponse>(
    `/billing/organizations/${organizationId}/checkout/`,
    {
      plan_code: planCode,
      interval,
    },
  );

  return response.data;
};

export const changeSubscription = async (
  organizationId: string,
  planCode: string,
  interval: "MONTHLY" | "ANNUAL",
): Promise<SubscriptionActionResponse> => {
  const response =
    await apiClient.post<SubscriptionActionResponse>(
      `/billing/organizations/${organizationId}/subscription/change/`,
      {
        plan_code: planCode,
        interval,
      },
    );

  return response.data;
};

export const cancelSubscription = async (
  organizationId: string,
): Promise<SubscriptionActionResponse> => {
  const response =
    await apiClient.post<SubscriptionActionResponse>(
      `/billing/organizations/${organizationId}/subscription/cancel/`,
    );

  return response.data;
};

export const resumeSubscription = async (
  organizationId: string,
): Promise<SubscriptionActionResponse> => {
  const response =
    await apiClient.post<SubscriptionActionResponse>(
      `/billing/organizations/${organizationId}/subscription/resume/`,
    );

  return response.data;
};