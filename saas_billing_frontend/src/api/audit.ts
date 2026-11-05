import apiClient from "./client";

export interface AuditLog {
  id: string;
  organization: string;
  user: string | null;
  user_email: string | null;
  action: string;
  resource_type: string;
  resource_id: string;
  description: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export const getAuditLogs = async (
  organizationId: string,
): Promise<AuditLog[]> => {
  const response = await apiClient.get<AuditLog[]>(
    `/audit/organizations/${organizationId}/`,
  );

  return response.data;
};