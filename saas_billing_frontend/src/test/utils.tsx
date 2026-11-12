import type { ReactElement, ReactNode } from "react";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import {
  OrganizationContext,
  type OrganizationContextType,
} from "../context/OrganizationContext";
import type { Organization } from "../types/auth";

export const acme: Organization = {
  id: "org-acme",
  name: "Acme Analytics",
  slug: "acme",
  role: "OWNER",
};

export function orgContext(
  role: string = "OWNER",
  organization: Organization = acme,
): OrganizationContextType {
  const active = { ...organization, role };

  return {
    organizations: [active],
    activeOrganization: active,
    activeOrganizationId: active.id,
    setActiveOrganization: () => {},
    selectNewOrganization: () => {},
  };
}

/** Render inside a router and an organization context with `role`. */
export function renderWithOrg(
  ui: ReactElement,
  { role = "OWNER", route = "/" }: { role?: string; route?: string } = {},
) {
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <MemoryRouter initialEntries={[route]}>
      <OrganizationContext.Provider value={orgContext(role)}>
        {children}
      </OrganizationContext.Provider>
    </MemoryRouter>
  );

  return render(ui, { wrapper: Wrapper });
}
