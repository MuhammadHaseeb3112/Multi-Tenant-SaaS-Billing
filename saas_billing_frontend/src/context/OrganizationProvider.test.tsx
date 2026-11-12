import type { ReactNode } from "react";
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { User } from "../types/auth";
import { AuthContext, type AuthContextType } from "./AuthContext";
import { useOrganization } from "./OrganizationContext";
import { OrganizationProvider } from "./OrganizationProvider";

const KEY = "active_organization_id";

const user: User = {
  id: "u1",
  email: "owner@example.com",
  first_name: "Owner",
  last_name: "",
  organizations: [
    { id: "org-a", name: "A", slug: "a", role: "OWNER" },
    { id: "org-b", name: "B", slug: "b", role: "MEMBER" },
  ],
};

function setup(initialUser: User | null) {
  let current: User | null = initialUser;

  const auth = (): AuthContextType => ({
    user: current,
    isAuthenticated: Boolean(current),
    isLoading: false,
    login: async () => {},
    refreshUser: async () => current,
    register: async () => {},
    logout: async () => {},
  });

  const Wrapper = ({ children }: { children: ReactNode }) => (
    <AuthContext.Provider value={auth()}>
      <OrganizationProvider>{children}</OrganizationProvider>
    </AuthContext.Provider>
  );

  const hook = renderHook(() => useOrganization(), { wrapper: Wrapper });

  return {
    ...hook,
    setUser(next: User | null) {
      current = next;
      hook.rerender();
    },
  };
}

describe("OrganizationProvider", () => {
  it("falls back to the first organization", () => {
    const { result } = setup(user);

    expect(result.current.activeOrganizationId).toBe("org-a");
    expect(localStorage.getItem(KEY)).toBe("org-a");
  });

  it("restores the saved organization", () => {
    localStorage.setItem(KEY, "org-b");

    const { result } = setup(user);

    expect(result.current.activeOrganization?.name).toBe("B");
  });

  it("keeps the saved organization while the user is still loading", () => {
    // Regression: the old effect wiped the saved choice on the first
    // render (user not loaded yet), so a page reload always jumped back
    // to the first organization.
    localStorage.setItem(KEY, "org-b");

    const { result, setUser } = setup(null);
    expect(result.current.activeOrganizationId).toBeNull();

    setUser(user);

    expect(result.current.activeOrganizationId).toBe("org-b");
    expect(localStorage.getItem(KEY)).toBe("org-b");
  });

  it("ignores a saved organization the user no longer belongs to", () => {
    localStorage.setItem(KEY, "org-gone");

    const { result } = setup(user);

    expect(result.current.activeOrganizationId).toBe("org-a");
  });

  it("switches and persists, but only to own organizations", () => {
    const { result } = setup(user);

    act(() => result.current.setActiveOrganization("org-b"));
    expect(result.current.activeOrganizationId).toBe("org-b");
    expect(localStorage.getItem(KEY)).toBe("org-b");

    act(() => result.current.setActiveOrganization("org-hacker"));
    expect(result.current.activeOrganizationId).toBe("org-b");
  });

  it("selects a just-created workspace once it is in the list", () => {
    const { result, rerender, setUser } = setup(user);

    // Created on the server, user not reloaded yet: stay where we are.
    act(() => result.current.selectNewOrganization("org-new"));
    expect(result.current.activeOrganizationId).toBe("org-a");

    setUser({
      ...user,
      organizations: [
        ...user.organizations,
        { id: "org-new", name: "New", slug: "new", role: "OWNER" },
      ],
    });
    rerender();

    expect(result.current.activeOrganizationId).toBe("org-new");
    expect(localStorage.getItem(KEY)).toBe("org-new");
  });
});
