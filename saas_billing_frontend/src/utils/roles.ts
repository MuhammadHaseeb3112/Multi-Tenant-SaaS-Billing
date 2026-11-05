import { useOrganization } from "../context/OrganizationContext";

// Mirrors the backend permission classes (apps/tenants/permissions.py).
// The backend is the real guard; this only hides actions a user
// cannot perform, so they don't click into a 403.

export type OrgRole = "OWNER" | "ADMIN" | "ACCOUNTANT" | "MEMBER";

const ADMIN_ROLES: OrgRole[] = ["OWNER", "ADMIN"];
const FINANCE_ROLES: OrgRole[] = ["OWNER", "ADMIN", "ACCOUNTANT"];

export function useOrgRole() {
  const { activeOrganization } = useOrganization();
  const role = (activeOrganization?.role ?? null) as OrgRole | null;

  return {
    role,
    // Team, subscription, checkout, API keys.
    isAdmin: role !== null && ADMIN_ROLES.includes(role),
    // Create / send / pay invoices, payments list.
    isFinance: role !== null && FINANCE_ROLES.includes(role),
  };
}
