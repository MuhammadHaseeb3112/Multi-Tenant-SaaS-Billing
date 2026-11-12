import { useEffect, useState } from "react";

import { getAnalyticsOverview } from "../../api/analytics";
import type { AnalyticsOverview } from "../../api/analytics";
import { getAuditLogs } from "../../api/audit";
import type { AuditLog } from "../../api/audit";
import { getSubscription } from "../../api/billing";
import type { Subscription } from "../../api/billing";
import { getInvoices } from "../../api/invoices";
import type { Invoice } from "../../api/invoices";
import { getUsageSummary } from "../../api/usage";
import type { UsageSummary } from "../../api/usage";

export interface DashboardData {
  usage: UsageSummary | null;
  subscription: Subscription | null;
  analytics: AnalyticsOverview | null;
  invoices: Invoice[];
  activity: AuditLog[];
}

/**
 * Loads the five dashboard widgets in parallel. Each request is
 * independent: one failing (e.g. a role that may not read invoices) never
 * blanks the others. The caller remounts the dashboard per organization
 * (key), so state always starts empty for the active org.
 */
export function useDashboardData(
  organizationId: string | null,
): DashboardData {
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [activity, setActivity] = useState<AuditLog[]>([]);

  useEffect(() => {
    if (!organizationId) {
      return;
    }

    const report = (what: string) => (error: unknown) => {
      console.error(`Failed to load dashboard ${what}:`, error);
    };

    void getUsageSummary(organizationId)
      .then(setUsage)
      .catch(report("usage"));
    void getSubscription(organizationId)
      .then(setSubscription)
      .catch(report("subscription"));
    void getAnalyticsOverview(organizationId)
      .then(setAnalytics)
      .catch(report("analytics"));
    void getInvoices(organizationId)
      .then(setInvoices)
      .catch(report("invoices"));
    void getAuditLogs(organizationId)
      .then(setActivity)
      .catch(report("activity"));
  }, [organizationId]);

  return { usage, subscription, analytics, invoices, activity };
}
