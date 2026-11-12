import type { ReactNode } from "react";
import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { OrganizationContext } from "../context/OrganizationContext";
import { orgContext } from "../test/utils";
import { useOrgRole } from "./roles";

const withRole = (role: string) =>
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <OrganizationContext.Provider value={orgContext(role)}>
        {children}
      </OrganizationContext.Provider>
    );
  };

describe("useOrgRole (mirrors backend permissions)", () => {
  it.each([
    ["OWNER", true, true],
    ["ADMIN", true, true],
    ["ACCOUNTANT", false, true],
    ["MEMBER", false, false],
  ])("%s -> admin=%s finance=%s", (role, isAdmin, isFinance) => {
    const { result } = renderHook(() => useOrgRole(), {
      wrapper: withRole(role),
    });

    expect(result.current.role).toBe(role);
    expect(result.current.isAdmin).toBe(isAdmin);
    expect(result.current.isFinance).toBe(isFinance);
  });
});
