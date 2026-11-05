import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { useAuth } from "./AuthContext";
import type { Organization } from "../types/auth";

interface OrganizationContextType {
  organizations: Organization[];
  activeOrganization: Organization | null;
  activeOrganizationId: string | null;
  setActiveOrganization: (organizationId: string) => void;
}

const OrganizationContext =
  createContext<OrganizationContextType | undefined>(
    undefined,
  );

interface OrganizationProviderProps {
  children: ReactNode;
}

const STORAGE_KEY = "active_organization_id";

export function OrganizationProvider({
  children,
}: OrganizationProviderProps) {
  const { user } = useAuth();

  const organizations = user?.organizations ?? [];

  const [activeOrganizationId, setActiveOrganizationId] =
    useState<string | null>(() => {
      return localStorage.getItem(STORAGE_KEY);
    });

  const activeOrganization =
    organizations.find(
      (organization) =>
        organization.id === activeOrganizationId,
    ) ??
    organizations[0] ??
    null;

  useEffect(() => {
    if (!organizations.length) {
      localStorage.removeItem(STORAGE_KEY);
      setActiveOrganizationId(null);
      return;
    }

    const savedOrganizationExists =
      activeOrganizationId &&
      organizations.some(
        (organization) =>
          organization.id === activeOrganizationId,
      );

    if (!savedOrganizationExists) {
      const firstOrganization = organizations[0];

      localStorage.setItem(
        STORAGE_KEY,
        firstOrganization.id,
      );

      setActiveOrganizationId(firstOrganization.id);
    }
  }, [organizations, activeOrganizationId]);

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

      setActiveOrganizationId(organizationId);
    },
    [organizations],
  );

  return (
    <OrganizationContext.Provider
      value={{
        organizations,
        activeOrganization,
        activeOrganizationId:
          activeOrganization?.id ?? null,
        setActiveOrganization,
      }}
    >
      {children}
    </OrganizationContext.Provider>
  );
}

export function useOrganization(): OrganizationContextType {
  const context = useContext(OrganizationContext);

  if (!context) {
    throw new Error(
      "useOrganization must be used inside an OrganizationProvider",
    );
  }

  return context;
}