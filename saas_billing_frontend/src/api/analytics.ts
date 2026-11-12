import apiClient from "./client";

export interface AnalyticsOverview {
  organization_id: string;
  currency: string;
  mrr: string;

  current_subscription: {
    plan: string | null;
    interval: string | null;
  };

  active_subscriptions: number;

  subscription_breakdown: {
    active: number;
    trialing: number;
    past_due: number;
    canceled: number;
    total: number;
  };

  // Money this organization has paid the platform (all time,
  // SUCCEEDED payments). Added in Phase 6.
  total_paid?: string;

  // Money collected from the organization's own customers
  // (invoice checkouts + manual payments), kept apart from the
  // subscription fees it paid the platform.
  collected_from_customers?: string;
  paid_to_platform?: string;
  open_invoices?: {
    count: number;
    amount: string;
  };

  churn: {
    churned: number;
    churn_rate: number;
  };

  revenue_trend: {
    month: string;
    revenue: string;
  }[];
}

export const getAnalyticsOverview = async (
  organizationId: string,
): Promise<AnalyticsOverview> => {
  const response = await apiClient.get<AnalyticsOverview>(
    `/analytics/organizations/${organizationId}/overview/`,
  );

  return response.data;
};