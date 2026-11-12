import { createContext, useContext } from "react";

import type { Organization } from "../types/auth";

// Context object + hook. The provider lives in OrganizationProvider.tsx so
// this file exports no components (keeps React Fast Refresh working).

export interface OrganizationContextType {
  organizations: Organization[];
  activeOrganization: Organization | null;
  activeOrganizationId: string | null;
  setActiveOrganization: (organizationId: string) => void;
  // Select a workspace that was just created. It may not be in
  // `organizations` yet (the user is reloading); until it appears the
  // current workspace stays active.
  selectNewOrganization: (organizationId: string) => void;
}

export const OrganizationContext =
  createContext<OrganizationContextType | undefined>(
    undefined,
  );

export function useOrganization(): OrganizationContextType {
  const context = useContext(OrganizationContext);

  if (!context) {
    throw new Error(
      "useOrganization must be used inside an OrganizationProvider",
    );
  }

  return context;
}
