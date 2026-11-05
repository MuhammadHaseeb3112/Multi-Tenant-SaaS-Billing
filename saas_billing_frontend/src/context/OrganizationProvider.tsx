import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { useAuth } from "./AuthContext";
import { OrganizationContext } from "./OrganizationContext";

const STORAGE_KEY = "active_organization_id";

interface OrganizationProviderProps {
  children: ReactNode;
}

export function OrganizationProvider({
  children,
}: OrganizationProviderProps) {
  const { user } = useAuth();

  // Stable reference: a new [] every render made the callbacks below
  // change on every render.
  const organizations = useMemo(
    () => user?.organizations ?? [],
    [user],
  );

  // The user's choice (persisted). It may point to an organization the
  // user no longer belongs to; activeOrganization below falls back to the
  // first organization in that case, so no effect has to "fix" the state.
  const [selectedOrganizationId, setSelectedOrganizationId] =
    useState<string | null>(() => {
      return localStorage.getItem(STORAGE_KEY);
    });

  const activeOrganization =
    organizations.find(
      (organization) =>
        organization.id === selectedOrganizationId,
    ) ??
    organizations[0] ??
    null;

  const activeOrganizationId = activeOrganization?.id ?? null;

  // Keep localStorage in sync with the organization actually in use.
  useEffect(() => {
    if (activeOrganizationId) {
      localStorage.setItem(STORAGE_KEY, activeOrganizationId);
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, [activeOrganizationId]);

  const setActiveOrganization = useCallback(
    (organizationId: string) => {
      const exists = organizations.some(
        (organization) =>
          organization.id === organizationId,
      );

      if (!exists) {
        return;
      }

      localStorage.setItem(
        STORAGE_KEY,
        organizationId,
      );

      setSelectedOrganizationId(organizationId);
    },
    [organizations],
  );

  return (
    <OrganizationContext.Provider
      value={{
        organizations,
        activeOrganization,
        activeOrganizationId,
        setActiveOrganization,
      }}
    >
      {children}
    </OrganizationContext.Provider>
  );
}
